"""Read-only anomaly signals; they never modify Health or category scores."""

from sqlalchemy import select

from sourcehealth.application.services import ServiceError
from sourcehealth.scoring.coverage import score_coverage
from sourcehealth.storage.models import AnalysisRun, Repository


def _metrics(run, check_name):
    results = run.results if run and isinstance(run.results, dict) else {}
    check = results.get("checks", {}).get(check_name, {})
    return check.get("metrics", {}) if isinstance(check, dict) else {}


def _coverage(run):
    if not run:
        return None
    value = score_coverage(run.scoring_policy_version, run.category_scores or {})
    return value["nominal_weight_percent"] if value else None


def derive_signals(current, previous=None):
    if current is None:
        return []
    signals = []
    activity = _metrics(current, "git_activity")
    commits, days = activity.get("commits_last_30_days"), activity.get("active_days_last_30_days")
    if isinstance(commits, int) and isinstance(days, int) and commits >= 15 and days <= 2:
        signals.append({"id": "commit_burst", "severity": "info", "title": "Высокая концентрация коммитов",
                        "description": "Одноразовый burst не считается эквивалентом устойчивой активности.",
                        "facts": {"commits_last_30_days": commits, "active_days_last_30_days": days}})
    cicd = current.category_scores.get("cicd", {}) if isinstance(current.category_scores, dict) else {}
    ci = _metrics(current, "cicd")
    observed = ci.get("runs_observed")
    if cicd.get("score") == 100 and isinstance(observed, int) and observed <= 2:
        signals.append({"id": "low_sample_ci", "severity": "info", "title": "Мало CI-наблюдений",
                        "description": "Высокий результат CI/CD основан на малом числе запусков.",
                        "facts": {"runs_observed": observed, "success_rate": ci.get("success_rate")}})
    if (previous and current.scoring_policy_version == previous.scoring_policy_version
            and isinstance(current.health_score, (int, float))
            and isinstance(previous.health_score, (int, float))):
        delta = round(current.health_score - previous.health_score, 2)
        current_coverage, previous_coverage = _coverage(current), _coverage(previous)
        coverage_delta = (current_coverage - previous_coverage
                          if current_coverage is not None and previous_coverage is not None else None)
        if abs(delta) >= 25:
            signals.append({"id": "score_jump", "severity": "warning", "title": "Резкое изменение Health",
                            "description": "Результат стоит сверить с изменением покрытия данных и категорий.",
                            "facts": {"previous_score": previous.health_score, "current_score": current.health_score,
                                      "delta": delta, "previous_coverage": previous_coverage,
                                      "current_coverage": current_coverage,
                                      "coverage_changed": coverage_delta is not None and abs(coverage_delta) >= 20}})
        if coverage_delta is not None and abs(coverage_delta) >= 30:
            signals.append({"id": "coverage_jump", "severity": "info", "title": "Сильно изменилось покрытие данных",
                            "description": "Сравнение Health между анализами требует осторожности.",
                            "facts": {"previous_coverage": previous_coverage,
                                      "current_coverage": current_coverage, "delta": coverage_delta}})
    return signals


class IntegrityService:
    def __init__(self, sessions):
        self.sessions = sessions

    def repository(self, repository_id):
        with self.sessions() as db:
            repo = db.scalar(select(Repository).where(
                Repository.id == repository_id, Repository.visibility == "public"))
            if repo is None:
                raise ServiceError("repository_not_found", 404)
            runs = list(db.scalars(select(AnalysisRun).where(
                AnalysisRun.repository_id == repo.id,
                AnalysisRun.profile == "mvp-v1",
                AnalysisRun.status.in_(("completed", "partial")),
            ).order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc()).limit(2)))
        signals = derive_signals(runs[0], runs[1] if len(runs) > 1 else None) if runs else []
        return {"repository_id": repo.id, "analysis_id": runs[0].id if runs else None,
                "has_signals": bool(signals), "signal_count": len(signals),
                "warning_count": sum(item["severity"] == "warning" for item in signals),
                "info_count": sum(item["severity"] == "info" for item in signals), "signals": signals}
