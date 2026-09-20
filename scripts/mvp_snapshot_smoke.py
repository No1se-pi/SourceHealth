"""Настоящий offline Docker scan синтетического Git snapshot; не live SourceCraft.

Сначала: docker build -f sourcehealth/sast/Dockerfile -t sourcehealth-sast .
Запуск: python scripts/mvp_snapshot_smoke.py
Создаёт только собственный unique volume; удаляет контейнеры/volume в finally.
"""

import json
import subprocess
import uuid


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout).stdout


def main():
    name = "sourcehealth-mvp-smoke-" + uuid.uuid4().hex
    volume = name + "-data"
    limits = ["--read-only", "--user", "10001:10001", "--cap-drop=ALL",
              "--security-opt=no-new-privileges", "--network=none", "--memory=512m",
              "--memory-swap=512m", "--cpus=1", "--pids-limit=128", "--log-driver=none",
              "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m"]
    # Trusted fixture setup, never commands sourced from an analyzed repository.
    seed = """
from pathlib import Path
import subprocess
p = Path('/workspace/repo')
p.mkdir()
(p / 'README.md').write_text('# Quick Start\\npython -m app\\n## Build\\ndocker build .\\n## Test\\npytest\\n')
(p / 'LICENSE').write_text('Fixture license')
(p / 'app.py').write_text('# TODO: fixture marker\\nraise RuntimeError(\"TARGET_CODE_MUST_NOT_EXECUTE\")\\n')
for command in [['init', '-q'], ['add', '.'], ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture']]:
    subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-C', str(p), *command], check=True)
"""
    created = False
    try:
        docker("volume", "create", volume)
        created = True
        docker("run", "--name", name + "-seed", *limits, "--mount",
               f"type=volume,source={volume},target=/workspace", "--entrypoint", "python",
               "sourcehealth-sast", "-I", "-c", seed)
        output = docker("run", "--name", name + "-scan", *limits, "--mount",
                        f"type=volume,source={volume},target=/workspace,readonly", "sourcehealth-sast",
                        "/workspace/repo", "--with-git", "--with-mvp", timeout=120)
        report = json.loads(output)
        assert report["complete"] is True
        assert set(report["checks"]) == {"sast", "git_activity", "documentation", "technical_debt"}
        assert report["checks"]["documentation"]["metrics"]["run_instructions"] is True
        assert report["checks"]["technical_debt"]["metrics"]["todo_count"] == 1
        assert report["checks"]["technical_debt"]["metrics"]["age_complete"] is True
        assert len(report["checks"]["documentation"]["metadata"]["head_sha"]) == 40
        print("MVP snapshot smoke passed: real offline container, Git/docs/debt/SAST, HEAD, no target execution.")
    finally:
        for suffix in ("-scan", "-seed"):
            subprocess.run(["docker", "rm", "--force", name + suffix], capture_output=True, timeout=30)
        if created:
            docker("volume", "rm", volume)


if __name__ == "__main__":
    main()
