"""Одноразовый Docker workflow для публичного репозитория SourceCraft.

    python -m sourcehealth.sast.container https://sourcecraft.dev/owner/repo \
        --output reports/health.json

Оркестратор запускается на хосте. Сначала контейнер Git скачивает репозиторий
в новый volume, затем отдельный контейнер без сети выполняет SAST и Git-анализ.
После получения результата контейнеры и volume удаляются в finally.
Docker socket, домашняя папка и credentials внутрь контейнеров не передаются.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

from sourcehealth.core.domain import sourcecraft_clone_url

from .__main__ import write_report


class ContainerError(RuntimeError):
    """Короткий код ошибки без вывода Git и без содержимого репозитория."""


def _docker(arguments: list[str], *, timeout: float = 30) -> str:
    """Запустить Docker без shell; скрыть потенциально недоверенный stderr."""
    try:
        completed = subprocess.run(
            ["docker", *arguments], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ContainerError("container_timeout") from error
    except OSError as error:
        raise ContainerError("docker_unavailable") from error
    if completed.returncode:
        raise ContainerError("docker_command_failed")
    return completed.stdout


def run_repository(url: str, *, image: str = "sourcehealth-sast", timeout: float = 180) -> dict:
    """Выполнить две стадии и вернуть общий отчёт, включая ошибки очистки.

    ``timeout`` ограничивает каждую стадию отдельно. Жёсткий лимит памяти/CPU
    распространяется и на существующий GitCollector. Volume не имеет дисковой
    квоты: для публичного сервиса нужны квоты worker-диска и очередь заданий.
    ``image`` должен быть доверенным образом оператора, не параметром веб-запроса.
    """
    import math

    clone_url = sourcecraft_clone_url(url)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    job = "sourcehealth-" + uuid.uuid4().hex
    volume = job + "-data"
    containers: list[str] = []
    volume_created = False
    stage = "prepare"
    report: dict = {"schema_version": "1.0", "complete": False, "checks": {}}
    # Общие ограничения обоих контейнеров. Default seccomp остаётся включённым.
    limits = [
        "--read-only", "--user", "10001:10001", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--memory=512m", "--memory-swap=512m",
        "--cpus=1", "--pids-limit=128", "--log-driver=none",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
    ]
    try:
        _docker(["image", "inspect", image])
        _docker(["volume", "create", volume])
        volume_created = True
        stage = "clone"
        clone_name = job + "-clone"
        _docker([
            "create", "--name", clone_name, *limits,
            "--mount", f"type=volume,source={volume},target=/workspace",
            "--entrypoint", "git", image,
            "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=",
            "-c", "http.followRedirects=false", "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always", "-c", "submodule.recurse=false",
            "clone", "--quiet", "--single-branch", "--no-tags", "--no-hardlinks",
            "--", clone_url, "/workspace/repo",
        ])
        containers.append(clone_name)
        _docker(["start", "--attach", clone_name], timeout=timeout)
        stage = "analyze"
        scan_name = job + "-scan"
        _docker([
            "create", "--name", scan_name, *limits, "--network=none",
            "--mount", f"type=volume,source={volume},target=/workspace,readonly",
            image, "/workspace/repo", "--with-git",
        ])
        containers.append(scan_name)
        # CLI=2 всё равно содержит полезный JSON неполной проверки.
        # Поэтому читаем stdout отдельно от кода завершения контейнера.
        try:
            completed = subprocess.run(
                ["docker", "start", "--attach", scan_name], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ContainerError("container_timeout") from error
        except OSError as error:
            raise ContainerError("docker_unavailable") from error
        try:
            candidate = json.loads(completed.stdout)
        except (ValueError, TypeError) as error:
            raise ContainerError("invalid_or_missing_report") from error
        if (not isinstance(candidate, dict) or candidate.get("schema_version") != "1.0"
                or not isinstance(candidate.get("checks"), dict)
                or type(candidate.get("complete")) is not bool
                or completed.returncode not in (0, 2)):
            raise ContainerError("invalid_report")
        sast = candidate["checks"].get("sast")
        if (not isinstance(sast, dict) or type(sast.get("complete")) is not bool
                or not isinstance(sast.get("findings"), list)
                or (candidate["complete"] and (not sast["complete"] or completed.returncode != 0))):
            raise ContainerError("inconsistent_report")
        report = candidate
    except ContainerError as error:
        report["error"] = {"stage": stage, "code": str(error)}
        report["complete"] = False
    finally:
        failed_cleanup: list[str] = []
        for name in reversed(containers):
            try:
                _docker(["rm", "--force", name])
            except ContainerError:
                failed_cleanup.append(name)
        if volume_created:
            try:
                _docker(["volume", "rm", volume])
            except ContainerError:
                failed_cleanup.append(volume)
        if failed_cleanup:
            report["cleanup_pending"] = failed_cleanup
            report["complete"] = False
    report["repository"] = {"url": clone_url, "history_scope": "default_branch_full"}
    return report


def main(argv: list[str] | None = None) -> int:
    """Записать JSON на хосте после очистки временных ресурсов."""
    parser = argparse.ArgumentParser(description="SourceCraft → Docker → Git + SAST → JSON")
    parser.add_argument("url", help="HTTPS-ссылка открытого репозитория SourceCraft")
    parser.add_argument("--output", type=Path, required=True, help="Результат на хосте")
    parser.add_argument("--image", default="sourcehealth-sast", help="Доверенный заранее собранный образ")
    parser.add_argument("--timeout", type=float, default=180, help="Таймаут каждой стадии, секунды")
    args = parser.parse_args(argv)
    try:
        report = run_repository(args.url, image=args.image, timeout=args.timeout)
        write_report(report, args.output)
    except (ValueError, OSError):
        print("Неверные параметры SourceCraft/Docker или недоступен файл отчёта.", file=sys.stderr)
        return 2
    if not report["complete"]:
        print("Проверка не завершена полностью; подробности в JSON-отчёте.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
