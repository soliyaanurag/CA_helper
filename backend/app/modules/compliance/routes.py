"""HTTP routes for the compliance module.

URLs: /api/v1/compliance/...  and admin screens under /api/v1/admin/compliance/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.core.db.enums import UserRole
from app.core.permissions import current_user, roles_required
from app.modules.compliance import services
from app.modules.compliance.schemas import ComplianceDashboardSchema

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
        return services.get_dashboard(current_user())
