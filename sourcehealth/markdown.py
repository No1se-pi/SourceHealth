"""Детерминированный Markdown из публичного JSON 3.0, без I/O и текущих часов."""

import html
import re


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
             f"Repo Health Score: {score if score is not None else 'NO_DATA — оценка не рассчитана'}", "",
             "## Категории", "", "| Категория | Score | Доступность | Объяснение |", "|---|---|---|---|"]
    for name, category in sorted(report.get("category_scores", {}).items()):
        value = category.get("score")
        lines.append(f"| {_text(name)} | {value if value is not None else 'NO_DATA'} | "
                     f"{_text(category['availability'])} | {_text(category['explanation'])} |")
    lines += ["", "## Сильные стороны", "", "Выводы появятся после утверждения правил и привязки к фактам.",
              "", "## Проблемы и ограничения данных", ""]
    for name, check in sorted(report.get("checks", {}).items()):
        lines.append(f"- {_text(name)}: {_text(check['availability'])}; находок: {len(check.get('findings', []))}.")
        for finding in check.get("findings", []):
            lines.append(f"  - {_text(finding.get('rule_id', 'finding'))}: {_text(finding.get('path', ''))}")
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
