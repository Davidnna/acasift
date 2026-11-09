import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import CourseMembership, User, Workspace, WorkspaceInvite, WorkspaceMembership
from app.services.workspace_service import ensure_personal_workspace


class InviteConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-workspace-invite-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    PUBLIC_APP_URL = "https://acasift.example.test"


class WorkspaceInviteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        InviteConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(InviteConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.owner = self._make_user("owner@example.test", "Workspace Owner")
        ensure_personal_workspace(self.owner)
        db.session.commit()

        self.owner_client = self.app.test_client()
        self._login(self.owner_client, self.owner.email)

        response = self.owner_client.post("/api/workspaces", json={
            "name": "CSC 401 Project Submissions",
            "description": "A shared space for project submissions.",
        })
        self.assertEqual(response.status_code, 201)
        self.workspace_id = response.get_json()["workspace"]["id"]

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
            password_hash=generate_password_hash("strong-password-123"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        ensure_personal_workspace(user)
        db.session.commit()
        return user

    def _login(self, client, email):
        response = client.post("/api/auth/login", json={
            "email": email,
            "password": "strong-password-123",
        })
        self.assertEqual(response.status_code, 200)

    def _create_invite(self, **payload):
        response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/invites",
            json=payload or {"role": "student"},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        result = response.get_json()
        token = parse_qs(urlparse(result["join_url"]).query)["token"][0]
        return result, token

    def test_create_shared_workspace_makes_creator_owner_and_active(self):
        workspace = db.session.get(Workspace, self.workspace_id)
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=self.owner.user_id
        ).one()
        self.assertEqual(workspace.workspace_type, "shared")
        self.assertEqual(workspace.name, "CSC 401 Project Submissions")
        self.assertEqual(membership.role, "owner")

    def test_invite_token_is_hashed_and_preview_is_limited(self):
        result, token = self._create_invite(role="student", max_uses=2)
        invite = db.session.get(WorkspaceInvite, result["invite"]["id"])
        self.assertEqual(len(invite.token_hash), 64)
        self.assertNotEqual(invite.token_hash, token)
        self.assertEqual(result["invite"]["role"], "student")

        preview = self.owner_client.get(
            "/api/workspaces/invites/preview",
            query_string={"token": token},
        )
        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertEqual(payload["workspace"]["name"], "CSC 401 Project Submissions")
        self.assertEqual(payload["role"], "student")
        self.assertTrue(payload["is_member"])

    def test_invited_user_can_join_with_role_and_invite_usage_is_counted(self):
        result, token = self._create_invite(role="student", max_uses=1)
        invited = self._make_user("student@example.test", "Student User")
        client = self.app.test_client()
        self._login(client, invited.email)

        response = client.post("/api/workspaces/invites/accept", json={"token": token})
        self.assertEqual(response.status_code, 201, response.get_json())
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=invited.user_id
        ).one()
        self.assertEqual(membership.role, "student")

        invite = db.session.get(WorkspaceInvite, result["invite"]["id"])
        self.assertEqual(invite.use_count, 1)

        third = self._make_user("third@example.test", "Third User")
        third_client = self.app.test_client()
        self._login(third_client, third.email)
        exhausted = third_client.post("/api/workspaces/invites/accept", json={"token": token})
        self.assertEqual(exhausted.status_code, 410)

    def test_workspace_owner_can_revoke_invitation(self):
        result, token = self._create_invite(role="member")
        response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/invites/{result['invite']['id']}/revoke",
            json={},
        )
        self.assertEqual(response.status_code, 200)
        preview = self.owner_client.get(
            "/api/workspaces/invites/preview",
            query_string={"token": token},
        )
        self.assertEqual(preview.status_code, 410)

    def test_invitation_cannot_grant_admin_or_owner_role(self):
        for role in ("admin", "owner"):
            response = self.owner_client.post(
                f"/api/workspaces/{self.workspace_id}/invites",
                json={"role": role},
            )
            self.assertEqual(response.status_code, 400)

    def test_invitation_expiry_must_be_in_the_future_and_timezone_aware(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/invites",
            json={"role": "member", "expires_at": past},
        )
        self.assertEqual(response.status_code, 400)

        no_timezone = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None).isoformat()
        response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/invites",
            json={"role": "member", "expires_at": no_timezone},
        )
        self.assertEqual(response.status_code, 400)

    def test_course_specific_student_invite_automatically_enrols_the_student(self):
        course_response = self.owner_client.post("/api/courses", json={
            "code": "CSC401",
            "title": "Research Methods",
            "description": "Project and research methods.",
        })
        self.assertEqual(course_response.status_code, 201, course_response.get_json())
        course_id = course_response.get_json()["course"]["id"]

        result, token = self._create_invite(
            role="student",
            course_id=course_id,
            max_uses=5,
        )
        self.assertEqual(result["invite"]["course_id"], course_id)

        student = self._make_user("course-student@example.test", "Course Student")
        client = self.app.test_client()
        self._login(client, student.email)
        response = client.post("/api/workspaces/invites/accept", json={"token": token})
        self.assertEqual(response.status_code, 201, response.get_json())

        workspace_membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=student.user_id, status="active"
        ).one()
        course_membership = CourseMembership.query.filter_by(
            course_id=course_id, user_id=student.user_id, status="active"
        ).one()
        self.assertEqual(workspace_membership.role, "student")
        self.assertEqual(course_membership.role, "student")

    def test_workspace_owner_can_promote_an_existing_member_to_admin(self):
        target = self._make_user("newadmin@example.test", "New Admin")
        add_response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/members",
            json={"email": target.email, "role": "member"},
        )
        self.assertEqual(add_response.status_code, 201)
        promote_response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/members/{target.user_id}/role",
            json={"role": "admin"},
        )
        self.assertEqual(promote_response.status_code, 200)
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=target.user_id
        ).one()
        self.assertEqual(membership.role, "admin")

    def test_non_owner_cannot_appoint_an_administrator(self):
        admin_user = self._make_user("admin@example.test", "Workspace Admin")
        db.session.add(WorkspaceMembership(
            workspace_id=self.workspace_id,
            user_id=admin_user.user_id,
            role="admin",
            status="active",
        ))
        target = self._make_user("target@example.test", "Target User")
        db.session.commit()

        client = self.app.test_client()
        self._login(client, admin_user.email)
        response = client.post(
            f"/api/workspaces/{self.workspace_id}/members",
            json={"email": target.email, "role": "admin"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
