"""Versioned prompt shared by every Yandex AI report mode."""

import json

from .contracts import AISummaryContext

PROMPT_VERSION = "sourcehealth-analyst-v1"
SCHEMA_VERSION = "ai-summary-v1"


def build_prompt(context: AISummaryContext) -> tuple[str, str]:
    system = (
        "Ты аналитик SourceHealth. Используй только переданный JSON. Не добавляй факты, "
        "не пересчитывай Health Score и считай NO_DATA неизвестными данными. "
        "Каждая сильная сторона и риск обязаны ссылаться на evidence_refs, а действие — "
        "на recommendation_ids или evidence_refs. Ответь только JSON по заданной схеме."
    )
    user = json.dumps(context.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return system, user


def response_schema() -> dict:
    statement = {
        "type": "object", "additionalProperties": False,
        "properties": {"text": {"type": "string", "maxLength": 500},
                       "evidence_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
        "required": ["text", "evidence_refs"],
    }
    action = {
        "type": "object", "additionalProperties": False,
        "properties": {"text": {"type": "string", "maxLength": 500},
                       "recommendation_ids": {"type": "array", "items": {"type": "string"}},
                       "evidence_refs": {"type": "array", "items": {"type": "string"}}},
        "required": ["text", "recommendation_ids", "evidence_refs"],
    }
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "executive_summary": {"type": "string", "maxLength": 1000},
            "strengths": {"type": "array", "items": statement, "maxItems": 5},
            "risks": {"type": "array", "items": statement, "maxItems": 5},
            "actions": {"type": "array", "items": action, "maxItems": 5},
            "limitations": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"text": {"type": "string", "maxLength": 500},
                               "evidence_refs": {"type": "array", "items": {"type": "string"}}},
                "required": ["text", "evidence_refs"],
            }, "maxItems": 5},
        },
        "required": ["schema_version", "executive_summary", "strengths", "risks", "actions", "limitations"],
    }
