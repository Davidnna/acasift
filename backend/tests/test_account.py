import os
import tempfile
import unittest

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
