"""Interpret privacy-safe deep Git and repository hygiene facts without I/O."""

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.core.domain import Evidence


class RepositoryInsightsAnalyzer:
    name = "repository_insights"

    def analyze(self, context):
        deep = context.metadata.get("deep_git")
        snapshot = context.metadata.get("snapshot")
        if not deep and not snapshot:
            return AnalyzerResult(self.name, status="partial", availability=A.NO_DATA,
                                  source="git_snapshot", error="insights_unavailable")
        metrics = {
            "sampled_commits": None, "history_complete": None, "contributors_count": None,
            "top_contributor_share": None, "top_2_contributors_share": None,
            "top_3_contributors_share": None, "contributor_distribution": None,
            "bus_factor_proxy": None, "bus_factor_threshold": None, "bus_factor_basis": None,
            "bus_factor_sample_commits": None, "bus_factor_complete": None,
            "bus_factor_reason": None, "ownership_groups": None, "ownership_complete": None,
            "ownership_sample_commits": None, "path_touches_observed": None,
            "deep_analytics_ms": None, "dependency_manifest_count": None,
            "dependency_lockfile_count": None, "ecosystems_detected": None,
            "lockfile_coverage": None, "dependency_update_automation": None,
            "security_policy_present": None, "branch_policy_present": None,
            "review_policy_present": None, "license_policy_present": None,
            "codeowners_present": None, "contributing_present": None,
            "snapshot_complete": None,
        }
        if deep:
            metrics.update(deep)
        if snapshot:
            metrics.update(snapshot["repository_hygiene"])
            metrics.update(codeowners_present=snapshot["documentation"]["codeowners"],
                           contributing_present=snapshot["documentation"]["contributing"],
                           snapshot_complete=snapshot["hygiene_complete"])
        complete = bool(deep and snapshot and deep["history_complete"]
                        and deep["ownership_complete"] and snapshot["hygiene_complete"])
        summary = ("Полная Git-история и tracked snapshot проанализированы без публикации авторов."
                   if complete else
                   "Углублённая аналитика основана на ограниченной выборке; авторы не публикуются.")
        evidence = [Evidence(id="insights:repository", source="git_snapshot", type="repository_insights",
                             reference=snapshot["head_sha"] if snapshot else "deep_git_observation", summary=summary,
                             timestamp=context.started_at.isoformat())]
        return AnalyzerResult(self.name, status="ok" if complete else "partial",
                              availability=A.AVAILABLE if complete else A.PARTIAL,
                              source="git_snapshot", analyzer_version="1", metrics=metrics,
                              metadata={"head_sha": snapshot["head_sha"] if snapshot else None,
                                        "complete": complete, "deep_git_available": bool(deep),
                                        "snapshot_available": bool(snapshot),
                                        "scope": snapshot["scope"] if snapshot else None}, evidence=evidence)
