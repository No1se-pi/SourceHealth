"""Bounded Yandex AI Studio provider for grounded repository reports."""

import json
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal

import httpx
from pydantic import ValidationError

from .config import (
    DETAIL_PROFILES,
    MAX_PROVIDER_CALLS,
    MAX_RETRY_AFTER_SECONDS,
    RETRY_DELAYS_SECONDS,
    AIReportDetail,
)
from .contracts import AISummaryContext, AISummaryResult
from .prompt import build_prompt, response_schema
from .provider import AIValidationError, validate_ai_output

AIModelMode = Literal["flash", "lite", "pro"]

MODEL_NAMES = {
    "flash": "Alice AI LLM Flash",
    "lite": "YandexGPT 5 Lite",
    "pro": "YandexGPT 5.1 Pro",
}
MODEL_ALIASES = {"flash": "aliceai-llm-flash", "lite": "yandexgpt-5-lite", "pro": "yandexgpt-5.1"}
logger = logging.getLogger(__name__)
REPAIR_INSTRUCTION = """Предыдущий ответ нарушил grounding-контракт.
Сформируй новый ответ с нуля.
Копируй evidence_refs и recommendation_ids только из переданного JSON.
Не создавай новые идентификаторы.
Если утверждение нельзя обосновать — пропусти его.
NO_DATA указывай только в limitations.
Сохрани требуемую структуру отчёта и глубину."""


class YandexAIError(RuntimeError):
    def __init__(self, code: str, status: int = 503):
        self.code, self.status = code, status
        super().__init__(code)


class YandexAISummaryProvider:
    endpoint = "https://ai.api.cloud.yandex.net/v1/chat/completions"

    def __init__(self, api_key: str, folder_id: str, *, timeout: float = 45, client=None):
        self.api_key, self.folder_id, self.timeout, self.client = api_key, folder_id, timeout, client
        self.last_attempts = 0

    def summarize(self, context: AISummaryContext, mode: AIModelMode,
                  detail: AIReportDetail = "brief") -> AISummaryResult:
        profile = DETAIL_PROFILES[detail]
        system, user = build_prompt(context, detail)
        if len(user.encode("utf-8")) > 128_000:
            raise YandexAIError("ai_context_too_large", 422)
        payload = {
            "model": f"gpt://{self.folder_id}/{MODEL_ALIASES[mode]}/latest",
            "temperature": 0.1,
            "max_completion_tokens": profile.max_completion_tokens,
            "store": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "sourcehealth_ai_report", "strict": True, "schema": response_schema(context, detail),
            }},
        }
        self.last_attempts = 0
        requests_left = MAX_PROVIDER_CALLS
        repair_reason = None
        for generation in range(2):
            response, used = self._request(
                payload, requests_left, timeout=max(self.timeout, profile.timeout_seconds),
                mode=mode, detail=detail,
            )
            requests_left -= used
            try:
                result = self._parse_and_validate(response, context, detail)
                if generation:
                    logger.info("ai_grounding_repair_succeeded", extra={
                        "component": "ai", "event": "ai_grounding_repair_succeeded", "mode": mode,
                        "detail": detail, "attempt": self.last_attempts,
                        "reason": repair_reason,
                    })
                return result
            except AIValidationError as exc:
                event = "ai_grounding_failed" if generation == 0 else "ai_grounding_repair_failed"
                logger.warning(event, extra={
                    "component": "ai", "event": event, "mode": mode, "detail": detail,
                    "attempt": self.last_attempts, "reason": exc.code,
                })
                if generation or requests_left == 0:
                    raise YandexAIError("ai_grounding_failed") from None
                repair_reason = exc.code
                payload = dict(payload)
                payload["messages"] = [
                    {"role": "system", "content": f"{system}\n\n{REPAIR_INSTRUCTION}"},
                    {"role": "user", "content": user},
                ]
        raise YandexAIError("ai_grounding_failed")

    @staticmethod
    def _parse_and_validate(response, context: AISummaryContext,
                            detail: AIReportDetail = "brief") -> AISummaryResult:
        try:
            text = response.json()["choices"][0]["message"]["content"]
            if len(text) > DETAIL_PROFILES[detail].hard_chars:
                raise YandexAIError("ai_response_too_large")
            payload = json.loads(text)
            canonical_categories = {category.name: category for category in context.categories}
            generated_categories = payload.get("category_analysis", [])
            if isinstance(generated_categories, dict):
                generated_categories = [
                    {"category": name, **value} for name, value in generated_categories.items()
                    if isinstance(value, dict)
                ]
            deduplicated_categories = []
            seen_categories = set()
            for category in generated_categories:
                if isinstance(category, dict) and category.get("category") in canonical_categories:
                    if category["category"] in seen_categories:
                        continue
                    seen_categories.add(category["category"])
                    canonical = canonical_categories[category["category"]]
                    category.setdefault("score", canonical.score)
                    category.setdefault("availability", canonical.availability)
                    category.setdefault("evidence_refs", canonical.evidence_refs)
                deduplicated_categories.append(category)
            payload["category_analysis"] = deduplicated_categories
            result = AISummaryResult.model_validate(payload)
            validate_ai_output(context, result, detail)
            if len(result.model_dump_json()) > DETAIL_PROFILES[detail].hard_chars:
                raise YandexAIError("ai_response_too_large")
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError):
            raise YandexAIError("ai_invalid_response") from None

    @staticmethod
    def _retry_after(response, fallback: float) -> float:
        raw = response.headers.get("Retry-After")
        if not raw:
            return fallback
        try:
            delay = float(raw)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                delay = (parsed - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return fallback
        return max(0.0, min(delay, MAX_RETRY_AFTER_SECONDS))

    def _request(self, payload, max_attempts=MAX_PROVIDER_CALLS, *, timeout: float | None = None,
                 mode: AIModelMode = "flash", detail: AIReportDetail = "brief"):
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(max_attempts):
            self.last_attempts += 1
            global_attempt = self.last_attempts
            reason = "ok"
            try:
                if self.client is not None:
                    response = self.client.post(
                        self.endpoint, headers=headers, json=payload, timeout=timeout or self.timeout,
                    )
                else:
                    with httpx.Client(timeout=timeout or self.timeout) as client:
                        response = client.post(self.endpoint, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError):
                reason = "transport_error"
                logger.info("ai_provider_attempt", extra={
                    "component": "ai", "event": "ai_provider_attempt", "mode": mode,
                    "detail": detail, "attempt": global_attempt, "reason": reason,
                })
                if attempt + 1 < max_attempts:
                    time.sleep(RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)])
                    continue
                raise YandexAIError("ai_provider_unavailable") from None
            if response.status_code in {429, 500, 502, 503, 504}:
                reason = "rate_limited" if response.status_code == 429 else "provider_unavailable"
            logger.info("ai_provider_attempt", extra={
                "component": "ai", "event": "ai_provider_attempt", "mode": mode,
                "detail": detail, "attempt": global_attempt, "reason": reason,
            })
            if reason != "ok" and attempt + 1 < max_attempts:
                fallback = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
                time.sleep(self._retry_after(response, fallback))
                continue
            if response.status_code in {401, 403}:
                raise YandexAIError("ai_provider_auth_failed")
            if response.status_code == 429:
                raise YandexAIError("ai_rate_limited", 429)
            if response.status_code >= 500:
                raise YandexAIError("ai_provider_unavailable")
            if response.status_code >= 400:
                raise YandexAIError("ai_request_rejected", 422)
            return response, attempt + 1
        raise YandexAIError("ai_provider_unavailable")
