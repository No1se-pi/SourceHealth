"""Версионированный JSON-контракт между анализаторами, scoring и интерфейсом."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from .domain import Category, DataAvailability, Evidence, Recommendation

AnalysisStatus = Literal["ok", "partial", "error"]


@dataclass
class AnalyzerResult:
    analyzer: str
    status: AnalysisStatus = "ok"
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    availability: DataAvailability = DataAvailability.AVAILABLE
    category: str | None = None
    source: str = "unspecified"
    analyzer_version: str = "1"
    contract_version: str = "3.0"
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Старые анализаторы передают только status; не изображаем доступность
        # полных данных при их ошибке/частичном выполнении.
        if self.availability == DataAvailability.AVAILABLE:
            if self.status == "error":
                self.availability = DataAvailability.ERROR
            elif self.status == "partial":
                self.availability = DataAvailability.PARTIAL

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
        DataAvailability(self.availability)
        if self.category is not None:
            Category(self.category)
        if any(not isinstance(item, Evidence) for item in self.evidence):
            raise ValueError("evidence must contain Evidence objects")
        if len({item.id for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence id")
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
    scoring_policy_version: str = "unconfigured-v1"
    health_score: float | None = None
    category_scores: dict[str, Any] = field(default_factory=dict)
    recommendations: list[Recommendation] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        """JSON 3.0 для persistence/API: локальный CLI JSON 2.0 остаётся совместимым.

        Публичный report возможен только с RepositoryRef, никогда с workspace.
        Доверенные адаптеры обязаны публиковать безопасные metrics/evidence.
        """
        from .domain import RepositoryRef

        RepositoryRef(**self.repository)
        result = self.to_dict()
        result.update(schema_version="3.0", scoring_policy_version=self.scoring_policy_version,
                      health_score=self.health_score, category_scores=self.category_scores,
                      recommendations=[asdict(item) for item in self.recommendations])
        json.dumps(result, allow_nan=False)
        return result

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
