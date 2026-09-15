"""GET-only клиент официального SourceCraft REST API.

Спецификация: https://api.sourcecraft.tech/docs/sourcecraft.swagger.json.
Транспорт инъецируется для тестов. PAT, body ошибок и query не логируются.
"""

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx


class SourceCraftError(RuntimeError):
    """Только стабильный код; исходный ответ сервиса не является сообщением ошибки."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SourceCraftClient:
    def __init__(self, *, pat: str | None = None, base_url: str = "https://api.sourcecraft.tech",
                 timeout: float = 15, max_pages: int = 100, max_response_bytes: int = 4_194_304,
                 transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        if base_url.rstrip("/") != "https://api.sourcecraft.tech":
            raise ValueError("untrusted SourceCraft API host")
        if timeout <= 0 or max_pages < 1 or max_response_bytes < 1:
            raise ValueError("positive client limits required")
        headers = {"User-Agent": "SourceHealth/0.4", "Accept": "application/json"}
        if pat:
            headers["Authorization"] = f"Bearer {pat}"
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout,
                                  follow_redirects=False, transport=transport)
        self.max_pages = max_pages
        self.max_response_bytes = max_response_bytes
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def repository_path(organization: str, repository: str) -> str:
        # Slugs are single URL segments, never a caller-controlled absolute URL.
        from sourcehealth.core.domain import RepositoryRef

        ref = RepositoryRef.from_url(f"https://sourcecraft.dev/{organization}/{repository}")
        return f"/repos/{quote(ref.organization_slug, safe='')}/{quote(ref.repository_slug, safe='')}"

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//") or any(x in path for x in ("://", "?", "#", "..")):
            raise ValueError("relative API path required")
        request_id = str(uuid4())
        for attempt in range(3):
            try:
                with self._http.stream("GET", path, params=params, headers={"X-Request-ID": request_id}) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 2:
                            raise SourceCraftError("source_unavailable")
                        delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                    elif response.status_code != 200:
                        code = {401: "authentication_required", 403: "access_denied", 404: "not_found"}.get(
                            response.status_code, "source_request_failed")
                        raise SourceCraftError(code)
                    else:
                        content = bytearray()
                        for chunk in response.iter_bytes(chunk_size=65536):
                            content.extend(chunk)
                            if len(content) > self.max_response_bytes:
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

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value:
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    delay = 0.5 * (2 ** attempt)
            # Не игнорируем длинный Retry-After ранним повтором: отдаём управление scheduler.
            if delay > 10:
                raise SourceCraftError("rate_limited")
            return max(0, delay)
        return 0.5 * (2 ** attempt)

    def iter_items(self, path: str, key: str, *, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Ограниченная token pagination. Уже отданные items сохраняются при ошибке следующей страницы."""
        query = {"page_size": 100, **(params or {})}
        seen = set()
        for _ in range(self.max_pages):
            payload = self.get(path, params=query)
            items = payload.get(key)
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise SourceCraftError("invalid_response")
            token = payload.get("next_page_token")
            if token not in (None, "") and (not isinstance(token, str) or token in seen):
                raise SourceCraftError("invalid_pagination")
            yield from items
            if token in (None, ""):
                return
            seen.add(token)
            query["page_token"] = token
        raise SourceCraftError("page_limit")

    def repository(self, organization: str, repository: str) -> dict[str, Any]:
        return self.get(self.repository_path(organization, repository))
