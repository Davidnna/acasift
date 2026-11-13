import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config import Config
from app import create_app
from app.services import scholarly_providers as providers


class ScholarlySearchConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-scholarly-search-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAX_EXTERNAL_SOURCES = 12
    MAX_EXTERNAL_DOWNLOADS = 4


class ScholarlyProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        ScholarlySearchConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(ScholarlySearchConfig)
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()
        self.temp_dir.cleanup()

    def test_targeted_queries_are_short_and_not_the_full_document(self):
        document = (
            "Community health nursing interventions and hypertension control outcomes.\\n"
            "This research examines blood pressure control in rural communities. "
            "Community health nursing programmes improve health education and follow-up. "
            "Hypertension control requires medication adherence and lifestyle modification. "
        ) * 20
        title = "Community Health Nursing and Hypertension Control Outcomes"
        queries = providers.targeted_queries(document, document_title=title)
        self.assertGreaterEqual(len(queries), 1)
        self.assertLessEqual(len(queries), 3)
        self.assertTrue(all(len(query) <= 180 for query in queries))
        self.assertEqual(queries[0], title)
        self.assertNotIn(document, queries)

    def test_reuse_licence_recognition_is_exact(self):
        self.assertEqual(
            providers._normalise_license("https://creativecommons.org/licenses/by/4.0/"),
            ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
        )
        self.assertEqual(
            providers._normalise_license("cc0-1.0"),
            ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        )
        self.assertEqual(providers._normalise_license("CC BY"), (None, "CC BY"))
        self.assertEqual(
            providers._normalise_license("CC BY-NC 4.0"),
            (None, "CC BY-NC 4.0"),
        )

    def test_source_links_must_be_https_and_must_not_contain_credentials(self):
        self.assertEqual(
            providers._safe_https_url("https://example.org/article"),
            "https://example.org/article",
        )
        self.assertIsNone(providers._safe_https_url("http://example.org/article"))
        self.assertIsNone(providers._safe_https_url("https://user:pass@example.org/article"))

    def test_private_network_hosts_are_rejected(self):
        with self.assertRaises(ValueError):
            providers._assert_public_host("127.0.0.1")

    def test_pdf_without_recognised_licence_is_not_retrieved(self):
        candidate = {
            "full_text_url": "https://example.org/article.pdf",
            "full_text_format": "pdf",
            "license_name": None,
        }
        with patch.object(providers, "_request_bytes") as request_bytes:
            with self.assertRaisesRegex(ValueError, "recognised reuse licence"):
                providers.fetch_permitted_full_text(candidate)
            request_bytes.assert_not_called()

    def test_all_scholarly_providers_are_searched_concurrently(self):
        calls = []

        def fake_provider(query, limit, state):
            calls.append((query, limit))
            return [{
                "provider": "mock",
                "provider_id": query,
                "title": f"Source for {query}",
                "authors": ["A. Author"],
                "year": 2025,
                "doi": None,
                "source_url": "https://example.org/record",
                "full_text_url": None,
                "full_text_format": None,
                "license_name": None,
                "license_url": None,
                "rights_status": "unknown",
            }]

        replacements = {key: fake_provider for key in providers.DISCOVERY_FUNCTIONS}
        with patch.dict(providers.DISCOVERY_FUNCTIONS, replacements):
            result = providers.discover_scholarly_sources(
                "A long enough document title about community health nursing and hypertension control. "
                "Community health nursing improves blood pressure control through education and adherence. " * 5,
                max_sources=24,
            )

        self.assertEqual(len(calls), len(providers.DISCOVERY_FUNCTIONS) * len(result["queries"]))
        self.assertEqual(len(result["providers"]), len(providers.DISCOVERY_FUNCTIONS))
        self.assertGreater(result["sources_discovered"], 0)

    def test_retrieved_source_text_is_returned_for_processing_not_saved_to_uploads(self):
        candidate = {
            "title": "Permitted source",
            "provider": "mock",
            "full_text_url": "https://example.org/article.pdf",
            "license_name": "CC BY 4.0",
            "full_text_format": "pdf",
        }
        extracted = {"text": "Temporary full text " * 100, "final_url": candidate["full_text_url"],
                     "license_name": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"}
        with patch.object(providers, "fetch_permitted_full_text", return_value=extracted):
            retrieved, failures = providers.retrieve_sources_concurrently([candidate], max_downloads=1)
        self.assertEqual(failures, [])
        self.assertEqual(len(retrieved), 1)
        self.assertIn("Temporary full text", retrieved[0][1]["text"])
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "uploads", "article.pdf")))


if __name__ == "__main__":
    unittest.main()
