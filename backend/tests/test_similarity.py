import unittest
from types import SimpleNamespace

from app.services.similarity_service import (
    compare_against_repository,
    find_ngram_matches,
    token_spans,
)


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
        self.assertEqual(result["passages"], [])

    def test_short_text_uses_bigram_instead_of_uninformative_unigram(self):
        query = "machine learning"
        reference = "machine learning supports pattern recognition"
        result = find_ngram_matches(query, reference, n=5)
        self.assertEqual(result["effective_ngram_size"], 2)
        self.assertGreater(result["matched_count"], 0)

    def test_single_token_does_not_count_as_phrase_overlap(self):
        result = find_ngram_matches("database", "database systems", n=5)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["effective_ngram_size"], 0)

    def test_case_and_punctuation_differences_preserve_original_offsets(self):
        query = "INFORMATION SYSTEMS organise data, support decisions and coordinate institutional processes."
        reference = "Information systems organise data support decisions and coordinate institutional processes."
        result = find_ngram_matches(query, reference, n=5)
        self.assertEqual(result["coverage"], 100.0)
        self.assertEqual(len(result["passages"]), 1)
        passage = result["passages"][0]
        self.assertEqual(
            query[passage["submitted_start"]:passage["submitted_end"]],
            passage["matched_text"],
        )
        self.assertTrue(passage["matched_text"].startswith("INFORMATION SYSTEMS"))

    def test_adjacent_ngrams_merge_using_token_alignment(self):
        query = "A copied passage contains several consecutive words, with punctuation between some terms."
        reference = "A copied passage contains several consecutive words with punctuation between some terms."
        result = find_ngram_matches(query, reference, n=5)
        self.assertEqual(len(result["passages"]), 1)
        self.assertIn("punctuation between some terms", result["passages"][0]["matched_text"])

    def test_disjoint_matches_remain_separate_passages(self):
        first = "Supervised learning classifies documents based on labelled examples"
        second = "The technique compares word sequences across reference documents to identify repeated passages"
        query = f"{first}. A separate section discusses unrelated background material. {second}."
        reference = f"{first}. Additional reference content appears here. {second}."
        result = find_ngram_matches(query, reference, n=5)
        self.assertGreaterEqual(len(result["passages"]), 2)
        joined = " ".join(item["matched_text"] for item in result["passages"])
        self.assertIn("Supervised learning", joined)
        self.assertIn("compares word sequences", joined)

    def test_match_count_counts_each_query_window_not_unique_gram_types(self):
        phrase = "The system stores document metadata and extracted text"
        query = f"{phrase}. {phrase}. Unrelated coastal sediment patterns appear here."
        reference = phrase + "."
        result = find_ngram_matches(query, reference, n=5)
        phrase_token_count = len(token_spans(phrase))
        expected_matched_windows = 2 * (phrase_token_count - 5 + 1)
        self.assertEqual(result["matched_count"], expected_matched_windows)
        self.assertGreater(result["total_count"], result["matched_count"])
        self.assertLess(result["coverage"], 100.0)

    def test_unicode_compatibility_normalisation(self):
        query = "The ﬁnal analysis compares repeated word sequences against curated reference documents."
        reference = "The final analysis compares repeated word sequences against curated reference documents."
        result = find_ngram_matches(query, reference, n=5)
        self.assertEqual(result["coverage"], 100.0)
        self.assertTrue(result["passages"])

    def test_token_spans_retain_offsets(self):
        text = "A  ﬁnal result"
        tokens = token_spans(text)
        self.assertEqual(tokens[1][0], "final")
        self.assertEqual(text[tokens[1][1]:tokens[1][2]], "ﬁnal")

    def test_empty_inputs_return_zero_metrics(self):
        result = find_ngram_matches("", "some reference text", n=5)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["total_count"], 0)
        self.assertEqual(result["coverage"], 0.0)


class RepositoryComparisonTests(unittest.TestCase):
    def test_repository_results_are_ranked_by_similarity(self):
        exact = SimpleNamespace(extracted_text="Database systems organise records into structured relational tables.", title="Exact")
        unrelated = SimpleNamespace(extracted_text="Photosynthesis converts light energy into chemical energy.", title="Unrelated")
        results = compare_against_repository(
            "Database systems organise records into structured relational tables.",
            [unrelated, exact],
            ngram_size=5,
        )
        self.assertEqual(results[0]["reference_document"].title, "Exact")
        self.assertGreater(results[0]["cosine_similarity"], results[1]["cosine_similarity"])

    def test_empty_repository_returns_no_results(self):
        self.assertEqual(compare_against_repository("some text", []), [])


if __name__ == "__main__":
    unittest.main()
