"""Opt-in contract check against one explicitly configured public SourceCraft repository."""

import os
import unittest
from datetime import datetime

PAT = os.getenv("SOURCECRAFT_PAT")
REPOSITORY_URL = os.getenv("SOURCEHEALTH_LIVE_REPO_URL")


@unittest.skipUnless(PAT and REPOSITORY_URL, "set SOURCECRAFT_PAT and SOURCEHEALTH_LIVE_REPO_URL")
class LiveSourceCraftTests(unittest.TestCase):
    def test_public_repository_and_all_mvp_collectors(self):
        from sourcehealth.core.domain import DataAvailability, RepositoryRef
        from sourcehealth.integrations.sourcecraft.analytics import (
            CICollector,
            ContributorsCollector,
            IssuesCollector,
            PullRequestsCollector,
            ReleasesCollector,
        )
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from sourcehealth.integrations.sourcecraft.collectors import RepositoryCollector

        ref = RepositoryRef.from_url(REPOSITORY_URL)
        results = []
        with SourceCraftClient(pat=PAT, deadline_seconds=120) as client:
            for collector in (RepositoryCollector, IssuesCollector, CICollector, PullRequestsCollector,
                              ContributorsCollector, ReleasesCollector):
                results.append(collector(client).collect(ref))

        metadata, *resources = results
        self.assertEqual(metadata.availability, DataAvailability.AVAILABLE)
        self.assertEqual(metadata.facts["visibility"], "public")
        for result in resources:
            self.assertIn(result.availability, {DataAvailability.AVAILABLE, DataAvailability.PARTIAL})
            self.assertIsInstance(result.facts["items"], list)
            self.assertIs(result.facts["complete"], result.availability == DataAvailability.AVAILABLE)
            self.assertNotEqual(result.availability, DataAvailability.SOURCE_UNAVAILABLE)
            self._validate_safe_facts(result.facts)

    def _validate_safe_facts(self, value):
        forbidden = {"name", "display_name", "email", "body", "description", "release_notes", "error_messages"}
        if isinstance(value, dict):
            self.assertFalse(forbidden.intersection(value))
            for key, item in value.items():
                if key.endswith("_at") and item is not None:
                    datetime.fromisoformat(item)
                self._validate_safe_facts(item)
        elif isinstance(value, list):
            for item in value:
                self._validate_safe_facts(item)


if __name__ == "__main__":
    unittest.main()
