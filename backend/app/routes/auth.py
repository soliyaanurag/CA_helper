"""HTTP routes for accounts: signup, email verification, login and passwords.

    POST /api/v1/auth/signup                 public
    POST /api/v1/auth/verify-email           public
    POST /api/v1/auth/verify-email/resend    public
    POST /api/v1/auth/login                  public
    POST /api/v1/auth/forgot-password        public
    POST /api/v1/auth/reset-password         public
    POST /api/v1/auth/change-password        any logged-in user
    POST /api/v1/auth/accept-terms           any logged-in user (consent for older accounts)
    GET  /api/v1/auth/me                     any logged-in user

Actions without data to return answer 204 (no body); the frontend shows its own
message. Routes stay thin: parse input, call one service function, serialize.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import ErrorSchema
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

BAD_CODE = "OTP_INVALID (wrong, used or unknown code) or OTP_EXPIRED (ask for a new one)"


@blp.route("/auth/signup")
class Signup(MethodView):
    @blp.doc(security=[])  # public: no token needed
    @blp.arguments(SignupSchema)
    @blp.response(201, UserSchema)
    @blp.alt_response(409, schema=ErrorSchema, description="EMAIL_TAKEN")
    def post(self, data):
        """Create a business or CA account; it can log in once its email is verified."""
        return auth_service.signup(**data)


@blp.route("/auth/verify-email")
class VerifyEmail(MethodView):
    @blp.doc(security=[])
    @blp.arguments(VerifyEmailSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description=BAD_CODE)
    @blp.alt_response(409, schema=ErrorSchema, description="EMAIL_ALREADY_VERIFIED")
    def post(self, data):
        """Verify the email with the 6-digit code sent at signup."""
        auth_service.verify_email(data["email"], data["code"])


@blp.route("/auth/verify-email/resend")
class ResendVerificationCode(MethodView):
    @blp.doc(security=[])
    @blp.arguments(AuthEmailSchema)
    @blp.response(204)
    @blp.alt_response(404, schema=ErrorSchema, description="USER_NOT_FOUND")
    @blp.alt_response(409, schema=ErrorSchema, description="EMAIL_ALREADY_VERIFIED")
    def post(self, data):
        """Email a new verification code."""
        auth_service.resend_verification_code(data["email"])


@blp.route("/auth/login")
class Login(MethodView):
    @blp.doc(security=[])
    @blp.arguments(LoginSchema)
    @blp.response(200, LoginResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="INVALID_CREDENTIALS")
    @blp.alt_response(403, schema=ErrorSchema, description="ACCOUNT_INACTIVE, EMAIL_NOT_VERIFIED")
    def post(self, data):
        user = auth_service.authenticate(data["email"], data["password"])
        return {
            "access_token": auth_service.issue_access_token(user),
            "user": user,
            "terms_accepted": user.terms_accepted_at is not None,
        }


@blp.route("/auth/forgot-password")
class ForgotPassword(MethodView):
    @blp.doc(security=[])
    @blp.arguments(AuthEmailSchema)
    @blp.response(204)
    @blp.alt_response(404, schema=ErrorSchema, description="USER_NOT_FOUND")
    def post(self, data):
        """Email a password reset code."""
        auth_service.request_password_reset(data["email"])


@blp.route("/auth/reset-password")
class ResetPassword(MethodView):
    @blp.doc(security=[])
    @blp.arguments(ResetPasswordSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description=BAD_CODE)
    def post(self, data):
        """Set a new password with the emailed reset code."""
        auth_service.reset_password(data["email"], data["code"], data["new_password"])


@blp.route("/auth/change-password")
class ChangePassword(MethodView):
    @login_required
    @blp.arguments(ChangePasswordSchema)
    @blp.response(204)
    @blp.alt_response(400, schema=ErrorSchema, description="WRONG_PASSWORD, SAME_PASSWORD")
    def post(self, data):
        """Change the logged-in user's password (needs the current one)."""
        auth_service.change_password(current_user(), data["current_password"], data["new_password"])


@blp.route("/auth/accept-terms")
class AcceptTerms(MethodView):
    @login_required
    @blp.response(204)
    def post(self):
        """Agree to the Terms and Privacy Policy (for users who signed up before consent)."""
        auth_service.accept_terms(current_user())


@blp.route("/auth/me")
class Me(MethodView):
    @login_required
    @blp.response(200, UserSchema)
    def get(self):
        return current_user()
