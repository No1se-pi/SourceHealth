"""Unit and contract tests for Catalog / Search v2.

Tests topic classification, metadata normalization, search ranking,
reusable catalog query filtering, and statistical aggregations.
"""

import unittest

from sourcehealth.catalog.query import (
    CatalogFilters,
    clean_query_term,
    compute_median_and_quartiles,
)
from sourcehealth.catalog.topics import (
    ALL_TOPICS,
    TOPIC_CLASSIFIER_VERSION,
    classify_topics,
)
from sourcehealth.integrations.sourcecraft.validation import (
    normalize_description,
    normalize_logo_url,
    normalize_origin,
    normalize_repository_metadata,
)


class TopicClassifierTests(unittest.TestCase):
    def test_topic_classifier_version(self):
        self.assertEqual(TOPIC_CLASSIFIER_VERSION, "catalog-topic-v1")

    def test_all_topics_count(self):
        # Exactly 11 topics per specification
        expected_topics = {
            "bots",
            "web",
            "ml_data",
            "games",
            "education",
            "mobile",
            "devops",
            "security",
            "tools",
            "libraries",
            "other",
        }
        self.assertEqual(set(ALL_TOPICS), expected_topics)
        self.assertEqual(len(ALL_TOPICS), 11)

    def test_classify_topics_deterministic_and_sorted(self):
        # ML / Data
        topics = classify_topics("pytorch-wrapper", "A neural network transformer inference engine", "nlp-tools", "Python")
        self.assertIn("ml_data", topics)
        self.assertEqual(topics, sorted(topics))

        # Web
        topics = classify_topics("react-dashboard", "Modern frontend web UI components", "ui", "TypeScript")
        self.assertIn("web", topics)
        self.assertEqual(topics, sorted(topics))

        # Security
        topics = classify_topics("sast-scanner", "Static application security vulnerability analyzer", "sec-tools", "Go")
        self.assertIn("security", topics)

        # DevOps
        topics = classify_topics("k8s-operator", "Kubernetes cluster helm deployment manifests", "infra", "Go")
        self.assertIn("devops", topics)

        # Bots
        topics = classify_topics("telegram-reminder", "Telegram bot for chat notifications", "tg-bot", "Python")
        self.assertIn("bots", topics)

        # Education
        topics = classify_topics("cs101-homework", "University lecture tutorials and study practice tasks", "edu", "Python")
        self.assertIn("education", topics)

    def test_classify_topics_max_limit_and_fallback(self):
        # Empty text falls back to ['other']
        topics = classify_topics("xyz123", "", "", "")
        self.assertEqual(topics, ["other"])

        # Multiple matches capped at 5
        topics = classify_topics(
            "super-tool",
            "neural network frontend backend telegram bot kubernetes game unity security library",
            "infra",
            "Python",
        )
        self.assertLessEqual(len(topics), 5)
        self.assertEqual(topics, sorted(topics))
        for t in topics:
            self.assertIn(t, ALL_TOPICS)


class MetadataNormalizationTests(unittest.TestCase):
    def test_description_normalization(self):
        desc = normalize_description("  Hello\x00\x08   world!\nThis is a test.  ")
        self.assertEqual(desc, "Hello world! This is a test.")

    def test_description_length_limit(self):
        long_str = "A" * 600
        desc = normalize_description(long_str)
        self.assertIsNotNone(desc)
        self.assertEqual(len(desc), 500)

    def test_logo_url_allowlist_and_https(self):
        # Allowed HTTPS domains
        valid_logo = "https://storage.yandexcloud.net/sourcehealth-logos/avatar.png"
        self.assertEqual(normalize_logo_url(valid_logo), valid_logo)

        sc_logo = "https://sourcecraft.dev/org/logo.jpg"
        self.assertEqual(normalize_logo_url(sc_logo), sc_logo)

        # Disallowed HTTP
        self.assertIsNone(normalize_logo_url("http://storage.yandexcloud.net/avatar.png"))

        # Disallowed domain
        self.assertIsNone(normalize_logo_url("https://malicious-site.com/image.png"))

    def test_origin_detection(self):
        self.assertEqual(normalize_origin({"parent": {"id": "p1"}}), "fork")
        self.assertEqual(normalize_origin({"migration_source": "github"}), "migrated")
        self.assertEqual(normalize_origin({"migrated_from": "gitlab"}), "migrated")
        self.assertEqual(normalize_origin({}), "native")

    def test_normalize_repository_metadata_full(self):
        raw = {
            "id": "repo-42",
            "slug": "awesome-app",
            "organization": {"slug": "cool-org"},
            "visibility": "public",
            "default_branch": "main",
            "description": "  A cool \x00 app! ",
            "logo": {"url": "https://avatars.mds.yandex.net/get-avatar/123"},
            "parent": {"id": "upstream"},
            "project": {"slug": "core-platform"},
            "language": {"name": "Rust"},
        }
        meta = normalize_repository_metadata(raw, require_public=True)
        self.assertEqual(meta.sourcecraft_id, "repo-42")
        self.assertEqual(meta.organization_slug, "cool-org")
        self.assertEqual(meta.repository_slug, "awesome-app")
        self.assertEqual(meta.canonical_url, "https://sourcecraft.dev/cool-org/awesome-app")
        self.assertEqual(meta.description, "A cool app!")
        self.assertEqual(meta.logo_url, "https://avatars.mds.yandex.net/get-avatar/123")
        self.assertEqual(meta.origin, "fork")
        self.assertEqual(meta.project_slug, "core-platform")
        self.assertEqual(meta.language, "Rust")


class CatalogQueryLogicTests(unittest.TestCase):
    def test_clean_query_term_urls_and_terms(self):
        self.assertIsNone(clean_query_term(None))
        self.assertIsNone(clean_query_term(""))
        self.assertIsNone(clean_query_term("   "))

        # SourceCraft full URL stripping
        self.assertEqual(
            clean_query_term("https://sourcecraft.dev/my-team/my-service"),
            "my-team/my-service",
        )
        self.assertEqual(
            clean_query_term("http://api.sourcecraft.tech/core/infra/"),
            "core/infra",
        )

        # Regular search terms
        self.assertEqual(clean_query_term("  fastapi   backend "), "fastapi   backend")

    def test_compute_median_and_quartiles_continuous(self):
        # Empty list
        med, q1, q3 = compute_median_and_quartiles([])
        self.assertIsNone(med)
        self.assertIsNone(q1)
        self.assertIsNone(q3)

        # Single value
        med, q1, q3 = compute_median_and_quartiles([80.0])
        self.assertEqual(med, 80.0)
        self.assertEqual(q1, 80.0)
        self.assertEqual(q3, 80.0)

        # Even number: [10, 20, 30, 40]
        # median: 25.0, q1: 17.5, q3: 32.5
        med, q1, q3 = compute_median_and_quartiles([10.0, 20.0, 30.0, 40.0])
        self.assertEqual(med, 25.0)
        self.assertEqual(q1, 17.5)
        self.assertEqual(q3, 32.5)

        # Odd number: [10, 20, 30, 40, 50]
        med, q1, q3 = compute_median_and_quartiles([10.0, 20.0, 30.0, 40.0, 50.0])
        self.assertEqual(med, 30.0)
        self.assertEqual(q1, 20.0)
        self.assertEqual(q3, 40.0)

    def test_catalog_filters_cache_key(self):
        f1 = CatalogFilters(q="test", language="Go", limit=20, offset=0)
        f2 = CatalogFilters(q="test", language="Go", limit=50, offset=100)
        # Limit and offset should not change stats cache key
        self.assertEqual(f1.cache_key(), f2.cache_key())

        f3 = CatalogFilters(q="test", language="Rust")
        self.assertNotEqual(f1.cache_key(), f3.cache_key())


if __name__ == "__main__":
    unittest.main()
