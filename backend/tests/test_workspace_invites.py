import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User, Workspace, WorkspaceInvite, WorkspaceMembership
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
            "name": "Research Group",
            "description": "A shared space for document collection and review.",
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
            json=payload or {"role": "member"},
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
        self.assertEqual(workspace.name, "Research Group")
        self.assertEqual(membership.role, "owner")

    def test_invite_token_is_hashed_and_preview_is_limited(self):
        result, token = self._create_invite(
            role="member",
            max_uses=2,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        )
        invite = db.session.get(WorkspaceInvite, result["invite"]["id"])
        self.assertEqual(len(invite.token_hash), 64)
        self.assertNotEqual(invite.token_hash, token)
        self.assertEqual(result["invite"]["role"], "member")
        manager_view = self.owner_client.get("/api/workspaces").get_json()
        manager_invite = next(item for item in manager_view["invites"] if item["id"] == invite.invite_id)
        self.assertIsNotNone(manager_invite["expires_at"])

        preview = self.owner_client.get(
            "/api/workspaces/invites/preview",
            query_string={"token": token},
        )
        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertEqual(payload["workspace"]["name"], "Research Group")
        self.assertEqual(payload["role"], "member")
        self.assertTrue(payload["is_member"])
        self.assertNotIn("expires_at", payload)

    def test_invited_user_can_join_with_role_and_invite_usage_is_counted(self):
        result, token = self._create_invite(role="member", max_uses=1)
        invited = self._make_user("member@example.test", "Workspace Member")
        client = self.app.test_client()
        self._login(client, invited.email)

        response = client.post("/api/workspaces/invites/accept", json={"token": token})
        self.assertEqual(response.status_code, 201, response.get_json())
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=invited.user_id
        ).one()
        self.assertEqual(membership.role, "member")

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
        for role in ("admin", "owner", "student", "lecturer"):
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

    def test_expired_invitation_does_not_disclose_expiration_to_recipient(self):
        result, token = self._create_invite(role="member")
        invite = db.session.get(WorkspaceInvite, result["invite"]["id"])
        invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

        response = self.owner_client.get(
            "/api/workspaces/invites/preview",
            query_string={"token": token},
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.get_json()["error"], "This invitation link is no longer available.")

    def test_workspace_owner_can_update_name_and_description(self):
        response = self.owner_client.post(
            f"/api/workspaces/{self.workspace_id}/manage",
            json={"name": "Updated Research Group", "description": "Updated description."},
        )
        self.assertEqual(response.status_code, 200)
        workspace = db.session.get(Workspace, self.workspace_id)
        self.assertEqual(workspace.name, "Updated Research Group")
        self.assertEqual(workspace.description, "Updated description.")

    def test_owner_leaving_transfers_ownership_to_highest_priority_role(self):
        admin = self._make_user("successor-admin@example.test", "Successor Admin")
        collaborator_one = self._make_user("successor-one@example.test", "Successor One")
        collaborator_two = self._make_user("successor-two@example.test", "Successor Two")
        member = self._make_user("successor-member@example.test", "Successor Member")
        for user, role in ((member, "member"), (collaborator_one, "member"), (collaborator_two, "member"), (admin, "admin")):
            db.session.add(WorkspaceMembership(
                workspace_id=self.workspace_id, user_id=user.user_id, role=role, status="active"
            ))
        db.session.commit()

        response = self.owner_client.post(f"/api/workspaces/{self.workspace_id}/leave", json={})
        self.assertEqual(response.status_code, 200)
        workspace = db.session.get(Workspace, self.workspace_id)
        self.assertEqual(workspace.owner_user_id, admin.user_id)
        successor_membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=admin.user_id
        ).one()
        self.assertEqual(successor_membership.role, "owner")
        owner_membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=self.owner.user_id
        ).one()
        self.assertEqual(owner_membership.status, "left")

    def test_owner_leaving_with_no_other_members_closes_workspace(self):
        response = self.owner_client.post(f"/api/workspaces/{self.workspace_id}/leave", json={})
        self.assertEqual(response.status_code, 200)
        workspace = db.session.get(Workspace, self.workspace_id)
        self.assertEqual(workspace.status, "deleted")
        owner_membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=self.owner.user_id
        ).one()
        self.assertEqual(owner_membership.status, "left")

    def test_member_can_leave_without_changing_workspace_owner(self):
        member = self._make_user("leaving-member@example.test", "Leaving Member")
        db.session.add(WorkspaceMembership(
            workspace_id=self.workspace_id, user_id=member.user_id, role="member", status="active"
        ))
        db.session.commit()
        client = self.app.test_client()
        self._login(client, member.email)
        response = client.post(f"/api/workspaces/{self.workspace_id}/leave", json={})
        self.assertEqual(response.status_code, 200)
        workspace = db.session.get(Workspace, self.workspace_id)
        self.assertEqual(workspace.owner_user_id, self.owner.user_id)
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace_id, user_id=member.user_id
        ).one()
        self.assertEqual(membership.status, "left")

    def test_only_workspace_owner_can_delete_shared_workspace(self):
        admin = self._make_user("deleting-admin@example.test", "Deleting Admin")
        db.session.add(WorkspaceMembership(
            workspace_id=self.workspace_id, user_id=admin.user_id, role="admin", status="active"
        ))
        db.session.commit()
        client = self.app.test_client()
        self._login(client, admin.email)
        forbidden = client.delete(f"/api/workspaces/{self.workspace_id}")
        self.assertEqual(forbidden.status_code, 403)
        deleted = self.owner_client.delete(f"/api/workspaces/{self.workspace_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(db.session.get(Workspace, self.workspace_id).status, "deleted")

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
