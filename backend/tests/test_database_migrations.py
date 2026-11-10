import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import text

from config import Config
from app import create_app
from app.extensions import db
from app.database import LEGACY_BASELINE_VERSION, MIGRATION_TABLE


class DatabaseMigrationConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-database-migration-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        DatabaseMigrationConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(DatabaseMigrationConfig)
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _migration_record(self):
        return db.session.execute(
            text(f"SELECT version, execution_mode FROM {MIGRATION_TABLE} WHERE version = :version"),
            {"version": LEGACY_BASELINE_VERSION},
        ).first()

    def test_fresh_database_bootstraps_and_records_verified_baseline(self):
        with patch("app.database._run_legacy_data_migration") as legacy_migration:
            result = self.app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, result.output)
        legacy_migration.assert_not_called()
        record = self._migration_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.execution_mode, "verified_existing_baseline")

    def test_recorded_migration_is_not_repeated_on_restart(self):
        first = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(first.exit_code, 0, first.output)

        with patch("app.database._run_legacy_data_migration", side_effect=AssertionError("migration reran")) as migration, \
             patch("app.database.db.create_all", side_effect=AssertionError("schema bootstrap reran")) as bootstrap:
            second = self.app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(second.exit_code, 0, second.output)
        migration.assert_not_called()
        bootstrap.assert_not_called()
        self.assertIn("current", second.output.lower())

    def test_failed_migration_is_not_marked_as_applied(self):
        with patch("app.database._legacy_baseline_status", return_value=(False, ["test pending migration"])), \
             patch("app.database._run_legacy_data_migration", side_effect=RuntimeError("simulated migration failure")):
            result = self.app.test_cli_runner().invoke(args=["init-db"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNone(self._migration_record())


if __name__ == "__main__":
    unittest.main()
