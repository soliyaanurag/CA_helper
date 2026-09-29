"""The only way the app talks to Gemini (CLAUDE.md rule 1: no PII to Gemini).

    scrub_pii(text) -> (clean_text, found)   replace PAN, GSTIN, email, phone and
                                             Aadhaar-like numbers with placeholders
    gemini_available() -> bool               is a GEMINI_API_KEY set?
    ask_gemini(prompt, want_json=False)      scrub the prompt, send it, return the reply text
    embed_texts(texts, for_question=False)   scrub the texts, return one vector (768 numbers) each

ask_gemini() always scrubs first, so no caller can forget. It never logs the prompt
or the reply, only which kinds of personal data it removed. Without a key, or when
Gemini fails or times out, it raises 503 GEMINI_UNAVAILABLE; features catch that and
fall back (for example NIC suggestions show keyword matches only).
"""

import logging
import re

from flask import current_app

from app.errors import ApiError

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
