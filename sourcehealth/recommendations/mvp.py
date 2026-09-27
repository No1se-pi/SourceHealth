"""Детерминированные действия по наблюдённым фактам, без обещаний численного прироста."""

from sourcehealth.core.domain import Category, Recommendation
from sourcehealth.scoring.mvp import usable

from . import validate_recommendations


def recommend(results):
    items = []

    def add(check, key, title, action, priority=2, *, description=None,
            expected_impact=None, category=None):
        if not check.evidence:
            return
        items.append(Recommendation(id=key, category=Category(category or check.category), title=title,
                     description=description or "Рекомендация основана на сохранённом наблюдении; численный прирост не обещается.",
                     priority=priority, evidence_refs=tuple(e.id for e in check.evidence), suggested_action=action,
                     expected_impact=expected_impact or ("High" if priority == 1 else "Medium")))

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
    insights = results.get("repository_insights")
    if insights and insights.availability in {"available", "partial"}:
        m = insights.metrics
        top_share = m.get("top_contributor_share")
        if m.get("bus_factor_proxy") == 1 or (top_share is not None and top_share >= 0.70):
            priority = 1 if top_share is not None and top_share >= 0.85 else 2
            add(insights, "insights:bus-factor", "Снизить зависимость от одного участника",
                "Распределить review и владение критичными зонами, описать их и обеспечить второго сопровождающего.",
                priority, category="code_health",
                description=f"Один участник выполнил {top_share:.0%} наблюдаемых коммитов; Bus Factor proxy основан на концентрации изменений.",
                expected_impact="Снизится риск остановки сопровождения и потери контекста.")
        dominant = [item for item in m.get("ownership_groups", []) if item.get("dominant_share", 0) >= 0.8]
        if dominant:
            groups = ", ".join(item["path_group"] for item in dominant[:5])
            add(insights, "insights:ownership", "Распределить владение ключевыми областями",
                "Назначить совместное review и передать знания ещё одному участнику для отмеченных областей.",
                category="code_health", description=f"В областях {groups} один участник выполнил не менее 80% наблюдаемых изменений.",
                expected_impact="Улучшится взаимозаменяемость сопровождающих.")
        if m.get("snapshot_complete"):
            for metric, key, title, action in (
                ("security_policy_present", "insights:security-policy", "Добавить SECURITY.md",
                 "Описать безопасный канал и порядок сообщения об уязвимостях."),
                ("codeowners_present", "insights:codeowners", "Добавить CODEOWNERS",
                 "Зафиксировать ответственных и обязательное review для критичных областей."),
                ("contributing_present", "insights:contributing", "Добавить CONTRIBUTING",
                 "Описать подготовку изменений, проверки и порядок review."),
                ("branch_policy_present", "insights:branch-policy", "Зафиксировать политику веток",
                 "Добавить .sourcecraft/branches.yaml с подходящими проекту правилами; отсутствие файла не доказывает отсутствие настроек платформы."),
                ("review_policy_present", "insights:review-policy", "Зафиксировать политику review",
                 "Добавить .sourcecraft/review.yaml с требованиями к проверке изменений; отсутствие файла не доказывает отсутствие настроек платформы."),
            ):
                if m.get(metric) is False:
                    add(insights, key, title, action, category="code_health",
                        description="В полном tracked snapshot соответствующий файл не обнаружен.",
                        expected_impact="Процесс сопровождения станет явным и воспроизводимым.")
            if m.get("dependency_manifest_count", 0) > 0:
                count = m["dependency_manifest_count"]
                if m.get("lockfile_coverage") == 0:
                    add(insights, "insights:dependency-locks", "Зафиксировать версии зависимостей",
                        "Добавить поддерживаемые экосистемами lockfiles и обновлять их вместе с manifests.",
                        category="code_health", description=f"Обнаружено manifests: {count}; соответствующие lockfiles не обнаружены.",
                        expected_impact="Сборки и проверки зависимостей станут воспроизводимее.")
                if m.get("dependency_update_automation") is False:
                    add(insights, "insights:dependency-updates", "Автоматизировать обновление зависимостей",
                        "Настроить Dependabot или Renovate с обязательными проверками изменений.",
                        category="code_health", description=f"Обнаружено manifests: {count}; известная конфигурация автоматических обновлений отсутствует.",
                        expected_impact="Устаревшие зависимости будут обнаруживаться раньше.")
                if m.get("license_policy_present") is False:
                    add(insights, "insights:license-policy", "Добавить политику лицензий зависимостей",
                        "Зафиксировать допустимые лицензии в .sourcecraft/security/licenses.yaml после проверки требований проекта.",
                        category="code_health", description="В tracked snapshot есть dependency manifests, но policy-файл лицензий не найден.",
                        expected_impact="Проверка состава зависимостей станет последовательной.")
    validate_recommendations(items, results)
    return sorted(items, key=lambda item: (item.priority, item.id))
