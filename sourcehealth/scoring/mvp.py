"""MVP policy v1: фиксированные transforms, coverage и replay без I/O/LLM."""

from datetime import datetime

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


class MVPPolicy:
    version = "mvp-score-v1"

    def evaluate(self, results):
        categories = {}
        for category in Category:
            relevant = [r for r in results.values() if r.category == category]
            availability = relevant[0].availability if relevant else A.NO_DATA
            if any(r.availability != availability for r in relevant):
                availability = A.PARTIAL
            explanation = ("SourceCraft AppSec interface is not confirmed; Security не заменяется local SAST."
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
        if usable(check) and check.metrics.get("complete") and check.metrics.get("stale_ratio") is not None:
            m = check.metrics
            components = [(60, 100 * (1 - clamp(m["stale_ratio"])))]
            if m.get("median_first_response_hours") is not None:
                components.append((20, 100 * (1 - clamp(m["median_first_response_hours"] / 168))))
            if m.get("median_close_hours") is not None:
                components.append((20, 100 * (1 - clamp(m["median_close_hours"] / 720))))
            assign("issues", components, [check], explanation="Stale 60; ответ до 7 дней 20; закрытие до 30 дней 20. Неизвестные времена исключены.")

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
            m = git.metrics
            components = [(40, 100 * clamp(m["commits_last_30_days"] / 20)),
                          (40, 100 * (1 - clamp(m["days_since_last_commit"] / 90)))]
            checks = [git]
            if platform:
                pm = platform.metrics
                if pm.get("recent_pr_activity") is not None:
                    components.append((10, 100 * clamp(pm["recent_pr_activity"] / 5)))
                if pm.get("contributors_count") is not None:
                    components.append((5, 100 * clamp(pm["contributors_count"] / 3)))
                if pm.get("release_count") is not None:
                    age = 365
                    if pm.get("last_release"):
                        age = (datetime.fromisoformat(platform.metadata["reference_time"]) - datetime.fromisoformat(pm["last_release"])).total_seconds() / 86400
                    components.append((5, 100 * (1 - clamp(age / 365))))
                if platform.evidence:
                    checks.append(platform)
            assign("activity", components, checks,
                   explanation="Git: 20 commits/30д и давность до 90д (40+40); PR 10, contributors 5, releases 5. Likes не учитываются.")
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
