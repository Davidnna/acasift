import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User
from app.acquisition_models import AcquisitionJob, AcquisitionSearchState, ScholarlyRecord
from app.services import acquisition_service as acquisition


class AcquisitionConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-acquisition-engine-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class AcquisitionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        AcquisitionConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(AcquisitionConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.admin = self._make_user("admin@example.test", "admin")
        self.member = self._make_user("member@example.test", "user")
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, email, role):
        user = User(
            first_name="Test",
            last_name="User",
            full_name="Test User",
            email=email,
            password_hash=generate_password_hash("test-password-123"),
            role=role,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.flush()
        return user

    def _login(self, email):
        client = self.app.test_client()
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": "test-password-123",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        return client

    def test_acquisition_search_fields_do_not_shadow_model_query_descriptor(self):
        self.assertIn("query", AcquisitionJob.__table__.columns)
        self.assertIn("query", AcquisitionSearchState.__table__.columns)
        self.assertTrue(callable(getattr(AcquisitionJob.query, "order_by", None)))
        self.assertTrue(callable(getattr(AcquisitionSearchState.query, "filter_by", None)))

    def test_pending_full_text_queue_uses_global_query_without_provider_argument(self):
        record = ScholarlyRecord(
            canonical_key="doi:" + ("a" * 64),
            title="Queued full-text publication",
            primary_provider="openalex",
            provider_ids_json="[]",
            full_text_url="https://example.org/article.pdf",
            full_text_format="pdf",
            license_name="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            rights_status="eligible",
            status="eligible",
            download_attempts=0,
        )
        db.session.add(record)
        db.session.commit()

        pending = acquisition._pending_full_text_records(5)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].record_id, record.record_id)

    def test_license_policy_accepts_exact_cc_by_and_cc0_only(self):
        self.assertEqual(
            acquisition._normalise_license("https://creativecommons.org/licenses/by/4.0/"),
            ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
        )
        self.assertEqual(
            acquisition._normalise_license("cc0-1.0"),
            ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        )
        self.assertEqual(acquisition._normalise_license("CC BY"), (None, "CC BY"))
        self.assertEqual(acquisition._normalise_license("CC BY-NC 4.0"), (None, "CC BY-NC 4.0"))

    def test_canonical_key_is_stable_and_fits_database_column(self):
        first = acquisition._canonical_key("10.1234/Very.Long.DOI", "Example title", 2024)
        second = acquisition._canonical_key("10.1234/very.long.doi", "Different title", 2020)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 80)

    def test_acquisition_endpoints_are_administrator_only(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/api/admin/acquisition").status_code, 401)
        member_client = self._login("member@example.test")
        self.assertEqual(member_client.get("/api/admin/acquisition").status_code, 403)
        admin_client = self._login("admin@example.test")
        response = admin_client.get("/api/admin/acquisition")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertIn("providers", payload)
        self.assertIn("jobs", payload)
        self.assertIn("searches", payload)
        self.assertIn("records", payload)
        self.assertIn("counts", payload)

    def test_metadata_only_discovery_is_persisted_and_search_is_resumable(self):
        def fake_discover(query, limit, state):
            state.offset += 1
            state.total_available = 2
            state.exhausted = False
            return [acquisition._normalised_record(
                "crossref",
                "10.1234/example.1",
                title="A Test Publication",
                authors=["A. Researcher"],
                year=2024,
                journal="Test Journal",
                doi="10.1234/example.1",
                source_url="https://example.org/article",
                license_value=None,
            )]

        with patch.dict(acquisition.DISCOVERY_FUNCTIONS, {"crossref": fake_discover}):
            job = acquisition.create_and_run_job(
                "crossref", "test publication", 10, self.admin.user_id
            )

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["discovered_count"], 1)
        self.assertEqual(ScholarlyRecord.query.count(), 1)
        self.assertEqual(AcquisitionSearchState.query.count(), 1)
        self.assertEqual(AcquisitionJob.query.count(), 1)
        self.assertEqual(AcquisitionSearchState.query.one().search_query, "test publication")
        self.assertEqual(AcquisitionJob.query.one().search_query, "test publication")
        record = ScholarlyRecord.query.one()
        self.assertEqual(record.status, "metadata_only")
        self.assertIsNone(record.document_id)

    def test_same_provider_and_query_reuses_pagination_state(self):
        state = AcquisitionSearchState(
            provider="crossref",
            query_hash=hashlib.sha256("test query".casefold().encode("utf-8")).hexdigest(),
            search_query="test query",
            offset=25,
            page=1,
            exhausted=False,
        )
        db.session.add(state)
        db.session.commit()

        def fake_discover(query, limit, current_state):
            self.assertEqual(current_state.offset, 25)
            current_state.offset += 10
            current_state.exhausted = True
            return []

        with patch.dict(acquisition.DISCOVERY_FUNCTIONS, {"crossref": fake_discover}):
            job = acquisition.create_and_run_job(
                "crossref", "test query", 10, self.admin.user_id
            )
        self.assertEqual(job["status"], "completed")
        self.assertEqual(AcquisitionSearchState.query.count(), 1)
        self.assertEqual(AcquisitionSearchState.query.one().offset, 35)


if __name__ == "__main__":
    unittest.main()
