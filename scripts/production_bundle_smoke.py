"""Production deployment bundle static smoke validation.

Validates deploy/compose.prod.yaml, deploy/Caddyfile, and deploy/*.service.example
without touching production or requiring real credentials.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def validate_production_compose(root: Path) -> None:
    compose_file = root / "deploy" / "compose.prod.yaml"
    if not compose_file.exists():
        raise FileNotFoundError(f"Missing {compose_file}")

    test_password = "smoke_synthetic_url_safe_pass_xyz123"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env", encoding="utf-8") as tf:
        tf.write(f"POSTGRES_PASSWORD={test_password}\n")
        temp_env_path = tf.name

    try:
        cmd = [
            "docker", "compose",
            "--env-file", temp_env_path,
            "-f", str(compose_file),
            "config", "--format", "json"
        ]
        env = os.environ.copy()
        env["SOURCEHEALTH_ENV_FILE"] = temp_env_path
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"docker compose config failed (code {proc.returncode}):\n{proc.stderr}")

        config = json.loads(proc.stdout)
        services = config.get("services", {})
        expected_services = {"postgres", "redis", "migrate", "backend", "worker"}
        missing = expected_services - set(services.keys())
        if missing:
            raise AssertionError(f"Missing expected services in compose.prod.yaml: {missing}")

        if config.get("name") != "sourcehealth":
            raise AssertionError(f"Production project must remain sourcehealth, got {config.get('name')!r}")
        if "caddy" in services:
            raise AssertionError("Production compose must not start Caddy; ingress is a host service")

        volumes = config.get("volumes", {})
        expected_volumes = {
            "postgres-data": "sourcehealth_postgres-data",
            "redis-data": "sourcehealth_redis-data",
        }
        for key, expected_name in expected_volumes.items():
            volume = volumes.get(key, {})
            if volume.get("name") != expected_name or not volume.get("external"):
                raise AssertionError(f"{key} must be external volume {expected_name}: {volume}")

        # 1. Existing PostgreSQL loopback contract
        pg = services["postgres"]
        pg_ports = pg.get("ports", [])
        pg_loopback = any(p.get("target") == 5432 and p.get("published") == "15432"
                          and p.get("host_ip") == "127.0.0.1" for p in pg_ports)
        if not pg_loopback:
            raise AssertionError(f"Postgres must preserve 127.0.0.1:15432, got {pg_ports}")

        # 2. Redis loopback bind
        redis = services["redis"]
        redis_ports = redis.get("ports", [])
        redis_loopback = any(p.get("target") == 6379 and p.get("host_ip") == "127.0.0.1" for p in redis_ports)
        if not redis_loopback:
            raise AssertionError(f"Redis must bind only to 127.0.0.1:6379, got {redis_ports}")

        backend_ports = services["backend"].get("ports", [])
        backend_loopback = any(p.get("target") == 8000 and p.get("published") == "8000"
                               and p.get("host_ip") == "127.0.0.1" for p in backend_ports)
        if not backend_loopback:
            raise AssertionError(f"Backend must preserve host Caddy upstream 127.0.0.1:8000: {backend_ports}")

        # 3. Internal hostnames & password propagation in app services
        for name in ("migrate", "backend", "worker"):
            svc = services[name]
            svc_env = svc.get("environment", {})
            db_url = svc_env.get("DATABASE_URL", "")
            if test_password not in db_url or "@postgres:5432/" not in db_url:
                raise AssertionError(f"Service {name} DATABASE_URL invalid or password not resolved: {db_url}")
            redis_url = svc_env.get("REDIS_URL", "")
            if "@redis:6379/" not in redis_url and "redis://redis:6379" not in redis_url:
                raise AssertionError(f"Service {name} REDIS_URL invalid: {redis_url}")

        # 4. Docker socket invariant across ALL services
        for name, svc in services.items():
            volumes = svc.get("volumes", [])
            for vol in volumes:
                src = str(vol.get("source", ""))
                tgt = str(vol.get("target", ""))
                if "docker.sock" in src or "docker.sock" in tgt:
                    raise AssertionError(f"Service {name} illegally mounts docker.sock: {vol}")

        print("  [PASS] deploy/compose.prod.yaml: existing project/volumes, host ingress, loopback binds, no docker.sock")
    finally:
        if os.path.exists(temp_env_path):
            os.unlink(temp_env_path)


def validate_systemd_units(root: Path) -> None:
    deploy_dir = root / "deploy"
    services = [
        deploy_dir / "sourcehealth-scheduler.service.example",
        deploy_dir / "sourcehealth-worker-code.service.example",
    ]
    for svc_path in services:
        if not svc_path.exists():
            raise FileNotFoundError(f"Missing {svc_path}")
        content = svc_path.read_text(encoding="utf-8")
        if "DATABASE_URL" in content:
            raise AssertionError(f"{svc_path.name} must not contain DATABASE_URL in Environment=")
        if "<password>" in content or "<url-encoded-password>" in content:
            raise AssertionError(f"{svc_path.name} contains password placeholder")
        if "/etc/sourcehealth/sourcehealth.env" not in content:
            raise AssertionError(f"{svc_path.name} must use /etc/sourcehealth/sourcehealth.env")

    timer_path = deploy_dir / "sourcehealth-scheduler.timer.example"
    if not timer_path.exists():
        raise FileNotFoundError(f"Missing {timer_path}")
    timer_content = timer_path.read_text(encoding="utf-8")
    if "OnUnitActiveSec=60s" not in timer_content:
        raise AssertionError("sourcehealth-scheduler.timer.example must preserve the production 60s interval")

    print("  [PASS] deploy/*.service.example & timer: existing env path and host-level process contract")


def validate_caddyfile(root: Path) -> None:
    caddyfile = root / "deploy" / "Caddyfile"
    if not caddyfile.exists():
        raise FileNotFoundError(f"Missing {caddyfile}")
    content = caddyfile.read_text(encoding="utf-8")

    # API and SPA separation check
    api_match = re.search(r"handle\s+/api/\*\s*\{[^}]*reverse_proxy\s+127\.0\.0\.1:8000[^}]*\}", content)
    if not api_match:
        raise AssertionError("Caddyfile missing host upstream 'handle /api/* { reverse_proxy 127.0.0.1:8000 }'")

    spa_match = re.search(r"handle\s*\{[^}]*root\s+\*\s+/opt/sourcehealth/frontend/dist[^}]*try_files\s+\{path\}\s+/index\.html[^}]*\}", content)
    if not spa_match:
        raise AssertionError("Caddyfile missing host frontend root /opt/sourcehealth/frontend/dist")

    if "redir https://sourcehealth.tech{uri} permanent" not in content:
        raise AssertionError("Caddyfile missing HTTP to HTTPS redirect")

    # If caddy executable available, validate syntax
    caddy_bin = shutil.which("caddy")
    if caddy_bin:
        proc = subprocess.run([caddy_bin, "validate", "--config", str(caddyfile)], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"caddy validate failed:\n{proc.stderr}")
        print("  [PASS] deploy/Caddyfile: mutual-exclusive handle routing + caddy validate passed")
    else:
        print("  [PASS] deploy/Caddyfile: mutual-exclusive handle routing syntax verified (caddy binary not in PATH)")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print("=== Running Production Bundle Smoke Validation ===")
    validate_production_compose(root)
    validate_systemd_units(root)
    validate_caddyfile(root)
    print("=== All Production Bundle Smoke Checks PASSED ===")


if __name__ == "__main__":
    main()
