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
        query = (select(AnalysisRun, UserRepository).join(
            UserRepository, UserRepository.repository_id == AnalysisRun.repository_id)
            .where(UserRepository.user_id == user_id,
                   AnalysisRun.status.in_(("completed", "partial"))))
        with self.sessions() as db:
            return derive(db.execute(query.order_by(AnalysisRun.completed_at, AnalysisRun.id).limit(5000)).all())

    @staticmethod
    def _dto(link, repo, run):
        preview = score_preview(run.scoring_policy_version, run.category_scores) if run else None
        return {"repository_id": repo.id, "organization_slug": repo.organization_slug,
                "repository_slug": repo.repository_slug, "health_score": repo.health_score,
                "score_preview": preview, "last_analysis_at": run.completed_at if run else None,
                "last_activity_at": repo.last_activity_at, "analysis_status": run.status if run else None,
                "next_analysis_at": repo.next_analysis_at, "refresh_preference": link.refresh_preference,
                "use_pat_for_scheduled_analysis": link.use_pat_for_scheduled_analysis}
