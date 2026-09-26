"""Achievements derived from immutable analysis history after tracking began."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Definition:
    id: str
    title: str
    description: str


DEFINITIONS = [
    Definition("first_checkup", "First Check-up", "Первый анализ отслеживаемого проекта."),
    Definition("ghost_hunter", "Ghost Hunter", "Найден предварительный Source Soul до официальной оценки."),
    Definition("documentation_enjoyer", "Documentation Enjoyer", "Документация получила не менее 90 баллов."),
    Definition("ci_wizard", "CI Wizard", "CI/CD получил 100 баллов."),
    Definition("clean_scan", "Clean Scan", "Официальный SourceCraft AppSec получил 100 баллов."),
    Definition("healthy_project", "Healthy Project", "Health Score достиг 80 баллов."),
    Definition("recovery", "Recovery", "Health вырос минимум на 20 баллов между анализами."),
    Definition("maintainer", "Maintainer", "Выполнено не менее 10 анализов отслеживаемых проектов."),
]


def derive(rows):
    """Rows are `(run, tracking)` pairs already scoped to the current user."""
    unlocked = {}
    terminal_count = 0
    by_repo = {}
    for run, tracking in sorted(rows, key=lambda pair: pair[0].completed_at or pair[0].queued_at):
        if run.completed_at is None or run.completed_at < tracking.created_at or run.status not in {"completed", "partial"}:
            continue
        terminal_count += 1
        categories = run.category_scores if isinstance(run.category_scores, dict) else {}
        previous = by_repo.get(run.repository_id)
        conditions = {
            "first_checkup": True,
            "ghost_hunter": run.health_score is None and _preview_numeric(run),
            "documentation_enjoyer": _score(categories, "documentation") >= 90,
            "ci_wizard": _score(categories, "cicd") == 100,
            "clean_scan": (_score(categories, "security") == 100
                           and categories.get("security", {}).get("availability") == "available"),
            "healthy_project": run.health_score is not None and run.health_score >= 80,
            "recovery": (previous is not None and previous.health_score is not None and run.health_score is not None
                         and run.health_score - previous.health_score >= 20),
        }
        for key, value in conditions.items():
            if value and key not in unlocked:
                unlocked[key] = (run.completed_at, run.repository_id)
        if run.health_score is not None:
            by_repo[run.repository_id] = run
    if terminal_count >= 10 and "maintainer" not in unlocked:
        eligible = [r for r, t in rows if r.completed_at and r.completed_at >= t.created_at]
        last = sorted(eligible, key=lambda r: r.completed_at)[9]
        unlocked["maintainer"] = (last.completed_at, last.repository_id)
    return [{"id": item.id, "title": item.title, "description": item.description,
             "unlocked": item.id in unlocked,
             "unlocked_at": unlocked.get(item.id, (None, None))[0],
             "repository_id": unlocked.get(item.id, (None, None))[1]} for item in DEFINITIONS]


def _score(categories, name):
    value = categories.get(name, {}).get("score")
    return float(value) if isinstance(value, (int, float)) else -1


def _preview_numeric(run):
    from sourcehealth.scoring.coverage import score_preview
    preview = score_preview(run.scoring_policy_version, run.category_scores)
    return bool(preview and preview.get("numeric"))
