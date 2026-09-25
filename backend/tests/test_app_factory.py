"""The app factory wires up modules, OpenAPI docs and the JSON error format."""

from app.core.errors import ApiError
from app.modules import discover_modules, module_name

EXPECTED_MODULES = {
    "onboarding",
    "compliance",
    "alerts",
    "documents",
    "assistant",
    "regulatory",
    "marketplace",
    "ca_workspace",
    "admin",
}


def test_all_modules_are_discovered():
    assert {module_name(m) for m in discover_modules()} == EXPECTED_MODULES


def test_every_module_blueprint_is_registered(app):
    assert set(app.blueprints) >= EXPECTED_MODULES


def test_openapi_spec_lists_health_and_module_tags(client):
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    spec = response.get_json()
    assert spec["info"]["title"] == "CA Helper API"
    assert "/api/health" in spec["paths"]
    assert {tag["name"] for tag in spec["tags"]} >= EXPECTED_MODULES


def test_swagger_ui_is_served(client):
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert b"swagger-ui" in response.data


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


def test_api_root_redirects_to_the_docs(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/api/docs"
    assert "/" not in client.get("/api/openapi.json").get_json()["paths"]
