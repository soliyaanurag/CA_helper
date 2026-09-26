"""HTTP routes for accounts: signup, email verification, login and passwords.

    POST /api/v1/auth/signup                 public, 5 per minute per IP
    POST /api/v1/auth/verify-email           public, 10 per minute per IP
    POST /api/v1/auth/verify-email/resend    public, 3 per minute per IP
    POST /api/v1/auth/login                  public, 10 per minute per IP
    POST /api/v1/auth/forgot-password        public, 3 per minute per IP
    POST /api/v1/auth/reset-password         public, 10 per minute per IP
    POST /api/v1/auth/change-password        any logged-in user, 10 per minute per IP
    GET  /api/v1/auth/me                     any logged-in user

Actions without data to return answer 204 (no body); the frontend shows its own
message. Routes stay thin: parse input, call one service function, serialize.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.extensions import limiter
from app.schemas.auth import (
    AuthEmailSchema,
    ChangePasswordSchema,
    LoginResponseSchema,
    LoginSchema,
    ResetPasswordSchema,
    SignupSchema,
    UserSchema,
    VerifyEmailSchema,
)
from app.services import auth_service
from app.utils.decorators import current_user, login_required

blp = Blueprint("auth", __name__, description="Signup, email verification, login and passwords")

TOO_MANY = "TOO_MANY_REQUESTS (rate limit per IP)"
BAD_CODE = "OTP_INVALID (wrong, used or unknown code) or OTP_EXPIRED (ask for a new one)"


@blp.route("/auth/signup")
class Signup(MethodView):
    @limiter.limit("5 per minute")
    @blp.doc(security=[])  # public: no token needed
    @blp.arguments(SignupSchema)
    @blp.response(201, UserSchema)
    @blp.alt_response(409, schema=ErrorSchema, description="EMAIL_TAKEN")
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Create a business or CA account; it can log in once its email is verified."""
        return auth_service.signup(**data)


@blp.route("/auth/verify-email")
class VerifyEmail(MethodView):
    @limiter.limit("10 per minute")
    @blp.doc(security=[])
    @blp.arguments(VerifyEmailSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description=BAD_CODE)
    @blp.alt_response(409, schema=ErrorSchema, description="EMAIL_ALREADY_VERIFIED")
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Verify the email with the 6-digit code sent at signup."""
        auth_service.verify_email(data["email"], data["code"])


@blp.route("/auth/verify-email/resend")
class ResendVerificationCode(MethodView):
    @limiter.limit("3 per minute")
    @blp.doc(security=[])
    @blp.arguments(AuthEmailSchema)
    @blp.response(204)
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Email a new verification code. Always 204, so it never reveals which emails exist."""
        auth_service.resend_verification_code(data["email"])


@blp.route("/auth/login")
class Login(MethodView):
    @limiter.limit("10 per minute")
    @blp.doc(security=[])
    @blp.arguments(LoginSchema)
    @blp.response(200, LoginResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="INVALID_CREDENTIALS")
    @blp.alt_response(403, schema=ErrorSchema, description="ACCOUNT_INACTIVE, EMAIL_NOT_VERIFIED")
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        user = auth_service.authenticate(data["email"], data["password"])
        return {"access_token": auth_service.issue_access_token(user), "user": user}


@blp.route("/auth/forgot-password")
class ForgotPassword(MethodView):
    @limiter.limit("3 per minute")
    @blp.doc(security=[])
    @blp.arguments(AuthEmailSchema)
    @blp.response(204)
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Email a password reset code. Always 204, so it never reveals which emails exist."""
        auth_service.request_password_reset(data["email"])


@blp.route("/auth/reset-password")
class ResetPassword(MethodView):
    @limiter.limit("10 per minute")
    @blp.doc(security=[])
    @blp.arguments(ResetPasswordSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description=BAD_CODE)
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Set a new password with the emailed reset code."""
        auth_service.reset_password(data["email"], data["code"], data["new_password"])


@blp.route("/auth/change-password")
class ChangePassword(MethodView):
    @login_required
    @limiter.limit("10 per minute")
    @blp.arguments(ChangePasswordSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description="WRONG_PASSWORD, SAME_PASSWORD")
    @blp.alt_response(429, schema=ErrorSchema, description=TOO_MANY)
    def post(self, data):
        """Change the logged-in user's password (needs the current one)."""
        auth_service.change_password(current_user(), data["current_password"], data["new_password"])


@blp.route("/auth/me")
class Me(MethodView):
    @login_required
    @blp.response(200, UserSchema)
    def get(self):
        return current_user()
