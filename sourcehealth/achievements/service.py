"""Achievements derived from immutable analysis history after tracking began."""

from dataclasses import dataclass
from typing import Any

OFFICIAL_CATEGORIES = ("security", "cicd", "activity", "documentation", "issues", "code_health")


@dataclass(frozen=True)
class Definition:
    id: str
    title: str
    description: str
    category: str = "progress"
    rarity: str = "common"
    icon_key: str = "default"
    hint: str = ""
    progress_target: int | None = None


DEFINITIONS = [
    Definition("first_checkup", "First Check-up", "Первый анализ отслеживаемого проекта.",
               category="start", rarity="common", icon_key="first_checkup",
               hint="Запустите первый анализ отслеживаемого репозитория."),
    Definition("ghost_hunter", "Ghost Hunter", "Найден предварительный Source Soul до официальной оценки.",
               category="exploration", rarity="uncommon", icon_key="ghost_hunter",
               hint="Найдите репозиторий с предварительным Source Soul."),
    Definition("documentation_enjoyer", "Documentation Enjoyer", "Документация получила не менее 90 баллов.",
               category="quality", rarity="common", icon_key="documentation_enjoyer",
               hint="Получите оценку 90+ в категории «Документация»."),
    Definition("ci_wizard", "CI Wizard", "CI/CD получил 100 баллов.",
               category="automation", rarity="uncommon", icon_key="ci_wizard",
               hint="Получите 100 баллов в категории «CI/CD»."),
    Definition("clean_scan", "Clean Scan", "Официальный SourceCraft AppSec получил 100 баллов.",
               category="security", rarity="rare", icon_key="clean_scan",
               hint="Получите 100 баллов по официальному SourceCraft AppSec."),
    Definition("healthy_project", "Healthy Project", "Health Score достиг 80 баллов.",
               category="quality", rarity="common", icon_key="healthy_project",
               hint="Достигните официального Health 80+ баллов."),
    Definition("recovery", "Recovery", "Health вырос минимум на 20 баллов между анализами.",
               category="progress", rarity="rare", icon_key="recovery",
               hint="Увеличьте Health минимум на 20 баллов между двумя последовательными анализами."),
    Definition("maintainer", "Maintainer", "Выполнено не менее 10 анализов отслеживаемых проектов.",
               category="progress", rarity="rare", icon_key="maintainer",
               hint="Выполните не менее 10 анализов после добавления проекта в отслеживание.",
               progress_target=10),
    Definition("full_house", "Шесть из шести", "Все 6 официальных категорий получили числовую оценку в одном анализе.",
               category="quality", rarity="rare", icon_key="full_house",
               hint="Получите числовую оценку во всех 6 категориях в рамках одного анализа."),
    Definition("perfect_health", "100 Club", "Официальный рейтинг Health достиг максимальных 100 баллов.",
               category="quality", rarity="epic", icon_key="perfect_health",
               hint="Достигните 100 баллов официального рейтинга Health."),
    Definition("triple_tracker", "Наблюдатель", "В отслеживание добавлено не менее 3 репозиториев.",
               category="exploration", rarity="common", icon_key="triple_tracker",
               hint="Добавьте в отслеживание не менее 3 репозиториев.",
               progress_target=3),
    Definition("portfolio_keeper", "Портфель", "Не менее 5 отслеживаемых репозиториев имеют завершённый анализ.",
               category="progress", rarity="uncommon", icon_key="portfolio_keeper",
               hint="Проанализируйте не менее 5 отслеживаемых репозиториев.",
               progress_target=5),
    Definition("persistent_maintainer", "Регулярный чек-ап", "Выполнено не менее 5 анализов отслеживаемых проектов.",
               category="progress", rarity="uncommon", icon_key="persistent_maintainer",
               hint="Выполните не менее 5 анализов после добавления проекта в отслеживание.",
               progress_target=5),
    Definition("clean_and_green", "Чисто и зелено", "Официальный AppSec и CI/CD получили по 100 баллов в одном анализе.",
               category="security", rarity="rare", icon_key="clean_and_green",
               hint="Получите 100 баллов по AppSec и 100 баллов по CI/CD в рамках одного анализа."),
]


def derive(rows, tracked_repositories=None):
    """Rows are `(run, tracking)` pairs already scoped to the current user."""
    unlocked: dict[str, tuple[Any, Any]] = {}
    terminal_count = 0
    by_repo: dict[Any, Any] = {}
    analyzed_tracked_repo_ids: set[Any] = set()

    # Tracked repositories count and identity
    if tracked_repositories is not None:
        tracked_count = len(tracked_repositories)
        sorted_links = sorted(tracked_repositories, key=lambda link: getattr(link, "created_at", None) or 0)
    else:
        unique_links = {getattr(t, "repository_id", None): t for _, t in rows if getattr(t, "repository_id", None)}
        tracked_count = len(unique_links)
        sorted_links = sorted(unique_links.values(), key=lambda link: getattr(link, "created_at", None) or 0)

    # 1. Check triple_tracker
    if tracked_count >= 3:
        third_link = sorted_links[2]
        unlocked["triple_tracker"] = (getattr(third_link, "created_at", None), getattr(third_link, "repository_id", None))

    # 2. Iterate runs in chronological order
    sorted_pairs = sorted(rows, key=lambda pair: pair[0].completed_at or pair[0].queued_at)
    for run, tracking in sorted_pairs:
        if run.completed_at is None or run.completed_at < tracking.created_at or run.status not in {"completed", "partial"}:
            continue
        terminal_count += 1
        is_mvp_v1 = getattr(run, "profile", None) == "mvp-v1"
        if is_mvp_v1:
            analyzed_tracked_repo_ids.add(run.repository_id)

        # Check portfolio_keeper (5 analyzed tracked repos with terminal mvp-v1 analysis)
        if len(analyzed_tracked_repo_ids) >= 5 and "portfolio_keeper" not in unlocked:
            unlocked["portfolio_keeper"] = (run.completed_at, run.repository_id)

        # Check persistent_maintainer (5 terminal analyses)
        if terminal_count >= 5 and "persistent_maintainer" not in unlocked:
            unlocked["persistent_maintainer"] = (run.completed_at, run.repository_id)

        # Check maintainer (10 terminal analyses)
        if terminal_count >= 10 and "maintainer" not in unlocked:
            unlocked["maintainer"] = (run.completed_at, run.repository_id)

        categories = run.category_scores if isinstance(run.category_scores, dict) else {}
        previous = by_repo.get(run.repository_id)

        # Check full_house: all 6 categories have numeric scores in ONE run
        all_six_numeric = (
            len(categories) >= 6
            and all(_score(categories, cat) >= 0 for cat in OFFICIAL_CATEGORIES)
        )

        # Check clean_scan and clean_and_green: AppSec == 100 with official provenance
        is_official_appsec_100 = (
            _score(categories, "security") == 100
            and categories.get("security", {}).get("availability") == "available"
            and _official_security(run)
        )

        conditions = {
            "first_checkup": True,
            "ghost_hunter": run.health_score is None and _preview_numeric(run),
            "documentation_enjoyer": _score(categories, "documentation") >= 90,
            "ci_wizard": _score(categories, "cicd") == 100,
            "clean_scan": is_official_appsec_100,
            "healthy_project": run.health_score is not None and run.health_score >= 80,
            "recovery": (previous is not None and previous.health_score is not None and run.health_score is not None
                         and run.health_score - previous.health_score >= 20),
            "full_house": is_mvp_v1 and all_six_numeric,
            "perfect_health": is_mvp_v1 and run.health_score is not None and run.health_score == 100,
            "clean_and_green": is_mvp_v1 and is_official_appsec_100 and _score(categories, "cicd") == 100,
        }
        for key, value in conditions.items():
            if value and key not in unlocked:
                unlocked[key] = (run.completed_at, run.repository_id)
        if run.health_score is not None:
            by_repo[run.repository_id] = run

    # Construct result list with live-derived progress
    result = []
    for item in DEFINITIONS:
        is_unlocked = item.id in unlocked
        unlocked_at, repo_id = unlocked.get(item.id, (None, None))

        # Progress calculation
        progress_current: int | None = None
        progress_target: int | None = item.progress_target
        progress_percent: float | None = None

        if item.id == "maintainer":
            progress_current = min(terminal_count, 10)
            progress_percent = round((progress_current / 10.0) * 100.0, 1)
        elif item.id == "persistent_maintainer":
            progress_current = min(terminal_count, 5)
            progress_percent = round((progress_current / 5.0) * 100.0, 1)
        elif item.id == "triple_tracker":
            progress_current = min(tracked_count, 3)
            progress_percent = round((progress_current / 3.0) * 100.0, 1)
        elif item.id == "portfolio_keeper":
            analyzed_count = len(analyzed_tracked_repo_ids)
            progress_current = min(analyzed_count, 5)
            progress_percent = round((progress_current / 5.0) * 100.0, 1)

        result.append({
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "rarity": item.rarity,
            "icon_key": item.icon_key,
            "hint": item.hint,
            "unlocked": is_unlocked,
            "unlocked_at": unlocked_at,
            "repository_id": repo_id,
            "progress_current": progress_current,
            "progress_target": progress_target,
            "progress_percent": progress_percent,
        })
    return result


def _score(categories, name):
    value = categories.get(name, {}).get("score")
    return float(value) if isinstance(value, (int, float)) else -1.0


def _preview_numeric(run):
    from sourcehealth.scoring.coverage import score_preview
    preview = score_preview(run.scoring_policy_version, run.category_scores)
    return bool(preview and preview.get("numeric"))


def _official_security(run):
    results = run.results if isinstance(run.results, dict) else {}
    check = results.get("checks", {}).get("sourcecraft_appsec", {})
    metrics = check.get("metrics", {}) if isinstance(check, dict) else {}
    return (check.get("source") == "sourcecraft_appsec"
            and check.get("availability") == "available"
            and metrics.get("complete") is True)
