"""MVP policy v1: фиксированные transforms, coverage и replay без I/O/LLM."""

from datetime import datetime
from math import isfinite
from typing import Any

from sourcehealth.core.domain import Category
from sourcehealth.core.domain import DataAvailability as A

from .engine import CategoryScore, ScoreResult

WEIGHTS = {"documentation": 15, "cicd": 15, "security": 20, "activity": 15, "issues": 15, "code_health": 20}
DOCUMENTATION_WEIGHTS = {"readme": 20, "license": 15, "run_instructions": 20, "build_instructions": 10,
                         "test_instructions": 15, "contributing": 5, "codeowners": 5, "docs_directory": 10}


def clamp(value):
    return max(0.0, min(1.0, value))


def usable(check):
    return check is not None and check.status == "ok" and check.availability in {A.AVAILABLE, A.NOT_CONFIGURED}


def activity_components(git, platform):
    """Expose the v1.2 component calculation for deterministic characterization without changing policy."""
    metrics = git.metrics
    recent = min(clamp(metrics["commits_last_30_days"] / 20),
                 clamp(metrics["active_days_last_30_days"] / 5))
    values = {"recent": 100 * recent,
              "recency": 100 * (1 - clamp(metrics["days_since_last_commit"] / 90)),
              "pull_requests": None, "contributors": None, "releases": None}
    components = [(40, values["recent"]), (40, values["recency"])]
    if platform:
        platform_metrics = platform.metrics
        if platform_metrics.get("recent_pr_activity") is not None:
            values["pull_requests"] = 100 * clamp(platform_metrics["recent_pr_activity"] / 5)
            components.append((10, values["pull_requests"]))
        if platform_metrics.get("contributors_count") is not None:
            values["contributors"] = 100 * clamp(platform_metrics["contributors_count"] / 3)
            components.append((5, values["contributors"]))
        if platform_metrics.get("release_count") is not None:
            age = 365
            if platform_metrics.get("last_release"):
                age = (datetime.fromisoformat(platform.metadata["reference_time"])
                       - datetime.fromisoformat(platform_metrics["last_release"])).total_seconds() / 86400
            values["releases"] = 100 * (1 - clamp(age / 365))
            components.append((5, values["releases"]))
    return components, values


class MVPPolicy:
    version = "mvp-score-v1.2"

    def evaluate(self, results):
        categories = {}
        for category in Category:
            relevant = [r for r in results.values() if r.category == category]
            availability = relevant[0].availability if relevant else A.NO_DATA
            if any(r.availability != availability for r in relevant):
                availability = A.PARTIAL
            explanation = ("Official SourceCraft AppSec не предоставил пригодных данных для этой оценки; local SAST не заменяет Security."
                           if category == Category.SECURITY else "Недостаточно полных наблюдений для оценки категории.")
            categories[category.value] = CategoryScore(category, availability=availability, explanation=explanation)

        def assign(name, components, checks, *, minimum=0, explanation=""):
            weight = sum(w for w, _ in components)
            if not components or weight < minimum:
                return
            refs = tuple(sorted({e.id for check in checks for e in check.evidence}))
            if not refs:
                return
            availability = A.AVAILABLE
            if any(check.availability == A.NOT_CONFIGURED for check in checks):
                availability = A.NOT_CONFIGURED
            if any(r.category == name and not usable(r) for r in results.values()):
                availability = A.PARTIAL
            categories[name] = CategoryScore(Category(name), round(sum(w * s for w, s in components) / weight, 2),
                                             availability, explanation, refs)

        check = results.get("documentation")
        if usable(check) and all(type(check.metrics.get(k)) is bool for k in DOCUMENTATION_WEIGHTS):
            assign("documentation", [(1, sum(w for k, w in DOCUMENTATION_WEIGHTS.items() if check.metrics[k]))], [check],
                   explanation="README 20, LICENSE 15, запуск 20, сборка 10, тесты 15, CONTRIBUTING 5, CODEOWNERS 5, docs 10.")

        check = results.get("issues")
        if (usable(check) and check.metrics.get("complete") and check.metrics.get("observed_count", 0) > 0
                and check.metrics.get("stale_ratio") is not None):
            m = check.metrics
            components = [(60, 100 * (1 - clamp(m["stale_ratio"])))]
            if m.get("external_response_rate") is not None:
                latency = m.get("median_first_external_response_hours")
                speed = 1 - clamp(latency / 168) if latency is not None else 0
                components.append((20, 100 * clamp(m["external_response_rate"]) * speed))
            if m.get("median_close_hours") is not None:
                components.append((20, 100 * (1 - clamp(m["median_close_hours"] / 720))))
            assign("issues", components, [check], explanation="Stale 60; внешний ответ до 7 дней × доля ответивших 20; закрытие до 30 дней 20. Неполная история ответов исключена.")

        check = results.get("cicd")
        if usable(check):
            m = check.metrics
            score = (0 if m.get("configured") is False else
                     40 if m.get("configured") is True and m.get("runs_observed") == 0 else
                     100 * m["success_rate"] if m.get("success_rate") is not None else None)
            if score is not None:
                assign("cicd", [(1, score)], [check],
                       explanation="100 × success/(success+failed+timeout+rejected). Нет конфигурации: 0; конфигурация без запусков: 40.")

        git, platform = results.get("git_activity"), results.get("platform_activity")
        if usable(git) and git.metrics.get("days_since_last_commit") is not None:
            # A same-day commit burst cannot max the recent activity component.
            components, _ = activity_components(git, platform)
            checks = [git]
            if platform:
                if platform.evidence:
                    checks.append(platform)
            assign("activity", components, checks,
                   explanation="Git: min(20 commits, 5 active days)/30д и давность до 90д (40+40); PR 10, contributors 5, releases 5. Likes не учитываются.")
        elif usable(git) and git.metrics.get("total_commits") == 0:
            assign("activity", [(1, 0)], [git], explanation="Полностью наблюдаемая пустая Git-история: 0.")

        debt, sast = results.get("technical_debt"), results.get("sast")
        components, checks = [], []
        if usable(debt) and debt.metrics.get("code_files", 0) > 0:
            m = debt.metrics
            components += [(40, 100 * (1 - clamp(m["marker_density"] / 5))),
                           (10, 100 * (1 - clamp(m["large_files"] / m["code_files"])))]
            if m.get("age_complete"):
                components.append((10, 100 * (1 - clamp((m["oldest_marker_age_days"] or 0) / 365))))
            checks.append(debt)
        if usable(sast) and sast.metrics.get("code_files_lexed", 0) > 0:
            summary = sast.metrics["summary"]
            components.append((40, max(0, 100 - 15 * summary["high"] - 5 * summary["medium"] - summary["low"])))
            checks.append(sast)
        assign("code_health", components, checks, minimum=50,
               explanation="TODO/FIXME density 40, large files 10, marker age 10, local SAST 40; нужно ≥50 внутренних весов.")

        # Reserved normalized AppSec input, not an external client or a fabricated production finding.
        security = [r for r in results.values() if r.category == "security" and r.source == "sourcecraft_appsec" and usable(r)]
        if security:
            check = security[0]
            counts = check.metrics.get("open_by_severity")
            if (check.metrics.get("complete") is True and isinstance(counts, dict)
                    and all(type(counts.get(k)) is int and counts[k] >= 0 for k in ("critical", "high", "medium", "low"))):
                score = max(0, 100 - sum(counts[k] * w for k, w in {"critical": 40, "high": 20, "medium": 5, "low": 1}.items()))
                assign("security", [(1, score)], [check], explanation="Открытые official AppSec: critical −40, high −20, medium −5, low −1; resolved исключены.")
        available = {name: c for name, c in categories.items() if c.score is not None}
        weight = sum(WEIGHTS[name] for name in available)
        health = (round(sum(WEIGHTS[name] * c.score for name, c in available.items()) / weight, 2)
                  if len(available) >= 3 and weight >= 50 else None)
        return ScoreResult(self.version, categories, health)


def calculate_mvp_health(category_scores: dict[str, float | None]) -> dict[str, Any]:
    """Calculate aggregate Health Score using canonical mvp-score-v1.2 aggregation semantics.

    category_scores: dict with keys from Category, mapped to score (0..100) or None (for NO_DATA).
    """
    measured: dict[str, float] = {}
    breakdown: dict[str, dict[str, Any]] = {}
    for name, norm_weight in WEIGHTS.items():
        score = category_scores.get(name)
        if score is not None:
            val = float(score)
            if not isfinite(val) or not 0.0 <= val <= 100.0:
                raise ValueError(f"Category '{name}' score must be between 0 and 100")
            measured[name] = val
            breakdown[name] = {
                "score": val,
                "weight": norm_weight,
                "available": True,
            }
        else:
            breakdown[name] = {
                "score": None,
                "weight": norm_weight,
                "available": False,
            }

    active_weight = sum(WEIGHTS[name] for name in measured)
    measurable_count = len(measured)
    eligible = measurable_count >= 3 and active_weight >= 50

    if eligible:
        health_score = round(sum(WEIGHTS[name] * s for name, s in measured.items()) / active_weight, 2)
        explanation = (
            f"Health Score = {health_score:.2f}, рассчитан по {measurable_count} доступным категориям "
            f"с суммарным весом {active_weight}%. Формула: Σ(w_i × s_i) / Σ(w_i). "
            f"Категории со статусом NO_DATA честно исключены из знаменателя и не штрафуют проект нулём."
        )
    else:
        health_score = None
        explanation = (
            f"Health не рассчитывается (null). Не выполнен обязательный порог допуска методики mvp-score-v1.2: "
            f"требуется не менее 3 доступных категорий и не менее 50% нормативного веса. "
            f"Сейчас доступно: {measurable_count} категорий ({active_weight}% веса). "
            f"Отсутствие данных не превращается в 0."
        )

    coverage = round(float(active_weight), 2)

    return {
        "policy_version": "mvp-score-v1.2",
        "health_score": health_score,
        "coverage": coverage,
        "eligible": eligible,
        "measurable_count": measurable_count,
        "active_weight": active_weight,
        "total_nominal_weight": sum(WEIGHTS.values()),
        "categories": breakdown,
        "explanation": explanation,
    }


DEMO_PRESETS: list[dict[str, Any]] = [
    {
        "id": "healthy",
        "name": "Здоровый проект",
        "description": "Все 6 категорий измерены, высокие показатели качества и безопасности.",
        "scores": {
            "documentation": 95.0,
            "cicd": 90.0,
            "security": 100.0,
            "activity": 85.0,
            "issues": 90.0,
            "code_health": 95.0,
        },
    },
    {
        "id": "no_security",
        "name": "Нет Security данных",
        "description": "Анализ без AppSec токена: Security=NO_DATA. Балл ренормализуется без штрафа нулём.",
        "scores": {
            "documentation": 90.0,
            "cicd": 85.0,
            "security": None,
            "activity": 80.0,
            "issues": 85.0,
            "code_health": 90.0,
        },
    },
    {
        "id": "broken_ci",
        "name": "Сломанный CI",
        "description": "Сбои в пайплайнах CI/CD снижают надежность автоматизации.",
        "scores": {
            "documentation": 85.0,
            "cicd": 15.0,
            "security": 90.0,
            "activity": 75.0,
            "issues": 80.0,
            "code_health": 85.0,
        },
    },
    {
        "id": "poor_docs",
        "name": "Плохая документация",
        "description": "Отсутствуют инструкции по сборке, тестированию и русскоязычный старт.",
        "scores": {
            "documentation": 20.0,
            "cicd": 85.0,
            "security": 95.0,
            "activity": 80.0,
            "issues": 85.0,
            "code_health": 90.0,
        },
    },
    {
        "id": "high_debt",
        "name": "Высокий технический долг",
        "description": "Много TODO/FIXME маркеров, старый код и замечания SAST-сканера.",
        "scores": {
            "documentation": 80.0,
            "cicd": 80.0,
            "security": 85.0,
            "activity": 75.0,
            "issues": 70.0,
            "code_health": 25.0,
        },
    },
    {
        "id": "low_data",
        "name": "Мало данных",
        "description": "Менее 3 категорий и менее 50% веса: Health не рассчитывается (NO_DATA).",
        "scores": {
            "documentation": 70.0,
            "cicd": 65.0,
            "security": None,
            "activity": None,
            "issues": None,
            "code_health": None,
        },
    },
]
