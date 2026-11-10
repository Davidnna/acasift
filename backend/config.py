import os


def normalise_database_url(url):
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-change-before-deployment")
    SQLALCHEMY_DATABASE_URI = normalise_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///acasift-dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "15")) * 1024 * 1024
    NGRAM_SIZE = int(os.environ.get("NGRAM_SIZE", "5"))
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "instance", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Temporary high-entropy secret used only for first-admin setup.
    ADMIN_BOOTSTRAP_TOKEN = os.environ.get("ADMIN_BOOTSTRAP_TOKEN", "")

    # Nylas Transactional Send (US region) for verification and password recovery.
    NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY", "")
    NYLAS_API_URI = os.environ.get("NYLAS_API_URI", "https://api.us.nylas.com").rstrip("/")
    NYLAS_SENDING_DOMAIN = os.environ.get("NYLAS_SENDING_DOMAIN", "acasift.nylas.email").strip().lower()
    NYLAS_FROM_NAME = os.environ.get("NYLAS_FROM_NAME", "AcaSift")
    NYLAS_FROM_EMAIL_VERIFICATION = os.environ.get(
        "NYLAS_FROM_EMAIL_VERIFICATION",
        f"verify@{NYLAS_SENDING_DOMAIN}",
    ).strip().lower()
    NYLAS_FROM_EMAIL_PASSWORD_RESET = os.environ.get(
        "NYLAS_FROM_EMAIL_PASSWORD_RESET",
        f"security@{NYLAS_SENDING_DOMAIN}",
    ).strip().lower()
    NYLAS_FROM_EMAIL_NOTIFICATION = os.environ.get(
        "NYLAS_FROM_EMAIL_NOTIFICATION",
        f"notifications@{NYLAS_SENDING_DOMAIN}",
    ).strip().lower()
    # Optional monitored mailbox for replies. These sender aliases are not inboxes.
    NYLAS_REPLY_TO = os.environ.get("NYLAS_REPLY_TO", "").strip().lower()
    NYLAS_API_TIMEOUT = int(os.environ.get("NYLAS_API_TIMEOUT", "20"))
    PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "https://acasift.onrender.com").rstrip("/")
    EMAIL_VERIFICATION_HOURS = int(os.environ.get("EMAIL_VERIFICATION_HOURS", "24"))
    PASSWORD_RESET_HOURS = int(os.environ.get("PASSWORD_RESET_HOURS", "1"))
