import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Document, User, Workspace, WorkspaceMembership
from app.submission_models import (
    SubmissionRequest,
    SubmissionRequestParticipant,
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

    def _create_request(self):
        return self.owner_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "Research document collection",
            "description": "Collect reports for a similarity review.",
            "instructions": "Upload the final document.",
            "accepted_file_types": ["pdf", "docx", "txt"],
            "max_file_size_mb": 15,
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
        other_request = self.owner_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "A different private request",
            "accepted_file_types": ["pdf", "docx", "txt"],
            "max_file_size_mb": 15,
        })
        self.assertEqual(other_request.status_code, 201, other_request.get_json())
        other_request_id = other_request.get_json()["submission_request"]["id"]
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
        self.assertEqual(self.reviewer_client.get(f"/api/submission-requests/{request_id}").status_code, 200)
        self.assertEqual(self.reviewer_client.get(f"/api/submission-requests/{other_request_id}").status_code, 403)

    def _open_request(self, request_id):
        response = self.owner_client.post(
            f"/api/submission-requests/{request_id}/status",
            json={"status": "open"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())

    def _submit(self, client, request_id, title, content):
        return client.post(
            f"/api/submission-requests/{request_id}/submissions",
            data={
                "title": title,
                "document": (io.BytesIO(content.encode("utf-8")), f"{title}.txt"),
            },
            content_type="multipart/form-data",
        )

    def _external_user(self):
        user = self._make_user("external@example.test")
        ensure_personal_workspace(user)
        db.session.commit()
        return user, self._login(user)

    def test_personal_workspace_cannot_create_submission_request(self):
        personal = ensure_personal_workspace(self.owner)
        db.session.commit()
        response = self.owner_client.post("/api/submission-requests", json={
            "workspace_id": personal.workspace_id,
            "title": "Not allowed",
        })
        self.assertEqual(response.status_code, 403)


    def test_external_link_participant_joins_without_workspace_membership(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        self._open_request(request_id)
        invite_response = self.owner_client.post(
            f"/api/submission-requests/{request_id}/invites",
            json={"expires_at": None, "max_uses": 3},
        )
        self.assertEqual(invite_response.status_code, 201, invite_response.get_json())
        token = parse_qs(urlparse(invite_response.get_json()["join_url"]).query)["token"][0]

        external_user, external_client = self._external_user()
        preview = external_client.get(f"/api/submission-request-invites/preview?token={token}")
        self.assertEqual(preview.status_code, 200, preview.get_json())
        accepted = external_client.post("/api/submission-request-invites/accept", json={"token": token})
        self.assertEqual(accepted.status_code, 201, accepted.get_json())
        self.assertIsNone(WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace.workspace_id,
            user_id=external_user.user_id,
            status="active",
        ).first())
        self.assertTrue(SubmissionRequestParticipant.query.filter_by(
            request_id=request_id,
            user_id=external_user.user_id,
            participation_type="external",
            status="active",
        ).first())
        detail = external_client.get(f"/api/submission-requests/{request_id}")
        self.assertEqual(detail.status_code, 200, detail.get_json())
        self.assertTrue(detail.get_json()["permissions"]["can_submit"])
        dashboard = external_client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.get_json()["my_submission_requests"][0]["id"], request_id)
        denied_list = external_client.get(f"/api/submission-requests?workspace_id={self.workspace.workspace_id}")
        self.assertEqual(denied_list.status_code, 403)

    def test_submission_upload_runs_request_peer_comparison_and_reviewer_feedback(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        self._open_request(request_id)
        assigned = self.owner_client.post(
            f"/api/submission-requests/{request_id}/reviewers",
            json={"user_id": self.reviewer.user_id},
        )
        self.assertEqual(assigned.status_code, 201)

        shared_phrase = (
            "Transparent document review requires careful source attribution, "
            "consistent evidence evaluation, reproducible methods and clear reporting."
        )
        db.session.add_all([
            Document(
                user_id=self.owner.user_id,
                title="Global reference source",
                original_filename="global-reference.txt",
                storage_path="global-reference.txt",
                file_type="txt",
                document_type="reference",
                extracted_text="Global material describes a separate governance framework and a distinct archival vocabulary.",
                file_hash="d" * 64,
                workspace_id=None,
                visibility_scope="platform",
                processing_status="processed",
            ),
            Document(
                user_id=self.owner.user_id,
                title="Workspace reference source",
                original_filename="workspace-reference.txt",
                storage_path="workspace-reference.txt",
                file_type="txt",
                document_type="reference",
                extracted_text="Workspace material describes a separate operational framework and a distinct review vocabulary.",
                file_hash="e" * 64,
                workspace_id=self.workspace.workspace_id,
                visibility_scope="workspace",
                processing_status="processed",
            ),
        ])
        db.session.commit()
        joined = self.member_client.post(f"/api/submission-requests/{request_id}/participate")
        self.assertEqual(joined.status_code, 201, joined.get_json())
        first = self._submit(
            self.member_client, request_id, "First contributor report",
            f"Introduction. {shared_phrase} Closing remarks.",
        )
        self.assertEqual(first.status_code, 201, first.get_json())
        self.assertEqual(first.get_json()["submission"]["status"], "analysed")

        unrelated_request = self.owner_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "Unrelated request",
            "accepted_file_types": ["txt"],
            "max_file_size_mb": 15,
        })
        self.assertEqual(unrelated_request.status_code, 201)
        unrelated_request_id = unrelated_request.get_json()["submission_request"]["id"]
        self._open_request(unrelated_request_id)
        self.assertEqual(self.member_client.post(
            f"/api/submission-requests/{unrelated_request_id}/participate"
        ).status_code, 201)
        unrelated_submission = self._submit(
            self.member_client,
            unrelated_request_id,
            "Unrelated request document",
            f"{shared_phrase} This document belongs to a different request.",
        )
        self.assertEqual(unrelated_submission.status_code, 201, unrelated_submission.get_json())

        external_user, external_client = self._external_user()
        invite_response = self.owner_client.post(
            f"/api/submission-requests/{request_id}/invites",
            json={"expires_at": None, "max_uses": None},
        )
        token = parse_qs(urlparse(invite_response.get_json()["join_url"]).query)["token"][0]
        self.assertEqual(external_client.post(
            "/api/submission-request-invites/accept", json={"token": token}
        ).status_code, 201)

        second = self._submit(
            external_client, request_id, "External contributor report",
            f"Opening. {shared_phrase} Additional discussion.",
        )
        self.assertEqual(second.status_code, 201, second.get_json())
        second_submission = second.get_json()["submission"]
        self.assertEqual(second_submission["status"], "analysed")
        self.assertIsNotNone(second_submission["comparison_id"])

        report = external_client.get(f"/api/comparisons/{second_submission['comparison_id']}")
        self.assertEqual(report.status_code, 200, report.get_json())
        report_results = report.get_json()["comparison"]["results"]
        source_scopes = {row["source_scope"] for row in report_results}
        self.assertEqual(source_scopes, {"global", "workspace", "request"})
        peer_results = [row for row in report_results if row["source_scope"] == "request"]
        self.assertEqual(len(peer_results), 1)
        self.assertEqual(peer_results[0]["reference_document"]["title"], "Another submission in this request")
        self.assertIsNone(peer_results[0]["reference_document"]["uploader"])
        self.assertIn("hidden to protect", peer_results[0]["passages"][0]["reference_text"])

        reviewer_report = self.reviewer_client.get(f"/api/comparisons/{second_submission['comparison_id']}")
        self.assertEqual(reviewer_report.status_code, 200, reviewer_report.get_json())
        reviewer_peer = [row for row in reviewer_report.get_json()["comparison"]["results"] if row["source_scope"] == "request"]
        self.assertEqual(reviewer_peer[0]["reference_document"]["title"], "First contributor report")
        self.assertEqual(reviewer_peer[0]["reference_document"]["uploader"], self.member.full_name)

        reviewer_detail = self.reviewer_client.get(f"/api/submission-requests/{request_id}")
        self.assertEqual(reviewer_detail.status_code, 200)
        self.assertEqual(len(reviewer_detail.get_json()["submissions"]), 2)
        reviewed = self.reviewer_client.post(
            f"/api/submission-requests/{request_id}/submissions/{second_submission['id']}/review",
            json={"decision": "revision_requested", "feedback": "Please review the cited source material."},
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.get_json())
        contributor_detail = external_client.get(f"/api/submission-requests/{request_id}")
        self.assertEqual(contributor_detail.status_code, 200)
        self.assertEqual(len(contributor_detail.get_json()["submissions"]), 1)
        self.assertEqual(contributor_detail.get_json()["submissions"][0]["review"]["decision"], "revision_requested")
        self.assertNotIn(self.member.full_name, str(contributor_detail.get_json()))

    def test_request_invite_revocation_blocks_new_external_participants(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        self._open_request(request_id)
        invite_response = self.owner_client.post(
            f"/api/submission-requests/{request_id}/invites",
            json={"expires_at": None, "max_uses": None},
        )
        invite = invite_response.get_json()["invite"]
        token = parse_qs(urlparse(invite_response.get_json()["join_url"]).query)["token"][0]
        revoked = self.owner_client.post(
            f"/api/submission-requests/{request_id}/invites/{invite['id']}/revoke"
        )
        self.assertEqual(revoked.status_code, 200)
        _, external_client = self._external_user()
        preview = external_client.get(f"/api/submission-request-invites/preview?token={token}")
        self.assertEqual(preview.status_code, 410)

    def test_workspace_member_removal_revokes_request_participation_and_reviewer_access(self):
        created = self._create_request()
        request_id = created.get_json()["submission_request"]["id"]
        self._open_request(request_id)
        self.assertEqual(self.member_client.post(
            f"/api/submission-requests/{request_id}/participate"
        ).status_code, 201)
        member_submission = self._submit(
            self.member_client,
            request_id,
            "Member report before removal",
            "A sufficiently long report that will become inaccessible after workspace removal.",
        )
        self.assertEqual(member_submission.status_code, 201, member_submission.get_json())
        member_comparison_id = member_submission.get_json()["submission"]["comparison_id"]
        self.assertEqual(self.owner_client.post(
            f"/api/submission-requests/{request_id}/reviewers",
            json={"user_id": self.reviewer.user_id},
        ).status_code, 201)
        removed = self.owner_client.post(
            f"/api/workspaces/{self.workspace.workspace_id}/members/{self.member.user_id}/remove",
            json={},
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.member_client.get(f"/api/submission-requests/{request_id}").status_code, 403)
        self.assertEqual(self.member_client.get(f"/api/comparisons/{member_comparison_id}").status_code, 403)
        self.assertEqual(self.reviewer_client.get(f"/api/submission-requests/{request_id}").status_code, 200)

    def test_resubmission_setting_is_enforced(self):
        created = self.owner_client.post("/api/submission-requests", json={
            "workspace_id": self.workspace.workspace_id,
            "title": "Single submission only",
            "accepted_file_types": ["txt"],
            "max_file_size_mb": 15,
            "allow_resubmissions": False,
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        request_id = created.get_json()["submission_request"]["id"]
        self._open_request(request_id)
        joined = self.member_client.post(f"/api/submission-requests/{request_id}/participate")
        self.assertEqual(joined.status_code, 201, joined.get_json())
        first = self._submit(self.member_client, request_id, "First file", "A sufficiently long document for the first request submission.")
        self.assertEqual(first.status_code, 201, first.get_json())
        second = self._submit(self.member_client, request_id, "Second file", "A different sufficiently long document for a second submission.")
        self.assertEqual(second.status_code, 409)
