"""Ограниченный по ресурсам обход файлов; содержимое никогда не исполняется."""

from __future__ import annotations

import io
import os
import stat
import time
import tokenize
from contextlib import closing
from dataclasses import asdict
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable, Iterator

from .models import Finding, ScanConfig, ScanResult
from .python_analysis import analyze_python
from .rules import DEFAULT_RULES, Rule, ruleset_digest
from .text_analysis import scan_text


class SASTScanError(RuntimeError):
    """Некорректный корень сканирования; ошибки отдельных файлов идут в отчёт."""


def _is_link(info: os.stat_result) -> bool:
    """Распознать symlink и Windows reparse point, включая junction."""
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


class SASTScanner:
    """Сканер рабочей копии с API ``scan(path).to_dict()``.

    Принимает обычную папку, Git не требуется. Один объект можно использовать
    повторно: счётчики и результаты принадлежат отдельному вызову scan.
    Правила — доверенный код приложения; файлы проекта — недоверенные данные.
    Для дерева, изменяемого другим процессом, используйте read-only контейнер:
    переносимые проверки путей не гарантируют защиту от всех TOCTOU-гонок.
    """

    def __init__(self, config: ScanConfig | None = None,
                 rules: Iterable[Rule] | None = None) -> None:
        """Использовать стандартные правила либо явно переданный набор."""
        self.config = config or ScanConfig()
        self.rules = tuple(DEFAULT_RULES if rules is None else rules)
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("Rule ids must be unique")
        self._digest = ruleset_digest(self.rules)

    def scan(self, repo_path: str | Path) -> ScanResult:
        """Прочитать поддерживаемые файлы и вернуть отчёт даже при частичных ошибках.

        Читается не более одного файла за раз. В отчёте нет абсолютного корня,
        текста строк, исключений ОС и значений найденных ключей.
        Таймер кооперативный: не прерывает зависший syscall или чужой regex.
        """
        started = time.monotonic()
        root = Path(repo_path).expanduser()
        try:
            if _is_link(root.lstat()) or not root.is_dir():
                raise SASTScanError("Scan root must be a real directory, not a link")
            root = root.resolve(strict=True)
        except (OSError, ValueError) as error:
            raise SASTScanError("Scan root is not accessible") from error
        result = ScanResult(rule_ids=[r.id for r in self.rules], config=asdict(self.config),
                            ruleset_digest=self._digest)
        deadline = started + self.config.timeout_seconds
        # Явно закрываем генератор и scandir-дескрипторы при выходе по лимиту,
        # не полагаясь на сборщик мусора конкретной реализации Python.
        with closing(self._files(root, result, deadline)) as paths:
            self._scan_files(paths, root, result, deadline)
        result.findings.sort(key=lambda f: (f.path, f.line, f.column, f.rule_id))
        result.files_with_findings = len({finding.path for finding in result.findings})
        result.duration_seconds = round(time.monotonic() - started, 6)
        return result

    def _scan_files(self, paths: Iterator[Path], root: Path, result: ScanResult, deadline: float) -> None:
        """Читать файлы по одному; повторно использовать набор правил расширения."""
        by_suffix: dict[str, tuple[Rule, ...]] = {}
        for path in paths:
            if result.files_scanned >= self.config.max_files:
                result.skip("file_limit", incomplete=True)
                break
            if result.bytes_read >= self.config.max_total_bytes:
                result.skip("total_bytes_limit", incomplete=True)
                break
            data = self._read(path, root, result)
            if data is None:
                continue
            relative = path.relative_to(root).as_posix()
            content = self._decode(data, path.suffix.lower(), relative, result)
            if content is None:
                continue
            result.files_scanned += 1
            suffix = path.suffix.lower()
            if suffix not in by_suffix:
                by_suffix[suffix] = tuple(r for r in self.rules if not r.suffixes or suffix in r.suffixes)
            rules = by_suffix[suffix]
            # Большинство файлов не содержит ни одного префикса vendor-токенов.
            # Исключаем такие правила до цикла по строкам, один раз на файл.
            lowered = content.lower() if any(r.engine == "regex" for r in rules) else ""
            regex_rules = tuple(sorted(
                (r for r in rules if r.engine == "regex" and
                 (not r.keywords or any(k in lowered for k in r.keywords))),
                key=lambda rule: rule.entropy_threshold is not None,
            ))
            # split('\n') сохраняет номера строк и не считает Unicode-разделители
            # физическими переводами строк в исходном файле.
            for number, line in enumerate(content.split("\n") if regex_rules else (), 1):
                if number % 64 == 1 and time.monotonic() >= deadline:
                    result.skip("timeout", incomplete=True)
                    break
                if len(line) > self.config.max_line_chars:
                    result.skip("long_line", incomplete=True)
                    result.diagnose("long_line", relative, number)
                    continue
                lower = line.lower()
                secret_spans: list[tuple[int, int]] = []
                for rule in regex_rules:
                    if rule.keywords and not any(k in lower for k in rule.keywords):
                        continue
                    for match in rule.regex.finditer(line):
                        if not rule.accepts(match):
                            continue
                        start, end = match.span("secret") if rule.entropy_threshold is not None else match.span()
                        if rule.entropy_threshold is not None and any(
                            start < other_end and end > other_start
                            for other_start, other_end in secret_spans
                        ):
                            continue
                        if rule.id.startswith("SECRET-"):
                            secret_spans.append((start, end))
                        result.findings.append(self._finding(rule, relative, number, start + 1))
                        if len(result.findings) >= self.config.max_findings:
                            result.skip("finding_limit", incomplete=True)
                            break
                    if not result.complete and "finding_limit" in result.skipped:
                        break
                if "finding_limit" in result.skipped:
                    break
            if "timeout" in result.skipped or "finding_limit" in result.skipped:
                break
            scan_text(content, relative, rules, self.config, result, deadline, self._finding)
            if "timeout" in result.skipped or "finding_limit" in result.skipped:
                break
            python_rules = tuple(r for r in rules if r.engine == "python_call")
            if python_rules:
                analyzed = analyze_python(content, python_rules, max_nodes=self.config.max_ast_nodes,
                                          deadline=deadline, max_findings=self.config.max_findings - len(result.findings))
                result.python_files_parsed += int(analyzed.parsed)
                result.findings.extend(self._finding(rule, relative, line, column)
                                       for rule, line, column in analyzed.hits)
                if analyzed.reason:
                    result.skip(analyzed.reason, incomplete=True)
                    result.diagnose(analyzed.reason, relative, analyzed.line)
                if analyzed.reason in ("timeout", "finding_limit"):
                    break

    @staticmethod
    def _finding(rule: Rule, path: str, line: int, column: int) -> Finding:
        """Скопировать только доверенные метаданные; source/value не передаются."""
        return Finding(rule.id, rule.severity, path, line, column, rule.message, rule.recommendation,
                       rule.category, rule.confidence, rule.cwe, rule.engine)

    @staticmethod
    def _decode(data: bytes, suffix: str, relative: str, result: ScanResult) -> str | None:
        """Распознать BOM UTF-8/16/32 и PEP 263 Python без угадывания кодировки.

        BOM проверяется до NUL: иначе UTF-16 ошибочно выглядел бы бинарным.
        Переводы CRLF/CR нормализуются, чтобы regex и AST давали одинаковые строки.
        Необъявленная legacy-кодировка помечается как неполное покрытие.
        """
        try:
            if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
                content = data.decode("utf-32")
            elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
                content = data.decode("utf-16")
            elif b"\x00" in data:
                result.skip("binary")
                return None
            elif suffix in (".py", ".pyw"):
                encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
                content = data.decode(encoding)
            else:
                content = data.decode("utf-8-sig")
            if "\x00" in content:
                result.skip("binary")
                return None
            return content.replace("\r\n", "\n").replace("\r", "\n")
        except (UnicodeError, LookupError, SyntaxError):
            result.skip("encoding", incomplete=True)
            result.diagnose("encoding", relative)
            return None

    def _files(self, root: Path, result: ScanResult, deadline: float) -> Iterator[Path]:
        """Обойти дерево через scandir без материализации всего списка файлов.

        Стек открытых итераторов ограничен max_depth; finally закрывает их
        также при раннем выходе сканера. Порядок обхода определяется ОС.
        """
        stack = []
        try:
            stack.append(os.scandir(root))
            while stack:
                if time.monotonic() >= deadline:
                    result.skip("timeout", incomplete=True)
                    return
                try:
                    entry = next(stack[-1])
                except StopIteration:
                    stack.pop().close()
                    continue
                except OSError:
                    result.skip("read_error", incomplete=True)
                    stack.pop().close()
                    continue
                if result.entries_seen >= self.config.max_entries:
                    result.skip("entry_limit", incomplete=True)
                    return
                result.entries_seen += 1
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if any(fnmatchcase(relative, pattern) for pattern in self.config.exclude_globs):
                    result.skip("excluded")
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                    if _is_link(info):
                        result.skip("link")
                    elif stat.S_ISDIR(info.st_mode):
                        if entry.name in self.config.exclude_dirs:
                            result.skip("excluded")
                        elif len(stack) >= self.config.max_depth:
                            result.skip("depth_limit", incomplete=True)
                            result.diagnose("depth_limit", relative)
                        else:
                            stack.append(os.scandir(path))
                    elif stat.S_ISREG(info.st_mode):
                        yield path
                    else:
                        result.skip("special_file")
                except OSError:
                    result.skip("read_error", incomplete=True)
                    result.diagnose("read_error", relative)
        except OSError:
            result.skip("read_error", incomplete=True)
        finally:
            for iterator in stack:
                iterator.close()

    def _read(self, path: Path, root: Path, result: ScanResult) -> bytes | None:
        """Ограничить чтение, отклонить ссылки, hardlink и специальные файлы.

        O_NOFOLLOW/O_NONBLOCK доступны на Unix; Windows использует lstat и
        reparse-проверку. fstat проверяет уже открытый дескриптор. Это защита
        статического дерева, но не полноценная песочница для меняющихся путей.
        """
        try:
            info = path.lstat()
            if _is_link(info) or not path.resolve().is_relative_to(root):
                result.skip("link")
                return None
            if not stat.S_ISREG(info.st_mode):
                result.skip("special_file")
                return None
            if info.st_nlink > 1:
                result.skip("hardlink")
                return None
            budget = min(self.config.max_file_bytes,
                         self.config.max_total_bytes - result.bytes_read)
            if info.st_size > budget:
                reason = "file_size_limit" if info.st_size > self.config.max_file_bytes else "total_bytes_limit"
                result.skip(reason, incomplete=True)
                result.diagnose(reason, path.relative_to(root).as_posix())
                return None
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            with os.fdopen(os.open(path, flags), "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink > 1:
                    result.skip("special_file")
                    return None
                data = stream.read(budget + 1)
            result.bytes_read += len(data)
            if len(data) > budget:
                result.skip("file_changed_or_limit", incomplete=True)
                return None
            return data
        except (OSError, ValueError):
            result.skip("read_error", incomplete=True)
            result.diagnose("read_error", path.relative_to(root).as_posix())
            return None
