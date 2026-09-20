"""Контракт рейтинга: популярность не подменяет качество или неизвестные данные."""

import unittest

from sourcehealth.integrations.sourcecraft.collectors import repository_likes


class RepositoryRatingTests(unittest.TestCase):
    def test_sparse_reactions_and_rating_are_not_likes(self):
        self.assertEqual(repository_likes({"value": 5, "percentile": 13, "reaction_counts": [
            {"type": "positive_high", "count": "1"}]}), 0)
        self.assertEqual(repository_likes({"reaction_counts": [
            {"type": "future_reaction", "count": "invalid"},
            {"type": "positive_low", "count": "17"}]}), 17)

    def test_invalid_ratings(self):
        for rating in (None, {}, {"reaction_counts": None}, {"reaction_counts": [None]}):
            with self.subTest(rating=rating):
                self.assertIsNone(repository_likes(rating))
        for count in (True, -1, 1.5, "-1", "+1", "1.0", "1e2", "", "2147483648", "9" * 100):
            with self.subTest(count=count):
                self.assertIsNone(repository_likes({"reaction_counts": [{"type": "positive_low", "count": count}]}))
        self.assertIsNone(repository_likes({"reaction_counts": [
            {"type": "positive_low", "count": "0"}, {"type": "positive_low", "count": "1"}]}))

    def test_explicit_empty_counters_and_zero(self):
        self.assertEqual(repository_likes({"reaction_counts": []}), 0)
        self.assertEqual(repository_likes({"reaction_counts": [{"type": "positive_low", "count": "0"}]}), 0)
