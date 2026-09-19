"""Documentation/debt интерпретируют безопасные факты snapshot, без I/O."""

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.core.domain import Evidence


class DocumentationAnalyzer:
    name, category = "documentation", "documentation"

    def analyze(self, context):
        facts = context.metadata.get("snapshot")
        if not facts:
            return AnalyzerResult(self.name, status="partial", availability=A.NO_DATA,
                                  category=self.category, source="git_snapshot", error="snapshot_unavailable")
        evidence = [Evidence(id=f"{self.name}:snapshot", source="git_snapshot", type="snapshot_observation",
                             reference=facts["head_sha"], summary="Проверка tracked snapshot; исходный текст не сохраняется.",
                             timestamp=context.started_at.isoformat())]
        if self.name == "documentation":
            evidence.extend(Evidence(id=f"documentation:{key}", source="git_snapshot", type="documentation_marker",
                                     reference=facts["head_sha"], location=path, summary=f"Обнаружен признак {key}.")
                            for key, path in sorted(facts["locations"].items()))
        return AnalyzerResult(self.name, status="ok" if facts["complete"] else "partial",
                              availability=A.AVAILABLE if facts["complete"] else A.PARTIAL,
                              category=self.category, source="git_snapshot", metrics=facts[self.name], evidence=evidence,
                              metadata={"head_sha": facts["head_sha"], "scope": facts["scope"],
                                        "ci_configured": facts["ci_configured"], "complete": facts["complete"]})


class TechnicalDebtAnalyzer(DocumentationAnalyzer):
    name, category = "technical_debt", "code_health"
