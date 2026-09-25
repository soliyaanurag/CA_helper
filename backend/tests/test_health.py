"""GET /api/health reports the API and database as healthy."""


def test_health_ok(client, database):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}
