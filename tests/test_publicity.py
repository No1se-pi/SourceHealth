"""Publicity projection contracts."""

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.application.services import ServiceError
from sourcehealth.publicity import PublicityService
from sourcehealth.settings import Settings


class Sessions:
    def __init__(self, values): self.values = values
    @contextmanager
    def __call__(self): yield self
    def scalar(self, statement): return self.values.pop(0)


class PublicityTests(unittest.TestCase):
    def repo(self, visibility="public", health=82.4):
        return SimpleNamespace(id=uuid4(), organization_slug="team", repository_slug="project",
                               visibility=visibility, health_score=health)

    def test_public_health_badge_and_latest_terminal_urls(self):
        repo, run = self.repo(), SimpleNamespace(id=uuid4())
        result = PublicityService(Sessions([repo, run]), "https://sourcehealth.tech/").repository(repo.id)
        self.assertEqual(result["repository_url"], f"https://sourcehealth.tech/repositories/{repo.id}")
        self.assertEqual(result["latest_analysis_url"], f"https://sourcehealth.tech/analyses/{run.id}")
        self.assertEqual(result["badge_markdown"],
                         "![SourceHealth](https://sourcehealth.tech/api/v1/badges/team/project.svg)")

    def test_health_null_is_not_replaced_and_no_analysis_has_no_report(self):
        repo = self.repo(health=None)
        result = PublicityService(Sessions([repo, None]), "https://sourcehealth.tech").repository(repo.id)
        self.assertIsNone(result["health_score"])
        self.assertFalse(result["health_available"])
        self.assertIsNone(result["markdown_report_url"])

    def test_private_or_revoked_repository_is_hidden(self):
        for visibility in ("private", "unknown"):
            with self.subTest(visibility=visibility), self.assertRaises(ServiceError) as caught:
                PublicityService(Sessions([None]), "https://sourcehealth.tech").repository(uuid4())
            self.assertEqual(caught.exception.status, 404)

    def test_public_origin_rejects_untrusted_or_path_bearing_values(self):
        self.assertEqual(Settings(_env_file=None, public_origin="http://localhost:8000/").public_origin,
                         "http://localhost:8000")
        for value in ("http://example.com", "https://example.com/path", "https://user:pass@example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings(_env_file=None, public_origin=value)
