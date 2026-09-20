"""Operator acceptance commands: safe output, deterministic exit codes, no implicit infrastructure."""

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ENABLED = importlib.util.find_spec("pydantic_settings") is not None

if ENABLED:
    import httpx
    from pydantic import SecretStr

    from sourcehealth.application.__main__ import main, worker_class
    from sourcehealth.application.acceptance import preflight, probe_sourcecraft
    from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
    from sourcehealth.settings import Settings
    from tests.mvp_fixtures import sourcecraft_transport

REPOSITORY_URL = "https://sourcecraft.dev/org/repo"


def settings_with_pat():
    # Keep token-shaped fixture values out of source control and scanner findings.
    return Settings(_env_file=None, sourcecraft_pat=SecretStr("test" + "-credential"))


@unittest.skipUnless(ENABLED, "install server dependencies for operator command tests")
class ProbeSourceCraftTests(unittest.TestCase):
    def test_worker_uses_non_forking_rq_implementation_on_windows(self):
        self.assertEqual(worker_class("nt").__name__, "SimpleWorker")
        self.assertEqual(worker_class("posix").__name__, "Worker")

    def run_probe(self, transport):
        with SourceCraftClient(transport=transport, sleep=lambda _: None) as client:
            return probe_sourcecraft(settings_with_pat(), REPOSITORY_URL, client=client)

    def test_complete_contract_is_successful_and_allowlisted(self):
        payload, code = self.run_probe(sourcecraft_transport())
        self.assertEqual(code, 0)
        self.assertEqual(payload["overall"], "ok")
        self.assertTrue(payload["authenticated"])
        self.assertEqual(set(payload["collectors"]), {
            "repository_metadata", "issues", "cicd", "pull_requests", "contributors", "releases",
        })
        rendered = json.dumps(payload, allow_nan=False)
        for forbidden in ("untrusted", "do-not-store", "private name", "test-credential"):
            self.assertNotIn(forbidden, rendered)

    def test_empty_resources_are_complete_not_outage(self):
        def handler(request):
            key = request.url.path.rsplit("/", 1)[-1]
            if key == "repo":
                return httpx.Response(200, json={"id": "repo-id", "slug": "repo", "visibility": "public"})
            return httpx.Response(200, json={{
                "issues": "issues", "runs": "runs", "pulls": "pull_requests",
                "contributors": "contributors", "releases": "releases",
            }[key]: []})

        payload, code = self.run_probe(httpx.MockTransport(handler))
        self.assertEqual(code, 0)
        self.assertTrue(all(item["complete"] for item in payload["collectors"].values()))

    def test_metadata_auth_not_found_and_schema_errors_are_fatal(self):
        cases = ((401, {}, "authentication_required"), (403, {}, "access_denied"),
                 (404, {}, "not_found"),
                 (200, {"id": 7, "slug": "repo", "visibility": "public", "raw": "private-body"},
                  "invalid_response"))
        for status, body, error in cases:
            with self.subTest(status=status, error=error):
                payload, code = self.run_probe(httpx.MockTransport(
                    lambda request, s=status, b=body: httpx.Response(s, json=b)))
                self.assertEqual(code, 2)
                self.assertEqual(payload["error"], error)
                self.assertNotIn("private-body", json.dumps(payload))

    def test_resource_rate_limit_outage_malformed_and_pagination_are_classified(self):
        for status, body, expected_code, expected_error in (
            (429, {}, 1, "rate_limited"),
            (503, {}, 1, "source_unavailable"),
            (200, {"issues": "wrong"}, 2, "invalid_response"),
            (200, {"issues": [], "next_page_token": 7}, 2, "invalid_pagination"),
        ):
            def handler(request, status=status, body=body):
                if request.url.path.endswith("/repo"):
                    return httpx.Response(200, json={"id": "repo-id", "slug": "repo", "visibility": "public"})
                if request.url.path.endswith("/issues"):
                    return httpx.Response(status, json=body)
                key = {"runs": "runs", "pulls": "pull_requests", "contributors": "contributors",
                       "releases": "releases"}[request.url.path.rsplit("/", 1)[-1]]
                return httpx.Response(200, json={key: []})

            with self.subTest(status=status, error=expected_error):
                payload, code = self.run_probe(httpx.MockTransport(handler))
                self.assertEqual(code, expected_code)
                self.assertEqual(payload["collectors"]["issues"]["error"], expected_error)

    def test_preflight_requires_pat_and_public_sourcecraft_url(self):
        settings = Settings(_env_file=None)
        self.assertEqual(preflight(settings, REPOSITORY_URL)[1], "sourcecraft_pat_not_configured")
        settings = settings_with_pat()
        self.assertEqual(preflight(settings, "https://example.com/org/repo")[1], "invalid_sourcecraft_url")

    def test_expired_probe_budget_is_a_fatal_metadata_failure(self):
        with SourceCraftClient(transport=sourcecraft_transport(), deadline_seconds=-1) as client:
            payload, code = probe_sourcecraft(settings_with_pat(), REPOSITORY_URL, client=client)
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "collection_budget_exceeded")

    def test_cli_probe_does_not_open_database_or_redis(self):
        expected = ({"overall": "ok", "authenticated": True, "collectors": {}}, 0)
        output = io.StringIO()
        with (patch("sourcehealth.application.__main__.Settings", return_value=settings_with_pat()),
              patch("sourcehealth.application.acceptance.probe_sourcecraft", return_value=expected),
              patch("sourcehealth.storage.database.create_database", side_effect=AssertionError("DB opened")),
              redirect_stdout(output)):
            self.assertEqual(main(["probe-sourcecraft", REPOSITORY_URL]), 0)
        self.assertEqual(json.loads(output.getvalue())["overall"], "ok")

    def test_cli_invalid_arguments_never_echo_rejected_value(self):
        secret = "accidental" + "-credential"
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            main(["probe-sourcecraft", REPOSITORY_URL, secret])
        self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
