"""Bounded read-only repository comparison."""

from sqlalchemy import select

from sourcehealth.application.services import ServiceError
from sourcehealth.scoring.coverage import score_coverage
from sourcehealth.storage.models import AnalysisRun, Repository

TERMINAL = ("completed", "partial")


class CompareService:
    def __init__(self, sessions):
        self.sessions = sessions

    def compare(self, repository_ids):
        ids = list(repository_ids)
        if not 2 <= len(ids) <= 4:
            raise ServiceError("invalid_repository_count", 422)
        if len(set(ids)) != len(ids):
            raise ServiceError("duplicate_repository", 422)
        with self.sessions() as db:
            repositories = list(db.scalars(select(Repository).where(Repository.id.in_(ids))))
            by_id = {row.id: row for row in repositories if row.visibility == "public"}
            if len(by_id) != len(ids):
                raise ServiceError("repository_not_found", 404)
            runs = list(db.scalars(select(AnalysisRun).where(
                AnalysisRun.repository_id.in_(ids), AnalysisRun.profile == "mvp-v1",
                AnalysisRun.status.in_(TERMINAL)
            ).order_by(AnalysisRun.repository_id, AnalysisRun.completed_at.desc(), AnalysisRun.id.desc())))
        latest = {}
        for run in runs:
            latest.setdefault(run.repository_id, run)
        items = [self._item(by_id[repo_id], latest.get(repo_id)) for repo_id in ids]
        versions = {item["scoring_policy_version"] for item in items if item["scoring_policy_version"]}
        return {"repositories": items, "comparable": {
            "health": all(item["health_score"] is not None for item in items),
            "policy_versions_match": len(versions) <= 1,
        }}

    @staticmethod
    def _item(repo, run):
        categories = run.category_scores if run and isinstance(run.category_scores, dict) else {}
        normalized = {name: {"score": value.get("score"), "availability": value.get("availability", "no_data")}
                      for name, value in categories.items() if isinstance(value, dict)}
        coverage = score_coverage(run.scoring_policy_version, categories) if run else None
        return {"repository_id": repo.id, "organization_slug": repo.organization_slug,
                "repository_slug": repo.repository_slug, "canonical_url": repo.canonical_url,
                "health_score": run.health_score if run else repo.health_score,
                "data_coverage_percent": coverage["nominal_weight_percent"] if coverage else None,
                "language": repo.language, "likes": repo.likes, "last_activity_at": repo.last_activity_at,
                "categories": normalized, "latest_analysis_id": run.id if run else None,
                "scoring_policy_version": run.scoring_policy_version if run else None}
