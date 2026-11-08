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
