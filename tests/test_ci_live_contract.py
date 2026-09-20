"""Sanitized shape of SourceCraft runs: public IDs absent, slug is stable."""

import unittest

from sourcehealth.integrations.sourcecraft.analytics import CICollector


class CIRunContractTests(unittest.TestCase):
    def test_public_run_counter_and_pending_dates(self):
        raw = {"id": "", "slug": "4", "status": "processing", "dates": {
            "created_at": "2026-09-20T16:57:18Z", "started_at": "2026-09-20T16:57:19Z",
            "finished_at": "1970-01-01T00:00:00Z"}}
        item = CICollector(None).normalize(raw)
        self.assertEqual(item["id"], "4")
        self.assertIsNone(item["completed_at"])
        self.assertIsNone(item["duration_seconds"])
        raw["status"] = "success"
        raw["dates"]["finished_at"] = "2026-09-20T16:59:17Z"
        self.assertEqual(CICollector(None).normalize(raw)["duration_seconds"], 118)
