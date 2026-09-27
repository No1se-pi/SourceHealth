"""Reproducible benchmark harness for SourceHealth queue and multi-worker concurrency.

Measures:
- queued -> started latency
- total run duration
- queue drain time
- completed / failed job counts
- maximum simultaneous active jobs
- per-stage timings

Scenarios:
A: 1 worker-code, 2 different repositories
B: 1 worker-code, 4 different repositories
C: 2 worker-code processes, 2 different repositories
D: 2 worker-code processes, 4 different repositories
"""

import argparse
import json
import os
import platform
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import delete, func, select, update

from sourcehealth.application.jobs import dispatch_pending
from sourcehealth.application.services import AnalysisService
from sourcehealth.core.domain import DataAvailability, RepositoryRef
from sourcehealth.integrations.sourcecraft.collectors import CollectedFacts
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database
from sourcehealth.storage.models import AnalysisRun, Repository


def get_environment_info() -> dict[str, Any]:
    return {
        "os": os.name,
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "cpu_count": os.cpu_count() or 1,
        "timestamp": datetime.now(UTC).isoformat(),
    }


class BenchmarkRunner:
    def __init__(self, database_url: str, redis_url: str, *, simulated_stage_ms: float = 50.0):
        self.database_url = database_url
        self.redis_url = redis_url
        self.simulated_stage_ms = simulated_stage_ms
        os.environ["DATABASE_URL"] = database_url
        os.environ["REDIS_URL"] = redis_url
        os.environ["ANALYSIS_PROFILE"] = "mvp-v1"
        os.environ["CODE_RUNTIME_ENABLED"] = "true"
        self.engine, self.sessions = create_database(database_url)
        self.redis = Redis.from_url(redis_url)
        self.redis.ping()
        self.settings = Settings(
            _env_file=None,
            database_url=database_url,
            redis_url=redis_url,
            analysis_profile="mvp-v1",
            code_runtime_enabled=True,
            session_secret="x" * 48,
        )
        self.service = AnalysisService(self.sessions, self.settings)

    def close(self):
        self.redis.close()
        self.engine.dispose()

    def _cleanup_test_data(self, repo_ids: list[UUID]):
        if not repo_ids:
            return
        with self.sessions.begin() as db:
            db.execute(update(Repository).where(Repository.id.in_(repo_ids)).values(latest_analysis_id=None))
            db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id.in_(repo_ids)))
            db.execute(delete(Repository).where(Repository.id.in_(repo_ids)))

    def _setup_mock_collectors(self):
        """Mock external network collectors with deterministic controlled latency."""
        from unittest.mock import patch

        delay = self.simulated_stage_ms / 1000.0

        def mock_timed(stage, collect, timings):
            time.sleep(delay)
            timings[f"{stage}_ms"] = int(delay * 1000)
            return CollectedFacts(
                source="sourcecraft_api",
                availability=DataAvailability.AVAILABLE,
                collected_at=datetime.now(UTC).isoformat(),
                facts={"id": 1, "visibility": "public", "likes": 5, "items": [], "complete": True},
            )

        def mock_runtime(*args, **kwargs):
            class FastRuntime:
                def analyze(self, repo):
                    time.sleep(delay)
                    return {
                        "schema_version": "1.0",
                        "complete": True,
                        "checks": {
                            "sast": {"complete": True, "findings": [], "files_scanned": 5},
                            "git_activity": {"complete": True, "metrics": {"last_commit_date": datetime.now(UTC).isoformat()}},
                            "documentation": {"complete": True, "metadata": {"head_sha": "a" * 40, "ci_configured": True},
                                              "metrics": {"has_readme": True, "has_license": True, "has_contributing": True,
                                                          "readme_bytes": 500, "readme_headings": 4}},
                            "technical_debt": {"complete": True, "metadata": {"head_sha": "a" * 40},
                                               "metrics": {"code_files": 10, "todo_count": 0, "fixme_count": 0, "files_with_debt": 0,
                                                           "marker_density": 0, "large_files": 0, "oldest_marker_age_days": None, "age_complete": True}},
                            "repository_insights": {"complete": True, "metadata": {"head_sha": "a" * 40}, "metrics": {"sampled_commits": 20}},
                        },
                        "repository": {"head_sha": "a" * 40},
                    }
            return FastRuntime()

        p1 = patch("sourcehealth.application.jobs._timed_collection", side_effect=mock_timed)
        p2 = patch("sourcehealth.application.jobs.configured_runtime", side_effect=mock_runtime)
        return p1, p2

    def run_scenario(self, scenario_name: str, worker_count: int, repo_count: int, timeout_sec: float = 30.0) -> dict[str, Any]:
        with self.sessions.begin() as db:
            db.execute(delete(AnalysisRun).where(AnalysisRun.status == "queued"))
        queue = Queue("analysis-code", connection=self.redis)
        queue.empty()

        repo_ids = []
        try:
            for i in range(repo_count):
                slug = f"bench-{scenario_name.lower()}-{uuid4().hex[:6]}-{i}"
                ref = RepositoryRef.from_url(f"https://sourcecraft.dev/benchmark/{slug}", visibility="public")
                r_id = self.service.register_repository(ref)
                repo_ids.append(r_id)

            run_ids = []
            for r_id in repo_ids:
                run = self.service.request_analysis(r_id, trigger="manual")
                run_ids.append(run.id)

            p1, p2 = self._setup_mock_collectors()
            with p1, p2:
                t_dispatch_start = time.perf_counter()
                dispatched = dispatch_pending(self.sessions, self.redis)

                workers_stop_event = threading.Event()
                active_workers_count = 0
                max_active_observed = 0
                counter_lock = threading.Lock()

                def worker_thread_target():
                    try:
                        w = SimpleWorker([queue], connection=self.redis)
                        while not workers_stop_event.is_set():
                            try:
                                dequeued = w.dequeue_job_and_maintain_ttl(0.1)
                            except Exception:
                                break
                            if dequeued:
                                job, job_queue = dequeued
                                nonlocal max_active_observed, active_workers_count
                                with counter_lock:
                                    active_workers_count += 1
                                    if active_workers_count > max_active_observed:
                                        max_active_observed = active_workers_count
                                try:
                                    w.perform_job(job, job_queue)
                                except Exception:
                                    pass
                                finally:
                                    with counter_lock:
                                        active_workers_count -= 1
                            else:
                                time.sleep(0.01)
                    except Exception:
                        pass

                threads = []
                for _ in range(worker_count):
                    t = threading.Thread(target=worker_thread_target, daemon=True)
                    t.start()
                    threads.append(t)

                # Monitor until all jobs terminal
                deadline = time.perf_counter() + timeout_sec
                all_done = False
                while time.perf_counter() < deadline:
                    with self.sessions() as db:
                        active_count = db.scalar(select(func.count()).select_from(AnalysisRun).where(
                            AnalysisRun.id.in_(run_ids),
                            AnalysisRun.status.in_(["queued", "collecting", "analyzing", "scoring"])
                        )) or 0
                    if active_count == 0:
                        all_done = True
                        break
                    time.sleep(0.05)

                drain_duration_ms = round((time.perf_counter() - t_dispatch_start) * 1000, 2)
                workers_stop_event.set()
                for t in threads:
                    t.join(timeout=3.0)

            # Collect metrics from DB
            with self.sessions() as db:
                runs = list(db.scalars(select(AnalysisRun).where(AnalysisRun.id.in_(run_ids))).all())

            terminal_ok = sum(1 for r in runs if r.status in ("completed", "partial"))
            failed = sum(1 for r in runs if r.status == "failed")
            latencies = []
            durations = []
            stage_timings_agg: dict[str, list[float]] = {}

            for r in runs:
                if r.started_at and r.queued_at:
                    lat_ms = (r.started_at - r.queued_at).total_seconds() * 1000
                    latencies.append(round(lat_ms, 2))
                if r.completed_at and r.started_at:
                    dur_ms = (r.completed_at - r.started_at).total_seconds() * 1000
                    durations.append(round(dur_ms, 2))
                if isinstance(r.metadata, dict) and "stage_timings_ms" in r.metadata:
                    for stage, ms in r.metadata["stage_timings_ms"].items():
                        stage_timings_agg.setdefault(stage, []).append(ms)

            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0

            return {
                "scenario": scenario_name,
                "workers": worker_count,
                "repositories": repo_count,
                "dispatched_count": dispatched,
                "completed": terminal_ok,
                "failed": failed,
                "queue_drain_time_ms": drain_duration_ms,
                "max_simultaneous_active": max_active_observed,
                "avg_queued_to_started_ms": avg_lat,
                "min_queued_to_started_ms": min(latencies) if latencies else 0.0,
                "max_queued_to_started_ms": max(latencies) if latencies else 0.0,
                "avg_run_duration_ms": avg_dur,
                "all_completed_cleanly": (terminal_ok == repo_count and all_done and failed == 0),
            }
        finally:
            self._cleanup_test_data(repo_ids)
            queue.empty()

    def run_all_scenarios(self) -> dict[str, Any]:
        env_info = get_environment_info()
        scenarios = [
            ("A", 1, 2),  # 1 worker, 2 repos
            ("B", 1, 4),  # 1 worker, 4 repos
            ("C", 2, 2),  # 2 workers, 2 repos
            ("D", 2, 4),  # 2 workers, 4 repos
        ]
        results = []
        for name, workers, repos in scenarios:
            res = self.run_scenario(name, workers, repos)
            results.append(res)

        # Calculate throughput comparisons
        drain_a = next(r["queue_drain_time_ms"] for r in results if r["scenario"] == "A")
        drain_c = next(r["queue_drain_time_ms"] for r in results if r["scenario"] == "C")
        drain_b = next(r["queue_drain_time_ms"] for r in results if r["scenario"] == "B")
        drain_d = next(r["queue_drain_time_ms"] for r in results if r["scenario"] == "D")

        speedup_2_repos = round(drain_a / drain_c, 2) if drain_c > 0 else 1.0
        speedup_4_repos = round(drain_b / drain_d, 2) if drain_d > 0 else 1.0

        return {
            "environment": env_info,
            "scenarios": results,
            "summary": {
                "speedup_2_repos_2_workers": f"{speedup_2_repos}x",
                "speedup_4_repos_2_workers": f"{speedup_4_repos}x",
                "drain_improvement_4_repos_pct": f"{round((1 - drain_d / drain_b) * 100, 1)}%",
            },
        }


def main():
    parser = argparse.ArgumentParser(description="SourceHealth Safe Multi-Worker Benchmark Harness")
    parser.add_argument("--database-url", default=os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql+psycopg://sourcehealth:sourcehealth@127.0.0.1:15432/sourcehealth_test")
    parser.add_argument("--redis-url", default=os.environ.get("TEST_REDIS_URL") or os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379/15")
    parser.add_argument("--json", action="store_true", help="Output raw JSON result")
    args = parser.parse_args()

    runner = BenchmarkRunner(args.database_url, args.redis_url)
    try:
        report = runner.run_all_scenarios()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("=" * 70)
            print("SOURCEHEALTH MULTI-WORKER CONCURRENCY BENCHMARK")
            print("=" * 70)
            print(f"OS: {report['environment']['platform']} | Python: {report['environment']['python_version']} | CPUs: {report['environment']['cpu_count']}")
            print("-" * 70)
            print(f"{'Scenario':<10} {'Workers':<9} {'Repos':<7} {'Drain (ms)':<12} {'Max Active':<12} {'Avg Lat (ms)':<14} {'Clean':<6}")
            print("-" * 70)
            for s in report["scenarios"]:
                print(f"{s['scenario']:<10} {s['workers']:<9} {s['repositories']:<7} {s['queue_drain_time_ms']:<12.1f} {s['max_simultaneous_active']:<12} {s['avg_queued_to_started_ms']:<14.1f} {str(s['all_completed_cleanly']):<6}")
            print("-" * 70)
            print(f"Drain improvement (4 repos, 2 workers vs 1 worker): {report['summary']['drain_improvement_4_repos_pct']} (Speedup: {report['summary']['speedup_4_repos_2_workers']})")
            print("=" * 70)
    finally:
        runner.close()


if __name__ == "__main__":
    main()
