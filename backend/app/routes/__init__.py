"""HTTP routes: one flask-smorest Blueprint per feature.

    health.py        GET /api/health (unversioned; the frontend's API status badge)
    auth.py          /api/v1/auth/...
    compliance.py    /api/v1/compliance/...
    ca_workspace.py  /api/v1/ca-workspace/...
    marketplace.py   /api/v1/marketplace/...
    onboarding.py    /api/v1/onboarding/...
    admin.py         /api/v1/admin/...
    alerts.py        /api/v1/alerts/...
    documents.py     /api/v1/documents/...
    regulatory.py    /api/v1/admin/regulatory/... (news monitor)

Add a new feature's blueprint to BLUEPRINTS below. Routes stay thin: parse input
(app/schemas/), call one service function (app/services/), serialize the result.
"""

from flask_smorest import Api

from app.routes import (
    admin,
    alerts,
    auth,
    ca_workspace,
    compliance,
    documents,
    health,
    marketplace,
    onboarding,
    regulatory,
)

# Every feature route lives under this prefix (docs/API_CONVENTIONS.md).
# /api/health, /api/docs and /api/openapi.json stay unversioned.
API_PREFIX = "/api/v1"

BLUEPRINTS = [
    auth.blp,
    onboarding.blp,
    compliance.blp,
    ca_workspace.blp,
    marketplace.blp,
    admin.blp,
    alerts.blp,
    documents.blp,
    regulatory.blp,
]


def register_routes(api: Api) -> None:
    """Register the health check, then every feature blueprint under API_PREFIX."""
    api.register_blueprint(health.blp)
    for blp in BLUEPRINTS:
        api.register_blueprint(blp, url_prefix=API_PREFIX)
