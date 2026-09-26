"""The app factory wires up the blueprints, OpenAPI docs and the JSON error format."""

from app.errors import ApiError

EXPECTED_BLUEPRINTS = {"health", "auth", "compliance", "ca_workspace", "admin"}


def test_every_blueprint_is_registered(app):
    assert set(app.blueprints) >= EXPECTED_BLUEPRINTS


def test_openapi_spec_lists_health_and_every_tag(client):
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    spec = response.get_json()
    assert spec["info"]["title"] == "CA Helper API"
    assert "/api/health" in spec["paths"]
    assert {tag["name"] for tag in spec["tags"]} >= EXPECTED_BLUEPRINTS


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
