"""GET-only client for the official SourceCraft AppSec API."""

import json
import time
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import httpx

from .client import SourceCraftError


class SourceCraftAppSecClient:
    def __init__(self, *, pat: str, timeout: float = 15, max_pages: int = 20,
                 max_response_bytes: int = 4_194_304, deadline_seconds: float = 60,
                 transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        if not pat or timeout <= 0 or max_pages < 1 or max_response_bytes < 1 or deadline_seconds <= 0:
            raise ValueError("valid credential and positive client limits required")
        self._http = httpx.Client(
            base_url="https://appsec.sourcecraft.tech",
            headers={"Authorization": f"Bearer {pat}", "Accept": "application/json",
                     "User-Agent": "SourceHealth/0.4"},
            timeout=timeout, follow_redirects=False, transport=transport)
        self._timeout = timeout
        self._deadline = time.monotonic() + deadline_seconds
        self._max_pages = max_pages
        self._max_response_bytes = max_response_bytes
        self._sleep = sleep

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._http.close()

    def get(self, path: str, *, params: Any = None) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//") or any(x in path for x in ("://", "?", "#", "..")):
            raise ValueError("relative API path required")
        request_id = str(uuid4())
        for attempt in range(3):
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise SourceCraftError("collection_budget_exceeded")
            try:
                with self._http.stream("GET", path, params=params, headers={"X-Request-ID": request_id},
                                       timeout=min(self._timeout, remaining)) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 2:
                            raise SourceCraftError("rate_limited" if response.status_code == 429 else "source_unavailable")
                        delay = 0.5 * (2 ** attempt)
                    elif response.status_code != 200:
                        code = {401: "authentication_required", 403: "access_denied", 404: "not_found"}.get(
                            response.status_code, "source_request_failed")
                        raise SourceCraftError(code)
                    else:
                        content = bytearray()
                        for chunk in response.iter_bytes(chunk_size=65536):
                            content.extend(chunk)
                            if len(content) > self._max_response_bytes:
                                raise SourceCraftError("response_limit")
                        try:
                            payload = json.loads(content)
                        except (ValueError, UnicodeError):
                            raise SourceCraftError("invalid_response") from None
                        if not isinstance(payload, dict):
                            raise SourceCraftError("invalid_response")
                        return payload
            except httpx.TransportError:
                if attempt == 2:
                    raise SourceCraftError("source_unavailable") from None
                delay = 0.5 * (2 ** attempt)
            self._sleep(delay)
        raise SourceCraftError("source_unavailable")

    def iter_defect_groups(self, repository_id: str, scan_uuid: str, severity: str) -> Iterator[dict[str, Any]]:
        params: list[tuple[str, str | int]] = [
            ("gitRepo", repository_id), ("scanUuid", scan_uuid), ("pageSize", 250), ("pageToken", ""),
            ("description", ""), ("file", ""), ("rule", ""), ("scanType", ""), ("type", ""),
            ("severity", severity),
        ]
        for status in ("OPEN", "TRIAGE_IN_PROGRESS", "TRIAGED_TP", "FIX_IN_PROGRESS"):
            params.append(("status", status))
        seen: set[str] = set()
        expected_total = None
        yielded = 0
        for _ in range(self._max_pages):
            payload = self.get("/v1/defect-groups", params=params)
            rows, token, total = payload.get("data"), payload.get("nextPageToken"), payload.get("totalSize")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise SourceCraftError("invalid_response")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise SourceCraftError("invalid_response")
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise SourceCraftError("invalid_pagination")
            if token not in (None, "") and (not isinstance(token, str) or token in seen):
                raise SourceCraftError("invalid_pagination")
            yielded += len(rows)
            yield from rows
            if token in (None, ""):
                if yielded != expected_total:
                    raise SourceCraftError("invalid_pagination")
                return
            seen.add(token)
            params = [(k, token if k == "pageToken" else v) for k, v in params]
        raise SourceCraftError("page_limit")
