"""Версионированный JSON-контракт между анализаторами, scoring и интерфейсом."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

AnalysisStatus = Literal["ok", "partial", "error"]


@dataclass
class AnalyzerResult:
    analyzer: str
    status: AnalysisStatus = "ok"
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Проверить контракт до включения результата в общий отчёт.

        Запрещаем NaN/Infinity: Python их кодирует, но это не стандартный JSON.
        Ошибка стороннего анализатора будет изолирована runner на этой границе.
        """
        if not isinstance(self.analyzer, str) or not self.analyzer:
            raise ValueError("analyzer must be a nonempty string")
        if self.status not in ("ok", "partial", "error"):
            raise ValueError("invalid analyzer status")
        if not all(isinstance(value, dict) for value in (self.metrics, self.metadata)):
            raise ValueError("metrics and metadata must be dictionaries")
        if not isinstance(self.findings, list) or any(not isinstance(f, dict) for f in self.findings):
            raise ValueError("findings must be a list of dictionaries")
        if self.error is not None and not isinstance(self.error, str):
            raise ValueError("error must be a string or null")
        result = asdict(self)
        json.dumps(result, allow_nan=False)
        return result


@dataclass
class AnalysisReport:
    repository: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    checks: dict[str, AnalyzerResult] = field(default_factory=dict)
    schema_version: str = field(default="2.0", init=False)

    @property
    def complete(self) -> bool:
        return all(check.status == "ok" for check in self.checks.values())

    @property
    def status(self) -> AnalysisStatus:
        if self.complete:
            return "ok"
        if all(check.status == "error" for check in self.checks.values()):
            return "error"
        return "partial"

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "status": self.status,
            "complete": self.complete,
            "checks": {name: check.to_dict() for name, check in self.checks.items()},
        }
        json.dumps(result, allow_nan=False)
        return result
