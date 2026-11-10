import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import User


class ReactAppConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ReactAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        ReactAppConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(ReactAppConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        self.temp_dir.cleanup()

    def test_public_and_client_side_routes_serve_react_shell(self):
        paths = [
            "/", "/about", "/features", "/how-it-works", "/faq", "/access",
            "/login", "/register", "/verify-email", "/resend-verification",
            "/forgot-password", "/reset-password", "/setup/first-admin", "/app/dashboard", "/app/documents", "/app/account", "/app/workspaces", "/app/submission-requests", "/app/submission-requests/1", "/join-submission-request?token=test-token", "/app/references/new", "/app/admin/users",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"id=\"root\"", response.data)

    def test_health_endpoint_remains_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_protected_api_requires_authentication(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Authentication required.")

    def test_legacy_dashboard_url_redirects_to_react_workspace(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/app/dashboard")

    def test_email_logo_is_served_as_png(self):
        response = self.client.get("/static/img/acasift-mark.png")
        self.assertEqual(response.status_code, 200)
        self.assertIn("image/png", response.content_type)
        self.assertGreater(len(response.data), 1000)

    def test_csrf_endpoint_returns_token(self):
        response = self.client.get("/api/csrf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json().get("csrf_token"))

    def test_state_changing_api_requests_require_csrf_token(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        rejected = self.client.post("/api/auth/login", json={"email": "nobody@example.edu", "password": "invalid"})
        self.assertEqual(rejected.status_code, 400)

        token_response = self.client.get("/api/csrf")
        token = token_response.get_json()["csrf_token"]
        accepted = self.client.post(
            "/api/auth/login",
            json={"email": "nobody@example.edu", "password": "invalid"},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(accepted.status_code, 401)

    def test_login_me_and_logout_api_flow(self):
        user = User(
            full_name="Test User",
            email="test@example.edu",
            password_hash=generate_password_hash("test-password-123"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        login_response = self.client.post(
            "/api/auth/login",
            json={"email": "TEST@example.edu", "password": "test-password-123"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.get_json()["user"]["email"], "test@example.edu")

        me_response = self.client.get("/api/auth/me")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["user"]["id"], user.user_id)

        admin_response = self.client.get("/api/admin/users")
        self.assertEqual(admin_response.status_code, 403)

        logout_response = self.client.post("/api/auth/logout")
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
