"""Детерминированные действия по наблюдённым фактам, без обещаний численного прироста."""

from sourcehealth.core.domain import Category, Recommendation
from sourcehealth.scoring.mvp import usable

from . import validate_recommendations


def recommend(results):
    items = []

    def add(check, key, title, action, priority=2):
        if not check.evidence:
            return
        items.append(Recommendation(id=key, category=Category(check.category), title=title,
                     description="Рекомендация основана на сохранённом наблюдении; численный прирост не обещается.",
                     priority=priority, evidence_refs=tuple(e.id for e in check.evidence), suggested_action=action,
                     expected_impact="High" if priority == 1 else "Medium"))

    docs = results.get("documentation")
    if usable(docs):
        for metric, title, action in (
            ("readme", "Добавить README", "Описать назначение проекта и первый запуск."),
            ("run_instructions", "Добавить Quick Start", "Указать зависимости и проверяемую команду локального запуска."),
            ("build_instructions", "Описать сборку", "Добавить команды сборки и ожидаемый результат."),
            ("test_instructions", "Описать тестирование", "Добавить команды запуска тестов."),
            ("license", "Указать лицензию", "Добавить подходящую проекту лицензию и проверить права на распространение."),
        ):
            if docs.metrics.get(metric) is False:
                add(docs, f"docs:{metric}", title, action)
    ci = results.get("cicd")
    if usable(ci):
        if ci.metrics.get("configured") is False:
            add(ci, "ci:configure", "Настроить CI", "Добавить .sourcecraft/ci.yaml с проверками проекта.", 1)
        elif ci.metrics.get("success_rate") is not None and ci.metrics["success_rate"] < 0.8:
            add(ci, "ci:failures", "Разобрать неуспешные CI-запуски", "Проверить последние failed/timeout/rejected runs и устранить причины.", 1)
    issues = results.get("issues")
    if usable(issues) and (issues.metrics.get("stale_open_count") or 0) > 0:
        add(issues, "issues:stale", "Провести triage зависших задач", "Обновить, назначить ответственного или закрыть задачи без обновлений 30 дней.")
    debt = results.get("technical_debt")
    if usable(debt) and (debt.metrics["todo_count"] + debt.metrics["fixme_count"]) > 0:
        add(debt, "debt:markers", "Разобрать TODO/FIXME", "Начать со старых маркеров; вынести актуальный долг в задачи и удалить устаревшие пометки.")
    sast = results.get("sast")
    if usable(sast) and any(sast.metrics["summary"].values()):
        add(sast, "code:local-findings", "Проверить находки локального статического анализа", "Проверить координаты и рекомендации правил; это code health, не официальный AppSec Score.", 1)
    for check in results.values():
        if check.category == "security" and check.source == "sourcecraft_appsec" and usable(check):
            counts = check.metrics.get("open_by_severity", {})
            if any(type(v) is int and v > 0 for v in counts.values()):
                add(check, "security:official-findings", "Устранить подтверждённые AppSec findings", "Открыть официальный scan и применить remediation, начиная с critical/high.", 1)
    validate_recommendations(items, results)
    return sorted(items, key=lambda item: (item.priority, item.id))
