"""Bounded Yandex AI Studio provider for grounded repository reports."""

import json
import time
from typing import Literal

import httpx
from pydantic import ValidationError

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


class YandexAIError(RuntimeError):
    def __init__(self, code: str, status: int = 503):
        self.code, self.status = code, status
        super().__init__(code)


class YandexAISummaryProvider:
    endpoint = "https://ai.api.cloud.yandex.net/v1/chat/completions"

    def __init__(self, api_key: str, folder_id: str, *, timeout: float = 45, client=None):
        self.api_key, self.folder_id, self.timeout, self.client = api_key, folder_id, timeout, client

    def summarize(self, context: AISummaryContext, mode: AIModelMode) -> AISummaryResult:
        system, user = build_prompt(context)
        if len(user.encode("utf-8")) > 128_000:
            raise YandexAIError("ai_context_too_large", 422)
        payload = {
            "model": f"gpt://{self.folder_id}/{MODEL_ALIASES[mode]}/latest",
            "temperature": 0.1,
            "max_completion_tokens": 3000,
            "store": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "sourcehealth_ai_summary", "strict": True, "schema": response_schema(),
            }},
        }
        response = self._request(payload)
        try:
            text = response.json()["choices"][0]["message"]["content"]
            if len(text.encode("utf-8")) > 64_000:
                raise YandexAIError("ai_response_too_large")
            result = AISummaryResult.model_validate(json.loads(text))
            validate_ai_output(context, result)
            return result
        except YandexAIError:
            raise
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError):
            raise YandexAIError("ai_invalid_response") from None
        except AIValidationError:
            raise YandexAIError("ai_grounding_failed") from None

    def _request(self, payload):
        headers = {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(2):
            try:
                if self.client is not None:
                    response = self.client.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.post(self.endpoint, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 0:
                    time.sleep(0.1)
                    continue
                raise YandexAIError("ai_provider_unavailable") from None
            if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                time.sleep(0.1)
                continue
            if response.status_code in {401, 403}:
                raise YandexAIError("ai_provider_auth_failed")
            if response.status_code == 429:
                raise YandexAIError("ai_rate_limited", 429)
            if response.status_code >= 500:
                raise YandexAIError("ai_provider_unavailable")
            if response.status_code >= 400:
                raise YandexAIError("ai_request_rejected", 422)
            return response
        raise YandexAIError("ai_provider_unavailable")
