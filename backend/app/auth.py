"""Accounts: signup with an emailed code, login, passwords and the email switch."""

import logging
import re
import secrets
import uuid
from datetime import timedelta

from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.models import EmailOtp, OtpPurpose, User, UserRole, db, utcnow
from app.utils import (
    MISSING,
    ApiError,
    current_user,
    hash_password,
    json_body,
    login_required,
    roles_required,
    send_email,
    validation_error,
    verify_password,
)

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)

# A code works once, for this long, and only the newest code of a user counts.
CODE_LIFETIME = timedelta(minutes=10)

# The password rule. The frontend checks the same rule (frontend/src/lib/passwords.js).
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128  # a huge password would tie up argon2
PASSWORD_RULE_TEXT = "Use 8 to 128 characters, with at least one letter and one number."
MAX_EMAIL_LENGTH = 254
MAX_NAME_LENGTH = 200
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_PATTERN = re.compile(r"^[0-9]{6}$")

# Subject and template of each code email.
CODE_EMAILS = {
    OtpPurpose.VERIFY_EMAIL: ("Your CA Helper verification code", "verify_email"),
    OtpPurpose.RESET_PASSWORD: ("Your CA Helper password reset code", "reset_password"),
}


def normalize_email(email: str) -> str:
    """Emails are stored and compared trimmed and lowercased."""
    return email.strip().lower()


def user_to_dict(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}


def issue_access_token(user: User) -> str:
    """A JWT: `sub` = the user's id, `role` = business | ca | admin."""
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


def get_user(user_id: str) -> User | None:
    """The user with this id, or None (used by the JWT user loader)."""
    try:
        return db.session.get(User, uuid.UUID(user_id))
    except (TypeError, ValueError):
        return None


def find_user_by_email(email: str) -> User | None:
    return db.session.scalar(select(User).where(User.email == normalize_email(email)))


# --- Checking the request fields ---------------------------------------------------------


def check_email(data: dict, errors: dict) -> str:
    """The `email` field (any text up to 254 characters; it only has to match an account)."""
    email = data.get("email")
    if email is None:
        errors["email"] = [MISSING]
    elif not isinstance(email, str) or not 1 <= len(email) <= MAX_EMAIL_LENGTH:
        errors["email"] = [f"Length must be between 1 and {MAX_EMAIL_LENGTH}."]
    return email


def check_new_password(data: dict, field: str, errors: dict) -> str:
    """Every password we store must follow the rule (signup, reset, change)."""
    password = data.get(field)
    if password is None:
        errors[field] = [MISSING]
    elif not (
        isinstance(password, str)
        and PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH
        and re.search(r"[A-Za-z]", password)
        and re.search(r"[0-9]", password)
    ):
        errors[field] = [PASSWORD_RULE_TEXT]
    return password


def check_password(data: dict, field: str, errors: dict) -> str:
    """A password that is only compared (login, the current password)."""
    password = data.get(field)
    if password is None:
        errors[field] = [MISSING]
    elif not isinstance(password, str) or not 1 <= len(password) <= PASSWORD_MAX_LENGTH:
        errors[field] = [f"Length must be between 1 and {PASSWORD_MAX_LENGTH}."]
    return password


def check_code(data: dict, errors: dict) -> str:
    code = data.get("code")
    if code is None:
        errors["code"] = [MISSING]
    elif not isinstance(code, str) or not CODE_PATTERN.match(code):
        errors["code"] = ["Enter the 6-digit code."]
    return code


# --- One-time codes ----------------------------------------------------------------------


def new_code(user: User, purpose: str) -> str:
    """Add a new code for the user and return it (only its hash is stored)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.session.add(
        EmailOtp(
            user=user,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=utcnow() + CODE_LIFETIME,
        )
    )
    return code


def email_code(user: User, purpose: str, code: str) -> None:
    subject, template = CODE_EMAILS[purpose]
    minutes = int(CODE_LIFETIME.total_seconds() // 60)
    send_email(user.email, subject, template, name=user.full_name, code=code, minutes=minutes)


def use_code(user: User | None, purpose: str, code: str) -> None:
    """Mark the user's newest code for `purpose` as used if `code` is that code.

    400 OTP_INVALID (no code, already used, wrong digits, unknown email) or
    400 OTP_EXPIRED (older than CODE_LIFETIME).
    """
    otp = None
    if user is not None:
        otp = db.session.scalar(
            select(EmailOtp)
            .where(EmailOtp.user_id == user.id, EmailOtp.purpose == purpose)
            .order_by(EmailOtp.created_at.desc())
            .limit(1)
        )
    if otp is None or otp.used_at is not None:
        raise ApiError(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    if otp.expires_at <= utcnow():
        raise ApiError(400, "OTP_EXPIRED", "This code has expired. Ask for a new one.")
    if not verify_password(otp.code_hash, code):
        raise ApiError(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    otp.used_at = utcnow()


def email_password_changed(user: User) -> None:
    """Tell the owner, so a change they did not make does not go unnoticed."""
    send_email(
        user.email, "Your CA Helper password was changed", "password_changed", name=user.full_name
    )


# --- Routes ------------------------------------------------------------------------------


@bp.post("/auth/signup")
def signup():
    """Create a business or CA account; it can log in once its email is verified."""
    data = json_body()
    errors = {}
    full_name = data.get("full_name")
    if full_name is None:
        errors["full_name"] = [MISSING]
    elif not isinstance(full_name, str) or not 1 <= len(full_name) <= MAX_NAME_LENGTH:
        errors["full_name"] = [f"Length must be between 1 and {MAX_NAME_LENGTH}."]
    elif not full_name.strip():
        errors["full_name"] = ["Must not be blank."]
    email = data.get("email")
    if email is None:
        errors["email"] = [MISSING]
    elif (
        not isinstance(email, str)
        or len(email) > MAX_EMAIL_LENGTH
        or not EMAIL_PATTERN.match(email)
    ):
        errors["email"] = ["Not a valid email address."]
    password = check_new_password(data, "password", errors)
    role = data.get("role")
    if role is None:
        errors["role"] = [MISSING]
    elif role not in (UserRole.BUSINESS, UserRole.CA):  # admins never sign up
        errors["role"] = ["Choose business or ca."]
    if data.get("terms_accepted") is None:
        errors["terms_accepted"] = [MISSING]
    elif data["terms_accepted"] is not True:
        errors["terms_accepted"] = ["Agree to the Terms and Privacy Policy to sign up."]
    if errors:
        raise validation_error(errors)

    email = normalize_email(email)
    if find_user_by_email(email):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
        terms_accepted_at=utcnow(),
    )
    db.session.add(user)
    code = new_code(user, OtpPurpose.VERIFY_EMAIL)
    db.session.commit()
    email_code(user, OtpPurpose.VERIFY_EMAIL, code)
    log.info("User %s signed up as %s", user.id, role)
    return jsonify(user_to_dict(user)), 201


@bp.post("/auth/verify-email")
def verify_email():
    """Verify the email with the 6-digit code sent at signup."""
    data = json_body()
    errors = {}
    email = check_email(data, errors)
    code = check_code(data, errors)
    if errors:
        raise validation_error(errors)

    user = find_user_by_email(email)
    if user is not None and user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    use_code(user, OtpPurpose.VERIFY_EMAIL, code)
    user.email_verified_at = utcnow()
    db.session.commit()
    log.info("User %s verified their email", user.id)
    return "", 204


@bp.post("/auth/verify-email/resend")
def resend_verification_code():
    """Email a new verification code; it replaces the old one."""
    errors = {}
    email = check_email(json_body(), errors)
    if errors:
        raise validation_error(errors)

    user = find_user_by_email(email)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "No account uses this email.")
    if user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    code = new_code(user, OtpPurpose.VERIFY_EMAIL)
    db.session.commit()
    email_code(user, OtpPurpose.VERIFY_EMAIL, code)
    return "", 204


@bp.post("/auth/login")
def login():
    data = json_body()
    errors = {}
    email = check_email(data, errors)
    password = check_password(data, "password", errors)
    if errors:
        raise validation_error(errors)

    user = find_user_by_email(email)
    if user is None or not verify_password(user.password_hash, password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if user.email_verified_at is None:
        raise ApiError(403, "EMAIL_NOT_VERIFIED", "Verify your email before logging in.")
    log.info("User %s logged in", user.id)
    return jsonify({"access_token": issue_access_token(user), "user": user_to_dict(user)})


@bp.post("/auth/forgot-password")
def forgot_password():
    """Email a password reset code (unverified accounts too)."""
    errors = {}
    email = check_email(json_body(), errors)
    if errors:
        raise validation_error(errors)

    user = find_user_by_email(email)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "No account uses this email.")
    code = new_code(user, OtpPurpose.RESET_PASSWORD)
    db.session.commit()
    email_code(user, OtpPurpose.RESET_PASSWORD, code)
    return "", 204


@bp.post("/auth/reset-password")
def reset_password():
    """Set a new password with the emailed reset code. The code proves the user owns the
    email, so an unverified email becomes verified too."""
    data = json_body()
    errors = {}
    email = check_email(data, errors)
    code = check_code(data, errors)
    new_password = check_new_password(data, "new_password", errors)
    if errors:
        raise validation_error(errors)

    user = find_user_by_email(email)
    use_code(user, OtpPurpose.RESET_PASSWORD, code)
    user.password_hash = hash_password(new_password)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    db.session.commit()
    email_password_changed(user)
    log.info("User %s reset their password", user.id)
    return "", 204


@bp.post("/auth/change-password")
@login_required
def change_password():
    """Change the logged-in user's password. A wrong current password is 400, not 401:
    a 401 would log the user out."""
    data = json_body()
    errors = {}
    current_password = check_password(data, "current_password", errors)
    new_password = check_new_password(data, "new_password", errors)
    if errors:
        raise validation_error(errors)

    user = current_user()
    if not verify_password(user.password_hash, current_password):
        raise ApiError(400, "WRONG_PASSWORD", "Your current password is wrong.")
    if new_password == current_password:
        raise ApiError(400, "SAME_PASSWORD", "Choose a password different from your current one.")
    user.password_hash = hash_password(new_password)
    db.session.commit()
    email_password_changed(user)
    log.info("User %s changed their password", user.id)
    return "", 204


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(user_to_dict(current_user()))


@bp.get("/auth/settings")
@roles_required(UserRole.BUSINESS, UserRole.CA)
def get_settings():
    return jsonify({"email_notifications": current_user().email_notifications})


@bp.put("/auth/settings")
@roles_required(UserRole.BUSINESS, UserRole.CA)
def save_settings():
    """Switch notification emails on or off. Emails with a code always go out."""
    value = json_body().get("email_notifications")
    if value is None:
        raise validation_error({"email_notifications": [MISSING]})
    if not isinstance(value, bool):
        raise validation_error({"email_notifications": ["Not a valid boolean."]})
    user = current_user()
    user.email_notifications = value
    db.session.commit()
    return jsonify({"email_notifications": user.email_notifications})


# --- For the admin module ----------------------------------------------------------------


def list_users(role, search, page: int, page_size: int) -> dict:
    """Accounts, newest first, optionally of one role and matching `search` (in the
    name or email). Paginated: {items, page, page_size, total}."""
    stmt = select(User).order_by(User.created_at.desc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))
    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    return {"items": result.items, "page": page, "page_size": page_size, "total": result.total}


def count_users_by_role() -> dict:
    """{"business": n, "ca": n, "admin": n} over all accounts."""
    counts = {role.value: 0 for role in UserRole}
    for role in db.session.scalars(select(User.role)):
        counts[role] += 1
    return counts
