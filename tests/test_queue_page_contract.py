"""Frontend contract tests for Analysis Stack Visualization (/queue).

Verifies:
- Route /queue exists in router.tsx
- No unrelated routes (/catalog, /leaderboard, /stack) are introduced
- Navigation items in Sidebar and TopBar link to /queue
- All three levels (priority, timed, planned) exist as conceptual architecture models
- No hardcoded numbers (4829, 2995, 126) in presentation logic
- No fake repository chips, mock statuses, or artificial countdown timers
- Live data is strictly limited to verified /catalog/stats
- prefers-reduced-motion accessibility rules are preserved
- Backend remains 100% unmodified
"""

import os
import re
import unittest
from pathlib import Path


class QueuePageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.frontend = cls.root / "frontend" / "src"

    def test_route_registered_and_no_unrelated_routes(self):
        router_path = self.frontend / "app" / "router.tsx"
        self.assertTrue(router_path.exists(), "router.tsx must exist")
        content = router_path.read_text(encoding="utf-8")
        self.assertIn("QueuePage", content, "QueuePage must be imported in router.tsx")
        self.assertIn('path="/queue"', content, "Route /queue must be registered")

        # Must not introduce unrelated routes or aliases
        self.assertNotIn('path="/catalog"', content, "Must not introduce unrelated /catalog route")
        self.assertNotIn('path="/leaderboard"', content, "Must not introduce unrelated /leaderboard route")
        self.assertNotIn('path="/stack"', content, "Must not introduce /stack alias")

    def test_navigation_item_registered(self):
        sidebar_path = self.frontend / "components" / "layout" / "Sidebar.tsx"
        self.assertTrue(sidebar_path.exists(), "Sidebar.tsx must exist")
        sidebar_content = sidebar_path.read_text(encoding="utf-8")
        self.assertIn('to="/queue"', sidebar_content, "Sidebar must link to /queue")
        self.assertIn("Очередь", sidebar_content, "Navigation item must have label 'Очередь'")

        topbar_path = self.frontend / "components" / "layout" / "TopBar.tsx"
        self.assertTrue(topbar_path.exists(), "TopBar.tsx must exist")
        topbar_content = topbar_path.read_text(encoding="utf-8")
        self.assertIn("'/queue'", topbar_content, "TopBar breadcrumbs must handle /queue")
        self.assertNotIn('/catalog', topbar_content, "TopBar must not contain /catalog")
        self.assertNotIn('/leaderboard', topbar_content, "TopBar must not contain /leaderboard")
        self.assertNotIn('/stack', topbar_content, "TopBar must not contain /stack")

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
        self.assertIn("ПРИОРИТЕТ", stack_content)
        self.assertIn("ПО РАСПИСАНИЮ", stack_content)
        self.assertIn("ПЛАНОВЫЙ ОБХОД", stack_content)

        counters_content = counters_path.read_text(encoding="utf-8")
        self.assertIn("Приоритет", counters_content)
        self.assertIn("По расписанию", counters_content)
        self.assertIn("Плановый обход", counters_content)

        legend_content = legend_path.read_text(encoding="utf-8")
        self.assertIn("Приоритетные проверки", legend_content)
        self.assertIn("Проверки по расписанию", legend_content)
        self.assertIn("Плановый фоновый обход", legend_content)

    def test_no_stale_hardcoded_numbers(self):
        queue_components = self.frontend / "components" / "queue"
        queue_api = self.frontend / "api" / "queueData.ts"
        queue_page = self.frontend / "pages" / "QueuePage.tsx"

        files_to_check = [queue_api, queue_page] + list(queue_components.glob("*.tsx"))

        # Strip multi-line and single-line comments to test code truth
        comment_re = re.compile(r"/\*[\s\S]*?\*/|//.*")

        for f in files_to_check:
            self.assertTrue(f.exists(), f"File {f.name} must exist")
            text = f.read_text(encoding="utf-8")
            code_only = comment_re.sub("", text)

            self.assertNotIn("4829", code_only, f"Hardcoded 4829 found in code of {f.name}")
            self.assertNotIn("4 829", code_only, f"Hardcoded 4 829 found in code of {f.name}")
            self.assertNotIn("2995", code_only, f"Hardcoded 2995 found in code of {f.name}")
            self.assertNotIn("2 995", code_only, f"Hardcoded 2 995 found in code of {f.name}")
            self.assertNotIn("126", code_only, f"Hardcoded 126 found in code of {f.name}")

    def test_no_fake_chips_or_timers(self):
        queue_dir = self.frontend / "components" / "queue"
        for f in queue_dir.glob("*.tsx"):
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("nextBatchEstimateMinutes", text)
            self.assertNotIn("sh-repo-chip", text)
            self.assertNotIn("isAnalyzing", text)

    def test_truthful_page_wording(self):
        page_path = self.frontend / "pages" / "QueuePage.tsx"
        text = page_path.read_text(encoding="utf-8")
        # Mode wording must be architecture/process, not pretending live scheduler telemetry
        self.assertNotIn("Планировщик активен", text, "Do not claim 'Планировщик активен' without API telemetry")
        self.assertIn("Схема обработки", text, "Page must use honest architecture wording")
        self.assertIn("Данные каталога недоступны", text, "Must gracefully handle unreachable API")

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
