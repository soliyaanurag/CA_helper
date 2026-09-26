"""GET /api/health reports whether the API and its database are up."""

from sqlalchemy.exc import OperationalError

from app.extensions import db


def test_health_ok(client, database):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_outage_in_one_log_line(client, database, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db.session, "execute", fail)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.get_json() == {"status": "degraded", "database": "unavailable"}
    [record] = [r for r in caplog.records if r.name == "app.routes.health"]
    assert record.getMessage() == "Health check: database unavailable (Exception)"
    assert record.exc_info is None  # no traceback in the log
