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
    MAX_COMPARISON_SOURCES = int(os.environ.get("MAX_COMPARISON_SOURCES", "50"))
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "instance", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Temporary high-entropy secret used only for first-admin setup.
    ADMIN_BOOTSTRAP_TOKEN = os.environ.get("ADMIN_BOOTSTRAP_TOKEN", "")

    # SMTP delivery for public registration and account recovery.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")
    PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "https://acasift.onrender.com").rstrip("/")
    EMAIL_VERIFICATION_HOURS = int(os.environ.get("EMAIL_VERIFICATION_HOURS", "24"))
    PASSWORD_RESET_HOURS = int(os.environ.get("PASSWORD_RESET_HOURS", "1"))
