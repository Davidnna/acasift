import os
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User, Workspace, WorkspaceMembership, AuthRateLimitEvent


class AuthConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-auth-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAIL_SERVER = "smtp.example.test"
    MAIL_PORT = 587
    MAIL_USERNAME = "test-user"
    MAIL_PASSWORD = "test-password"
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_DEFAULT_SENDER = "AcaSift <no-reply@example.test>"
    PUBLIC_APP_URL = "https://acasift.example.test"
    EMAIL_VERIFICATION_HOURS = 24
    PASSWORD_RESET_HOURS = 1


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        AuthConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(AuthConfig)
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def register_payload(self, **overrides):
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "other_names": "Augusta",
            "email": "ada@example.test",
            "password": "a-strong-password-123",
            "confirm_password": "a-strong-password-123",
        }
        payload.update(overrides)
        return payload

    def create_verified_user(self, email="ada@example.test", password="a-strong-password-123"):
        user = User(
            first_name="Ada", last_name="Lovelace", other_names="Augusta",
            full_name="Ada Augusta Lovelace", email=email,
            password_hash=generate_password_hash(password), role="user", is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name="Ada's workspace", workspace_type="personal", status="active", owner_user_id=user.user_id)
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMembership(workspace_id=workspace.workspace_id, user_id=user.user_id, role="owner", status="active"))
        db.session.commit()
        return user

    def test_public_registration_creates_inactive_user_and_private_workspace(self):
        with patch("app.api.send_verification_email") as send_email:
            response = self.client.post("/api/auth/register", json=self.register_payload())
        self.assertEqual(response.status_code, 201)
        user = User.query.filter_by(email="ada@example.test").one()
        self.assertFalse(user.is_active)
        self.assertIsNone(user.email_verified_at)
        self.assertIsNotNone(user.email_verification_token_hash)
        self.assertNotEqual(user.email_verification_token_hash, send_email.call_args.args[1])
        self.assertEqual(WorkspaceMembership.query.filter_by(user_id=user.user_id).count(), 1)
        self.assertEqual(Workspace.query.filter_by(owner_user_id=user.user_id, workspace_type="personal").count(), 1)
        self.assertEqual(user.role, "user")

    def test_registration_requires_email_delivery_configuration(self):
        self.app.config["MAIL_SERVER"] = ""
        response = self.client.post("/api/auth/register", json=self.register_payload())
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(User.query.filter_by(email="ada@example.test").first())

    def test_failed_verification_delivery_keeps_pending_account_for_resend(self):
        from app.services.email_service import EmailDeliveryError
        with patch("app.api.send_verification_email", side_effect=EmailDeliveryError("smtp unavailable")):
            response = self.client.post("/api/auth/register", json=self.register_payload())
        self.assertEqual(response.status_code, 503)
        user = User.query.filter_by(email="ada@example.test").one()
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.email_verification_token_hash)
        self.assertEqual(WorkspaceMembership.query.filter_by(user_id=user.user_id).count(), 1)

    def test_registration_validates_password_confirmation(self):
        response = self.client.post("/api/auth/register", json=self.register_payload(confirm_password="different-password-123"))
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(User.query.filter_by(email="ada@example.test").first())

    def test_unverified_user_cannot_sign_in(self):
        with patch("app.api.send_verification_email"):
            self.client.post("/api/auth/register", json=self.register_payload())
        response = self.client.post("/api/auth/login", json={"email": "ada@example.test", "password": "a-strong-password-123"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("verify your email", response.get_json()["error"].lower())

    def test_verification_token_activates_user_and_signs_them_in(self):
        with patch("app.api.send_verification_email") as send_email:
            created = self.client.post("/api/auth/register", json=self.register_payload())
        self.assertEqual(created.status_code, 201)
        raw_token = send_email.call_args.args[1]
        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(email="ada@example.test").one()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_verified_at)
        self.assertIsNone(user.email_verification_token_hash)
        self.assertTrue(response.get_json()["user"]["email_verified"])
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_verification_token_is_one_time(self):
        with patch("app.api.send_verification_email") as send_email:
            self.client.post("/api/auth/register", json=self.register_payload())
        token = send_email.call_args.args[1]
        first = self.client.post("/api/auth/verify-email", json={"token": token})
        second = self.client.post("/api/auth/verify-email", json={"token": token})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_expired_verification_token_is_rejected(self):
        with patch("app.api.send_verification_email") as send_email:
            self.client.post("/api/auth/register", json=self.register_payload())
        user = User.query.filter_by(email="ada@example.test").one()
        user.email_verification_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        response = self.client.post("/api/auth/verify-email", json={"token": send_email.call_args.args[1]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(user.is_active)

    def test_resend_verification_uses_generic_response(self):
        with patch("app.api.send_verification_email"):
            self.client.post("/api/auth/register", json=self.register_payload())
        with patch("app.api.send_verification_email") as send_email:
            response = self.client.post("/api/auth/resend-verification", json={"email": "ada@example.test"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("If an unverified account exists", response.get_json()["message"])
        self.assertEqual(send_email.call_count, 1)
        self.assertNotIn("ada@example.test", response.get_data(as_text=True))

    def test_password_reset_request_does_not_disclose_account_existence(self):
        known = self.client.post("/api/auth/password-reset/request", json={"email": "nobody@example.test"})
        self.assertEqual(known.status_code, 200)
        user = self.create_verified_user()
        with patch("app.api.send_password_reset_email") as send_email:
            existing = self.client.post("/api/auth/password-reset/request", json={"email": user.email})
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(known.get_json(), existing.get_json())
        self.assertEqual(send_email.call_count, 1)

    def test_password_reset_changes_password_and_invalidates_existing_sessions(self):
        user = self.create_verified_user()
        self.client.post("/api/auth/login", json={"email": user.email, "password": "a-strong-password-123"})
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        with patch("app.api.send_password_reset_email") as send_email:
            request_response = self.client.post("/api/auth/password-reset/request", json={"email": user.email})
        self.assertEqual(request_response.status_code, 200)
        raw_token = send_email.call_args.args[1]
        reset_response = self.client.post("/api/auth/password-reset/confirm", json={
            "token": raw_token,
            "new_password": "a-new-strong-password-456",
            "confirm_password": "a-new-strong-password-456",
        })
        self.assertEqual(reset_response.status_code, 200)
        self.assertTrue(check_password_hash(user.password_hash, "a-new-strong-password-456"))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        new_login = self.client.post("/api/auth/login", json={"email": user.email, "password": "a-new-strong-password-456"})
        self.assertEqual(new_login.status_code, 200)

    def test_password_reset_token_is_one_time(self):
        user = self.create_verified_user()
        with patch("app.api.send_password_reset_email") as send_email:
            self.client.post("/api/auth/password-reset/request", json={"email": user.email})
        token = send_email.call_args.args[1]
        payload = {"token": token, "new_password": "new-password-12345", "confirm_password": "new-password-12345"}
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/password-reset/confirm", json=payload).status_code, 400)

    def test_password_reset_rejects_expired_token(self):
        user = self.create_verified_user()
        raw_token = "expired-reset-token"
        user.password_reset_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        response = self.client.post("/api/auth/password-reset/confirm", json={
            "token": raw_token,
            "new_password": "new-password-12345",
            "confirm_password": "new-password-12345",
        })
        self.assertEqual(response.status_code, 400)

    def test_login_rate_limit_returns_429_and_retry_after(self):
        for _ in range(8):
            response = self.client.post("/api/auth/login", json={"email": "locked@example.test", "password": "wrong-password"})
            self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/auth/login", json={"email": "locked@example.test", "password": "wrong-password"})
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.headers.get("Retry-After"))

    def test_rate_limit_events_store_hashed_keys_not_raw_emails(self):
        self.client.post("/api/auth/login", json={"email": "private@example.test", "password": "wrong-password"})
        event = AuthRateLimitEvent.query.filter_by(action="login").first()
        self.assertIsNotNone(event)
        self.assertNotIn("private@example.test", event.key_hash)
        self.assertEqual(len(event.key_hash), 64)


if __name__ == "__main__":
    unittest.main()
