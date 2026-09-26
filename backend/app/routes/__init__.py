"""HTTP routes: one flask-smorest Blueprint per feature.

    health.py        GET /api/health (unversioned, for Docker/CI healthchecks)
    auth.py          /api/v1/auth/...
    compliance.py    /api/v1/compliance/...
    ca_workspace.py  /api/v1/ca-workspace/...
    admin.py         /api/v1/admin/...

Add a new feature's blueprint to BLUEPRINTS below. Routes stay thin: parse input
(app/schemas/), call one service function (app/services/), serialize the result.
"""

from flask_smorest import Api

from app.routes import admin, auth, ca_workspace, compliance, health

# Every feature route lives under this prefix (docs/API_CONVENTIONS.md).
# /api/health, /api/docs and /api/openapi.json stay unversioned.
API_PREFIX = "/api/v1"

BLUEPRINTS = [
    auth.blp,
    compliance.blp,
    ca_workspace.blp,
    admin.blp,
]


def register_routes(api: Api) -> None:
    """Register the health check, then every feature blueprint under API_PREFIX."""
    api.register_blueprint(health.blp)
    for blp in BLUEPRINTS:
        api.register_blueprint(blp, url_prefix=API_PREFIX)
