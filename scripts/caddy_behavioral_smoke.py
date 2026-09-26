"""Reproducible Caddy behavioral routing smoke test.

Validates the mutual-exclusive routing architecture of deploy/Caddyfile:
1. /api/v1/health -> 200 Backend JSON
2. /some/spa/path -> 200 SPA index.html
3. /api/not-real  -> 404 Backend JSON (NOT index.html)

Completely offline and safe: uses local ephemeral ports, a mock HTTP backend,
a temporary static frontend, no production network, and clean process teardown.
"""

from __future__ import annotations

import http.server
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class MockBackendHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # Suppress request logging for clean test output

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/health":
            body = json.dumps({"status": "ok", "service": "sourcehealth"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = json.dumps({"detail": "Not Found"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_caddy_behavioral_smoke() -> None:
    caddy_bin = shutil.which("caddy")
    if not caddy_bin:
        raise RuntimeError("caddy binary not found in PATH; cannot execute behavioral test")

    backend_port = find_free_port()
    caddy_port = find_free_port()

    # 1. Start Mock Backend Server
    backend_server = http.server.HTTPServer(("127.0.0.1", backend_port), MockBackendHandler)
    backend_thread = threading.Thread(target=backend_server.serve_forever, daemon=True)
    backend_thread.start()

    with tempfile.TemporaryDirectory(prefix="caddy-behavioral-") as tmpdir:
        tmp_path = Path(tmpdir)
        frontend_dir = tmp_path / "frontend"
        frontend_dir.mkdir(parents=True, exist_ok=True)
        spa_marker = "<!-- SOURCEHEALTH_SPA_ROOT_MOCK -->"
        (frontend_dir / "index.html").write_text(
            f"<!DOCTYPE html><html><body>{spa_marker}</body></html>",
            encoding="utf-8",
        )

        # Caddy requires forward slashes even on Windows
        caddy_root = str(frontend_dir).replace("\\", "/")

        test_caddyfile = tmp_path / "Caddyfile"
        caddyfile_content = f"""{{
    admin off
}}

:{caddy_port} {{
    handle /api/* {{
        reverse_proxy 127.0.0.1:{backend_port}
    }}

    handle {{
        root * "{caddy_root}"
        try_files {{path}} /index.html
        file_server
    }}
}}
"""
        test_caddyfile.write_text(caddyfile_content, encoding="utf-8")

        # 2. Start Caddy process
        caddy_proc = subprocess.Popen(
            [caddy_bin, "run", "--config", str(test_caddyfile), "--adapter", "caddyfile"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        try:
            # Wait for Caddy to bind port
            caddy_ready = False
            base_url = f"http://127.0.0.1:{caddy_port}"
            for _ in range(50):
                time.sleep(0.1)
                try:
                    with urlopen(f"{base_url}/api/v1/health", timeout=1) as resp:
                        if resp.status == 200:
                            caddy_ready = True
                            break
                except Exception:
                    continue

            if not caddy_ready:
                stderr_output = caddy_proc.stderr.read() if caddy_proc.stderr else ""
                raise RuntimeError(f"Caddy failed to start on port {caddy_port}. Stderr:\n{stderr_output}")

            # 3. Behavioral Assertions
            print(f"Caddy running on port {caddy_port}, backend on port {backend_port}")

            # Case 1: /api/v1/health -> 200 Backend JSON
            with urlopen(f"{base_url}/api/v1/health", timeout=5) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                content_type = resp.headers.get("Content-Type", "")
                if status != 200 or "application/json" not in content_type:
                    raise AssertionError(f"/api/v1/health expected 200 application/json, got {status} {content_type}")
                data = json.loads(body)
                if data != {"status": "ok", "service": "sourcehealth"}:
                    raise AssertionError(f"/api/v1/health unexpected JSON: {data}")
                if spa_marker in body:
                    raise AssertionError("/api/v1/health illegally returned SPA index.html")
                print("  [PASS] /api/v1/health -> 200 Backend JSON (application/json)")

            # Case 2: /some/spa/path -> 200 SPA index.html
            with urlopen(f"{base_url}/some/spa/path", timeout=5) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                if status != 200:
                    raise AssertionError(f"/some/spa/path expected 200, got {status}")
                if spa_marker not in body:
                    raise AssertionError(f"/some/spa/path failed to return SPA index.html fallback, got:\n{body}")
                print("  [PASS] /some/spa/path -> 200 SPA index.html fallback")

            # Case 3: /api/not-real -> 404 Backend JSON (NOT index.html)
            req = Request(f"{base_url}/api/not-real")
            try:
                urlopen(req, timeout=5)
                raise AssertionError("/api/not-real expected 404, got 200")
            except HTTPError as err:
                if err.code != 404:
                    raise AssertionError(f"/api/not-real expected 404, got {err.code}")
                content_type = err.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    raise AssertionError(f"/api/not-real expected application/json, got {content_type}")
                body = err.read().decode("utf-8")
                if spa_marker in body:
                    raise AssertionError("/api/not-real illegally served SPA index.html instead of Backend 404!")
                data = json.loads(body)
                if data != {"detail": "Not Found"}:
                    raise AssertionError(f"/api/not-real unexpected backend response: {data}")
                print("  [PASS] /api/not-real -> 404 Backend JSON (NOT index.html)")

            print("=== All Caddy Behavioral Routing Checks PASSED ===")

        finally:
            caddy_proc.terminate()
            try:
                caddy_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                caddy_proc.kill()
            backend_server.shutdown()
            backend_server.server_close()


if __name__ == "__main__":
    run_caddy_behavioral_smoke()
