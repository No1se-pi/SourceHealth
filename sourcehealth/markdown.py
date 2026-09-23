"""Детерминированный Markdown из публичного JSON 3.0, без I/O и текущих часов."""

import html
import re

from sourcehealth.scoring.coverage import score_coverage, score_preview


def _text(value) -> str:
    # Escape raw HTML and Markdown delimiters from repository-provided strings.
    text = html.escape(str(value), quote=True).replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)


def render_markdown(report) -> str:
    """Принимает AnalysisReport либо сохранённый публичный JSON. null не становится 0."""
    if hasattr(report, "to_public_dict"):
        report = report.to_public_dict()
    if report.get("schema_version") != "3.0":
        raise ValueError("Markdown requires public report schema 3.0")
    repository = report["repository"]
    title = f"{repository['organization_slug']}/{repository['repository_slug']}"
    score = report.get("health_score")
    lines = [f"# SourceHealth — {_text(title)}", "", f"Репозиторий: {_text(repository['canonical_url'])}",
             f"Анализ: {_text(report['completed_at'])}",
             f"Методика: {_text(report.get('scoring_policy_version', 'unconfigured-v1'))}", "",
             f"Repo Health Score: {score if score is not None else 'NO_DATA — итоговая оценка пока не рассчитана'}", ""]
    preview = score_preview(report.get("scoring_policy_version"), report.get("category_scores", {}))
    if score is None and preview:
        if preview["numeric"]:
            lines += [f"Source Soul: ≈{preview['score']} / 100",
                      f"Предварительная оценка по {preview['nominal_weight_percent']}% номинального веса, "
                      f"{preview['scored_categories']} из 6 категорий."]
        else:
            lines += ["Source Soul: формируется",
                      f"Охват: {preview['nominal_weight_percent']}%, категорий: {preview['scored_categories']}."]
        lines += ["Source Soul не является официальным Health Score и не участвует в рейтинге.", ""]
    lines += [
             "## Категории", "", "| Категория | Score | Доступность | Объяснение |", "|---|---|---|---|"]
    for name, category in sorted(report.get("category_scores", {}).items()):
        value = category.get("score")
        lines.append(f"| {_text(name)} | {value if value is not None else 'NO_DATA'} | "
                     f"{_text(category['availability'])} | {_text(category['explanation'])} |")
    lines += ["", "## Сильные стороны", ""]
    strengths = [name for name, c in report.get("category_scores", {}).items() if c.get("score") is not None and c["score"] >= 80]
    lines += [f"- {_text(name)}: оценка не ниже 80 по сохранённой методике." for name in sorted(strengths)] or ["Недостаточно подтверждённых высоких оценок."]
    scored = [name for name, c in report.get("category_scores", {}).items() if c.get("score") is not None]
    lines += ["", f"Охват: рассчитано категорий {len(scored)} из 6. NO_DATA — данных нет; это не нулевая оценка.",
              "", "## Проблемы и ограничения данных", ""]
    coverage = score_coverage(report.get("scoring_policy_version"), report.get("category_scores", {}))
    if coverage:
        lines += [f"Охват оценки по номинальным весам: {coverage['nominal_weight_percent']}%.",
                  f"Без оценки: {_text(', '.join(coverage['unscored_categories']) or 'нет')}.",
                  f"Частичные категории: {_text(', '.join(coverage['partial_categories']) or 'нет')}. "
                  "Процент весов не означает полноту всех проверок.", ""]
    for name, check in sorted(report.get("checks", {}).items()):
        lines.append(f"- {_text(name)}: {_text(check['availability'])}; находок: {len(check.get('findings', []))}.")
        for finding in check.get("findings", []):
            lines.append(f"  - {_text(finding.get('rule_id', 'finding'))}: {_text(finding.get('path', ''))}")
    appsec = next((check for check in report.get("checks", {}).values()
                   if check.get("source") == "sourcecraft_appsec"
                   and check.get("availability") == "available"
                   and check.get("metrics", {}).get("complete") is True), None)
    counts = appsec.get("metrics", {}).get("open_by_severity") if appsec else None
    if isinstance(counts, dict) and all(type(counts.get(k)) is int for k in ("critical", "high", "medium", "low")):
        weights = {"critical": 40, "high": 20, "medium": 5, "low": 1}
        penalty = sum(counts[name] * weights[name] for name in weights)
        security_score = report.get("category_scores", {}).get("security", {}).get("score")
        lines += ["", "### Official SourceCraft AppSec", "", "| Severity | Open | Penalty |",
                  "|---|---:|---:|"]
        for name in weights:
            lines.append(f"| {name.title()} | {counts[name]} | {-counts[name] * weights[name]} |")
        lines += ["", f"Итого открыто: {sum(counts.values())}.", "",
                  f"Security: max(0, 100 - {penalty}) = "
                  f'{security_score if security_score is not None else "NO_DATA"}.']
    lines += ["", "## Рекомендации", ""]
    recommendations = sorted(report.get("recommendations", []), key=lambda r: (r["priority"], r["id"]))
    for item in recommendations:
        lines += [f"- P{item['priority']}: {_text(item['title'])}. {_text(item['description'])}",
                  f"  Действие: {_text(item['suggested_action'])}. Факты: {_text(', '.join(item['evidence_refs']))}"]
    if not recommendations:
        lines.append("Рекомендации пока не сформированы; это не доказательство отсутствия проблем.")
    lines += ["", "## Подтверждающие факты", ""]
    for _, check in sorted(report.get("checks", {}).items()):
        for evidence in sorted(check.get("evidence", []), key=lambda e: e["id"]):
            lines.append(f"- {_text(evidence['id'])}: {_text(evidence['summary'])} ({_text(evidence['source'])}); "
                         f"{_text(evidence.get('url') or evidence['reference'])}")
    return "\n".join(lines) + "\n"
