"""Контрактные fixtures по Swagger 19.09.2026; это не результаты live SourceCraft."""

from datetime import UTC, datetime

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import Evidence
from sourcehealth.git.activity import GitActivityAnalyzer
from sourcehealth.git.models import Commit
from sourcehealth.sast.models import ScanResult
from sourcehealth.scoring.mvp import DOCUMENTATION_WEIGHTS

NOW = datetime(2026, 9, 19, tzinfo=UTC)
STAMP = "2026-09-18T00:00:00+00:00"
SHA = "a" * 40


def platform_payloads():
    return {
        "issues": {"issues": [{"id": "issue-1", "slug": "1", "status": {"status_type": "completed"},
                                "visibility": "public", "author": {"id": "issue-author"},
                                "created_at": "2026-09-17T00:00:00Z", "updated_at": STAMP,
                                "completed_at": STAMP, "description": "untrusted issue content"}]},
        "comments": {"issue_comments": [{"id": "comment-1", "author": {"id": "responder"}, "created_at": "2026-09-17T01:00:00Z",
                                          "body": "untrusted comment content"}]},
        "runs": {"runs": [{"id": "run-1", "status": "success", "dates": {"created_at": STAMP,
                            "started_at": STAMP, "finished_at": "2026-09-18T00:02:00Z"}, "error_messages": ["untrusted stderr"]}]},
        "pulls": {"pull_requests": [{"id": "pull-1", "status": "merged", "created_at": STAMP, "updated_at": STAMP}]},
        "contributors": {"contributors": [{"id": "user-1", "display_name": "private name", "email": "do-not-store"}]},
        "releases": {"releases": [{"id": "release-1", "status": "published", "released_at": STAMP,
                                    "release_notes": "untrusted release text"}]},
    }


def runtime_payload():
    metadata = {"head_sha": SHA, "complete": True, "ci_configured": True,
                "scope": "tracked_default_branch_excluding_generated"}
    docs = AnalyzerResult("documentation", category="documentation", source="git_snapshot", metadata=metadata,
                          metrics={**dict.fromkeys(DOCUMENTATION_WEIGHTS, True), "readme_bytes": 500, "readme_headings": 4})
    debt = AnalyzerResult("technical_debt", category="code_health", source="git_snapshot", metadata=metadata,
                          metrics={"code_files": 10, "todo_count": 0, "fixme_count": 0, "files_with_debt": 0,
                                   "marker_density": 0, "large_files": 0, "oldest_marker_age_days": None, "age_complete": True})
    commits = [Commit(str(i), "", "", NOW, "") for i in range(20)]
    return {"schema_version": "1.0", "complete": True, "checks": {
        "git_activity": {"status": "ok", "metrics": GitActivityAnalyzer().analyze(commits, now=NOW).to_dict()},
        "sast": ScanResult(files_scanned=10, code_files_lexed=10).to_dict(),
        "documentation": docs.to_dict(), "technical_debt": debt.to_dict(),
    }}


def appsec_fixture():
    # Reserved internal normalized contract, not a guessed SourceCraft wire DTO.
    return AnalyzerResult("official_test", category="security", source="sourcecraft_appsec",
                          metrics={"complete": True, "open_by_severity": dict.fromkeys(("critical", "high", "medium", "low"), 0)},
                          evidence=[Evidence("appsec:fixture", "sourcecraft_appsec", "test_contract", "scan-fixture", "Контрактная fixture.")])


def sourcecraft_transport(repository_slug="repo"):
    import httpx

    payloads = platform_payloads()

    def handler(request):
        last = request.url.path.rsplit("/", 1)[-1]
        if last in payloads:
            return httpx.Response(200, json=payloads[last])
        return httpx.Response(200, json={"id": "repo-id", "slug": repository_slug, "visibility": "public",
                                        "default_branch": "main", "language": {"name": "Python"}})
    return httpx.MockTransport(handler)


def mvp_context():
    from types import SimpleNamespace

    from sourcehealth.application.jobs import collect_mvp
    from sourcehealth.core import AnalysisContext
    from sourcehealth.core.domain import DataAvailability, RepositoryRef
    from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

    context = AnalysisContext(repository=RepositoryRef.from_url("https://sourcecraft.dev/org/repo", visibility="public"),
                              started_at=NOW, sourcecraft_facts={"repository_metadata": {"visibility": "public"}},
                              collection_statuses={"repository_metadata": DataAvailability.AVAILABLE})
    with SourceCraftClient(transport=sourcecraft_transport()) as client:
        return collect_mvp(context, SimpleNamespace(), client=client)
