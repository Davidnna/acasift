import io
import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User, Workspace, WorkspaceMembership, Document
from app.services.workspace_service import ensure_personal_workspace


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
        self.admin = User(
            first_name="Platform", last_name="Admin", full_name="Platform Admin",
            email="admin@example.test", password_hash=generate_password_hash("admin-password-123"),
            role="admin", is_active=True,
        )
        db.session.add(self.admin)
        db.session.flush()
        ensure_personal_workspace(self.admin)
        db.session.commit()
        self.client.post("/api/auth/login", json={
            "email": "admin@example.test", "password": "admin-password-123",
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def test_login_creates_or_returns_personal_workspace(self):
        payload = self.client.get("/api/workspaces").get_json()
        self.assertEqual(len(payload["workspaces"]), 1)
        self.assertEqual(payload["workspaces"][0]["type"], "personal")
        self.assertEqual(payload["workspaces"][0]["role"], "owner")

    def test_personal_workspace_creation_is_idempotent(self):
        first = ensure_personal_workspace(self.admin)
        second = ensure_personal_workspace(self.admin)
        self.assertEqual(first.workspace_id, second.workspace_id)
        self.assertEqual(Workspace.query.filter_by(owner_user_id=self.admin.user_id, workspace_type="personal").count(), 1)

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
        other = User(
            first_name="Other", last_name="User", full_name="Other User",
            email="other@example.test", password_hash=generate_password_hash("other-password-123"),
            role="user", is_active=True,
        )
        db.session.add(other)
        db.session.flush()
        other_workspace = ensure_personal_workspace(other)
        db.session.commit()
        response = self.client.post("/api/workspaces/current", json={
            "workspace_id": other_workspace.workspace_id,
        })
        self.assertEqual(response.status_code, 403)


    def test_personal_workspace_cannot_upload_shared_reference_documents(self):
        response = self.client.post(
            "/api/workspace/references",
            data={"document": (io.BytesIO(b"Private workspace reference"), "reference.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 403)

    def test_document_list_does_not_expose_another_users_private_submission(self):
        second = User(
            first_name="Second", last_name="User", full_name="Second User",
            email="second@example.test", password_hash=generate_password_hash("second-password-123"),
            role="user", is_active=True,
        )
        db.session.add(second)
        db.session.flush()
        second_workspace = ensure_personal_workspace(second)
        admin_workspace = ensure_personal_workspace(self.admin)

        def make_document(owner, workspace_id, title, document_type="submission", scope="private"):
            return Document(
                user_id=owner.user_id,
                workspace_id=workspace_id,
                visibility_scope=scope,
                title=title,
                original_filename=f"{title}.txt",
                storage_path=f"{title}.txt",
                file_type="txt",
                document_type=document_type,
                extracted_text="sample text",
                file_hash=(title.lower().replace(" ", "0") + "0" * 64)[:64],
                processing_status="processed",
            )

        db.session.add_all([
            make_document(self.admin, admin_workspace.workspace_id, "Admin private submission"),
            make_document(second, second_workspace.workspace_id, "Second private submission"),
            make_document(self.admin, None, "Platform reference", "reference", "platform"),
        ])
        db.session.commit()

        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.get_json()["documents"]}
        self.assertIn("Admin private submission", titles)
        self.assertIn("Platform reference", titles)
        self.assertNotIn("Second private submission", titles)



if __name__ == "__main__":
    unittest.main()
