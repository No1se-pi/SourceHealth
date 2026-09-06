"""Воспроизводимый локальный benchmark; создание файлов не входит в замер.

    python -m sourcehealth.SAST.benchmark --files 1000 --repeat 3

Профили: clean (обычный код без опасных вызовов), python (нужен AST, но аргументы
безопасны), secrets (искусственные credentials), adversarial (длинные строки
с похожими на секреты именами). Это синтетика, не обещание скорости на всех repo.
"""

import argparse
import json
import platform
import statistics
import tempfile
import os
from pathlib import Path

from . import DEFAULT_RULES, SASTScanner, ScanConfig
from .__main__ import write_report

MIB = 1_048_576


def generate_polyglot(root: Path, mib: int = 500, file_kib: int = 1024,
                      hot: bool = False) -> set[tuple[str, str]]:
    """Создать точный объём разных исходников и вернуть координаты пяти контролей.

    Каталог должен быть пустым: генератор не перезаписывает чужие данные. Файлы
    различаются номером модуля и функций; кеширование одинаковых файлов не даёт
    выигрыша. Контроли находятся в конце файлов, включая первый и последний.
    hot добавляет частые безопасные вызовы интересующих API, нагружая лексер.
    Это текстовые фикстуры, их сборка/исполнение не требуется и не производится.
    """
    if not 4 <= mib <= 2048 or file_kib not in (64, 256, 1024):
        raise ValueError('mib must be 4..2048; file-kib must be 64, 256 or 1024')
    count = mib * 1024 // file_kib
    if count % 4:
        raise ValueError('The file count must be a multiple of four')
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError('Benchmark directory must exist and be empty')
    rust_index = (count // 2 // 4) * 4 + 1
    java_index = rust_index + 1
    controls = {
        0: ('GO-TLS-NO-VERIFY', 'var risky = tls.Config{InsecureSkipVerify: true}\n'),
        rust_index: ('RUST-TLS-NO-VERIFY', 'fn risky() { client.danger_accept_invalid_certs(true); }\n'),
        java_index: ('JAVA-WEAK-HASH', 'void risky() { MessageDigest.getInstance("MD5"); }\n'),
        count - 1: ('CPP-STRCPY', 'void risky(char* d, char* s) { strcpy(d, s); }\n'),
    }
    suffixes = ('.go', '.rs', '.java', '.cpp')
    expected = set()
    for index in range(count):
        kind = index % 4
        suffix = suffixes[kind]
        filename = f'unit_{index:05}{suffix}'
        header = (f'// Synthetic benchmark module {index}\n' + (
            'package sample\nimport "fmt"\nimport "crypto/tls"\n',
            '',
            f'import java.security.MessageDigest;\nclass Unit{index} {{\n',
            '#include <cstdio>\n#include <cstring>\n',
        )[kind]).encode('ascii')
        footer = ''
        if index in controls:
            rule_id, footer = controls[index]
            expected.add((rule_id, filename))
        if index == count - 1:
            footer += 'const char* token = "ghp_' + 'Ab3D' * 9 + '";\n'
            expected.add(('SECRET-GITHUB-TOKEN', filename))
        if kind == 2:
            footer += '}\n'
        tail = footer.encode('ascii')
        remaining = file_kib * 1024 - len(header) - len(tail)
        rows = [header]
        number = 0
        while True:
            # Имена уникальны в модуле; обычный профиль содержит много кода,
            # а не длинный повтор комментария или набор бинарных заглушек.
            templates = (
                'func f_{n}(v string) string {{ return fmt.Sprintf("%s", v) }}\n',
                'fn f_{n}(v: &str) -> String {{ format!("{{}}", v) }}\n',
                'static String f_{n}(String v) {{ return v.trim(); }}\n',
                'int f_{n}(const char* s) {{ char b[128]; return snprintf(b, sizeof(b), "%s", s); }}\n',
            ) if not hot else (
                'var cfg_{n} = tls.Config{{InsecureSkipVerify: false}}\n',
                'fn f_{n}() {{ client.danger_accept_invalid_certs(false); }}\n',
                'void f_{n}() {{ MessageDigest.getInstance("SHA-256"); }}\n',
                'void f_{n}(const char* s) {{ printf("%s", s); }}\n',
            )
            row = templates[kind].format(n=number).encode('ascii')
            if len(row) > remaining:
                break
            rows.append(row)
            remaining -= len(row)
            number += 1
        rows.extend((b'\n' * remaining, tail))
        (root / filename).write_bytes(b''.join(rows))
    return expected


def benchmark_polyglot(mib: int = 500, repeat: int = 3, file_kib: int = 1024,
                       hot: bool = False, directory: Path | None = None) -> dict:
    """Проверить не только время, но и полный объём, число файлов и все контроли.

    Без directory временная папка удаляется после замера. Явно указанная пустая
    папка сохраняется для A/B сравнения другим исполняемым файлом. Создание дерева,
    импорт правил, Git и загрузка репозитория в scan_seconds не входят.
    """
    if not 1 <= repeat <= 10:
        raise ValueError('repeat must be 1..10')

    def run(root):
        expected = generate_polyglot(root, mib, file_kib, hot)
        files = mib * 1024 // file_kib
        scanner = SASTScanner(ScanConfig(max_total_bytes=mib * MIB + 1,
                                        max_files=files + 1, timeout_seconds=120))
        runs = []
        for _ in range(repeat):
            result = scanner.scan(root)
            actual = {(f.rule_id, f.path) for f in result.findings}
            runs.append({
                'seconds': result.duration_seconds, 'files': result.files_scanned,
                'bytes': result.bytes_read, 'findings': len(result.findings),
                'complete': result.complete, 'skipped': result.skipped,
                'code_files_lexed': result.code_files_lexed,
                'controls_found': len(actual & expected),
                'verified': (result.complete and result.bytes_read == mib * MIB
                             and result.files_scanned == files and actual == expected
                             and len(result.findings) == len(expected)),
            })
        median = statistics.median(item['seconds'] for item in runs)
        return {
            'python': platform.python_version(), 'platform': platform.system(),
            'logical_cpus': os.cpu_count(), 'scan_workers': 1,
            'profile': 'polyglot-hot' if hot else 'polyglot',
            'rule_count': len(DEFAULT_RULES), 'expected_bytes': mib * MIB,
            'expected_files': files, 'expected_controls': sorted(expected),
            'runs': runs, 'median_seconds': round(median, 6),
            'median_mib_per_second': round(mib / median, 3) if median else None,
            'cache_note': 'No result cache; OS filesystem cache is not cleared.',
        }

    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        return run(directory)
    with tempfile.TemporaryDirectory(prefix='sourcehealth-polyglot-') as directory_name:
        return run(Path(directory_name))


def benchmark(files: int = 1000, repeat: int = 3, profile: str = "clean") -> dict:
    """Создать ограниченное временное дерево и измерить только scanner.scan()."""
    if not 1 <= files <= 10_000 or not 1 <= repeat <= 10:
        raise ValueError("files must be 1..10000 and repeat must be 1..10")
    profiles = {
        "clean": ('API_KEY = os.getenv("API_KEY")\ndef add(a, b):\n    return a + b\n') * 150,
        "python": ('import subprocess\nsubprocess.run(["echo", data], shell=False)\n') * 100,
        "secrets": 'TOKEN="ghp_' + 'Ab3D' * 9 + '"\n',
        "adversarial": ('# API_KEY=' + 'a' * 8000 + '\n') * 2,
    }
    if profile not in profiles:
        raise ValueError("Unknown benchmark profile")
    results = []
    with tempfile.TemporaryDirectory(prefix="sourcehealth-benchmark-") as directory:
        root = Path(directory)
        for index in range(files):
            (root / f"module_{index}.py").write_text(profiles[profile], encoding="utf-8")
        # Лимиты benchmark явно расширены под заявленное число фикстур.
        # Не переносите эти настройки автоматически в публичный worker.
        config = ScanConfig(max_files=files + 1, max_findings=files + 1,
                            max_total_bytes=200 * 1_048_576, timeout_seconds=120)
        scanner = SASTScanner(config)
        for _ in range(repeat):
            result = scanner.scan(root)
            results.append({
                "seconds": result.duration_seconds, "files": result.files_scanned,
                "bytes": result.bytes_read, "findings": len(result.findings),
                "python_files_parsed": result.python_files_parsed,
                "complete": result.complete, "skipped": result.skipped,
            })
    median = statistics.median(run["seconds"] for run in results)
    return {
        "python": platform.python_version(), "platform": platform.system(),
        "profile": profile, "rule_count": len(DEFAULT_RULES), "runs": results,
        "median_seconds": round(median, 6),
        "median_mib_per_second": round(results[0]["bytes"] / 1_048_576 / median, 3) if median else None,
    }


def main() -> int:
    """Напечатать JSON замеров; вернуть 2 при неполноте хотя бы одного прогона."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=1000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--profile", choices=("clean", "python", "secrets", "adversarial", "polyglot", "polyglot-hot"), default="clean")
    parser.add_argument('--mib', type=int, default=500, help='Объём polyglot в MiB')
    parser.add_argument('--file-kib', type=int, default=1024, choices=(64, 256, 1024))
    parser.add_argument('--directory', type=Path, help='Сохранить polyglot-фикстуры в пустой папке')
    parser.add_argument('--output', type=Path, help='Сохранить JSON замера')
    args = parser.parse_args()
    try:
        if args.profile.startswith('polyglot'):
            report = benchmark_polyglot(args.mib, args.repeat, args.file_kib,
                                       args.profile == 'polyglot-hot', args.directory)
        else:
            report = benchmark(args.files, args.repeat, args.profile)
    except ValueError as error:
        parser.error(str(error))
    write_report(report, args.output)
    return 0 if all(run["complete"] and run.get('verified', True) for run in report["runs"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
