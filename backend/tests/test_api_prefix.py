"""Module routes live under /api/v1; health and docs stay unversioned."""

from types import ModuleType

import pytest
from flask_smorest import Blueprint

import app.modules
from app import create_app
from app.modules import API_PREFIX, discover_modules, register_blueprints


def test_every_module_blueprint_is_registered_under_api_v1():
    calls = []

    class RecordingApi:
        def register_blueprint(self, blp, **options):
            calls.append((blp.name, options))

    register_blueprints(RecordingApi())

    assert len(calls) == len(discover_modules())
    assert all(options == {"url_prefix": "/api/v1"} for _, options in calls)
    assert API_PREFIX == "/api/v1"


@pytest.fixture()
def app_with_demo_module(monkeypatch):
    """A fresh app whose only module is a test-only one with a single route."""
    blp = Blueprint("demo", __name__, description="Test-only module")

    @blp.route("/demo/ping")
    @blp.response(200)
    def ping():
        return {"pong": True}

    demo = ModuleType("app.modules.demo")
    demo.blp = blp
    monkeypatch.setattr(app.modules, "discover_modules", lambda: [demo])
    yield create_app("testing")
    # The flask-smorest `api` object is shared, and create_app() rebuilds its OpenAPI
    # spec. Build a normal app again so later tests see every module in the spec.
    monkeypatch.undo()
    create_app("testing")


def test_module_routes_are_served_under_api_v1(app_with_demo_module):
    client = app_with_demo_module.test_client()

    assert client.get("/api/v1/demo/ping").get_json() == {"pong": True}
    assert client.get("/api/demo/ping").status_code == 404


def test_openapi_spec_lists_versioned_module_paths(app_with_demo_module):
    paths = app_with_demo_module.test_client().get("/api/openapi.json").get_json()["paths"]

    assert "/api/v1/demo/ping" in paths
    assert "/api/health" in paths


def test_health_stays_unversioned(client, database):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404
