"""Configuration classes, selected by the APP_ENV environment variable.

    development  local work (make dev-backend, python main.py, the worker)
    testing      pytest; uses TEST_DATABASE_URL, never the dev database

All values come from environment variables, loaded from the root .env file
(see .env.example for what each one means). A feature that needs a new
variable adds it here and to .env.example in the same PR.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Load the shared root .env. Variables that are already set win,
# so values injected by CI are never overridden.
load_dotenv(REPO_ROOT / ".env")


class BaseConfig:
    APP_ENV = "base"

    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    # Access tokens only for now (no refresh token yet); lifetime in minutes.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")))

    # Debugger and auto-reload for `python main.py` (the manual dev server) only.
    # `make dev-backend` passes --debug itself.
    DEV_SERVER_DEBUG = False

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- CORS: browser origins allowed to call the API (comma-separated) ---
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    # --- Rate limiting (Flask-Limiter) ---
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
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
        # (health, login). Enforcement is done by app/core/permissions.py.
        "security": [{"bearerAuth": []}],
    }


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    # Insecure fallbacks so a half-configured laptop still starts. `make setup`
    # writes real random values into .env, so these are normally unused.
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-insecure-secret-key"
    JWT_SECRET_KEY = BaseConfig.JWT_SECRET_KEY or "dev-only-insecure-jwt-key-set-a-real-one"
    DEV_SERVER_DEBUG = True


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough"
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    # Rate limiting stays ON so the login limit is tested; backend/conftest.py
    # clears the in-memory counters before every test.
    RATELIMIT_STORAGE_URI = "memory://"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=60)
    LOG_LEVEL = "INFO"  # fixed, so a developer's .env cannot change test behaviour


_CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig}


def get_config(name: str | None = None) -> type[BaseConfig]:
    """Return the config class for `name` (default: the APP_ENV variable)."""
    name = name or os.getenv("APP_ENV", "development")
    if name not in _CONFIGS:
        raise RuntimeError(f"Unknown APP_ENV {name!r}; use one of {sorted(_CONFIGS)}")
    return _CONFIGS[name]
