"""HTTP routes for admin: /api/v1/admin/...

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.models.enums import UserRole
from app.schemas.admin import AdminDashboardSchema
from app.services import admin_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("admin", __name__, description="Admin: users, CA verification and service catalog")


@blp.route("/admin/dashboard")
class AdminDashboard(MethodView):
    @roles_required(UserRole.ADMIN)
    @blp.response(200, AdminDashboardSchema)
    def get(self):
        return admin_service.get_dashboard(current_user())
