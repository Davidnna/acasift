import os
import tempfile
import unittest

from config import Config
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import check_password_hash


class BootstrapConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ADMIN_BOOTSTRAP_TOKEN = "test-only-bootstrap-token-with-more-than-32-characters"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        BootstrapConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(BootstrapConfig)
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def payload(self, **overrides):
        data = {
            "first_name": "AcaSift",
            "last_name": "Administrator",
            "other_names": "",
            "email": "admin@example.edu",
            "password": "a-strong-password-123",
            "setup_token": BootstrapConfig.ADMIN_BOOTSTRAP_TOKEN,
        }
        data.update(overrides)
        return data

    def test_setup_is_available_only_with_token_and_without_admin(self):
        response = self.client.get("/api/bootstrap/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["available"])

        admin = User(
            full_name="Existing Admin",
            email="existing@example.edu",
            password_hash="not-used",
            role="admin",
            is_active=True,
        )
        db.session.add(admin)
        db.session.commit()

        response = self.client.get("/api/bootstrap/status")
        self.assertFalse(response.get_json()["available"])

    def test_invalid_setup_token_is_rejected(self):
        response = self.client.post(
            "/api/bootstrap/first-admin",
            json=self.payload(setup_token="wrong-token"),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.query.filter_by(role="admin").count(), 0)

    def test_first_admin_is_created_with_hashed_password_and_signed_in(self):
        response = self.client.post(
            "/api/bootstrap/first-admin",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 201)
        user = User.query.filter_by(email="admin@example.edu").one()
        self.assertEqual(user.role, "admin")
        self.assertEqual(user.first_name, "AcaSift")
        self.assertEqual(user.last_name, "Administrator")
        self.assertEqual(user.full_name, "AcaSift Administrator")
        self.assertTrue(user.is_active)
        self.assertTrue(check_password_hash(user.password_hash, "a-strong-password-123"))
        self.assertNotEqual(user.password_hash, "a-strong-password-123")

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.get_json()["user"]["is_admin"])

    def test_second_bootstrap_attempt_is_rejected(self):
        first = self.client.post("/api/bootstrap/first-admin", json=self.payload())
        self.assertEqual(first.status_code, 201)

        # A new client simulates a different visitor who also knows the token.
        second_client = self.app.test_client()
        second = second_client.post("/api/bootstrap/first-admin", json=self.payload(
            email="second@example.edu",
        ))
        self.assertEqual(second.status_code, 409)
        self.assertEqual(User.query.filter_by(role="admin").count(), 1)

    def test_existing_non_admin_email_is_not_promoted(self):
        regular = User(
            full_name="Existing User",
            email="admin@example.edu",
            password_hash="not-used",
            role="user",
            is_active=True,
        )
        db.session.add(regular)
        db.session.commit()

        response = self.client.post("/api/bootstrap/first-admin", json=self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(User.query.filter_by(email="admin@example.edu").one().role, "user")

    def test_password_minimum_is_enforced(self):
        response = self.client.post(
            "/api/bootstrap/first-admin",
            json=self.payload(password="short"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.query.filter_by(role="admin").count(), 0)

    def test_bootstrap_is_disabled_when_token_is_not_configured(self):
        self.app.config["ADMIN_BOOTSTRAP_TOKEN"] = ""
        status = self.client.get("/api/bootstrap/status")
        self.assertFalse(status.get_json()["available"])

        response = self.client.post("/api/bootstrap/first-admin", json=self.payload())
        self.assertEqual(response.status_code, 410)
        self.assertEqual(User.query.filter_by(role="admin").count(), 0)


if __name__ == "__main__":
    unittest.main()
