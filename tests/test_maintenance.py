"""Periodic maintenance keeps independent responsibilities failure-isolated."""

import io
import logging
import unittest
from unittest.mock import Mock

from sourcehealth.application.__main__ import _run_catalog_maintenance
from sourcehealth.integrations.sourcecraft.client import SourceCraftError
from sourcehealth.logging_config import EventFormatter


class MaintenanceFailureIsolationTests(unittest.TestCase):
    def run_degraded(self, code):
        enqueue_due = Mock(return_value=["run-1", "run-2"])
        dispatch = Mock(return_value=2)
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(EventFormatter())
        logger = logging.getLogger("sourcehealth.application.__main__")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        try:
            result = _run_catalog_maintenance(
                "maintain",
                Mock(side_effect=SourceCraftError(code)),
                enqueue_due,
                dispatch,
            )
        finally:
            logger.removeHandler(handler)
        return result, enqueue_due, dispatch, output.getvalue()

    def test_maintain_catalog_response_limit_does_not_block_scheduler(self):
        result, enqueue_due, dispatch, log_output = self.run_degraded("response_limit")

        enqueue_due.assert_called_once_with()
        dispatch.assert_called_once_with()
        self.assertEqual(result, {
            "catalog_sync": {"ok": False, "error": "response_limit"},
            "scheduled": 2,
            "dispatched": 2,
        })
        self.assertIn('"sourcecraft_error_code": "response_limit"', log_output)
        self.assertNotIn("response body", log_output)
        self.assertNotIn("credential", log_output)

    def test_maintain_source_unavailable_does_not_block_scheduler(self):
        result, enqueue_due, dispatch, _ = self.run_degraded("source_unavailable")

        enqueue_due.assert_called_once_with()
        dispatch.assert_called_once_with()
        self.assertEqual(result["catalog_sync"], {"ok": False, "error": "source_unavailable"})

    def test_enqueue_due_catalog_failure_does_not_block_scheduler(self):
        enqueue_due = Mock(return_value=["run-1"])
        dispatch = Mock(return_value=1)

        result = _run_catalog_maintenance(
            "enqueue-due",
            Mock(side_effect=SourceCraftError("response_limit")),
            enqueue_due,
            dispatch,
        )

        enqueue_due.assert_called_once_with()
        dispatch.assert_called_once_with()
        self.assertEqual(result["scheduled"], 1)
        self.assertEqual(result["dispatched"], 1)
        self.assertEqual(result["catalog_sync"], {"ok": False, "error": "response_limit"})

    def test_standalone_catalog_sync_preserves_failure_semantics(self):
        with self.assertRaisesRegex(SourceCraftError, "^response_limit$"):
            _run_catalog_maintenance(
                "catalog-sync",
                Mock(side_effect=SourceCraftError("response_limit")),
            )

    def test_unexpected_programming_error_is_not_hidden(self):
        enqueue_due = Mock()
        dispatch = Mock()

        with self.assertRaisesRegex(RuntimeError, "programming defect"):
            _run_catalog_maintenance(
                "maintain",
                Mock(side_effect=RuntimeError("programming defect")),
                enqueue_due,
                dispatch,
            )
        enqueue_due.assert_not_called()
        dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
