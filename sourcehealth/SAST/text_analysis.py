"""Пакетное применение native re вместо Python-цикла на каждую строку.

text_regex имеет явно файловую семантику re.MULTILINE; прежний engine=regex
сохраняет построчный контракт для совместимости сторонних правил. code_regex
дополнительно учитывает лексический контекст четырёх языков.
"""

from __future__ import annotations

import re
import time
from typing import Callable

from .code_analysis import LineMap, lexical_context
from .models import Finding, ScanConfig, ScanResult
from .rules import Rule


def scan_text(content: str, path: str, rules: tuple[Rule, ...], config: ScanConfig,
              result: ScanResult, deadline: float,
              finding_factory: Callable[[Rule, str, int, int], Finding]) -> None:
    """Применить файловые правила; находки сразу ограничиваются общим лимитом.

    Дедупликация секретов выполняется по пересечению позиций без хранения значений.
    Лексический контекст и индекс строк строятся только при необходимости.
    """
    lowered = content.lower()
    active = tuple(sorted(
        (rule for rule in rules if rule.engine in ("text_regex", "code_regex")
         and (not rule.keywords or any(word in lowered for word in rule.keywords))
         and (rule.prefilter_regex is None or rule.prefilter_regex.search(content))),
        key=lambda rule: rule.entropy_threshold is not None,
    ))
    if not active:
        return
    lines = LineMap(content)
    # Проверка длины выполняется в C; ^ ограничивает попытки началом строки.
    long_lines = [(m.start(), content.find("\n", m.end()))
                  for m in re.finditer(r"(?m)^[^\n]{" + str(config.max_line_chars + 1) + r"}", content)]
    for start, _ in long_lines:
        result.skip("long_line", incomplete=True)
        result.diagnose("long_line", path, lines.locate(start)[0])
    if long_lines:
        # Длинные строки не передаются regex. Сохраняем позиции остальных строк.
        pieces = []
        previous = 0
        for start, end in long_lines:
            end = len(content) if end < 0 else end
            pieces.extend((content[previous:start], " " * (end - start)))
            previous = end
        pieces.append(content[previous:])
        content = "".join(pieces)
    contexts = {}
    secret_spans: list[tuple[int, int]] = []
    for rule in active:
        if time.monotonic() >= deadline:
            result.skip("timeout", incomplete=True)
            return
        context = None
        text = content
        if rule.engine == "code_regex":
            if rule.language not in contexts:
                # Без комментариев текст не изменится. Если нет и сырого
                # совпадения, токенизация не может добавить находку.
                if "/*" not in content and "//" not in content and not rule.regex.search(content):
                    continue
                contexts[rule.language] = lexical_context(content, rule.language)
                result.code_files_lexed += 1
                if contexts[rule.language].error:
                    result.skip("lexical_error", incomplete=True)
                    result.diagnose("lexical_error", path)
            context = contexts[rule.language]
            text = context.text
        for index, match in enumerate(rule.regex.finditer(text)):
            if index % 256 == 0 and time.monotonic() >= deadline:
                result.skip("timeout", incomplete=True)
                return
            if context is not None and not context.is_code(match.start()):
                continue
            if not rule.accepts(match):
                continue
            start, end = match.span("secret") if rule.entropy_threshold is not None else match.span()
            if rule.entropy_threshold is not None and any(start < b and end > a for a, b in secret_spans):
                continue
            if rule.category == "secret" or rule.id.startswith("SECRET-"):
                secret_spans.append((start, end))
            line, column = lines.locate(start)
            result.findings.append(finding_factory(rule, path, line, column))
            if len(result.findings) >= config.max_findings:
                result.skip("finding_limit", incomplete=True)
                return
