"""Interpret privacy-safe deep Git and repository hygiene facts without I/O."""

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.core.domain import Evidence


class RepositoryInsightsAnalyzer:
    name = "repository_insights"

    def analyze(self, context):
        deep = context.metadata.get("deep_git")
        snapshot = context.metadata.get("snapshot")
        if not deep or not snapshot:
            return AnalyzerResult(self.name, status="partial", availability=A.NO_DATA,
                                  source="git_snapshot", error="insights_unavailable")
        metrics = {**deep, **snapshot["repository_hygiene"],
                   "codeowners_present": snapshot["documentation"]["codeowners"],
                   "contributing_present": snapshot["documentation"]["contributing"],
                   "snapshot_complete": snapshot["hygiene_complete"]}
        complete = bool(deep["history_complete"] and deep["ownership_complete"]
                        and snapshot["hygiene_complete"])
        summary = ("Полная Git-история и tracked snapshot проанализированы без публикации авторов."
                   if complete else
                   "Углублённая аналитика основана на ограниченной выборке; авторы не публикуются.")
        evidence = [Evidence(id="insights:repository", source="git_snapshot", type="repository_insights",
                             reference=snapshot["head_sha"], summary=summary,
                             timestamp=context.started_at.isoformat())]
        return AnalyzerResult(self.name, status="ok" if complete else "partial",
                              availability=A.AVAILABLE if complete else A.PARTIAL,
                              source="git_snapshot", analyzer_version="1", metrics=metrics,
                              metadata={"head_sha": snapshot["head_sha"], "complete": complete,
                                        "scope": snapshot["scope"]}, evidence=evidence)
