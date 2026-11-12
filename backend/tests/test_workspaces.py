import os
import tempfile
import unittest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User, Workspace, WorkspaceMembership, Document
from app.submission_models import DocumentSubmission, SubmissionRequest


class WorkspaceConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-workspace-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        WorkspaceConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(WorkspaceConfig)
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.admin = self._make_user("admin@example.test", "Platform Admin")
        self.workspace = self._make_workspace(self.admin, "Research Group", "owner")
        db.session.commit()
        self.client.post("/api/auth/login", json={
            "email": "admin@example.test", "password": "admin-password-123",
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, email, name):
        first, last = name.split(" ", 1)
        user = User(
            first_name=first,
            last_name=last,
            full_name=name,
            email=email,
            password_hash=generate_password_hash("admin-password-123"),
            role="admin" if email.startswith("admin") else "user",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.flush()
        return user

    def _make_workspace(self, user, name, role="owner"):
        workspace = Workspace(
            name=name,
            workspace_type="shared",
            status="active",
            owner_user_id=user.user_id,
        )
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=workspace.workspace_id,
            user_id=user.user_id,
            role=role,
            status="active",
        ))
        db.session.flush()
        return workspace

    def test_workspace_list_contains_only_shared_workspaces(self):
        legacy = Workspace(
            name="Archived personal workspace",
            workspace_type="personal",
            status="archived",
            owner_user_id=self.admin.user_id,
        )
        db.session.add(legacy)
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=legacy.workspace_id,
            user_id=self.admin.user_id,
            role="owner",
            status="active",
        ))
        db.session.commit()

        payload = self.client.get("/api/workspaces").get_json()
        self.assertEqual(len(payload["workspaces"]), 1)
        self.assertEqual(payload["workspaces"][0]["type"], "shared")
        self.assertEqual(payload["active_workspace_id"], self.workspace.workspace_id)

    def test_user_without_a_shared_workspace_is_not_given_a_personal_workspace(self):
        other = self._make_user("other@example.test", "Other User")
        db.session.commit()
        other_client = self.app.test_client()
        login = other_client.post("/api/auth/login", json={
            "email": "other@example.test", "password": "admin-password-123",
        })
        self.assertEqual(login.status_code, 200)

        payload = other_client.get("/api/workspaces").get_json()
        self.assertEqual(payload["workspaces"], [])
        self.assertIsNone(payload["active_workspace_id"])
        self.assertEqual(Workspace.query.filter_by(owner_user_id=other.user_id).count(), 0)

    def test_init_db_migrates_existing_organisation_workspaces_to_shared(self):
        legacy = Workspace(
            name="Legacy University Workspace",
            workspace_type="organization",
            status="active",
            owner_user_id=self.admin.user_id,
        )
        db.session.add(legacy)
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=legacy.workspace_id,
            user_id=self.admin.user_id,
            role="owner",
            status="active",
        ))
        db.session.commit()

        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)
        db.session.refresh(legacy)
        self.assertEqual(legacy.workspace_type, "shared")
        self.assertEqual(legacy.name, "Legacy University Workspace")

    def test_user_cannot_switch_to_workspace_without_membership(self):
        other = self._make_user("other@example.test", "Other User")
        other_workspace = self._make_workspace(other, "Other Research Group")
        db.session.commit()
        response = self.client.post("/api/workspaces/current", json={
            "workspace_id": other_workspace.workspace_id,
        })
        self.assertEqual(response.status_code, 403)

    def test_direct_document_upload_is_disabled(self):
        response = self.client.post("/api/documents", json={})
        self.assertEqual(response.status_code, 410)

    def test_my_submissions_lists_only_documents_submitted_by_the_current_user(self):
        request_record = SubmissionRequest(
            workspace_id=self.workspace.workspace_id,
            title="Research report collection",
            status="open",
            accepted_file_types=["txt"],
            max_file_size_mb=15,
            created_by_user_id=self.admin.user_id,
        )
        db.session.add(request_record)
        db.session.flush()

        own_document = Document(
            user_id=self.admin.user_id,
            workspace_id=self.workspace.workspace_id,
            visibility_scope="private",
            title="My submission",
            original_filename="my-submission.txt",
            storage_path="my-submission.txt",
            file_type="txt",
            document_type="submission",
            extracted_text="sample text",
            file_hash="a" * 64,
            processing_status="processed",
        )
        db.session.add(own_document)
        db.session.flush()
        db.session.add(DocumentSubmission(
            request_id=request_record.request_id,
            contributor_user_id=self.admin.user_id,
            document_id=own_document.document_id,
            attempt_number=1,
            status="submitted",
        ))
        db.session.commit()

        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 200)
        documents = response.get_json()["documents"]
        titles = {item["title"] for item in documents}
        self.assertEqual(titles, {"My submission"})
        self.assertEqual(documents[0]["processing_status"], "submitted")


if __name__ == "__main__":
    unittest.main()
