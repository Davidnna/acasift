import io
import os
import tempfile
import unittest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.database import _run_reference_architecture_migration
from app.extensions import db
from app.models import Comparison, ComparisonResult, Document, User, Workspace, WorkspaceMembership
from app.services.reference_service import register_reference_entry, resolve_reference_sources
from app.services.workspace_service import ensure_personal_workspace
from app.submission_models import DocumentSubmission, SubmissionRequest
from app.reference_models import ReferenceEntry


class ReferenceConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-reference-architecture-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ReferenceArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        ReferenceConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(ReferenceConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.owner = self._make_user("owner@example.test", role="admin")
        self.member = self._make_user("member@example.test")
        self.other = self._make_user("other@example.test")
        db.session.flush()
        self.owner_personal = ensure_personal_workspace(self.owner)
        self.member_personal = ensure_personal_workspace(self.member)
        self.other_personal = ensure_personal_workspace(self.other)

        self.shared = Workspace(
            name="Shared Research Group",
            workspace_type="shared",
            status="active",
            owner_user_id=self.owner.user_id,
        )
        db.session.add(self.shared)
        db.session.flush()
        db.session.add_all([
            WorkspaceMembership(workspace_id=self.shared.workspace_id, user_id=self.owner.user_id, role="owner", status="active"),
            WorkspaceMembership(workspace_id=self.shared.workspace_id, user_id=self.member.user_id, role="member", status="active"),
        ])
        db.session.commit()

        self.owner_client = self._login(self.owner)
        self.member_client = self._login(self.member)
        with self.owner_client.session_transaction() as session:
            session["active_workspace_id"] = self.owner_personal.workspace_id
        with self.member_client.session_transaction() as session:
            session["active_workspace_id"] = self.member_personal.workspace_id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, email, role="user"):
        user = User(
            first_name=email.split("@")[0],
            last_name="Test",
            full_name=email.split("@")[0].title(),
            email=email,
            password_hash=generate_password_hash("test-password-123"),
            role=role,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        return user

    def _login(self, user):
        client = self.app.test_client()
        response = client.post("/api/auth/login", json={
            "email": user.email,
            "password": "test-password-123",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        return client

    def _document(self, owner, title, document_type="reference", workspace_id=None, visibility_scope="private", fingerprint=None):
        document = Document(
            user_id=owner.user_id,
            title=title,
            original_filename=f"{title}.txt",
            storage_path=f"{title}.txt",
            file_type="txt",
            document_type=document_type,
            extracted_text=f"Unique source text for {title} with enough words to compare reliably.",
            file_hash=fingerprint or (title.lower().replace(" ", "-") + "0" * 64)[:64],
            workspace_id=workspace_id,
            visibility_scope=visibility_scope,
            processing_status="processed",
        )
        db.session.add(document)
        db.session.flush()
        return document

    def test_personal_reference_upload_is_private_and_listed(self):
        response = self.owner_client.post(
            "/api/reference-library",
            data={"title": "Personal source", "document": (io.BytesIO(b"A private personal reference document."), "personal.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        entry = ReferenceEntry.query.one()
        self.assertEqual(entry.scope, "personal")
        self.assertEqual(entry.owner_user_id, self.owner.user_id)
        self.assertEqual(entry.status, "active")

        listing = self.owner_client.get("/api/reference-library")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.get_json()["entries"]), 1)

        with self.member_client.session_transaction() as session:
            session["active_workspace_id"] = self.member_personal.workspace_id
        other_listing = self.member_client.get("/api/reference-library")
        self.assertEqual(other_listing.status_code, 200)
        self.assertEqual(other_listing.get_json()["entries"], [])

    def test_shared_reference_requires_permission_confirmation(self):
        with self.owner_client.session_transaction() as session:
            session["active_workspace_id"] = self.shared.workspace_id
        denied = self.owner_client.post(
            "/api/reference-library",
            data={"title": "Shared source", "document": (io.BytesIO(b"Shared reference text."), "shared.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(denied.status_code, 400)

        accepted = self.owner_client.post(
            "/api/reference-library",
            data={
                "title": "Shared source",
                "permission_confirmed": "yes",
                "document": (io.BytesIO(b"Shared reference text."), "shared.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(accepted.status_code, 201, accepted.get_json())
        entry = ReferenceEntry.query.one()
        self.assertEqual(entry.scope, "workspace")
        self.assertTrue(entry.rights_verified)

    def test_global_reference_requires_rights_basis_and_attestation(self):
        denied = self.owner_client.post(
            "/api/admin/references",
            data={"title": "Global source", "document": (io.BytesIO(b"Global reference text."), "global.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(denied.status_code, 400)

        accepted = self.owner_client.post(
            "/api/admin/references",
            data={
                "title": "Global source",
                "rights_basis": "public_domain",
                "rights_confirmed": "yes",
                "source_url": "https://example.org/public-source",
                "document": (io.BytesIO(b"Global reference text."), "global.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(accepted.status_code, 201, accepted.get_json())
        entry = ReferenceEntry.query.one()
        self.assertEqual(entry.scope, "global")
        self.assertTrue(entry.rights_verified)
        self.assertEqual(entry.status, "active")

    def test_resolver_keeps_reference_scopes_private_and_separate(self):
        global_doc = self._document(self.owner, "Global source", visibility_scope="platform")
        personal_doc = self._document(self.owner, "Owner personal source", workspace_id=self.owner_personal.workspace_id)
        other_personal_doc = self._document(self.other, "Other personal source", workspace_id=self.other_personal.workspace_id)
        workspace_doc = self._document(self.owner, "Workspace source", workspace_id=self.shared.workspace_id, visibility_scope="workspace")
        unverified_workspace_doc = self._document(self.owner, "Unverified workspace source", workspace_id=self.shared.workspace_id, visibility_scope="workspace")

        register_reference_entry(global_doc, "global", self.owner.user_id, status="active", rights_basis="public_domain", rights_verified=True)
        register_reference_entry(personal_doc, "personal", self.owner.user_id, owner_user_id=self.owner.user_id, status="active", rights_basis="personal_use_only")
        register_reference_entry(other_personal_doc, "personal", self.other.user_id, owner_user_id=self.other.user_id, status="active", rights_basis="personal_use_only")
        register_reference_entry(workspace_doc, "workspace", self.owner.user_id, workspace_id=self.shared.workspace_id, status="active", rights_basis="workspace_permission", rights_verified=True)
        register_reference_entry(unverified_workspace_doc, "workspace", self.owner.user_id, workspace_id=self.shared.workspace_id, status="review_required", rights_basis="legacy_unverified", rights_verified=False)
        db.session.commit()

        personal_sources = resolve_reference_sources(
            user_id=self.owner.user_id,
            workspace_id=self.owner_personal.workspace_id,
        )
        personal_titles = {document.title for document, _scope in personal_sources}
        self.assertEqual(personal_titles, {"Global source", "Owner personal source"})

        shared_sources = resolve_reference_sources(
            user_id=self.member.user_id,
            workspace_id=self.shared.workspace_id,
        )
        shared_titles = {document.title for document, _scope in shared_sources}
        self.assertEqual(shared_titles, {"Global source", "Workspace source"})
        self.assertNotIn("Owner personal source", shared_titles)
        self.assertNotIn("Other personal source", shared_titles)
        self.assertNotIn("Unverified workspace source", shared_titles)

    def test_request_comparison_resolves_all_scopes_and_excludes_contributors_own_documents(self):
        global_doc = self._document(self.owner, "Request global source", visibility_scope="platform")
        workspace_doc = self._document(self.owner, "Request workspace source", workspace_id=self.shared.workspace_id, visibility_scope="workspace")
        own_doc = self._document(self.member, "Member own submission", document_type="submission", workspace_id=self.shared.workspace_id)
        peer_doc = self._document(self.other, "Peer submission", document_type="submission", workspace_id=self.shared.workspace_id)
        request_record = SubmissionRequest(
            workspace_id=self.shared.workspace_id,
            title="Request source scope test",
            status="open",
            accepted_file_types=["txt"],
            max_file_size_mb=15,
            created_by_user_id=self.owner.user_id,
        )
        db.session.add(request_record)
        db.session.flush()
        own_submission = DocumentSubmission(
            request_id=request_record.request_id,
            contributor_user_id=self.member.user_id,
            document_id=own_doc.document_id,
            attempt_number=1,
            status="analysed",
        )
        peer_submission = DocumentSubmission(
            request_id=request_record.request_id,
            contributor_user_id=self.other.user_id,
            document_id=peer_doc.document_id,
            attempt_number=1,
            status="analysed",
        )
        db.session.add_all([own_submission, peer_submission])
        register_reference_entry(global_doc, "global", self.owner.user_id, status="active", rights_basis="public_domain", rights_verified=True)
        register_reference_entry(workspace_doc, "workspace", self.owner.user_id, workspace_id=self.shared.workspace_id, status="active", rights_basis="workspace_permission", rights_verified=True)
        register_reference_entry(own_doc, "request", self.member.user_id, owner_user_id=self.member.user_id, request_id=request_record.request_id, status="active", rights_basis="request_scoped_submission")
        register_reference_entry(peer_doc, "request", self.other.user_id, owner_user_id=self.other.user_id, request_id=request_record.request_id, status="active", rights_basis="request_scoped_submission")
        db.session.commit()

        sources = resolve_reference_sources(
            user_id=self.member.user_id,
            workspace_id=self.shared.workspace_id,
            request_id=request_record.request_id,
            exclude_document_id=own_doc.document_id,
            exclude_contributor_user_id=self.member.user_id,
        )
        source_map = {document.title: scope for document, scope in sources}
        self.assertEqual(source_map, {
            "Request global source": "global",
            "Request workspace source": "workspace",
            "Peer submission": "request",
        })
        self.assertNotIn("Member own submission", source_map)

    def test_legacy_reference_migration_is_idempotent_and_quarantines_unverified_global(self):
        global_doc = self._document(self.owner, "Legacy global", visibility_scope="platform")
        workspace_doc = self._document(self.owner, "Legacy shared", workspace_id=self.shared.workspace_id, visibility_scope="workspace")
        personal_doc = self._document(self.owner, "Legacy personal", workspace_id=self.owner_personal.workspace_id, visibility_scope="private")
        db.session.commit()

        _run_reference_architecture_migration(self.app)
        entries = {entry.document_id: entry for entry in ReferenceEntry.query.all()}
        self.assertEqual(entries[global_doc.document_id].scope, "global")
        self.assertEqual(entries[global_doc.document_id].status, "review_required")
        self.assertEqual(entries[workspace_doc.document_id].scope, "workspace")
        self.assertEqual(entries[workspace_doc.document_id].status, "review_required")
        self.assertEqual(entries[personal_doc.document_id].scope, "personal")
        self.assertEqual(entries[personal_doc.document_id].status, "active")

        first_count = ReferenceEntry.query.count()
        _run_reference_architecture_migration(self.app)
        self.assertEqual(ReferenceEntry.query.count(), first_count)

    def test_comparison_result_records_reference_scope(self):
        submitted = self._document(self.owner, "Submitted", document_type="submission", workspace_id=self.owner_personal.workspace_id)
        reference = self._document(self.owner, "Reference", visibility_scope="platform")
        comparison = Comparison(
            submitted_document_id=submitted.document_id,
            user_id=self.owner.user_id,
            workspace_id=self.owner_personal.workspace_id,
            status="completed",
        )
        db.session.add(comparison)
        db.session.flush()
        result = ComparisonResult(
            comparison_id=comparison.comparison_id,
            reference_document_id=reference.document_id,
            source_scope="global",
            cosine_similarity=12.5,
            matched_ngram_coverage=10.0,
            matched_ngram_count=2,
            total_query_ngrams=20,
        )
        db.session.add(result)
        db.session.commit()
        self.assertEqual(ComparisonResult.query.one().source_scope, "global")


if __name__ == "__main__":
    unittest.main()
