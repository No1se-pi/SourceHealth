"""Структурированные события без дампов исключений, payload и конфигурации."""

import json
import logging
from datetime import UTC, datetime


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        values = {"time": datetime.now(UTC).isoformat(), "level": record.levelname,
                  "component": getattr(record, "component", record.name),
                  "event": getattr(record, "event", record.msg)}
        # These integration diagnostics are stable allowlisted values. Arbitrary
        # record fields, response bodies and exception text remain excluded.
        for name in ("request_id", "analysis_id", "repository_id", "endpoint", "sourcecraft_error_code",
                     "availability", "organization_slug", "repository_slug"):
            values[name] = getattr(record, name, None)
        for name in ("analyzer", "complete", "duration_ms", "repository_metadata_ms", "appsec_ms", "issues_ms",
                     "cicd_ms", "pull_requests_ms", "contributors_ms", "releases_ms", "runtime_ms", "scoring_ms",
                     "total_ms"):
            if hasattr(record, name):
                values[name] = getattr(record, name)
        # Не включаем exc_info, args, query string и произвольный record.__dict__.
        return json.dumps(values, ensure_ascii=True, default=str)


def configure_logging() -> None:
    logger = logging.getLogger("sourcehealth")
    if not any(isinstance(handler.formatter, EventFormatter) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(EventFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
