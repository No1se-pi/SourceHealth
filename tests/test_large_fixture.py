"""Дешёвые regressions генератора; 10k benchmark запускается отдельно."""

import tempfile
import unittest
from pathlib import Path

from scripts.generate_large_sourcecraft_fixture import SOURCE_ROOT, generate


class LargeFixtureTests(unittest.TestCase):
    def test_deterministic_history_and_exact_count(self):
        with tempfile.TemporaryDirectory() as directory:
            first = generate(Path(directory) / "a", 120)
            second = generate(Path(directory) / "b", 120)
            self.assertEqual(first, second)
            self.assertEqual(first["tracked_files"], 120)
            self.assertEqual(first["commits"], 1)
            self.assertFalse(first["sourcecraft_acceptance"])
            self.assertFalse(first["large_threshold_met"])

    def test_refuses_existing_destination_and_sourcehealth_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate(directory, 120)
        with self.assertRaises(ValueError):
            generate(SOURCE_ROOT / "must-not-create-fixture", 120)
