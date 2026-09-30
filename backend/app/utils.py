"""Helpers every feature uses: errors, access control, email, passwords, Gemini, GSTIN
checks, amounts, the upload checks and the page shapes of list endpoints.
"""

import json
import logging
import re
import smtplib
import uuid
from collections.abc import Callable
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from flask import Flask, current_app, request
from flask_jwt_extended import get_current_user, verify_jwt_in_request
from jinja2 import Template
from sqlalchemy import select
from werkzeug.exceptions import HTTPException

from app.models import Business, db, User, UserRole


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# --- errors ------------------------------------------------------------------------


class ApiError(Exception):
    """An expected error with a specific HTTP status and error code."""

    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict:
    """Build the standard error payload."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def default_code(status: int) -> str:
    """Default error code for an HTTP status, e.g. 404 -> "NOT_FOUND"."""
    if status == 422:
        return "VALIDATION_ERROR"
    try:
        return HTTPStatus(status).name
    except ValueError:
        return "ERROR"


def register_error_handlers(app: Flask) -> None:
    """Answer every error in the standard JSON shape."""

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_body(error.code, error.message, error.details), error.status

    # 404, 405, 413, ... and 500 (an unexpected exception arrives as InternalServerError,
    # whose text is generic, so the exception's own text never reaches the client).
    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        status = error.code or 500
        return error_body(default_code(status), error.description or HTTPStatus(status).phrase), status


# The message of a required field that was not sent.
MISSING = "Missing data for required field."


def json_body() -> dict:
    """The request's JSON object ({} when the body is empty or not a JSON object)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def validation_error(errors: dict, location: str = "json") -> ApiError:
    """The 422 answer for invalid fields: details {location: {field: [message]}}."""
    return ApiError(422, "VALIDATION_ERROR", "Some fields are invalid.", {location: errors})


PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


def read_page_args(errors: dict) -> tuple[int, int]:
    """?page= (from 1) and ?page_size= (1 to 100, default 20) of a list endpoint. A wrong
    value is added to `errors` (the caller raises the 422 with its other query errors)."""
    numbers = {}
    for name, default, largest in (("page", 1, None), ("page_size", PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX)):
        text = request.args.get(name)
        numbers[name] = default
        if text is None:
            continue
        try:
            value = int(text)
        except ValueError:
            errors[name] = ["Not a valid integer."]
            continue
        if largest is None and value < 1:
            errors[name] = ["Must be greater than or equal to 1."]
        elif largest is not None and not 1 <= value <= largest:
            errors[name] = [f"Must be greater than or equal to 1 and less than or equal to {largest}."]
        numbers[name] = value
    return numbers["page"], numbers["page_size"]


def read_uuid(value):
    """A UUID from a request value (text), or None when it is not one."""
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def iso(value) -> str | None:
    """A date or datetime as ISO text for JSON, e.g. "2026-10-13" (None stays None)."""
    return value.isoformat() if value is not None else None


def money(value) -> str | None:
    """An amount as text with 2 decimals, e.g. "1250.00" (None stays None)."""
    if value is None:
        return None
    return f"{Decimal(value).quantize(Decimal('0.01')):f}"


# --- pagination --------------------------------------------------------------------------


PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


# --- passwords ---------------------------------------------------------------------------


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True if `password` matches the stored hash. Never raises for a wrong password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# --- email -------------------------------------------------------------------------


log = logging.getLogger(__name__)

# Messages "sent" while MAIL_SUPPRESS_SEND is on (tests read and clear this list).
outbox: list[EmailMessage] = []

# The text of every email, rendered with Jinja (plain text, no HTML escaping).
EMAIL_TEMPLATES = {
    "ca_rejected": """Hello {{ name }},

We could not verify your CA Helper profile. The reason:

    {{ reason }}

Correct your profile (or upload your Certificate of Practice again) and save it:
it then goes back to the admin for another check.

CA Helper
""",
    "ca_verified": """Hello {{ name }},

Your CA Helper profile is verified. Businesses can now find you under "Find a CA"
and send you requests.

CA Helper
""",
    "engagement_accepted": """Hello {{ owner_name }},

Good news: {{ ca_name }} has accepted your request at their listed prices.
The filings in it are now marked "With CA".

You can see the details in "My engagements" in CA Helper.

CA Helper
""",
    "engagement_declined": """Hello {{ owner_name }},

{{ ca_name }} has declined your request. The filings in it are free again, so you
can request another CA from "Find a CA" in CA Helper.

CA Helper
""",
    "engagement_expired": """Hello {{ owner_name }},

{{ ca_name }} did not answer your request within 48 hours, so it has expired.
The filings in it are free again.

To pick another CA, open "Find a CA" in CA Helper and choose the service:
{{ service_names }}

CA Helper
""",
    "engagement_quoted": """Hello {{ owner_name }},

{{ ca_name }} has sent you a quote with new prices for your request.

Their reason:
{{ reason }}

Open "My engagements" in CA Helper to see the new prices and accept or reject the quote.

CA Helper
""",
    "engagement_requested": """Hello {{ ca_name }},

{{ business_name }} has sent you a request for {{ filing_count }} filing{{ "s" if filing_count != 1 }}.

Open "My engagements" in CA Helper to accept it at your listed prices, send a
quote with a reason, or decline it. Please answer within 48 hours.

CA Helper
""",
    "notification": """Hello {{ name }},

{{ title }}

{{ body }}

You can see it in the notification tray (the bell) in CA Helper.
To change which emails you get, open "Notification settings".

CA Helper
""",
    "password_changed": """Hello {{ name }},

The password of your CA Helper account was just changed.

If this was you, there is nothing to do. If it was not, reset your password at once with
"Forgot password?" on the login page.

CA Helper
""",
    "pro_bono_matched": """Hello {{ owner_name }},

Good news: {{ ca_name }} has taken your pro-bono request and will help you with
those filings for free. The filings are now marked "With CA".

You can see the details in "My engagements" in CA Helper.

CA Helper
""",
    "reminders": """Hello {{ name }},

{% if lines|length == 1 %}One filing needs your attention:{% else %}{{ lines|length }} filings need your attention:{% endif %}
{% for line in lines %}
  - {{ line }}
{%- endfor %}

Open CA Helper to see each filing (the bell lists them too).
To change which emails you get, open "Notification settings".

CA Helper
""",
    "reset_password": """Hello {{ name }},

Someone asked to reset the password of your CA Helper account. Your code is:

    {{ code }}

It expires in {{ minutes }} minutes. Enter it on the "Reset your password" page.

If this was not you, ignore this email: your password stays the same.

CA Helper
""",
    "verify_email": """Hello {{ name }},

Welcome to CA Helper. Your email verification code is:

    {{ code }}

It expires in {{ minutes }} minutes. Enter it on the "Verify your email" page to finish signing up.

If you did not create a CA Helper account, you can ignore this email.

CA Helper
""",
}


def send_email(to: str, subject: str, template: str, **context) -> bool:
    """Send one plain-text email. Returns True if it was handed to the SMTP server."""
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(Template(EMAIL_TEMPLATES[template]).render(**context))

    if config["MAIL_SUPPRESS_SEND"]:
        outbox.append(message)
        return True
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10) as smtp:
            smtp.send_message(message)
    except OSError as error:  # smtplib's errors are OSErrors too
        # Only the error type: its text can contain the recipient's address (PII).
        log.error("Could not send the %s email: %s", template, type(error).__name__)
        return False
    log.info("Sent the %s email", template)
    return True


# --- access control --------------------------------------------------------------------------


def current_user() -> User:
    """The logged-in, active user of this request. Call only behind @roles_required."""
    return get_current_user()


def current_business_or_none() -> Business | None:
    """The logged-in business user's registered business, or None before registration."""
    return db.session.scalar(
        select(Business).where(Business.user_id == current_user().id)
    )


def current_business() -> Business:
    """The logged-in business user's registered business. Call only behind
    @roles_required(UserRole.BUSINESS). 404 BUSINESS_NOT_FOUND before registration."""
    business = current_business_or_none()
    if business is None:
        raise ApiError(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    return business


def roles_required(*roles: UserRole) -> Callable:
    """Allow the endpoint only for logged-in users with one of `roles`."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Raises for a missing/bad token; loads the user and rejects inactive ones.
            verify_jwt_in_request()
            if current_user().role not in roles:
                raise ApiError(403, "FORBIDDEN", "You do not have access to this page.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def login_required(view: Callable) -> Callable:
    """Allow the endpoint for any logged-in, active user (every role)."""
    return roles_required(*UserRole)(view)


def require_ca_access(business_id) -> None:
    """Stop unless the logged-in CA has an ACTIVE engagement with this business.

    Answers 404 BUSINESS_NOT_FOUND (not 403), so a CA cannot even find out that a
    business exists. Call only behind @roles_required(UserRole.CA).
    """
    from app import marketplace  # imported here: marketplace imports this module

    ca_profile_id = marketplace.own_profile_id(current_user())
    if ca_profile_id is None or not marketplace.ca_can_see_business(
        ca_profile_id, business_id
    ):
        raise ApiError(404, "BUSINESS_NOT_FOUND", "This business was not found.")


# --- gstin -------------------------------------------------------------------------------


_STATES_FILE = REPO_ROOT / "content" / "reference" / "gst_states.json"
GST_STATES = json.loads(_STATES_FILE.read_text())["states"]
_CODE_OF = {state["name"]: state["code"] for state in GST_STATES}

_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def state_code(name: str) -> str | None:
    """The GST code of a state or union territory, e.g. "27" for Maharashtra."""
    return _CODE_OF.get(name)


def gstin_check_character(first_14: str) -> str:
    """The 15th character of a GSTIN: every character's value (0-9, A-Z = 0-35) is
    multiplied by 1 and 2 in turn; the digits of each product in base 36 are added up;
    the check character makes the total a multiple of 36."""
    total = 0
    for index, character in enumerate(first_14):
        product = _CHARACTERS.index(character) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARACTERS[(36 - total % 36) % 36]


def gstin_error(gstin: str, pan: str | None, state: str) -> str | None:
    """What is wrong with a (well-formed) GSTIN for this PAN and state, or None."""
    if gstin_check_character(gstin[:14]) != gstin[14]:
        return "This GSTIN is not valid: its last character does not match. Check for a typo."
    code = state_code(state)
    if code is not None and gstin[:2] != code:
        return f"This GSTIN starts with {gstin[:2]}, but the code of {state} is {code}."
    if pan and gstin[2:12] != pan:
        return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN."
    return None


# --- money -------------------------------------------------------------------------------


def format_inr(amount) -> str:
    digits = str(int(Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


# --- storage -----------------------------------------------------------------------------


# Allowed file types and the bytes every such file starts with.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def check_file(data: bytes, mime_type: str) -> None:
    """400 FILE_EMPTY, 400 FILE_TYPE_NOT_ALLOWED (not a real PDF/JPG/PNG),
    400 FILE_TOO_LARGE (over MAX_UPLOAD_MB)."""
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        raise ApiError(400, "FILE_EMPTY", "The file is empty.")
    start = ALLOWED_TYPES.get(mime_type)
    if start is None or not data.startswith(start):
        raise ApiError(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ApiError(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")


# --- Gemini -----------------------------------------------------------------------------


log = logging.getLogger(__name__)

# (placeholder, pattern), checked in this order. A GSTIN contains a PAN, so GSTINs go
# first; a 12-digit Aadhaar-like number goes before phone numbers (10 digits).
PII_PATTERNS = [
    ("GSTIN", re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("AADHAAR", re.compile(r"\b[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}\b")),
    ("PHONE", re.compile(r"(\+91[ -]?)?\b[6-9][0-9]{4}[ -]?[0-9]{5}\b")),
]


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Replace personal data in `text` with placeholders like [PAN].

    Returns the cleaned text and the kinds that were found, e.g. ["PAN", "EMAIL"].
    Names cannot be found by a pattern: the forms ask users not to type them.
    """
    found = []
    for kind, pattern in PII_PATTERNS:
        if pattern.search(text):
            found.append(kind)
            text = pattern.sub(f"[{kind}]", text)
    return text, found


def gemini_available() -> bool:
    """True when a Gemini API key is configured."""
    return bool(current_app.config.get("GEMINI_API_KEY"))


def _client():
    """A Gemini client with our timeout and retry rule.

    Only 503 ("this model is currently experiencing high demand") is retried, twice.
    A 429 means our quota is used up: retrying at once would only use up more of it.
    """
    # Imported here so the app starts (and tests run) without loading the Gemini library.
    from google import genai
    from google.genai import types

    config = current_app.config
    return genai.Client(
        api_key=config["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=config["GEMINI_TIMEOUT_SECONDS"] * 1000,
            retry_options=types.HttpRetryOptions(attempts=3, http_status_codes=[503]),
        ),
    )


def _failure_reason(error: Exception) -> str:
    """Why a Gemini call failed, for the log, e.g. "429 RESOURCE_EXHAUSTED: You exceeded
    your current quota". Google's message never contains our prompt."""
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    message = getattr(error, "message", None)
    if code is None and status is None:
        return type(error).__name__  # e.g. a timeout or no network
    reason = f"{code} {status}"
    if message:
        reason += ": " + str(message)[:200]
    return reason


def _send_to_gemini(prompt: str, want_json: bool) -> str:
    """Send an already-scrubbed prompt to Gemini and return the reply text.

    Kept separate so tests can replace it; nothing else may call it.
    """
    from google.genai import types

    config = current_app.config
    client = _client()
    # We only ask for text; the library's automatic function calling stays off.
    settings = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
    if want_json:
        settings.response_mime_type = "application/json"
    response = client.models.generate_content(
        model=config["GEMINI_MODEL"], contents=prompt, config=settings
    )
    return response.text or ""


def ask_gemini(prompt: str, want_json: bool = False) -> str:
    """Scrub `prompt`, send it to Gemini and return the reply text.

    want_json=True asks Gemini to answer with JSON only (the caller parses it).
    503 GEMINI_UNAVAILABLE when no key is set or the call fails.
    """
    clean_prompt, found = scrub_pii(prompt)
    if found:
        log.warning("Removed personal data before sending to Gemini: %s", ", ".join(found))

    if not gemini_available():
        raise ApiError(503, "GEMINI_UNAVAILABLE", "AI suggestions are not available right now.")

    try:
        return _send_to_gemini(clean_prompt, want_json)
    except Exception as error:  # any library, network or quota error
        log.error(
            "Gemini call failed (model %s): %s",
            current_app.config["GEMINI_MODEL"],
            _failure_reason(error),
        )
        raise ApiError(
            503, "GEMINI_UNAVAILABLE", "AI suggestions are not available right now."
        ) from error


# --- Embeddings (the AI assistant's search, AS1 / AS2) ------------------------------------

EMBEDDING_SIZE = 768  # the kb_chunks.embedding column is vector(768)
EMBED_BATCH = 50  # texts per request


def _send_embeddings(texts: list[str], for_question: bool) -> list[list[float]]:
    """Send already-scrubbed texts to Gemini's embedding model; one vector per text.

    Kept separate so tests can replace it; nothing else may call it.
    """
    from google.genai import types

    config = current_app.config
    client = _client()
    # A question and the texts that answer it are embedded slightly differently.
    task = "RETRIEVAL_QUERY" if for_question else "RETRIEVAL_DOCUMENT"
    response = client.models.embed_content(
        model=config["GEMINI_EMBED_MODEL"],
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_SIZE, task_type=task),
    )
    return [list(embedding.values) for embedding in response.embeddings]


def embed_texts(texts: list[str], for_question: bool = False) -> list[list[float]]:
    """Scrub each text and return its vector (768 numbers), in the same order.

    for_question=True for a user's question, False for knowledge-base texts.
    503 GEMINI_UNAVAILABLE when no key is set or the call fails.
    """
    clean_texts = []
    for text in texts:
        clean, found = scrub_pii(text)
        if found:
            log.warning("Removed personal data before embedding: %s", ", ".join(found))
        clean_texts.append(clean)

    if not gemini_available():
        raise ApiError(503, "GEMINI_UNAVAILABLE", "AI suggestions are not available right now.")

    vectors = []
    try:
        for start in range(0, len(clean_texts), EMBED_BATCH):
            vectors.extend(_send_embeddings(clean_texts[start : start + EMBED_BATCH], for_question))
    except Exception as error:  # any library, network or quota error
        log.error(
            "Gemini embedding failed (model %s): %s",
            current_app.config["GEMINI_EMBED_MODEL"],
            _failure_reason(error),
        )
        raise ApiError(
            503, "GEMINI_UNAVAILABLE", "AI suggestions are not available right now."
        ) from error
    return vectors
