"""ML/LLM получают подготовленные данные; не имеют доступа к I/O и scoring."""

from typing import Protocol

from sourcehealth.core.domain import Evidence


class ContextModel(Protocol):
    version: str

    def predict(self, features: dict[str, float | None]) -> dict[str, float | None]: ...


class EvidenceExplainer(Protocol):
    def explain(self, facts: tuple[Evidence, ...]) -> str:
        """Текст фактов недоверенный; вывод не команды и не новая оценка."""
        ...
