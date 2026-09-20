"""Поведение collectors на официальных DTO, HTTP failures и недоверенных полях."""

import json
import unittest
from copy import deepcopy

import httpx

from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.core.domain import RepositoryRef
from sourcehealth.integrations.sourcecraft.analytics import (
    CatalogCollector,
    CICollector,
    ContributorsCollector,
    IssuesCollector,
    PullRequestsCollector,
    ReleasesCollector,
)
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from tests.mvp_fixtures import platform_payloads


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.ref = RepositoryRef.from_url("https://sourcecraft.dev/org/repo", visibility="public")
        self.payloads = platform_payloads()

    def client(self, handler, **kwargs):
        return SourceCraftClient(transport=httpx.MockTransport(handler), sleep=lambda _: None, **kwargs)

    def test_all_collectors_keep_only_allowlisted_fields(self):
        for cls, key in [(IssuesCollector, "issues"), (CICollector, "runs"), (PullRequestsCollector, "pulls"),
                         (ContributorsCollector, "contributors"), (ReleasesCollector, "releases")]:
            with self.subTest(collector=cls.__name__):
                requests = []

                def handler(request):
                    requests.append(request)
                    return httpx.Response(200, json=self.payloads["comments" if request.url.path.endswith("/comments") else key])

                with self.client(handler) as client:
                    result = cls(client).collect(self.ref)
                self.assertEqual(result.availability, A.AVAILABLE)
                self.assertEqual(len(result.facts["items"]), 1)
                self.assertNotIn("untrusted", json.dumps(result.facts))
                self.assertNotIn("private name", json.dumps(result.facts))
                self.assertNotIn("do-not-store", json.dumps(result.facts))
                if cls is IssuesCollector:
                    self.assertNotIn("filter", requests[0].url.params)
                    self.assertEqual(result.facts["items"][0]["first_external_response_at"], "2026-09-17T01:00:00+00:00")
                if cls is CICollector:
                    self.assertEqual(result.facts["items"][0]["duration_seconds"], 120)

    def test_empty_partial_unavailable_and_invalid_for_each_resource(self):
        for cls, key in [(IssuesCollector, "issues"), (CICollector, "runs"), (PullRequestsCollector, "pulls"),
                         (ContributorsCollector, "contributors"), (ReleasesCollector, "releases")]:
            response_key = next(iter(self.payloads[key]))
            for mode in ("empty", "partial", "outage", "invalid"):
                with self.subTest(collector=cls.__name__, mode=mode):
                    def handler(request):
                        if request.url.path.endswith("/comments"):
                            return httpx.Response(200, json=self.payloads["comments"])
                        if mode == "outage" or request.url.params.get("page_token"):
                            return httpx.Response(503, text="private error body")
                        if mode == "invalid":
                            return httpx.Response(200, json={response_key: [{"id": "bad"}] if cls is not ContributorsCollector else [42]})
                        if mode == "empty":
                            return httpx.Response(200, json={response_key: []})
                        return httpx.Response(200, json={**self.payloads[key], "next_page_token": "next"})

                    with self.client(handler) as client:
                        result = cls(client).collect(self.ref)
                    expected = {"empty": A.AVAILABLE, "partial": A.PARTIAL, "outage": A.SOURCE_UNAVAILABLE, "invalid": A.SOURCE_UNAVAILABLE}[mode]
                    self.assertEqual(result.availability, expected)
                    self.assertEqual(result.facts["complete"], mode == "empty")
                    self.assertNotIn("private error body", str(result))

    def test_private_issue_and_draft_release_never_enter_public_facts(self):
        for cls, key, field, value in [(IssuesCollector, "issues", "visibility", "private"),
                                      (ReleasesCollector, "releases", "status", "draft")]:
            payload = deepcopy(self.payloads[key])
            next(iter(payload.values()))[0][field] = value
            with self.client(lambda _: httpx.Response(200, json=payload)) as client:
                self.assertEqual(cls(client).collect(self.ref).facts["items"], [])

    def test_comment_budget_and_partial_comments_leave_latency_unknown(self):
        with self.client(lambda r: httpx.Response(503) if r.url.path.endswith("comments") else
                         httpx.Response(200, json=self.payloads["issues"])) as client:
            result = IssuesCollector(client).collect(self.ref)
        self.assertEqual(result.availability, A.AVAILABLE)
        self.assertFalse(result.facts["items"][0]["response_complete"])
        self.assertIsNone(result.facts["items"][0]["first_external_response_at"])

    def test_catalog_deduplication_scope_and_limits(self):
        row = {"id": "r1", "slug": "repo", "organization": {"slug": "org"}, "visibility": "public"}
        payload = {"repositories": [row, row, {**row, "id": "r2", "slug": "other"}]}
        requests = []
        with self.client(lambda r: (requests.append(r) or httpx.Response(200, json=payload))) as client:
            result = CatalogCollector(client, max_items=1).discover()
        self.assertEqual(result.availability, A.PARTIAL)
        self.assertEqual(len(result.facts["items"]), 1)
        self.assertEqual(requests[0].url.path, "/repos")
        self.assertEqual(requests[0].url.params["sort_by"], "created_at")

    def test_external_response_excludes_self_and_never_retains_author_ids(self):
        comment = self.payloads["comments"]["issue_comments"][0]
        own = {**comment, "author": {"id": "issue-author"}, "created_at": "2026-09-17T00:01:00Z"}
        for comments, expected_complete, expected_time in (
            ([own, comment], True, "2026-09-17T01:00:00+00:00"),
            ([own], True, None),
            ([], True, None),
            ([{**comment, "author": None}], False, None),
        ):
            with self.subTest(comments=comments):
                with self.client(lambda request: httpx.Response(200, json={"issue_comments": comments}
                                 if request.url.path.endswith("comments") else self.payloads["issues"])) as client:
                    collected = IssuesCollector(client).collect(self.ref)
                item = collected.facts["items"][0]
                self.assertEqual(item["response_complete"], expected_complete)
                self.assertEqual(item["first_external_response_at"], expected_time)
                self.assertNotIn("author", json.dumps(collected.facts))
                self.assertNotIn("responder", json.dumps(collected.facts))
        self.payloads["issues"]["issues"][0].pop("author")
        with self.client(lambda _: httpx.Response(200, json=self.payloads["issues"])) as client:
            item = IssuesCollector(client).collect(self.ref).facts["items"][0]
        self.assertFalse(item["response_complete"])
        self.assertNotIn("_author_id", item)

    def test_expired_collection_budget_makes_no_request(self):
        with self.client(lambda _: self.fail("must not request"), deadline_seconds=-1) as client:
            result = CICollector(client).collect(self.ref)
        self.assertEqual(result.error, "collection_budget_exceeded")
