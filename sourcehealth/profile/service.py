"""Profile queries and tracking commands; no credentials cross this boundary."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from sourcehealth.achievements.service import derive
from sourcehealth.application.services import ServiceError
from sourcehealth.scoring.coverage import score_preview
from sourcehealth.storage.models import AnalysisRun, Repository, UserRepository

REFRESH_VALUES = {"adaptive", "1h", "6h", "24h", "7d", "off"}


class ProfileService:
    def __init__(self, sessions):
        self.sessions = sessions

    def repositories(self, user_id, *, limit=100, offset=0):
        query = (select(UserRepository, Repository, AnalysisRun)
                 .join(Repository, Repository.id == UserRepository.repository_id)
                 .outerjoin(AnalysisRun, AnalysisRun.id == Repository.latest_analysis_id)
                 .where(UserRepository.user_id == user_id)
                 .order_by(UserRepository.created_at, Repository.id).offset(offset).limit(limit))
        with self.sessions() as db:
            rows = db.execute(query).all()
            return [self._dto(link, repo, run) for link, repo, run in rows]

    def track(self, user_id, repository_id):
        with self.sessions.begin() as db:
            repo = db.get(Repository, repository_id)
            if repo is None or repo.visibility != "public":
                raise ServiceError("repository_not_found", 404)
            db.execute(insert(UserRepository).values(user_id=user_id, repository_id=repository_id)
                       .on_conflict_do_nothing())
        return self.get(user_id, repository_id)

    def get(self, user_id, repository_id):
        query = (select(UserRepository, Repository, AnalysisRun).select_from(UserRepository)
                 .join(Repository, Repository.id == UserRepository.repository_id)
                 .outerjoin(AnalysisRun, AnalysisRun.id == Repository.latest_analysis_id)
                 .where(UserRepository.user_id == user_id, UserRepository.repository_id == repository_id))
        with self.sessions() as db:
            row = db.execute(query).one_or_none()
            if row is None:
                raise ServiceError("tracked_repository_not_found", 404)
            return self._dto(*row)

    def update(self, user_id, repository_id, *, refresh_preference, use_pat):
        if refresh_preference not in REFRESH_VALUES:
            raise ServiceError("invalid_refresh_preference", 422)
        with self.sessions.begin() as db:
            link = db.get(UserRepository, (user_id, repository_id), with_for_update=True)
            if link is None:
                raise ServiceError("tracked_repository_not_found", 404)
            link.refresh_preference = refresh_preference
            link.use_pat_for_scheduled_analysis = use_pat
        return self.get(user_id, repository_id)

    def untrack(self, user_id, repository_id):
        with self.sessions.begin() as db:
            link = db.get(UserRepository, (user_id, repository_id), with_for_update=True)
            if link is not None:
                db.delete(link)

    def achievements(self, user_id):
        user_repos_query = select(UserRepository).where(UserRepository.user_id == user_id)
        runs_query = (select(AnalysisRun, UserRepository).join(
            UserRepository, UserRepository.repository_id == AnalysisRun.repository_id)
            .where(UserRepository.user_id == user_id,
                   AnalysisRun.status.in_(("completed", "partial"))))
        with self.sessions() as db:
            tracked_links = db.execute(user_repos_query).scalars().all()
            run_rows = db.execute(runs_query.order_by(AnalysisRun.completed_at, AnalysisRun.id).limit(5000)).all()
            return derive(run_rows, tracked_repositories=tracked_links)

    @staticmethod
    def compute_summary(repos_dto, achievements_dto):
        def _get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        tracked_count = len(repos_dto)
        analyzed_count = sum(1 for r in repos_dto if _get(r, "last_analysis_at") is not None)
        scores = [_get(r, "health_score") for r in repos_dto if _get(r, "health_score") is not None]
        official_health_count = len(scores)
        best_health = max(scores) if scores else None

        if scores:
            sorted_scores = sorted(scores)
            n = len(sorted_scores)
            mid = n // 2
            median_health = (sorted_scores[mid] if n % 2 == 1
                             else round((sorted_scores[mid - 1] + sorted_scores[mid]) / 2.0, 2))
        else:
            median_health = None

        next_dates = [_get(r, "next_analysis_at") for r in repos_dto if _get(r, "next_analysis_at") is not None]
        next_analysis_at = min(next_dates) if next_dates else None

        achievements_unlocked = sum(1 for a in achievements_dto if _get(a, "unlocked"))

        portfolio_healthy = sum(1 for s in scores if s >= 80)
        portfolio_medium = sum(1 for s in scores if 60 <= s < 80)
        portfolio_needs_attention = sum(1 for s in scores if s < 60)
        portfolio_no_data = sum(1 for r in repos_dto if _get(r, "health_score") is None)

        return {
            "tracked_count": tracked_count,
            "analyzed_count": analyzed_count,
            "official_health_count": official_health_count,
            "best_health": best_health,
            "median_health": median_health,
            "next_analysis_at": next_analysis_at,
            "achievements_unlocked": achievements_unlocked,
            "portfolio_healthy": portfolio_healthy,
            "portfolio_medium": portfolio_medium,
            "portfolio_needs_attention": portfolio_needs_attention,
            "portfolio_no_data": portfolio_no_data,
        }

    def summary(self, user_id, repos_dto=None, achievements_dto=None):
        if repos_dto is None:
            repos_dto = self.repositories(user_id, limit=5000)
        if achievements_dto is None:
            achievements_dto = self.achievements(user_id)
        return self.compute_summary(repos_dto, achievements_dto)


    @staticmethod
    def _dto(link, repo, run):
        preview = score_preview(run.scoring_policy_version, run.category_scores) if run else None
        return {"repository_id": repo.id, "organization_slug": repo.organization_slug,
                "repository_slug": repo.repository_slug, "health_score": repo.health_score,
                "score_preview": preview, "last_analysis_at": run.completed_at if run else None,
                "last_activity_at": repo.last_activity_at, "analysis_status": run.status if run else None,
                "next_analysis_at": repo.next_analysis_at, "refresh_preference": link.refresh_preference,
                "use_pat_for_scheduled_analysis": link.use_pat_for_scheduled_analysis}
