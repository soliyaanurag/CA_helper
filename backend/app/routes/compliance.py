"""HTTP routes for compliance: /api/v1/compliance/...

    GET /api/v1/compliance/dashboard   business   welcome text (the home dashboard later)
    GET /api/v1/compliance/items       business   the business's filings, soonest due first

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.compliance import ComplianceDashboardSchema, ComplianceItemSchema
from app.services import compliance_service
from app.utils.decorators import current_business, current_user, roles_required

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


# The logged-in business sees all its filings (created when it registered).
@blp.route("/compliance/items", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, ComplianceItemSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def list_items():
    return compliance_service.list_filings(current_business())
