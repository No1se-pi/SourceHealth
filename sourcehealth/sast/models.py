"""JSON-совместимые модели SAST: в них намеренно нет исходного кода и секретов."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ANALYZER_VERSION = "0.3.0"


@dataclass(frozen=True)
class ScanConfig:
    """Лимиты одного сканирования; размеры в байтах, время в секундах.

    Исключения задаёт вызывающая программа, а не проверяемый репозиторий.
    ``exclude_dirs`` сравнивается с именем каталога на любой глубине.
    ``exclude_globs`` — с относительным POSIX-путём через fnmatchcase.
    """

    max_file_bytes: int = 1_048_576
    max_total_bytes: int = 512 * 1_048_576
    max_files: int = 10_000
    max_entries: int = 100_000
    max_depth: int = 64
    max_line_chars: int = 8192
    max_findings: int = 1000
    max_ast_nodes: int = 50_000
    timeout_seconds: float = 30.0
    exclude_dirs: tuple[str, ...] = (
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
        "__pycache__", "vendor", "dist", "build",
    )
    exclude_globs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Отклонить нулевые, отрицательные и бесконечные лимиты заранее."""
        import math

        for name, value in asdict(self).items():
            if name.startswith("max_") and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        for name in ("exclude_dirs", "exclude_globs"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"{name} must contain nonempty strings")
            object.__setattr__(self, name, tuple(values))


@dataclass(frozen=True)
class Finding:
    """Одна эвристическая находка, а не доказанная уязвимость.

    Строка и колонка начинаются с 1; колонка измеряется символами Unicode.
    Путь относителен корню. Сообщения берутся только из доверенных правил.
    Отсутствие snippet/value защищает также соседние секреты в той же строке.
    """

    rule_id: str
    severity: str
    path: str
    line: int
    column: int
    message: str
    recommendation: str
    category: str = "security"
    confidence: str = "medium"
    cwe: str | None = None
    engine: str = "regex"

    def to_dict(self) -> dict[str, Any]:
        """Вернуть обычный словарь для общего отчёта SourceHealth."""
        return asdict(self)


@dataclass
class ScanResult:
    """Результат и наблюдаемое покрытие сканирования.

    ``complete`` относится к области проверки после штатных исключений.
    Лимиты, ошибки чтения/кодировки и длинные строки делают его False.
    ``skipped`` содержит счётчики причин; большие списки путей не накапливаются.
    """

    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    bytes_read: int = 0
    entries_seen: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    complete: bool = True
    duration_seconds: float = 0.0
    rule_ids: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    ruleset_digest: str = ""
    python_files_parsed: int = 0
    files_with_findings: int = 0
    code_files_lexed: int = 0
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def skip(self, reason: str, *, incomplete: bool = False) -> None:
        """Учесть пропуск, при необходимости отметить неполный анализ."""
        self.skipped[reason] = self.skipped.get(reason, 0) + 1
        if incomplete:
            self.complete = False

    def diagnose(self, reason: str, path: str, line: int | None = None) -> None:
        """Сохранить до 100 координат неполноты; исходный текст ошибок не попадает в JSON."""
        if len(self.diagnostics) < 100:
            entry: dict[str, Any] = {"reason": reason, "path": path}
            if line is not None:
                entry["line"] = line
            self.diagnostics.append(entry)

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать результат с версией схемы и сводкой по severity."""
        result = asdict(self)
        result.update(schema_version="1.0", analyzer="sast", analyzer_version=ANALYZER_VERSION)
        result["summary"] = {
            severity: sum(f.severity == severity for f in self.findings)
            for severity in ("high", "medium", "low")
        }
        return result
