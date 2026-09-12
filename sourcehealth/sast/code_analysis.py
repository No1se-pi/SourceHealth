"""Лексический контекст Go/Rust/Java/C++ без компиляторов и исполнения кода.

Движок сохраняет длины/переводы строк, маскирует комментарии и отличает начало
вызова от примера внутри строкового литерала. Сам regex может видеть строковые
аргументы, например Cipher.getInstance("DES"). Это не AST и не разрешение типов.
Большие обычные файлы без совпадений не токенизируются вообще.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache


@lru_cache(maxsize=4)
def _tokens(language: str) -> re.Pattern[str]:
    """Найти только начало токена; C-движок быстро пропускает обычный код.

    Большая alternation с raw-префиксами заставляла regex рассматривать почти
    каждую букву. Контекст префикса проверяется теперь лишь около кавычки.
    """
    return re.compile(r'''//|/\*|["']''' + (r'|`' if language == 'go' else ''))


_STRING = re.compile(r'"(?:\\[\s\S]|[^"\\])*"')
_CHAR = re.compile(r"'(?:\\[^\n]|[^'\\\n]){1,12}'")
_RUST_CHAR = re.compile(r"'(?:\\(?:u\{[a-fA-F0-9_]{1,12}\}|x[0-9A-Fa-f]{2}|[^\n])|[^'\\\n])'")
_CPP_DELIMITER = re.compile(r'([^\s()\\]{0,16})\(')


def _raw_ending(content: str, start: int, language: str) -> tuple[int, str] | None:
    """Распознать raw/text-block по кавычке и вернуть конец открывающего маркера."""
    if language == 'go' and content[start] == '`':
        return start + 1, '`'
    if content[start] != '"':
        return None
    if language == 'java' and content.startswith('"""', start):
        return start + 3, '"""'
    if language == 'cpp' and start and content[start - 1] == 'R':
        delimiter = _CPP_DELIMITER.match(content, start + 1)
        if delimiter:
            return delimiter.end(), ')' + delimiter[1] + '"'
    if language == 'rust':
        back = start
        while back > 0 and start - back < 255 and content[back - 1] == '#':
            back -= 1
        if back and content[back - 1] == 'r':
            return start + 1, '"' + content[back:start]
    return None


def _blank(value: str) -> str:
    """Заменить непереводы строк пробелами, сохранив позиции Unicode code points."""
    return re.sub(r"[^\n]+", lambda match: " " * len(match[0]), value)


@dataclass
class CodeContext:
    """Текст без комментариев и интервалы, в которых нельзя начинать находку."""

    text: str
    starts: list[int] = field(default_factory=list)
    ends: list[int] = field(default_factory=list)
    error: bool = False

    def is_code(self, offset: int) -> bool:
        """O(log n) проверка принадлежности позиции комментарию/литералу."""
        index = bisect_right(self.starts, offset) - 1
        return index < 0 or offset >= self.ends[index]


def lexical_context(content: str, language: str) -> CodeContext:
    """Лексически отделить комментарии/литералы; у Rust вложенные block comments.

    Незакрытый литерал/комментарий помечается error, а остаток файла считается
    не-кодом. C++ продолжения // через backslash-newline также скрываются.
    Java Unicode-escapes и C/C++ preprocessor не интерпретируются: эти ограничения
    описаны в README, результат не является доказательством безопасности.
    """
    context = CodeContext(content)
    pieces: list[str] = []
    cursor = 0
    copied = 0
    tokenizer = _tokens(language)
    while match := tokenizer.search(content, cursor):
        start, end = match.span()
        token = match[0]
        if (language == 'cpp' and token == "'" and start > 0 and end < len(content)
                and content[start - 1] in '0123456789abcdefABCDEF'
                and content[end] in '0123456789abcdefABCDEF'):
            # C++14: 1'000 и 0xFF'AB — числа с разделителем, не начало char literal.
            cursor = end
            continue
        comment = token in {"//", "/*"}
        raw = _raw_ending(content, start, language) if not comment else None
        if raw:
            end, terminator = raw
            close = content.find(terminator, end)
            if language == "java":
                # Нечётное число backslash перед кавычкой экранирует её.
                while close >= 0:
                    back = close
                    while back > end and content[back - 1] == "\\":
                        back -= 1
                    if (close - back) % 2 == 0:
                        break
                    close = content.find(terminator, close + 1)
            context.error |= close < 0
            end = len(content) if close < 0 else close + len(terminator)
        elif token == "//":
            end = content.find("\n", end)
            end = len(content) if end < 0 else end
            while language == "cpp" and end < len(content) and content[end - 1:end] == "\\":
                following = content.find("\n", end + 1)
                end = len(content) if following < 0 else following
        elif token == "/*":
            depth = 1
            while depth:
                close = content.find("*/", end)
                if close < 0:
                    end = len(content)
                    context.error = True
                    break
                nested = content.find("/*", end, close) if language == "rust" else -1
                if nested >= 0:
                    depth += 1
                    end = nested + 2
                else:
                    depth -= 1
                    end = close + 2
        else:
            literal = (_STRING if token == '"' else _RUST_CHAR if language == 'rust' else _CHAR).match(content, start)
            if literal:
                end = literal.end()
            elif token == "'" and language == 'rust':
                # Lifetime 'a и метка 'loop не являются символьными литералами.
                cursor = end
                continue
            else:
                context.error = True
                end = len(content)
        context.starts.append(start)
        context.ends.append(end)
        if comment:
            pieces.extend((content[copied:start], _blank(content[start:end])))
            copied = end
        cursor = end
    if pieces:
        pieces.append(content[copied:])
        context.text = "".join(pieces)
    return context


class LineMap:
    """Ленивый индекс строк: строится только для файлов с находками/диагностикой."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.starts: list[int] | None = None

    def locate(self, offset: int) -> tuple[int, int]:
        """Вернуть строку/колонку с 1 без повторного пересчёта всего префикса."""
        if self.starts is None:
            self.starts = [0, *(match.end() for match in re.finditer("\n", self.content))]
        index = bisect_right(self.starts, offset) - 1
        return index + 1, offset - self.starts[index] + 1
