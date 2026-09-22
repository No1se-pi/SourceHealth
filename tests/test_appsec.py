import json
import unittest

import httpx

from sourcehealth.analyzers.platform import SourceCraftSecurityAnalyzer
from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import DataAvailability, RepositoryRef
from sourcehealth.integrations.sourcecraft.appsec import SourceCraftAppSecClient
from sourcehealth.integrations.sourcecraft.client import SourceCraftError
from sourcehealth.integrations.sourcecraft.collectors import AppSecCollector
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import MVPPolicy


class AppSecTests(unittest.TestCase):
    def setUp(self):
        self.ref = RepositoryRef.from_url("https://sourcecraft.dev/team/repo", visibility="public")

    def client(self, handler, **limits):
        return SourceCraftAppSecClient(pat="test-credential", transport=httpx.MockTransport(handler),
                                       sleep=lambda _: None, **limits)

    def test_finished_scan_is_normalized_without_raw_fields(self):
        requests = []

        def handler(request):
            self.assertEqual(request.headers["authorization"], "Bearer test-credential")
            requests.append(request)
            if request.url.path == "/v1/scans/latest":
                return httpx.Response(200, json={"uuid": "scan-uuid", "status": 1})
            if request.url.path == "/v1/scans/scan-uuid":
                return httpx.Response(200, json={"uuid": "scan-uuid", "status": "FINISHED"})
            severity = request.url.params.get("severity")
            rows = ([{"uuid": "group-1", "codeBlock": "must-not-persist", "severity": 3}]
                    if severity == "HIGH" else [])
            return httpx.Response(200, json={"data": rows, "nextPageToken": "", "totalSize": len(rows)})

        with self.client(handler) as client:
            result = AppSecCollector(client).collect(self.ref, "repo-uuid")
        self.assertEqual(result.availability, DataAvailability.AVAILABLE)
        self.assertEqual(result.facts["open_by_severity"],
                         {"critical": 0, "high": 1, "medium": 0, "low": 0})
        self.assertNotIn("must-not-persist", json.dumps(result.facts))
        group_requests = [r for r in requests if r.url.path == "/v1/defect-groups"]
        self.assertEqual(len(group_requests), 4)
        self.assertEqual(group_requests[0].url.params.get_list("status"),
                         ["OPEN", "TRIAGE_IN_PROGRESS", "TRIAGED_TP", "FIX_IN_PROGRESS"])

        context = AnalysisContext(repository=self.ref, sourcecraft_facts={"appsec": result.facts},
                                  collection_statuses={"appsec": result.availability},
                                  metadata={"collection": {"appsec": {"error": None}}})
        analyzed = SourceCraftSecurityAnalyzer().analyze(context)
        self.assertEqual(analyzed.status, "ok")
        self.assertEqual(analyzed.source, "sourcecraft_appsec")
        from sourcehealth.runner import AnalysisRunner
        report = AnalysisRunner([SourceCraftSecurityAnalyzer()]).analyze_context(context)
        ScoringEngine(MVPPolicy()).apply(report)
        serialized = json.dumps(report.to_public_dict())
        self.assertEqual(report.category_scores["security"]["score"], 80)
        self.assertNotIn("must-not-persist", serialized)

    def test_unfinished_unknown_and_auth_failures_never_score(self):
        def unfinished(request):
            body = {"uuid": "scan-uuid"} if request.url.path.endswith("latest") else {"status": "FAILED"}
            return httpx.Response(200, json=body)

        with self.client(unfinished) as client:
            result = AppSecCollector(client).collect(self.ref, "repo-uuid")
        self.assertEqual(result.availability, DataAvailability.PARTIAL)
        self.assertFalse(result.facts["complete"])

        for status, error in ((401, "appsec_authentication_required"), (403, "appsec_access_denied"),
                              (404, "appsec_not_found")):
            with self.subTest(status=status):
                with self.client(lambda _: httpx.Response(status)) as client:
                    result = AppSecCollector(client).collect(self.ref, "repo-uuid")
                self.assertEqual(result.availability, DataAvailability.NO_DATA)
                self.assertEqual(result.error, error)

    def test_client_bounds_response_pagination_and_error_text(self):
        with self.client(lambda _: httpx.Response(200, content=b"x" * 20), max_response_bytes=10) as client:
            with self.assertRaisesRegex(SourceCraftError, "^response_limit$"):
                client.get("/v1/scans/latest")
        marker = "private-response-marker"
        with self.client(lambda _: httpx.Response(500, text=marker)) as client:
            with self.assertRaises(SourceCraftError) as caught:
                client.get("/v1/scans/latest")
        self.assertNotIn(marker, str(caught.exception))

    def test_client_enforces_total_deadline_while_streaming(self):
        ticks = iter((0.0, 0.0, 2.0))
        with self.client(lambda _: httpx.Response(200, json={}), deadline_seconds=1,
                         clock=lambda: next(ticks)) as client:
            with self.assertRaisesRegex(SourceCraftError, "^collection_budget_exceeded$"):
                client.get("/v1/scans/latest")

    def test_client_rejects_bad_paths_malformed_json_and_repeated_tokens(self):
        with self.client(lambda _: httpx.Response(200, content=b"not-json")) as client:
            with self.assertRaisesRegex(SourceCraftError, "^invalid_response$"):
                client.get("/v1/scans/latest")
            with self.assertRaises(ValueError):
                client.get("https://evil.example/")

        pages = 0
        def repeated(_):
            nonlocal pages
            pages += 1
            return httpx.Response(200, json={"data": [], "nextPageToken": "same", "totalSize": 0})
        with self.client(repeated) as client:
            with self.assertRaisesRegex(SourceCraftError, "^invalid_pagination$"):
                list(client.iter_defect_groups("repo", "scan", "HIGH"))
        self.assertEqual(pages, 2)

    def test_schema_failure_is_partial_and_not_fake_zero(self):
        def handler(request):
            if request.url.path.endswith("latest"):
                return httpx.Response(200, json={"uuid": "scan"})
            if request.url.path.endswith("/scan"):
                return httpx.Response(200, json={"status": "FINISHED"})
            return httpx.Response(200, json={"data": [{"uuid": 7}], "nextPageToken": "", "totalSize": 1})
        with self.client(handler) as client:
            result = AppSecCollector(client).collect(self.ref, "repo")
        self.assertEqual(result.availability, DataAvailability.PARTIAL)
        self.assertEqual(result.facts, {"complete": False})

    def test_duplicate_defect_group_is_partial_not_double_counted(self):
        def handler(request):
            if request.url.path.endswith("latest"):
                return httpx.Response(200, json={"uuid": "scan"})
            if request.url.path.endswith("/scan"):
                return httpx.Response(200, json={"status": "FINISHED"})
            return httpx.Response(200, json={
                "data": [{"uuid": "duplicate"}, {"uuid": "duplicate"}],
                "nextPageToken": "", "totalSize": 2,
            })

        with self.client(handler) as client:
            result = AppSecCollector(client).collect(self.ref, "repo")
        self.assertEqual(result.availability, DataAvailability.PARTIAL)
        self.assertEqual(result.error, "appsec_invalid_pagination")
        self.assertEqual(result.facts, {"complete": False})

    def test_missing_credential_or_repository_id_is_no_data(self):
        result = AppSecCollector(None).collect(self.ref)
        self.assertEqual(result.error, "appsec_credential_unavailable")
        self.assertEqual(result.availability, DataAvailability.NO_DATA)


if __name__ == "__main__":
    unittest.main()
