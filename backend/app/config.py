"""Configuration classes, selected by the APP_ENV environment variable.

    development  local work (`make dev-backend`, the worker, `flask` commands)
    testing      pytest; uses TEST_DATABASE_URL, never the dev database

All values come from environment variables, loaded from the root .env file
(see .env.example for what each one means).
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Load the shared root .env. Variables that are already set win, so values set
# by CI are never overridden.
load_dotenv(REPO_ROOT / ".env")


class BaseConfig:
    APP_ENV = "base"

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # Access tokens only for now (no refresh token yet); lifetime in minutes.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")))

    # Fernet key for encrypted columns (app/utils/encryption.py). No fallback: without it,
    # saving or reading an encrypted value fails with instructions.
    FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")

    # --- Uploaded files (app/utils/storage.py): encrypted, outside the repo's tracked files ---
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "instance/uploads")  # relative to backend/
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    # Flask refuses bigger requests (413) before reading them; 1 MB of room for the form.
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Email (app/utils/email.py). Development: Mailpit from `make infra` ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "1025"))
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "CA Helper <no-reply@ca-helper.local>")
    # True: nothing is sent; messages are kept in app.utils.email.outbox (tests).
    MAIL_SUPPRESS_SEND = False

    # --- Gemini (app/utils/gemini_client.py). No key: AI features use their fallback ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))

    # --- Rate limiting (Flask-Limiter): counters kept in memory, per process ---
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_HEADERS_ENABLED = True

    # --- Logging: DEBUG | INFO | WARNING | ERROR ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    # --- OpenAPI docs (flask-smorest) ---
    API_TITLE = "CA Helper API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"  # served at /api/openapi.json
    OPENAPI_SWAGGER_UI_PATH = "/docs"  # Swagger UI at /api/docs
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
    API_SPEC_OPTIONS = {
        "info": {"description": "CA Helper (ComplianceConnect) REST API."},
        # Adds the "Authorize" button in Swagger UI for JWT access tokens.
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        # Every endpoint needs a token unless it opts out with @blp.doc(security=[])
        # (health, login). Enforcement is done by app/utils/decorators.py.
        "security": [{"bearerAuth": []}],
    }


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    # Insecure fallbacks so a half-configured laptop still starts. `make setup`
    # writes real random values into .env, so these are normally unused.
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-insecure-secret-key"
    JWT_SECRET_KEY = BaseConfig.JWT_SECRET_KEY or "dev-only-insecure-jwt-key-set-a-real-one"


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough"
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    # Rate limiting stays ON so the login limit is tested; tests/conftest.py
    # clears the in-memory counters before every test.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=60)
    # A fixed test-only key, so a developer's .env cannot change test behaviour.
    FIELD_ENCRYPTION_KEY = "Z5radg25qAqquvqRiPO960hRLtJmVhE0P3dYa_T1Mk8="
    # Tests read emails from app.utils.email.outbox; nothing reaches Mailpit.
    MAIL_SUPPRESS_SEND = True
    # Fixed here so a developer's .env cannot change test behaviour.
    LOG_LEVEL = "INFO"
    # Tests never call the real Gemini: without a key the client refuses (tests fake it).
    GEMINI_API_KEY = None


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    """Return the config class for `name` (default: the APP_ENV variable)."""
    name = name or os.getenv("APP_ENV", "development")
    if name not in _CONFIGS:
        raise RuntimeError(f"Unknown APP_ENV {name!r}; use one of {sorted(_CONFIGS)}")
    return _CONFIGS[name]
