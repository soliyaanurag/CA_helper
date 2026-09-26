"""HTTP routes for ca workspace: /api/v1/ca-workspace/...

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.models.enums import UserRole
from app.schemas.ca_workspace import CaDashboardSchema
from app.services import ca_workspace_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint(
    "ca_workspace", __name__, description="CA multi-client dashboard and client workspace"
)


@blp.route("/ca-workspace/dashboard")
class CaDashboard(MethodView):
    @roles_required(UserRole.CA)
    @blp.response(200, CaDashboardSchema)
    def get(self):
        return ca_workspace_service.get_dashboard(current_user())
