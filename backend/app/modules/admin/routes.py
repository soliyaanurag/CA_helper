"""HTTP routes for the admin module.

URLs: /api/v1/admin/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.core.db.enums import UserRole
from app.core.permissions import current_user, roles_required
from app.modules.admin import services
from app.modules.admin.schemas import AdminDashboardSchema

blp = Blueprint(
    "admin",
    __name__,
    description="Admin: users, CA verification and service catalog",
)


@blp.route("/admin/dashboard")
class AdminDashboard(MethodView):
    @roles_required(UserRole.ADMIN)
    @blp.response(200, AdminDashboardSchema)
    def get(self):
        return services.get_dashboard(current_user())
