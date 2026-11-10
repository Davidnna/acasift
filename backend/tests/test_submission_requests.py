import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User, Workspace, WorkspaceMembership
from app.submission_models import (
    SubmissionRequest,
    SubmissionRequestReviewer,
)
from config import Config
from app.services.workspace_service import ensure_personal_workspace


class SubmissionConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-submission-request-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class SubmissionRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        SubmissionConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(SubmissionConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.owner = self._make_user("owner@example.test")
        self.member = self._make_user("member@example.test")
        self.reviewer = self._make_user("reviewer@example.test")
        db.session.flush()
        self.workspace = Workspace(
            name="Independent Research Group",
            workspace_type="shared",
            status="active",
            owner_user_id=self.owner.user_id,
        )
        db.session.add(self.workspace)
        db.session.flush()
        for user, role in (
            (self.owner, "owner"),
            (self.member, "member"),
            (self.reviewer, "member"),
        ):
            db.session.add(WorkspaceMembership(
                workspace_id=self.workspace.workspace_id,
                user_id=user.user_id,
                role=role,
                status="active",
            ))
            ensure_personal_workspace(user)
        db.session.commit()

        self.owner_client = self._login(self.owner)
        self.member_client = self._login(self.member)
        self.reviewer_client = self._login(self.reviewer)
        for client in (self.owner_client, self.member_client, self.reviewer_client):
            with client.session_transaction() as session:
                session["active_workspace_id"] = self.workspace.workspace_id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, email):
        user = User(
            first_name=email.split("@")[0],
            last_name="Test",
            full_name=email.split("@")[0].title(),
            email=email,
            password_hash=generate_password_hash("test-password-123"),
            role="user",
            is_active=True,
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

    def _create_request(self):
        return self.owner_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "Research document collection",
            "description": "Collect reports for a similarity review.",
            "instructions": "Upload the final document.",
            "accepted_file_types": ["pdf", "docx", "txt"],
            "max_file_size_mb": 25,
            "allow_resubmissions": True,
            "allow_external_participants": True,
        })

    def test_owner_can_create_a_submission_request(self):
        response = self._create_request()
        self.assertEqual(response.status_code, 201, response.get_json())
        item = SubmissionRequest.query.one()
        self.assertEqual(item.title, "Research document collection")
        self.assertEqual(item.status, "draft")

    def test_ordinary_member_cannot_create_a_submission_request(self):
        response = self.member_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "Unauthorised request",
        })
        self.assertEqual(response.status_code, 403)

    def test_workspace_member_can_discover_open_request_and_participate(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        opened = self.owner_client.post(
            f"/api/submission-requests/{request_id}/status",
            json={"status": "open"},
        )
        self.assertEqual(opened.status_code, 200)

        listing = self.member_client.get(
            f"/api/submission-requests?workspace_id={self.workspace.workspace_id}"
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.get_json()["submission_requests"]), 1)

        joined = self.member_client.post(
            f"/api/submission-requests/{request_id}/participate"
        )
        self.assertEqual(joined.status_code, 201)

    def test_reviewer_permission_is_request_scoped(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        assigned = self.owner_client.post(
            f"/api/submission-requests/{request_id}/reviewers",
            json={"user_id": self.reviewer.user_id},
        )
        self.assertEqual(assigned.status_code, 201)
        self.assertEqual(
            SubmissionRequestReviewer.query.filter_by(
                request_id=request_id,
                user_id=self.reviewer.user_id,
            ).count(),
            1,
        )

    def test_personal_workspace_cannot_create_submission_request(self):
        personal = ensure_personal_workspace(self.owner)
        db.session.commit()
        response = self.owner_client.post("/api/submission-requests", json={
            "workspace_id": personal.workspace_id,
            "title": "Not allowed",
        })
        self.assertEqual(response.status_code, 403)
