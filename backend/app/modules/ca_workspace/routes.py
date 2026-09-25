"""HTTP routes for the ca_workspace module.

URLs: /api/v1/ca-workspace/...  and admin screens under /api/v1/admin/ca-workspace/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.core.db.enums import UserRole
from app.core.permissions import current_user, roles_required
from app.modules.ca_workspace import services
from app.modules.ca_workspace.schemas import CaDashboardSchema

blp = Blueprint(
    "ca_workspace",
    __name__,
    description="CA multi-client dashboard and client workspace",
)


@blp.route("/ca-workspace/dashboard")
class CaDashboard(MethodView):
    @roles_required(UserRole.CA)
    @blp.response(200, CaDashboardSchema)
    def get(self):
        return services.get_dashboard(current_user())
