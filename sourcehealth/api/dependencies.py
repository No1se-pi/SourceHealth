"""Общие проверки сессии, Origin и публичности для HTTP routers."""

from sourcehealth.application.services import ServiceError
from sourcehealth.storage.models import AnalysisRun, Repository


def require_user(request):
    user = request.app.state.auth.current_user(request.cookies.get("sh_session"))
    if user is None:
        raise ServiceError("authentication_required", 401)
    return user

def check_origin(request):
    # All cookie-authenticated mutations require an exact browser Origin.
    if request.headers.get("origin") != request.app.state.settings.public_origin.rstrip("/"):
        raise ServiceError("invalid_origin", 403)

def public_repository(db, repository_id):
    repo = db.get(Repository, repository_id)
    if repo is None or repo.visibility != "public":
        raise ServiceError("repository_not_found", 404)
    return repo

def public_run(db, analysis_id):
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise ServiceError("analysis_not_found", 404)
    public_repository(db, run.repository_id)
    return run
