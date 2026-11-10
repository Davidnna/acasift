import os
import tempfile
import unittest
from datetime import datetime, timezone

from config import Config
from app import create_app
from app.extensions import db
from app.models import User


class LegacyDatabaseConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-migration-secret"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class AuthenticationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        LegacyDatabaseConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        LegacyDatabaseConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(self.temp_dir.name, 'legacy.db')}"
        self.app = create_app(LegacyDatabaseConfig)
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def test_init_db_adds_auth_columns_and_preserves_active_legacy_account(self):
        with db.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(30) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            created = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
            connection.exec_driver_sql(
                "INSERT INTO users (user_id, full_name, email, password_hash, role, is_active, created_at) "
                "VALUES (1, 'Legacy User', 'legacy@example.test', 'legacy-hash', 'user', TRUE, ?)",
                (created.isoformat(),),
            )

        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)

        user = db.session.get(User, 1)
        self.assertEqual(user.email, "legacy@example.test")
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(user.auth_version, 0)
        self.assertIsNone(user.password_reset_token_hash)
        self.assertIsNone(user.pending_email)
        self.assertIsNone(user.email_change_token_hash)
        self.assertIsNone(user.profile_image_data)
        self.assertIsNone(user.profile_image_mime)
        self.assertEqual(len(user.workspace_memberships), 1)


if __name__ == "__main__":
    unittest.main()
