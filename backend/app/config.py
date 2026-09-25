"""Configuration classes, selected by the APP_ENV environment variable.

    development  local work (hybrid mode, and full-Docker mode by default)
    testing      pytest; uses TEST_DATABASE_URL, never the dev database
    production   deployment; refuses to start without real secrets

All values come from environment variables. In hybrid mode they are loaded
from the root .env file (see .env.example for what each one means).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Load the shared root .env (hybrid mode). Variables that are already set win,
# so values injected by docker-compose or CI are never overridden.
# In Docker there is no .env file inside the image, so this does nothing.
load_dotenv(REPO_ROOT / ".env")


def _env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a list of strings."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    APP_ENV = "base"

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- CORS / frontend ---
    CORS_ORIGINS = _env_list("CORS_ORIGINS", "http://localhost:5173")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # --- Email ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "1025"))
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "CA Helper <no-reply@ca-helper.local>")

    # --- Encryption and file storage (used from Phase 1) ---
    FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")
    BLIND_INDEX_KEY = os.getenv("BLIND_INDEX_KEY")
    # A relative path is resolved against backend/.
    UPLOAD_DIR = str(BACKEND_DIR / os.getenv("UPLOAD_DIR", "instance/uploads"))

    # --- Gemini (used from Phase 1, only through app/core/ai/gemini_client.py) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
    GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL")

    # --- Rate limiting (Flask-Limiter) ---
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # --- Dates: stored in UTC, displayed in this timezone ---
    DISPLAY_TIMEZONE = "Asia/Kolkata"

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
    }


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    # Debug mode is NOT set here: `make dev-backend` passes `--debug` to `flask run`.
    # That keeps gunicorn in full-Docker mode non-debug (JSON 500s, no debugger).
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
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    # These must be set explicitly in production (checked in get_config).
    REQUIRED = ("SECRET_KEY", "JWT_SECRET_KEY", "SQLALCHEMY_DATABASE_URI")


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    """Return the config class for `name` (default: the APP_ENV variable)."""
    name = name or os.getenv("APP_ENV", "development")
    if name not in _CONFIGS:
        raise RuntimeError(f"Unknown APP_ENV {name!r}; use one of {sorted(_CONFIGS)}")
    config = _CONFIGS[name]
    if config is ProductionConfig:
        missing = [key for key in ProductionConfig.REQUIRED if not getattr(config, key)]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")
    return config
