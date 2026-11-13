import os
import tempfile
import unittest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.database import _run_external_scholarly_analysis_migration
from app.extensions import db
from app.models import (
    Comparison,
    Document,
    ExternalComparisonResult,
    ExternalMatchedPassage,
    User,
    Workspace,
)
from app.reference_models import ReferenceEntry
from app.acquisition_models import ScholarlyRecord


class RetiredReferenceConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-retired-reference-features"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class RetiredReferenceFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        RetiredReferenceConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(RetiredReferenceConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.admin = User(
            first_name="Admin",
            last_name="Test",
            full_name="Admin Test",
            email="admin@example.test",
            password_hash=generate_password_hash("test-password-123"),
            role="admin",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(self.admin)
        db.session.commit()
        self.client = self.app.test_client()
        response = self.client.post("/api/auth/login", json={
            "email": self.admin.email,
            "password": "test-password-123",
        })
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def test_reference_bank_and_acquisition_routes_are_not_exposed(self):
        paths = (
            "/api/admin/references",
            "/api/admin/acquisition",
            "/api/reference-library",
            "/api/workspace/references",
        )
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, (path, response.get_json()))

    def test_legacy_reference_and_acquisition_records_are_retained(self):
        workspace = Workspace(
            name="Historical shared workspace",
            workspace_type="shared",
            status="active",
            owner_user_id=self.admin.user_id,
        )
        db.session.add(workspace)
        db.session.flush()
        document = Document(
            user_id=self.admin.user_id,
            title="Historical reference record",
            original_filename="historical.txt",
            storage_path="historical.txt",
            file_type="txt",
            document_type="reference",
            extracted_text="Historical source text retained for audit compatibility.",
            file_hash="a" * 64,
            visibility_scope="platform",
            processing_status="processed",
        )
        db.session.add(document)
        db.session.flush()
        entry = ReferenceEntry(
            document_id=document.document_id,
            scope="global",
            scope_key="global",
            status="active",
            provenance_type="legacy_platform_reference",
            created_by_user_id=self.admin.user_id,
        )
        record = ScholarlyRecord(
            canonical_key="legacy:" + ("b" * 64),
            title="Historical scholarly metadata",
            primary_provider="openalex",
            provider_ids_json="[]",
            status="metadata_only",
        )
        db.session.add_all([entry, record])
        db.session.commit()

        _run_external_scholarly_analysis_migration(self.app)

        db.session.refresh(entry)
        db.session.refresh(record)
        self.assertEqual(entry.status, "archived")
        self.assertEqual(record.status, "retired")
        self.assertIsNotNone(db.session.get(ReferenceEntry, entry.entry_id))
        self.assertIsNotNone(db.session.get(ScholarlyRecord, record.record_id))
        self.assertIsNotNone(db.session.get(Document, document.document_id))

    def test_external_report_schema_stores_only_short_evidence_excerpts(self):
        workspace = Workspace(
            name="Evidence workspace",
            workspace_type="shared",
            status="active",
            owner_user_id=self.admin.user_id,
        )
        db.session.add(workspace)
        db.session.flush()
        submitted = Document(
            user_id=self.admin.user_id,
            title="Submitted",
            original_filename="submitted.txt",
            storage_path="submitted.txt",
            file_type="txt",
            document_type="submission",
            extracted_text="Submitted content " * 40,
            file_hash="c" * 64,
            workspace_id=workspace.workspace_id,
            visibility_scope="private",
            processing_status="processed",
        )
        db.session.add(submitted)
        db.session.flush()
        comparison = Comparison(
            submitted_document_id=submitted.document_id,
            user_id=self.admin.user_id,
            workspace_id=workspace.workspace_id,
            status="completed",
            external_search_status="completed",
        )
        db.session.add(comparison)
        db.session.flush()
        source = ExternalComparisonResult(
            comparison_id=comparison.comparison_id,
            provider="openalex",
            title="External source title",
            authors_json='["A. Author"]',
            source_url="https://example.org/record",
            full_text_url="https://example.org/source.pdf",
            license_name="CC BY 4.0",
            exact_ngram_coverage=12.5,
            composite_similarity=12.5,
        )
        db.session.add(source)
        db.session.flush()
        passage = ExternalMatchedPassage(
            external_result_id=source.external_result_id,
            submitted_start=0,
            submitted_end=20,
            matched_text="A short matched submitted passage",
            source_excerpt="A short matched source excerpt",
            match_method="exact_ngram",
            match_score=100,
        )
        db.session.add(passage)
        db.session.commit()

        columns = set(ExternalComparisonResult.__table__.columns.keys())
        self.assertNotIn("full_text", columns)
        self.assertNotIn("extracted_text", columns)
        self.assertLessEqual(len(passage.source_excerpt), 350)
        self.assertEqual(ExternalMatchedPassage.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
