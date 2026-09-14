"""Opt-in smoke на настоящем API, не запускается без явного флага и repo URL."""

import os
import unittest


@unittest.skipUnless(os.getenv("SOURCECRAFT_LIVE_TEST") == "1" and os.getenv("SOURCECRAFT_TEST_REPOSITORY"),
                     "live SourceCraft smoke is opt-in")
class LiveSourceCraftTests(unittest.TestCase):
    def test_public_metadata(self):
        from sourcehealth.core.domain import RepositoryRef
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from sourcehealth.integrations.sourcecraft.collectors import RepositoryCollector

        ref = RepositoryRef.from_url(os.environ["SOURCECRAFT_TEST_REPOSITORY"])
        with SourceCraftClient(pat=os.getenv("SOURCECRAFT_PAT")) as client:
            result = RepositoryCollector(client).collect(ref)
        self.assertEqual(result.availability, "available")
