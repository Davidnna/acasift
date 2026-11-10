import io
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from app import create_app
from app.extensions import db
from app.models import User


class AccountConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-account-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    NYLAS_API_KEY = "test-nylas-api-key"
    NYLAS_API_URI = "https://api.us.nylas.com"
    NYLAS_SENDING_DOMAIN = "acasift.nylas.email"
    NYLAS_FROM_EMAIL_VERIFICATION = "verify@acasift.nylas.email"
    NYLAS_FROM_EMAIL_PASSWORD_RESET = "security@acasift.nylas.email"
    NYLAS_FROM_EMAIL_NOTIFICATION = "notifications@acasift.nylas.email"
    PUBLIC_APP_URL = "https://acasift.example.test"
    EMAIL_VERIFICATION_HOURS = 24


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        AccountConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(AccountConfig)
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(
            first_name="Ada", last_name="Lovelace", other_names="Augusta",
            full_name="Ada Augusta Lovelace", email="ada@example.edu",
            password_hash=generate_password_hash("old-password-123"),
            role="user", is_active=True,
        )
        db.session.add(self.user)
        db.session.commit()
        self.client.post("/api/auth/login", json={"email": "ada@example.edu", "password": "old-password-123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def test_account_overview_returns_profile_and_activity(self):
        response = self.client.get("/api/account")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["user"]["first_name"], "Ada")
        self.assertEqual(data["user"]["last_name"], "Lovelace")
        self.assertIn("activity", data)

    def test_profile_update_rebuilds_display_name(self):
        response = self.client.post("/api/account/profile", json={
            "first_name": "David", "other_names": "Chukwuemeka", "last_name": "Nna",
        })
        self.assertEqual(response.status_code, 200)
        user = db.session.get(User, self.user.user_id)
        self.assertEqual(user.full_name, "David Chukwuemeka Nna")
        self.assertEqual(user.other_names, "Chukwuemeka")

    def test_profile_update_requires_first_and_last_name(self):
        response = self.client.post("/api/account/profile", json={
            "first_name": "David", "last_name": "", "other_names": "",
        })
        self.assertEqual(response.status_code, 400)

    def test_password_change_requires_current_password_and_updates_hash(self):
        response = self.client.post("/api/account/password", json={
            "current_password": "old-password-123",
            "new_password": "new-password-456",
            "confirm_password": "new-password-456",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(check_password_hash(self.user.password_hash, "new-password-456"))

    def test_password_change_invalidates_other_authenticated_sessions(self):
        second_client = self.app.test_client()
        second_login = second_client.post("/api/auth/login", json={
            "email": "ada@example.edu", "password": "old-password-123",
        })
        self.assertEqual(second_login.status_code, 200)
        self.assertEqual(second_client.get("/api/auth/me").status_code, 200)

        changed = self.client.post("/api/account/password", json={
            "current_password": "old-password-123",
            "new_password": "new-password-456",
            "confirm_password": "new-password-456",
        })
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(second_client.get("/api/auth/me").status_code, 401)

    def test_password_change_rejects_wrong_current_password(self):
        response = self.client.post("/api/account/password", json={
            "current_password": "incorrect-password",
            "new_password": "new-password-456",
            "confirm_password": "new-password-456",
        })
        self.assertEqual(response.status_code, 400)

    def test_password_change_rejects_mismatched_confirmation(self):
        response = self.client.post("/api/account/password", json={
            "current_password": "old-password-123",
            "new_password": "new-password-456",
            "confirm_password": "different-password-789",
        })
        self.assertEqual(response.status_code, 400)

    @patch("app.api.send_email_change_verification")
    def test_email_change_keeps_old_address_until_new_address_is_confirmed(self, send_email):
        response = self.client.post("/api/account/email-change", json={
            "new_email": "ada.new@example.edu",
            "current_password": "old-password-123",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.user = db.session.get(User, self.user.user_id)
        self.assertEqual(self.user.email, "ada@example.edu")
        self.assertEqual(self.user.pending_email, "ada.new@example.edu")
        raw_token = send_email.call_args.args[2]
        self.assertNotEqual(self.user.email_change_token_hash, raw_token)

        confirmation = self.client.post("/api/auth/confirm-email-change", json={"token": raw_token})
        self.assertEqual(confirmation.status_code, 200, confirmation.get_json())
        self.assertEqual(confirmation.get_json()["email"], "ada.new@example.edu")
        self.assertEqual(self.user.email, "ada.new@example.edu")
        self.assertIsNone(self.user.pending_email)
        self.assertIsNone(self.user.email_change_token_hash)
        self.assertIsNotNone(self.user.email_verified_at)

    def test_email_change_requires_current_password_and_unique_address(self):
        wrong_password = self.client.post("/api/account/email-change", json={
            "new_email": "ada.new@example.edu",
            "current_password": "incorrect-password",
        })
        self.assertEqual(wrong_password.status_code, 400)

        other = User(
            first_name="Grace", last_name="Hopper", full_name="Grace Hopper",
            email="grace@example.edu", password_hash=generate_password_hash("other-password-123"),
            role="user", is_active=True,
        )
        db.session.add(other)
        db.session.commit()
        duplicate = self.client.post("/api/account/email-change", json={
            "new_email": "GRACE@example.edu",
            "current_password": "old-password-123",
        })
        self.assertEqual(duplicate.status_code, 409)

    @patch("app.api.send_email_change_verification")
    def test_expired_email_change_token_cannot_change_address(self, send_email):
        from datetime import datetime, timedelta, timezone
        response = self.client.post("/api/account/email-change", json={
            "new_email": "ada.new@example.edu",
            "current_password": "old-password-123",
        })
        self.assertEqual(response.status_code, 200)
        raw_token = send_email.call_args.args[2]
        self.user.email_change_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        confirmation = self.client.post("/api/auth/confirm-email-change", json={"token": raw_token})
        self.assertEqual(confirmation.status_code, 400)
        self.assertEqual(self.user.email, "ada@example.edu")

    def test_profile_picture_is_validated_resized_and_can_be_removed(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (1200, 900), color=(24, 169, 153)).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        response = self.client.post(
            "/api/account/profile-picture",
            data={"image": (image_buffer, "portrait.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()["user"]
        self.assertTrue(payload["profile_image_url"].startswith("/api/users/"))
        self.assertEqual(self.user.profile_image_mime, "image/webp")
        self.assertLessEqual(len(self.user.profile_image_data), 600 * 1024)

        picture = self.client.get(payload["profile_image_url"])
        self.assertEqual(picture.status_code, 200)
        self.assertEqual(picture.mimetype, "image/webp")
        self.assertIn("private", picture.headers.get("Cache-Control", ""))

        removed = self.client.delete("/api/account/profile-picture")
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(self.user.profile_image_data)
        refreshed_account = self.client.get("/api/account").get_json()
        self.assertIsNone(refreshed_account["user"]["profile_image_url"])

    def test_profile_picture_is_not_visible_to_users_outside_the_active_workspace(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (80, 80), color=(24, 169, 153)).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        upload = self.client.post(
            "/api/account/profile-picture",
            data={"image": (image_buffer, "portrait.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200)
        picture_url = upload.get_json()["user"]["profile_image_url"]

        other = User(
            first_name="Grace", last_name="Hopper", full_name="Grace Hopper",
            email="grace@example.edu", password_hash=generate_password_hash("other-password-123"),
            role="user", is_active=True,
        )
        db.session.add(other)
        db.session.commit()
        other_client = self.app.test_client()
        other_login = other_client.post("/api/auth/login", json={
            "email": "grace@example.edu", "password": "other-password-123",
        })
        self.assertEqual(other_login.status_code, 200)
        denied = other_client.get(picture_url)
        self.assertEqual(denied.status_code, 404)

    def test_profile_picture_rejects_non_image_upload(self):
        response = self.client.post(
            "/api/account/profile-picture",
            data={"image": (io.BytesIO(b"not an image"), "portrait.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.user.profile_image_data)

    def test_admin_creates_user_with_separate_name_fields(self):
        admin = User(
            first_name="System", last_name="Admin", other_names=None,
            full_name="System Admin", email="system-admin@example.edu",
            password_hash=generate_password_hash("admin-password-123"),
            role="admin", is_active=True,
        )
        db.session.add(admin)
        db.session.commit()
        admin_client = self.app.test_client()
        admin_client.post("/api/auth/login", json={
            "email": "system-admin@example.edu", "password": "admin-password-123",
        })
        response = admin_client.post("/api/admin/users", json={
            "first_name": "Grace", "other_names": "Brewster", "last_name": "Murray Hopper",
            "email": "grace@example.edu", "password": "initial-password-123", "role": "user",
        })
        self.assertEqual(response.status_code, 201)
        created = User.query.filter_by(email="grace@example.edu").one()
        self.assertEqual(created.first_name, "Grace")
        self.assertEqual(created.other_names, "Brewster")
        self.assertEqual(created.last_name, "Murray Hopper")
        self.assertEqual(created.full_name, "Grace Brewster Murray Hopper")
        self.assertIsNotNone(created.email_verified_at)


if __name__ == "__main__":
    unittest.main()
