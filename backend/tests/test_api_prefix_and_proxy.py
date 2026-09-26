"""Feature routes live under /api/v1; health and docs stay unversioned; ProxyFix is opt-in."""

import pytest
from flask import request
from flask_smorest import Blueprint

import app.routes
from app import create_app
from app.config import TestingConfig
from app.routes import API_PREFIX, BLUEPRINTS, register_routes


def test_every_feature_blueprint_is_registered_under_api_v1():
    calls = []

    class RecordingApi:
        def register_blueprint(self, blp, **options):
            calls.append((blp.name, options))

    register_routes(RecordingApi())

    assert calls[0] == ("health", {})
    assert len(calls[1:]) == len(BLUEPRINTS)
    assert all(options == {"url_prefix": "/api/v1"} for _, options in calls[1:])
    assert API_PREFIX == "/api/v1"


@pytest.fixture()
def app_with_demo_blueprint(monkeypatch):
    """A fresh app whose only feature blueprint is a test-only one with a single route."""
    blp = Blueprint("demo", __name__, description="Test-only feature")

    @blp.route("/demo/ping")
    @blp.response(200)
    def ping():
        return {"pong": True}

    monkeypatch.setattr(app.routes, "BLUEPRINTS", [blp])
    return create_app("testing")


def test_feature_routes_are_served_under_api_v1(app_with_demo_blueprint):
    client = app_with_demo_blueprint.test_client()

    assert client.get("/api/v1/demo/ping").get_json() == {"pong": True}
    assert client.get("/api/demo/ping").status_code == 404


def test_openapi_spec_lists_versioned_feature_paths(app_with_demo_blueprint):
    paths = app_with_demo_blueprint.test_client().get("/api/openapi.json").get_json()["paths"]

    assert "/api/v1/demo/ping" in paths
    assert "/api/health" in paths


def test_health_stays_unversioned(client, database):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404


def _remote_addr(app) -> str:
    """Client address and scheme as the app sees them, for a request with proxy headers."""
    captured = {}

    @app.get("/api/v1/whoami")
    def whoami():
        captured["addr"] = request.remote_addr
        captured["scheme"] = request.scheme
        return {}

    app.test_client().get(
        "/api/v1/whoami",
        headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"},
    )
    return f"{captured['addr']} {captured['scheme']}"


def test_proxy_fix_off_ignores_forwarded_headers():
    assert _remote_addr(create_app("testing")) == "127.0.0.1 http"


def test_proxy_fix_on_trusts_forwarded_headers(monkeypatch):
    monkeypatch.setattr(TestingConfig, "TRUST_PROXY", True)

    assert _remote_addr(create_app("testing")) == "203.0.113.7 https"
