"""Business logic for accounts: signup, email verification, login and passwords.

signup(full_name, email, password, role) -> User     new unverified account + emailed code
verify_email(email, code)                             marks the email verified
resend_verification_code(email)                       emails a new code (at most one a minute)
authenticate(email, password) -> User                 login (refused until the email is verified)
request_password_reset(email)                         emails a reset code (at most one a minute)
reset_password(email, code, new_password)             sets a new password with that code
change_password(user, current_password, new_password) for a logged-in user
accept_terms(user)                                    records consent (for accounts from before it)
list_users(role, search, page, page_size) / count_users_by_role()   for the admin screens
issue_access_token(user) -> str                       JWT for a logged-in user
get_user(user_id) -> User | None                      used by the JWT user loader
normalize_email(email) -> str

One-time codes (table `email_otps`): 6 random digits, stored as an argon2 hash,
valid for OTP_LIFETIME and OTP_MAX_ATTEMPTS wrong guesses. Only the newest code
for a purpose counts, so asking for a new code cancels the old one.
"""

import logging
import secrets
import uuid
from datetime import timedelta

from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import EmailOtp, User
from app.models.base import utcnow
from app.models.email_otp import OtpPurpose
from app.models.enums import UserRole
from app.utils.email import send_email
from app.utils.passwords import hash_password, needs_rehash, verify_password

log = logging.getLogger(__name__)

OTP_LIFETIME = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
# A new code is sent at most once per OTP_RESEND_WAIT per account and purpose,
# so nobody can flood someone's inbox.
OTP_RESEND_WAIT = timedelta(seconds=60)

# Subject and template (app/templates/email/<template>.txt) of each code email.
CODE_EMAILS = {
    OtpPurpose.VERIFY_EMAIL: ("Your CA Helper verification code", "verify_email"),
    OtpPurpose.RESET_PASSWORD: ("Your CA Helper password reset code", "reset_password"),
}


def normalize_email(email: str) -> str:
    """Emails are stored and compared trimmed and lowercased."""
    return email.strip().lower()


def _user_by_email(email: str) -> User | None:
    return db.session.scalar(select(User).where(User.email == normalize_email(email)))


def _user_by_email_or_404(email: str) -> User:
    user = _user_by_email(email)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "No account uses this email.")
    return user


# --- One-time codes (helpers; none of them commits) ------------------------------


def _newest_code(user: User, purpose: OtpPurpose) -> EmailOtp | None:
    return db.session.scalar(
        select(EmailOtp)
        .where(EmailOtp.user_id == user.id, EmailOtp.purpose == purpose)
        .order_by(EmailOtp.created_at.desc())
        .limit(1)
    )


def _sent_recently(user: User, purpose: OtpPurpose) -> bool:
    newest = _newest_code(user, purpose)
    return newest is not None and newest.created_at > utcnow() - OTP_RESEND_WAIT


def _add_code(user: User, purpose: OtpPurpose) -> str:
    """Add a new code row for the user and return the plain code. Does not commit."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.session.add(
        EmailOtp(
            user=user,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=utcnow() + OTP_LIFETIME,
        )
    )
    return code


def _email_code(user: User, purpose: OtpPurpose, code: str) -> None:
    subject, template = CODE_EMAILS[purpose]
    minutes = int(OTP_LIFETIME.total_seconds() // 60)
    send_email(user.email, subject, template, name=user.full_name, code=code, minutes=minutes)


def _use_code(user: User | None, purpose: OtpPurpose, code: str) -> None:
    """Mark the user's newest code for `purpose` as used if `code` matches it.

    Raises 400 OTP_INVALID (no such code, already used, wrong digits; also for an
    unknown email) or 400 OTP_EXPIRED (too old, or too many wrong guesses).
    A wrong guess is committed before the error is raised, so it counts even
    though the request fails. Otherwise does not commit.
    """
    otp = _newest_code(user, purpose) if user else None
    if otp is None or otp.used_at is not None:
        raise ApiError(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    if otp.expires_at <= utcnow() or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise ApiError(
            400,
            "OTP_EXPIRED",
            "This code has expired or was entered wrongly too many times. Ask for a new one.",
        )
    if not verify_password(otp.code_hash, code):
        otp.attempts += 1
        db.session.commit()
        raise ApiError(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    otp.used_at = utcnow()


# --- Signup and email verification ------------------------------------------------


def signup(full_name: str, email: str, password: str, role: UserRole, terms_accepted: bool) -> User:
    """Create an unverified business or CA account and email it a verification code.

    409 EMAIL_TAKEN if the email already has an account. Admins are never created
    here (the request schema allows only business and ca). `terms_accepted` is always
    True (the schema requires it); it records when the user agreed to the terms.
    """
    email = normalize_email(email)
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
        terms_accepted_at=utcnow() if terms_accepted else None,
    )
    db.session.add(user)
    code = _add_code(user, OtpPurpose.VERIFY_EMAIL)
    db.session.commit()
    _email_code(user, OtpPurpose.VERIFY_EMAIL, code)
    log.info("User %s signed up as %s", user.id, role)
    return user


def verify_email(email: str, code: str) -> None:
    """Mark the account's email as verified if `code` is its newest verification code.

    409 EMAIL_ALREADY_VERIFIED; otherwise the errors of _use_code().
    """
    user = _user_by_email(email)
    if user is not None and user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    _use_code(user, OtpPurpose.VERIFY_EMAIL, code)
    user.email_verified_at = utcnow()
    db.session.commit()
    log.info("User %s verified their email", user.id)


def resend_verification_code(email: str) -> None:
    """Email a new verification code to an unverified account.

    404 USER_NOT_FOUND for an unknown email, 409 EMAIL_ALREADY_VERIFIED. Does nothing when
    a code was sent less than OTP_RESEND_WAIT ago.
    """
    user = _user_by_email_or_404(email)
    if user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    if _sent_recently(user, OtpPurpose.VERIFY_EMAIL):
        return
    code = _add_code(user, OtpPurpose.VERIFY_EMAIL)
    db.session.commit()
    _email_code(user, OtpPurpose.VERIFY_EMAIL, code)


# --- Login ------------------------------------------------------------------------


def authenticate(email: str, password: str) -> User:
    """Return the user for these credentials, or raise ApiError.

    401 INVALID_CREDENTIALS for an unknown email or a wrong password (the same
    error for both); 403 EMAIL_NOT_VERIFIED until the user has entered their emailed code.
    Rehashes the password if argon2's parameters changed since it was stored.
    """
    user = db.session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not verify_password(user.password_hash, password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if user.email_verified_at is None:
        raise ApiError(403, "EMAIL_NOT_VERIFIED", "Verify your email before logging in.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        log.info("Rehashed password for user %s", user.id)
    db.session.commit()
    log.info("User %s logged in", user.id)
    return user


def issue_access_token(user: User) -> str:
    """Access token: `sub` = the user's id, `role` = business | ca | admin, `exp` from
    JWT_ACCESS_TOKEN_EXPIRES."""
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


def get_user(user_id: str) -> User | None:
    """The user with this id, or None."""
    try:
        key = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, key)


# --- Passwords --------------------------------------------------------------------


def _email_password_changed(user: User) -> None:
    """Tell the owner, so a change they did not make does not go unnoticed."""
    send_email(
        user.email, "Your CA Helper password was changed", "password_changed", name=user.full_name
    )


def request_password_reset(email: str) -> None:
    """Email a password reset code to an active account.

    404 USER_NOT_FOUND for an unknown email. Does nothing when a reset code was sent less
    than OTP_RESEND_WAIT ago. Works for unverified accounts too.
    """
    user = _user_by_email_or_404(email)
    if _sent_recently(user, OtpPurpose.RESET_PASSWORD):
        return
    code = _add_code(user, OtpPurpose.RESET_PASSWORD)
    db.session.commit()
    _email_code(user, OtpPurpose.RESET_PASSWORD, code)


def reset_password(email: str, code: str, new_password: str) -> None:
    """Set a new password if `code` is the account's newest reset code.

    The code proves the user owns the email, so an unverified email becomes
    verified too. Errors: those of _use_code().
    """
    user = _user_by_email(email)
    _use_code(user, OtpPurpose.RESET_PASSWORD, code)
    user.password_hash = hash_password(new_password)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    db.session.commit()
    _email_password_changed(user)
    log.info("User %s reset their password", user.id)


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Change a logged-in user's password.

    400 WRONG_PASSWORD if `current_password` is wrong (400, not 401: a 401 would
    log the user out); 400 SAME_PASSWORD if the new password is the current one.
    """
    if not verify_password(user.password_hash, current_password):
        raise ApiError(400, "WRONG_PASSWORD", "Your current password is wrong.")
    if new_password == current_password:
        raise ApiError(400, "SAME_PASSWORD", "Choose a password different from your current one.")
    user.password_hash = hash_password(new_password)
    db.session.commit()
    _email_password_changed(user)
    log.info("User %s changed their password", user.id)


def accept_terms(user: User) -> None:
    """Record that a user who signed up before the consent step agreed to the terms."""
    if user.terms_accepted_at is None:
        user.terms_accepted_at = utcnow()
    db.session.commit()
    log.info("User %s accepted the terms", user.id)


# --- For the admin module ---------------------------------------------------------------


def list_users(role: UserRole | None, search: str | None, page: int, page_size: int) -> dict:
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
