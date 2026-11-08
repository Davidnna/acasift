import unittest

from app.services.similarity_service import find_ngram_matches


class NgramMatchingTests(unittest.TestCase):
    def test_exact_passage_is_detected(self):
        query = "Academic integrity requires students to acknowledge the original source."
        reference = "Academic integrity requires students to acknowledge the original source in their work."
        result = find_ngram_matches(query, reference, n=4)
        self.assertGreater(result["matched_count"], 0)
        self.assertGreater(result["coverage"], 0)
        self.assertTrue(result["passages"])

    def test_unrelated_text_has_no_matching_ngrams(self):
        query = "Database systems organise information using structured relational tables."
        reference = "Photosynthesis converts light energy into chemical energy in green plants."
        result = find_ngram_matches(query, reference, n=4)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["coverage"], 0.0)

    def test_short_text_uses_smaller_ngram(self):
        query = "machine learning"
        reference = "machine learning supports pattern recognition"
        result = find_ngram_matches(query, reference, n=5)
        self.assertGreater(result["matched_count"], 0)


if __name__ == "__main__":
    unittest.main()
