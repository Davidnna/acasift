import json
import unittest
from unittest.mock import patch

from config import Config
from app import create_app
from app.services.email_service import (
    EmailConfigurationError,
    email_is_configured,
    send_password_reset_email,
    send_verification_email,
)


class NylasTestConfig(Config):
    TESTING = True
    SECRET_KEY = "nylas-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    NYLAS_API_KEY = "test-api-key"
    NYLAS_API_URI = "https://api.us.nylas.com"
    NYLAS_SENDING_DOMAIN = "acasift.nylas.email"
    NYLAS_FROM_EMAIL_VERIFICATION = "verify@acasift.nylas.email"
    NYLAS_FROM_EMAIL_PASSWORD_RESET = "security@acasift.nylas.email"
    NYLAS_FROM_EMAIL_NOTIFICATION = "notifications@acasift.nylas.email"
    NYLAS_REPLY_TO = "helpdesk@example.com"
    NYLAS_API_TIMEOUT = 5
    PUBLIC_APP_URL = "https://acasift.onrender.com"
    EMAIL_VERIFICATION_HOURS = 24
    PASSWORD_RESET_HOURS = 1


class FakeResponse:
    status = 200

    def __init__(self, payload=None):
        self.payload = payload or {"data": {"message_id": "nylas-message-123"}}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeUser:
    first_name = "Ada"
    full_name = "Ada Lovelace"
    email = "ada@example.com"


class NylasEmailTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(NylasTestConfig)
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    @patch("app.services.email_service.urlopen")
    def test_verification_uses_us_transactional_send_and_verification_sender(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse()
        send_verification_email(FakeUser(), "raw-verification-token")

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url,
            "https://api.us.nylas.com/v3/domains/acasift.nylas.email/messages/send",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        self.assertEqual(payload["from"]["email"], "verify@acasift.nylas.email")
        self.assertEqual(payload["from"]["name"], "AcaSift Account Verification")
        self.assertEqual(payload["to"][0]["email"], "ada@example.com")
        self.assertEqual(payload["reply_to"][0]["email"], "helpdesk@example.com")
        self.assertIn("raw-verification-token", payload["body"])

    @patch("app.services.email_service.urlopen")
    def test_password_reset_uses_distinct_security_sender(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse()
        send_password_reset_email(FakeUser(), "raw-reset-token")

        payload = json.loads(mocked_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["from"]["email"], "security@acasift.nylas.email")
        self.assertEqual(payload["from"]["name"], "AcaSift Security")
        self.assertIn("raw-reset-token", payload["body"])

    def test_email_configuration_requires_api_key_and_valid_domain_sender(self):
        self.assertTrue(email_is_configured())
        self.app.config["NYLAS_API_KEY"] = ""
        self.assertFalse(email_is_configured())

    @patch("app.services.email_service.urlopen")
    def test_sender_must_belong_to_configured_domain(self, mocked_urlopen):
        self.app.config["NYLAS_FROM_EMAIL_VERIFICATION"] = "verify@example.com"
        with self.assertRaises(EmailConfigurationError):
            send_verification_email(FakeUser(), "raw-token")
        mocked_urlopen.assert_not_called()

    @patch("app.services.email_service.urlopen")
    def test_reply_to_is_omitted_when_not_configured(self, mocked_urlopen):
        self.app.config["NYLAS_REPLY_TO"] = ""
        mocked_urlopen.return_value = FakeResponse()
        send_verification_email(FakeUser(), "raw-token")
        payload = json.loads(mocked_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertNotIn("reply_to", payload)


if __name__ == "__main__":
    unittest.main()
