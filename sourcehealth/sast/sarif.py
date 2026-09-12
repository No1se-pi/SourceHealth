"""Экспорт находок в SARIF 2.1.0 для CI и редакторов без исходного кода.

JSON SourceHealth остаётся основным форматом. SARIF хранит результаты SAST,
каталог правил, диагностику и сводку покрытия; метрики Git остаются в обычном JSON.
"""

from __future__ import annotations

from urllib.parse import quote

from .models import ANALYZER_VERSION
from .rules import Rule


def to_sarif(report: dict, rules: tuple[Rule, ...]) -> dict:
    """Преобразовать общий JSON-отчёт в SARIF; пути экранируются как URI.

    Колонки SourceHealth измеряются Unicode code points, что явно указано
    в run.columnKind. Неполная проверка сохраняет находки, но отмечает invocation
    как неуспешный. Код CLI также остаётся 2, а не становится успешным из-за экспорта.
    """
    sast = report["checks"]["sast"]
    catalogue = []
    for rule in rules:
        entry = {
            "id": rule.id,
            "shortDescription": {"text": rule.message},
            "help": {"text": rule.recommendation},
            "properties": {"category": rule.category, "confidence": rule.confidence,
                           "tags": [rule.category, *([rule.cwe] if rule.cwe else [])]},
        }
        if rule.references:
            entry["helpUri"] = rule.references[0]
        catalogue.append(entry)
    indices = {rule.id: index for index, rule in enumerate(rules)}
    results = []
    for finding in sast["findings"]:
        results.append({
            "ruleId": finding["rule_id"], "ruleIndex": indices[finding["rule_id"]],
            "level": {"high": "error", "medium": "warning", "low": "note"}[finding["severity"]],
            "message": {"text": finding["message"] + " " + finding["recommendation"]},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": quote(finding["path"], safe="/")},
                "region": {"startLine": finding["line"], "startColumn": finding["column"]},
            }}],
            "properties": {"confidence": finding["confidence"], "engine": finding["engine"]},
        })
    notifications = [{"level": "warning", "message": {"text": f"{reason}: {count}"}}
                     for reason, count in sorted(sast["skipped"].items())]
    return {
        "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/schemas/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "SourceHealth SAST", "semanticVersion": ANALYZER_VERSION, "rules": catalogue}},
            "columnKind": "unicodeCodePoints",
            "newlineSequences": ["\r\n", "\r", "\n"],
            "results": results,
            "invocations": [{"executionSuccessful": report["complete"], "toolExecutionNotifications": notifications}],
            "properties": {"sourcehealth": {
                "complete": report["complete"], "rulesetDigest": sast["ruleset_digest"],
                "filesScanned": sast["files_scanned"], "summary": sast["summary"],
                "diagnostics": sast["diagnostics"],
            }},
        }],
    }
