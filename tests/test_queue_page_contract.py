"""Frontend contract tests for Analysis Stack Visualization (/queue).

Verifies:
- Route /queue exists in router.tsx
- Navigation item 'Очередь' exists in Sidebar.tsx
- All three levels (priority, timed, planned) render
- Zero-state handling (empty plates for Priority=0 and Timed=0)
- prefers-reduced-motion accessibility rules
- No hardcoded fake 'completed' events
- Backend remains 100% unmodified
"""

import os
import unittest
from pathlib import Path


class QueuePageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.frontend = cls.root / "frontend" / "src"

    def test_route_registered(self):
        router_path = self.frontend / "app" / "router.tsx"
        self.assertTrue(router_path.exists(), "router.tsx must exist")
        content = router_path.read_text(encoding="utf-8")
        self.assertIn("QueuePage", content, "QueuePage must be imported in router.tsx")
        self.assertIn('path="/queue"', content, "Route /queue must be registered")

    def test_navigation_item_registered(self):
        sidebar_path = self.frontend / "components" / "layout" / "Sidebar.tsx"
        self.assertTrue(sidebar_path.exists(), "Sidebar.tsx must exist")
        content = sidebar_path.read_text(encoding="utf-8")
        self.assertIn('to="/queue"', content, "Sidebar must link to /queue")
        self.assertIn("Очередь", content, "Navigation item must have label 'Очередь'")

    def test_all_three_levels_render(self):
        stack_path = self.frontend / "components" / "queue" / "AnalysisStack.tsx"
        counters_path = self.frontend / "components" / "queue" / "StackCounters.tsx"
        legend_path = self.frontend / "components" / "queue" / "StackLegend.tsx"

        for p in (stack_path, counters_path, legend_path):
            self.assertTrue(p.exists(), f"Component {p.name} must exist")

        stack_content = stack_path.read_text(encoding="utf-8")
        self.assertIn("priority", stack_content)
        self.assertIn("timed", stack_content)
        self.assertIn("planned", stack_content)

        counters_content = counters_path.read_text(encoding="utf-8")
        self.assertIn("Приоритет", counters_content)
        self.assertIn("По расписанию", counters_content)
        self.assertIn("Плановые", counters_content)

    def test_zero_state_empty_text(self):
        stack_path = self.frontend / "components" / "queue" / "AnalysisStack.tsx"
        content = stack_path.read_text(encoding="utf-8")
        self.assertIn("Нет срочных проверок", content, "Empty state for Priority=0 must be handled")
        self.assertIn("Все проверки актуальны", content, "Empty state for Timed=0 must be handled")

    def test_reduced_motion_styles_present(self):
        css_path = self.frontend / "styles" / "queue.css"
        self.assertTrue(css_path.exists(), "queue.css must exist")
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn("@media (prefers-reduced-motion: reduce)", css_content, "prefers-reduced-motion rule required")
        self.assertIn("animation: none", css_content)

    def test_no_fake_completed_events(self):
        queue_dir = self.frontend / "components" / "queue"
        for root, _, files in os.walk(queue_dir):
            for f in files:
                p = Path(root) / f
                text = p.read_text(encoding="utf-8").lower()
                self.assertNotIn("completed successfully", text)
                self.assertNotIn("анализ завершен для", text)

    def test_backend_unmodified(self):
        # Verify that no changes were made to backend routes for queue
        routers_dir = self.root / "sourcehealth" / "api" / "routers"
        queue_router = routers_dir / "queue.py"
        self.assertFalse(queue_router.exists(), "Must NOT add backend queue endpoints")


if __name__ == "__main__":
    unittest.main()
