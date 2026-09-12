"""Доверенные regex/AST-правила: новая проверка не меняет обход файлов.

Regex компилируется один раз при создании Rule. Правила не загружаются из
проверяемого проекта: пользовательский regex способен вызвать ReDoS.
Встроенные text_regex/code_regex обрабатывают ограниченный файл; слишком длинные
строки маскируются. Старый engine=regex сохраняет построчную семантику.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Pattern


def shannon_entropy(value: str) -> float:
    """Вернуть H = -sum(p * log2(p)) в битах на символ; H('') = 0.

    Энтропия измеряет разнообразие символов, а не действительность ключа.
    Поэтому она применяется только к присваиваниям с именем вроде api_key.
    """
    if not value:
        return 0.0
    size = len(value)
    return -sum((count / size) * math.log2(count / size)
                for count in Counter(value).values())


@dataclass(frozen=True)
class Rule:
    """Regex или AST-правило, заданное автором SourceHealth.

    ``keywords`` — необязательный быстрый фильтр (любое слово, без регистра).
    ``suffixes`` ограничивает расширения; пустой tuple означает любой текст.
    ``entropy_threshold`` требует именованную regex-группу ``secret``.
    ``engine=python_call`` использует ``calls/check/argument/value`` вместо regex.
    ``code_regex`` требует language и соответствующие suffixes; комментарии
    маскируются, начало совпадения проверяется на принадлежность к коду.
    ``prefilter`` для файловых движков должен допускать все совпадения pattern.
    ``category/confidence/cwe/references`` объясняют находку в отчёте/каталоге.
    Не помещайте в message/recommendation совпавший текст.
    """

    id: str
    pattern: str
    message: str
    recommendation: str
    severity: str = "medium"
    keywords: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = ()
    entropy_threshold: float | None = None
    category: str = "security"
    confidence: str = "medium"
    cwe: str | None = None
    references: tuple[str, ...] = ()
    engine: str = "regex"
    calls: tuple[str, ...] = ()
    check: str = "any"
    argument: str | int | None = None
    value: str | int | bool | None = None
    language: str | None = None
    prefilter: str | None = None
    regex: Pattern[str] | None = field(init=False, repr=False, compare=False)
    prefilter_regex: Pattern[str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Проверить метаданные и скомпилировать доверенное выражение."""
        if not isinstance(self.id, str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]{1,63}", self.id):
            raise ValueError("Invalid rule id")
        if self.severity not in ("high", "medium", "low"):
            raise ValueError("Invalid severity")
        for value in (self.message, self.recommendation):
            if not isinstance(value, str) or not value:
                raise ValueError("message and recommendation must be nonempty strings")
        if self.engine not in ("regex", "text_regex", "code_regex", "python_call"):
            raise ValueError("Unknown rule engine")
        if self.confidence not in ("high", "medium", "low"):
            raise ValueError("Invalid confidence")
        if self.category not in ("security", "secret", "injection", "deserialization", "crypto", "configuration", "memory"):
            raise ValueError("Invalid category")
        if self.cwe is not None and (not isinstance(self.cwe, str) or not re.fullmatch(r"CWE-[1-9][0-9]*", self.cwe)):
            raise ValueError("Invalid CWE")
        for name in ("keywords", "suffixes", "references", "calls"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"{name} must contain nonempty strings")
            object.__setattr__(self, name, tuple(v.lower() if name in ("keywords", "suffixes") else v for v in values))
        if any(not url.startswith("https://") for url in self.references):
            raise ValueError("References must be HTTPS URLs")
        if self.check not in ("any", "equals", "dynamic", "unsafe_yaml", "weak_hash", "formatted_sql", "jwt_verification"):
            raise ValueError("Unknown Python call check")
        if self.argument is not None and not (
            (type(self.argument) is int and self.argument >= 0)
            or (isinstance(self.argument, str) and self.argument.isidentifier())
        ):
            raise ValueError("argument must be a keyword or a nonnegative position")
        if self.value is not None and type(self.value) not in (str, int, bool):
            raise ValueError("value must be a scalar")
        if self.engine == "code_regex":
            languages = {"go": {".go"}, "rust": {".rs"}, "java": {".java"},
                         "cpp": {".c", ".h", ".cc", ".hh", ".cpp", ".hpp", ".cxx", ".hxx", ".ipp", ".tpp"}}
            if (self.language not in languages or not self.suffixes
                    or not set(self.suffixes) <= languages[self.language]):
                raise ValueError("code_regex needs a supported language and matching suffixes")
        elif self.language is not None:
            raise ValueError("language is only used by code_regex")
        if self.prefilter is not None and (not isinstance(self.prefilter, str) or not self.prefilter):
            raise ValueError("prefilter must be a nonempty regex string")
        if self.prefilter is not None and self.engine not in ('text_regex', 'code_regex'):
            raise ValueError('prefilter is only used by text_regex/code_regex')
        object.__setattr__(self, "prefilter_regex", re.compile(self.prefilter, re.MULTILINE) if self.prefilter else None)
        if self.engine == "python_call":
            if not self.calls or self.entropy_threshold is not None or self.pattern:
                raise ValueError("Python rules need calls, an empty pattern and no entropy threshold")
            if self.check in ("equals", "dynamic") and self.argument is None:
                raise ValueError("This check needs an argument")
            if any(not re.fullmatch(r"(?:[A-Za-z_]\w*|\*(?=\.))(?:\.[A-Za-z_]\w*)*", name) for name in self.calls):
                raise ValueError("Invalid Python call name")
            if self.check not in ("equals", "dynamic") and (self.argument is not None or self.value is not None):
                raise ValueError("This check does not accept argument/value")
            if self.suffixes != (".py", ".pyw"):
                raise ValueError("Python call rules use suffixes [.py, .pyw]")
            compiled = None
        else:
            if not isinstance(self.pattern, str) or not self.pattern:
                raise ValueError("Regex rules need a nonempty pattern")
            if self.calls or self.check != "any" or self.argument is not None or self.value is not None:
                raise ValueError("Python selectors cannot be used with the regex engine")
            compiled = re.compile(self.pattern, re.MULTILINE if self.engine in ("text_regex", "code_regex") else 0)
        if self.entropy_threshold is not None:
            if (type(self.entropy_threshold) not in (int, float)
                    or not math.isfinite(self.entropy_threshold)
                    or self.entropy_threshold < 0 or "secret" not in compiled.groupindex):
                raise ValueError("Entropy rules need a secret group and finite threshold >= 0")
        object.__setattr__(self, "regex", compiled)

    def accepts(self, match: re.Match[str]) -> bool:
        """Отфильтровать низкую энтропию и распространённые шаблоны значений."""
        if self.entropy_threshold is None:
            return True
        value = match.group("secret")
        if not value:
            return False
        lower = value.lower()
        if any(marker in lower for marker in (
            "example", "placeholder", "changeme", "your_", "your-", "${", "{{",
        )):
            return False
        return shannon_entropy(value) >= self.entropy_threshold

    def to_dict(self) -> dict:
        """Метаданные и селекторы без скомпилированного regex; для каталога правил."""
        from dataclasses import fields

        return {item.name: getattr(self, item.name) for item in fields(self) if item.init}


def ruleset_digest(rules: tuple[Rule, ...]) -> str:
    """SHA-256 доверенных правил для сравнения версий отчётов; секреты не хешируются."""
    payload = json.dumps([rule.to_dict() for rule in rules], sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def load_rules(directory: str | Path | None = None) -> tuple[Rule, ...]:
    """Загрузить по одному правилу из каждого *.json в доверенной папке.

    По умолчанию используется rules/ рядом с этим модулем, независимо от cwd.
    Файлы читаются в алфавитном порядке; подпапки не обходятся. Неизвестные поля,
    повреждённый JSON/regex и повторяющиеся id останавливают загрузку: нельзя
    молча пропустить неработающую проверку. Загрузка происходит один раз при
    импорте, а не для каждого сканируемого файла. После правок перезапустите CLI.

    Не передавайте сюда каталог, контролируемый автором проверяемого проекта.
    JSON не выполняет Python, но содержащийся в нём regex всё ещё доверенный.
    """
    folder = Path(directory) if directory is not None else Path(__file__).with_name("rules")
    if not folder.is_dir():
        raise ValueError("Rules directory is not accessible")
    loaded: list[Rule] = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_keys)
            if not isinstance(data, dict):
                raise ValueError("Rule must be a JSON object")
            # У Python AST-правила нет regex. Сохраняем совместимость Rule(...)
            # с прежним позиционным параметром pattern, но в JSON он необязателен.
            loaded.append(Rule(**{"pattern": "", **data}))
        except (OSError, ValueError, TypeError, re.error) as error:
            raise ValueError(f"Invalid rule file: {path.name}") from error
    if not loaded:
        raise ValueError("Rules directory contains no JSON rules")
    if len({rule.id for rule in loaded}) != len(loaded):
        raise ValueError("Rule ids must be unique")
    return tuple(loaded)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    """Не позволить опечатке с повторным полем незаметно заменить значение JSON."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


# Имена файлов фиксируют порядок каталога; scanner сам ставит entropy fallback последним.
DEFAULT_RULES: tuple[Rule, ...] = load_rules()
