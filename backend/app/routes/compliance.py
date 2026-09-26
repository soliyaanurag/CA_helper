"""HTTP routes for compliance: /api/v1/compliance/...

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.models.enums import UserRole
from app.schemas.compliance import ComplianceDashboardSchema
from app.services import compliance_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint(
    "compliance",
    __name__,
    description="Obligations, compliance calendar, item pages and home dashboard",
)


@blp.route("/compliance/dashboard")
class ComplianceDashboard(MethodView):
    @roles_required(UserRole.BUSINESS)
    @blp.response(200, ComplianceDashboardSchema)
    def get(self):
        return compliance_service.get_dashboard(current_user())
