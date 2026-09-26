"""Feature routes live under /api/v1; health and docs stay unversioned."""

from app.routes import API_PREFIX, BLUEPRINTS


def test_every_feature_blueprint_is_served_under_api_v1(app):
    for blp in BLUEPRINTS:
        rules = [r.rule for r in app.url_map.iter_rules() if r.endpoint.startswith(f"{blp.name}.")]

        assert rules, f"blueprint {blp.name!r} has no routes"
        assert all(rule.startswith(f"{API_PREFIX}/") for rule in rules), rules


def test_health_stays_unversioned(client, database):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404
