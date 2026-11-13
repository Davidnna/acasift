import os
import tempfile
import unittest
from unittest.mock import patch

from config import Config
from app import create_app
from app.services.external_similarity_service import compare_with_live_scholarly_sources


class ExternalSimilarityConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-external-similarity-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAX_EXTERNAL_SOURCES = 12
    MAX_EXTERNAL_DOWNLOADS = 4


class ExternalSimilarityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        ExternalSimilarityConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(ExternalSimilarityConfig)
        self.context = self.app.app_context()
        self.context.push()
        os.environ["ENABLE_LOCAL_SEMANTIC"] = "false"

    def tearDown(self):
        self.context.pop()
        self.temp_dir.cleanup()

    def test_report_contains_short_evidence_but_not_retrieved_full_text(self):
        submitted = (
            "Community health nursing interventions improve hypertension control "
            "through patient education, medication adherence and regular follow up. "
        ) * 5
        source_text = (
            "Community health nursing interventions improve hypertension control "
            "through patient education, medication adherence and regular follow up. "
        ) * 8
        mock_run = {
            "status": "completed",
            "queries": ["community hypertension nursing"],
            "providers": {
                "openalex": {
                    "queries_attempted": 1,
                    "queries_succeeded": 1,
                    "records_returned": 1,
                    "errors": [],
                }
            },
            "sources_discovered": 1,
            "sources_downloaded": 1,
            "sources_compared": 1,
            "retrieval_failures": [],
            "retrieved_sources": [(
                {
                    "provider": "openalex",
                    "providers": ["openalex"],
                    "provider_id": "W123",
                    "title": "Community Hypertension Nursing",
                    "authors": ["A. Researcher"],
                    "year": 2024,
                    "journal": "Public Health Journal",
                    "doi": "10.1234/example",
                    "source_url": "https://example.org/record",
                },
                {
                    "text": source_text,
                    "final_url": "https://example.org/fulltext.pdf",
                    "license_name": "CC BY 4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                },
            )],
        }

        with patch(
            "app.services.external_similarity_service.run_live_scholarly_discovery",
            return_value=mock_run,
        ):
            report = compare_with_live_scholarly_sources(
                submitted,
                document_title="Community Health Nursing and Hypertension Control",
            )

        self.assertFalse(report["full_text_retained"])
        self.assertEqual(report["sources_compared"], 1)
        self.assertEqual(report["sources_with_matches"], 1)
        evidence = report["evidence"][0]
        self.assertNotIn("text", evidence)
        self.assertNotIn("abstract", evidence)
        self.assertTrue(evidence["source_url"].startswith("https://"))
        self.assertTrue(evidence["doi"])
        self.assertTrue(evidence["passages"])
        self.assertLessEqual(len(evidence["passages"][0]["source_excerpt"]), 350)
        self.assertLessEqual(len(evidence["passages"][0]["matched_text"]), 350)


if __name__ == "__main__":
    unittest.main()
