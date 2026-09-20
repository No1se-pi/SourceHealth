"""Общий CLI: python -m sourcehealth PATH --output report.json.

Exit codes: 0 — проверка завершена; 1 — превышен --fail-on;
2 — ошибка или неполная проверка. Код 2 приоритетнее найденных проблем.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from sourcehealth.reporting import analyze_repository, to_legacy_report
from sourcehealth.sast import DEFAULT_RULES, SASTScanError, SASTScanner, ScanConfig, load_rules
from sourcehealth.sast.sarif import to_sarif


def write_report(report: dict[str, Any], output: Path | None) -> None:
    """Записать UTF-8 JSON атомарно либо вывести его в stdout.

    Временный файл создаётся рядом с результатом: os.replace не пересекает
    файловые системы. При ошибке предыдущий отчёт остаётся целым.
    Имя output выбирает оператор, не содержимое проверяемого репозитория.
    """
    serialized = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if output is None:
        sys.stdout.write(serialized)
        return
    output = output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None, *, legacy: bool = False,
         with_git_default: bool = True) -> int:
    """Разобрать параметры и вернуть машинно-читаемый код завершения."""
    parser = argparse.ArgumentParser(description="Лёгкий SAST рабочей копии; код проекта не запускается.")
    parser.add_argument("path", nargs="?", help="Папка с исходным кодом")
    parser.add_argument("--output", type=Path, help="JSON-файл; по умолчанию stdout")
    parser.add_argument("--with-git", action="store_true", default=with_git_default,
                        help="Добавить анализ Git-активности")
    parser.add_argument("--no-git", dest="with_git", action="store_false", help="Не собирать Git-историю")
    parser.add_argument("--with-mvp", action="store_true", help="Добавить documentation и technical debt snapshot checks")
    parser.add_argument("--exclude", action="append", default=[], help="Исключение fnmatch для относительного пути")
    parser.add_argument("--timeout", type=float, default=30, help="Лимит времени SAST, секунды")
    parser.add_argument("--max-file-bytes", type=int, default=1_048_576)
    parser.add_argument("--max-findings", type=int, default=1000)
    parser.add_argument("--max-total-bytes", type=int, default=512 * 1_048_576)
    parser.add_argument("--max-files", type=int, default=10_000)
    parser.add_argument("--rules-dir", type=Path, help="Заменить встроенные правила набором из доверенной папки")
    parser.add_argument("--disable-rule", action="append", default=[], help="Отключить правило по ID; можно повторять")
    parser.add_argument("--list-rules", action="store_true", help="Вывести JSON-каталог активных правил без сканирования")
    parser.add_argument("--format", choices=("json", "sarif"), default="json", help="Формат отчёта (по умолчанию json)")
    parser.add_argument("--fail-on", choices=("high", "medium", "low"), help="Вернуть 1 при находке этого уровня или выше")
    args = parser.parse_args(argv)
    if not args.list_rules and not args.path:
        parser.error("укажите папку либо --list-rules")
    if args.format == "sarif" and args.with_git:
        parser.error("для объединённого отчёта с Git используйте --format json")
    try:
        rules = load_rules(args.rules_dir) if args.rules_dir else DEFAULT_RULES
        if set(args.disable_rule) - {rule.id for rule in rules}:
            parser.error("--disable-rule содержит неизвестный ID; смотрите --list-rules")
        rules = tuple(rule for rule in rules if rule.id not in args.disable_rule)
        if not rules:
            parser.error("должно остаться хотя бы одно активное правило")
        if args.list_rules:
            write_report({"rules": [rule.to_dict() for rule in rules]}, args.output)
            return 0
        exclusions = list(args.exclude)
        # Повторный запуск не должен сканировать собственный прошлый отчёт.
        if args.output:
            root = Path(args.path).expanduser().resolve()
            destination = args.output.expanduser().resolve()
            if destination.is_relative_to(root):
                exclusions.append(destination.relative_to(root).as_posix())
        config = ScanConfig(timeout_seconds=args.timeout, max_file_bytes=args.max_file_bytes,
                            max_findings=args.max_findings, exclude_globs=tuple(exclusions),
                            max_total_bytes=args.max_total_bytes, max_files=args.max_files)
        analysis = analyze_repository(args.path, SASTScanner(config, rules), with_git=args.with_git, with_mvp=args.with_mvp)
        report = to_legacy_report(analysis) if legacy or args.format == "sarif" else analysis.to_dict()
        write_report(to_sarif(report, rules) if args.format == "sarif" else report, args.output)
    except (SASTScanError, OSError, ValueError):
        print("SAST: не удалось прочитать каталог, применить параметры или записать отчёт.", file=sys.stderr)
        return 2
    if not report["complete"]:
        return 2
    ranks = {"low": 1, "medium": 2, "high": 3}
    if args.fail_on and any(ranks[f["severity"]] >= ranks[args.fail_on]
                            for f in report["checks"]["sast"]["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
