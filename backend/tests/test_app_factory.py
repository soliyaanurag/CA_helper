"""The app factory wires up the blueprints and the JSON error format."""

from app import create_app
from app.utils import ApiError
from tests.conftest import TEST_CONFIG

EXPECTED_BLUEPRINTS = {"health", "auth", "compliance", "ca_workspace", "admin"}


def test_every_blueprint_is_registered(app):
    assert set(app.blueprints) >= EXPECTED_BLUEPRINTS


def test_unknown_url_returns_standard_error(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]


def test_api_error_returns_standard_error(app):
    with app.test_request_context():
        result = app.handle_user_exception(
            ApiError(409, "DUPLICATE_PAN", "Already registered.", {"field": "pan"})
        )
        response = app.make_response(result)

    assert response.status_code == 409
    assert response.get_json() == {
        "error": {
            "code": "DUPLICATE_PAN",
            "message": "Already registered.",
            "details": {"field": "pan"},
        }
    }


def test_unhandled_error_returns_standard_500_error():
    app = create_app(TEST_CONFIG)
    app.config["PROPAGATE_EXCEPTIONS"] = False  # behave like production: no traceback

    @app.get("/api/v1/boom")
    def boom():
        raise RuntimeError("boom")

    response = app.test_client().get("/api/v1/boom")

    assert response.status_code == 500
    error = response.get_json()["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert error["message"]
    assert "boom" not in error["message"]  # no exception text leaks to the client


def test_api_root_redirects_to_the_health_check(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/api/health"
