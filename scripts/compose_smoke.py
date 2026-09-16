"""Disposable, offline Compose acceptance. Never uses the developer's project volumes or .env."""

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="sourcehealth-smoke-" + uuid4().hex[:12])
    args = parser.parse_args()
    if not re.fullmatch(r"sourcehealth-smoke-[a-z0-9-]+", args.project):
        parser.error("only disposable sourcehealth-smoke-* project names are allowed")
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "POSTGRES_PORT": "0", "REDIS_PORT": "0", "BACKEND_PORT": "0"}
    with tempfile.TemporaryDirectory(prefix="sourcehealth-smoke-") as directory:
        workspace = Path(directory)
        (workspace / "empty.env").write_text("", encoding="utf-8")
        override = {"services": {name: {"build": {"context": str(root)},
                                          "environment": {"ANALYSIS_PROFILE": "platform-v1",
                                                          "CODE_RUNTIME_ENABLED": "false"}}
                                 for name in ("migrate", "backend", "worker", "scheduler")}}
        (workspace / "override.json").write_text(json.dumps(override), encoding="utf-8")
        command = ["docker", "compose", "--project-name", args.project, "--project-directory", directory,
                   "--env-file", str(workspace / "empty.env"), "-f", str(root / "compose.yaml"),
                   "-f", str(workspace / "override.json")]

        def compose(*arguments, capture=False, timeout=600):
            result = subprocess.run([*command, *arguments], env=env, check=True, timeout=timeout,
                                    stdout=subprocess.PIPE if capture else None, text=True, encoding="utf-8")
            return result.stdout or ""

        try:
            compose("config", "--quiet")
            compose("up", "--build", "-d")
            deadline = time.monotonic() + 120
            while True:
                output = compose("ps", "--all", "--format", "json", capture=True, timeout=30)
                rows = json.loads(output) if output.lstrip().startswith("[") else [json.loads(s) for s in output.splitlines()]
                services = {row["Service"]: row for row in rows}
                healthy = all(services.get(name, {}).get("Health") == "healthy"
                              for name in ("backend", "postgres", "redis"))
                if healthy and services.get("worker", {}).get("State") == "running":
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("compose health/worker readiness timed out")
                time.sleep(2)
            if services.get("migrate", {}).get("ExitCode") != 0:
                raise RuntimeError("migration did not complete successfully")
            address = compose("port", "backend", "8000", capture=True, timeout=30).strip()
            with urlopen(f"http://{address}/api/v1/health", timeout=5) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ok", "service": "sourcehealth"}
            compose("exec", "-T", "worker", "python", "-c",
                    "from redis import Redis; from rq import Worker; "
                    "r=Redis.from_url('redis://redis:6379/0'); "
                    "assert any('analysis' in w.queue_names() for w in Worker.all(connection=r))", timeout=30)
            print("Compose smoke passed: migration, PostgreSQL/Redis/backend health, HTTP 200, registered worker.")
        except Exception:
            compose("logs", "--tail", "50", "backend", "worker", "migrate", timeout=30)
            raise
        finally:
            compose("down", "-v", "--remove-orphans", timeout=120)


if __name__ == "__main__":
    main()
