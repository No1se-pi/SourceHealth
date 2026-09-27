"""Read-only projection for sharing a public SourceHealth result."""

from sqlalchemy import select

from sourcehealth.application.services import ServiceError
from sourcehealth.storage.models import AnalysisRun, Repository


class PublicityService:
    def __init__(self, sessions, public_base_url: str):
        self.sessions = sessions
        self.base = public_base_url.rstrip("/")

    def repository(self, repository_id):
        with self.sessions() as db:
            repo = db.scalar(select(Repository).where(
                Repository.id == repository_id, Repository.visibility == "public"))
            if repo is None:
                raise ServiceError("repository_not_found", 404)
            run = db.scalar(select(AnalysisRun).where(
                AnalysisRun.repository_id == repo.id,
                AnalysisRun.profile == "mvp-v1",
                AnalysisRun.status.in_(("completed", "partial")),
            ).order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc()).limit(1))
            badge = f"{self.base}/api/v1/badges/{repo.organization_slug}/{repo.repository_slug}.svg"
            analysis_id = run.id if run else None
            return {
                "repository_id": repo.id,
                "organization_slug": repo.organization_slug,
                "repository_slug": repo.repository_slug,
                "health_score": run.health_score if run else None,
                "health_available": run is not None and run.health_score is not None,
                "repository_url": f"{self.base}/repositories/{repo.id}",
                "badge_url": badge,
                "badge_markdown": f"![SourceHealth]({badge})",
                "badge_html": f'<a href="{self.base}/repositories/{repo.id}"><img src="{badge}" alt="SourceHealth" /></a>',
                "latest_analysis_id": analysis_id,
                "latest_analysis_url": f"{self.base}/analyses/{analysis_id}" if analysis_id else None,
                "markdown_report_url": (f"{self.base}/api/v1/analyses/{analysis_id}/report.md"
                                        if analysis_id else None),
            }
