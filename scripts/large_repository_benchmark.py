"""Opt-in local benchmark: no platform facts, never live SourceCraft acceptance.

python -m scripts.large_repository_benchmark
Создаёт временные fixtures вне checkout; печатает только безопасные агрегаты.
"""

import json
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from scripts.generate_large_sourcecraft_fixture import generate
from sourcehealth.analyzers import GitActivityAnalyzerAdapter, SASTAnalyzerAdapter
from sourcehealth.analyzers.snapshot import DocumentationAnalyzer, TechnicalDebtAnalyzer
from sourcehealth.application.pipeline import analyze_context
from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import RepositoryRef
from sourcehealth.reporting import to_legacy_report
from sourcehealth.runner import AnalysisRunner, prepare_context
from sourcehealth.sast import SASTScanner
from sourcehealth.scoring.coverage import score_coverage
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import MVPPolicy
from sourcehealth.snapshot import SnapshotCollector

NOW = datetime(2026, 9, 19, tzinfo=UTC)


def measure(path):
    started = time.monotonic()
    context = replace(prepare_context(path), started_at=NOW)
    git_seconds = time.monotonic() - started
    before = time.monotonic()
    snapshot = SnapshotCollector().collect(path, NOW)
    snapshot_seconds = time.monotonic() - before
    context = replace(context, metadata={"snapshot": snapshot})
    local = AnalysisRunner([SASTAnalyzerAdapter(SASTScanner()), GitActivityAnalyzerAdapter(),
                            DocumentationAnalyzer(), TechnicalDebtAnalyzer()]).analyze_context(context)
    payload = to_legacy_report(local)

    class LocalMeasurement:
        def analyze(self, repository):
            return payload

    platform = AnalysisContext(repository=RepositoryRef.from_url(
        "https://sourcecraft.dev/fixture/large-local", visibility="public"), started_at=NOW)
    report = analyze_context(platform, include_code=True, with_mvp=True, runtime=LocalMeasurement())
    ScoringEngine(MVPPolicy()).apply(report)
    sast = payload["checks"]["sast"]
    before = time.monotonic()
    serialized = json.dumps(report.to_public_dict(), ensure_ascii=False).encode()
    serialization_seconds = time.monotonic() - before
    return {"local_only": True, "reference_time": NOW.isoformat(), "policy": MVPPolicy.version,
            "git_seconds": round(git_seconds, 4), "snapshot_seconds": round(snapshot_seconds, 4),
            "scan_seconds": sast.get("duration_seconds"),
            "serialization_seconds": round(serialization_seconds, 4), "report_bytes": len(serialized),
            "total_seconds": round(time.monotonic() - started, 4),
            "complete": local.complete, "files_scanned": sast["files_scanned"],
            "python_files_parsed": sast["python_files_parsed"],
            "code_files_lexed": sast["code_files_lexed"],
            "code_files_analyzed": sast["code_files_analyzed"], "findings": len(sast["findings"]),
            "unique_findings": len({(f["rule_id"], f["path"], f["line"], f["column"]) for f in sast["findings"]}),
            "skipped": sast["skipped"], "health": report.health_score,
            "categories": report.category_scores,
            "coverage": score_coverage(report.scoring_policy_version, report.category_scores)}


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="sourcehealth-large-benchmark-") as directory:
        for count in (120, 10_000, 10_001):
            path = Path(directory) / str(count)
            fixture = generate(path, count)
            results.append({"fixture": fixture, "measurement": measure(path)})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
