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
        self.assertEqual(
            providers._normalise_license("cc-by-4.0"),
            ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
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
        with providers._DISCOVERY_CACHE_LOCK:
            providers._DISCOVERY_CACHE.clear()
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
        self.assertEqual(len(result["providers"]), len(providers.DISCOVERY_FUNCTIONS) + 1)
        self.assertIn("unpaywall", result["providers"])
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


    def test_openaire_parser_normalises_metadata_and_only_uses_exact_licence(self):
        payload = {
            "header": {"numFound": 1},
            "results": [{
                "id": "openaire-record-1",
                "mainTitle": "A study of open scholarly infrastructure",
                "publicationDate": "2024-06-01",
                "pids": [{"scheme": "doi", "value": "10.1234/OPEN"}],
                "authors": [{"fullName": "A. Researcher"}],
                "instances": [{
                    "license": "https://creativecommons.org/licenses/by/4.0/",
                    "urls": ["https://repository.example.org/article.pdf"],
                }],
            }],
        }
        with patch.object(providers, "_json_request", return_value=payload):
            state = SimpleNamespace(page=1, total_available=None, exhausted=False)
            records = providers._discover_openaire("open scholarly infrastructure", 5, state)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["provider"], "openaire")
        self.assertEqual(records[0]["doi"], "10.1234/open")
        self.assertEqual(records[0]["license_name"], "CC BY 4.0")
        self.assertEqual(records[0]["full_text_format"], "pdf")

    def test_unpaywall_unversioned_cc_by_does_not_authorise_automatic_retrieval(self):
        candidate = {
            "doi": "10.1234/example",
            "title": "Example scholarly work",
            "provider": "crossref",
            "license_name": None,
            "full_text_url": None,
        }
        response = {
            "best_oa_location": {
                "license": "cc-by",
                "url_for_pdf": "https://repository.example.org/article.pdf",
                "url_for_landing_page": "https://repository.example.org/article",
                "version": "publishedVersion",
            }
        }
        with patch.object(providers, "_json_request", return_value=response):
            status = providers._enrich_with_unpaywall([candidate], "contact@example.org")
        self.assertEqual(status["queries_succeeded"], 1)
        self.assertEqual(candidate.get("license_name"), None)
        self.assertEqual(candidate.get("full_text_url"), None)
        self.assertEqual(candidate.get("rights_status"), "review_required")

    def test_unpaywall_versioned_cc_by_can_supply_a_permitted_pdf_location(self):
        candidate = {"doi": "10.1234/example", "title": "Example", "provider": "crossref"}
        response = {"best_oa_location": {
            "license": "cc-by-4.0",
            "url_for_pdf": "https://repository.example.org/article.pdf",
            "url_for_landing_page": "https://repository.example.org/article",
            "version": "publishedVersion",
        }}
        with patch.object(providers, "_json_request", return_value=response):
            status = providers._enrich_with_unpaywall([candidate], "contact@example.org")
        self.assertEqual(status["records_enriched"], 1)
        self.assertEqual(candidate["license_name"], "CC BY 4.0")
        self.assertEqual(candidate["full_text_format"], "pdf")

    def test_metadata_cache_returns_copy_and_does_not_mutate_cached_record(self):
        calls = []
        def fake_search(query, limit, state):
            calls.append(query)
            return [{"title": "Cached source"}]
        first, hit_first = providers._cached_provider_search(
            "cache-test", "cache query", 5, fake_search, 300
        )
        first[0]["title"] = "mutated caller copy"
        second, hit_second = providers._cached_provider_search(
            "cache-test", "cache query", 5, fake_search, 300
        )
        self.assertFalse(hit_first)
        self.assertTrue(hit_second)
        self.assertEqual(second[0]["title"], "Cached source")
        self.assertEqual(len(calls), 1)

    def test_process_wide_executor_is_reused(self):
        first = providers._shared_executor("test-pool", 2)
        second = providers._shared_executor("test-pool", 2)
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
