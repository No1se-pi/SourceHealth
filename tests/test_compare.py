"""Compare contracts preserve nullable facts and selected order."""

import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.application.services import ServiceError
from sourcehealth.compare import CompareService


class DB:
    def __init__(self, result_sets): self.result_sets = iter(result_sets)
    def scalars(self, statement): return next(self.result_sets)


class Sessions:
    def __init__(self, result_sets): self.db = DB(result_sets)
    @contextmanager
    def __call__(self): yield self.db


def repository(visibility="public", health=None):
    return SimpleNamespace(id=uuid4(), organization_slug="team", repository_slug=uuid4().hex,
                           canonical_url="https://sourcecraft.dev/team/repo", visibility=visibility,
                           health_score=health, language="Python", likes=3,
                           last_activity_at=datetime(2026, 1, 1, tzinfo=UTC))


def run(repo, *, policy="mvp-score-v1.2", health=80, no_data=False):
    categories = {name: {"score": 80, "availability": "available"} for name in
                  ("documentation", "cicd", "security", "activity", "issues", "code_health")}
    if no_data:
        categories["security"] = {"score": None, "availability": "no_data"}
    return SimpleNamespace(id=uuid4(), repository_id=repo.id, category_scores=categories,
                           scoring_policy_version=policy, health_score=health)


class CompareTests(unittest.TestCase):
    def test_two_and_four_repositories_preserve_order(self):
        for count in (2, 4):
            repos = [repository() for _ in range(count)]
            runs = [run(repo) for repo in repos]
            result = CompareService(Sessions([list(reversed(repos)), runs])).compare([r.id for r in repos])
            self.assertEqual([item["repository_id"] for item in result["repositories"]], [r.id for r in repos])

    def test_limits_duplicates_and_private_are_rejected(self):
        with self.assertRaises(ServiceError):
            CompareService(Sessions([])).compare([uuid4()])
        with self.assertRaises(ServiceError):
            CompareService(Sessions([])).compare([uuid4() for _ in range(5)])
        duplicate = uuid4()
        with self.assertRaisesRegex(ServiceError, "duplicate_repository"):
            CompareService(Sessions([])).compare([duplicate, duplicate])
        public, private = repository(), repository("private")
        with self.assertRaisesRegex(ServiceError, "repository_not_found"):
            CompareService(Sessions([[public, private], []])).compare([public.id, private.id])

    def test_no_data_policy_mismatch_and_no_analysis_are_honest(self):
        first, second = repository(), repository(health=55)
        result = CompareService(Sessions([[first, second],
                                          [run(first, no_data=True), run(second, policy="future-score-v2")]])).compare(
                                              [first.id, second.id])
        self.assertIsNone(result["repositories"][0]["categories"]["security"]["score"])
        self.assertEqual(result["repositories"][0]["categories"]["security"]["availability"], "no_data")
        self.assertFalse(result["comparable"]["policy_versions_match"])
        empty = CompareService(Sessions([[first, second], []])).compare([first.id, second.id])
        self.assertEqual(empty["repositories"][1]["health_score"], 55)
        self.assertEqual(empty["repositories"][1]["categories"], {})
