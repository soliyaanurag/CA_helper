"""HTTP routes for core/auth, registered under /api/v1 by create_app().

    POST /api/v1/auth/login   public, 10 per minute per IP
    GET  /api/v1/auth/me      any logged-in user

Routes stay thin: parse input, call one service function, serialize.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.core.auth import services
from app.core.auth.schemas import LoginResponseSchema, LoginSchema, UserSchema
from app.core.auth.tokens import issue_access_token
from app.core.errors import ErrorSchema
from app.core.permissions import current_user, login_required
from app.extensions import limiter

blp = Blueprint("auth", __name__, description="Login and the current user")


@blp.route("/auth/login")
class Login(MethodView):
    @limiter.limit("10 per minute")
    @blp.doc(security=[])  # public: no token needed
    @blp.arguments(LoginSchema)
    @blp.response(200, LoginResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="INVALID_CREDENTIALS")
    @blp.alt_response(403, schema=ErrorSchema, description="ACCOUNT_INACTIVE")
    @blp.alt_response(429, schema=ErrorSchema, description="TOO_MANY_REQUESTS (10 per minute)")
    def post(self, data):
        user = services.authenticate(data["email"], data["password"])
        return {"access_token": issue_access_token(user), "user": user}


@blp.route("/auth/me")
class Me(MethodView):
    @login_required
    @blp.response(200, UserSchema)
    def get(self):
        return current_user()
