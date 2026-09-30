"""Request and response shapes for /api/v1/assistant/...

Business logic for the AI assistant: a searchable knowledge base, and answers with sources.

ingest_knowledge() -> dict      AS1: read content/, cut it into chunks, embed and save them
ask(user, question) -> dict     AS2-AS4: find the best chunks, let Gemini answer from them
list_history(user) -> list      AS5: the user's questions and answers, oldest first
clear_history(user) -> None     AS5: soft-delete them

How an answer is made ("RAG", retrieval-augmented generation):
  1. Search: the question becomes a vector (gemini_client.embed_texts) and pgvector finds
     the TOP_K closest chunks (cosine distance, only those within MAX_DISTANCE). Without
     Gemini: the chunks sharing the most words with the question.
  2. Answer: Gemini gets the question, those chunks numbered [1]..[5] and category-level
     facts about the user (e.g. "proprietorship, micro, regular_qrmp"; never a name, PAN,
     GSTIN or amount; rule 1), and must answer only from the chunks, citing their numbers.
     Without Gemini, the answer is the found passages themselves.
  3. "Ask a CA" (AS4) is suggested when Gemini says the question needs a professional's
     judgment, or the question mentions notices, penalties, appeals, ...

The knowledge base is our own guides (content/forms/, still DRAFT) and official FAQ pages
copied into content/faqs/ with their source URL. kb_chunks holds only this public text.

Routes for the AI assistant (all under /api/v1), for business owners and CAs.

    POST   /api/v1/assistant/ask       ask a question: an answer with its sources (AS2-AS4)
    GET    /api/v1/assistant/history   the user's past questions and answers (AS5)
    DELETE /api/v1/assistant/history   clear them

    flask assistant ingest             build / refresh the knowledge base from content/ (AS1)

Each route only checks who is calling, reads the input, calls one function in
app/assistant.py and returns its result as JSON.
"""

import json
import logging
import re

import click
import yaml
from flask_smorest import Blueprint
from marshmallow import fields, Schema, validate
from sqlalchemy import delete, select

from app import compliance, onboarding, utils
from app.models import ChatMessage, ChatRole, db, KbChunk, today_in_india, User, UserRole
from app.utils import ApiError, current_user, REPO_ROOT, roles_required


# --- Request and response shapes ---------------------------------------------------------


class QuestionSchema(Schema):
    """POST /assistant/ask. Do not type personal details: they are removed before Gemini."""

    question = fields.String(required=True, validate=validate.Length(3, 500))


class CitationSchema(Schema):
    """One source an answer used: our guide or an official FAQ page."""

    number = fields.Integer(required=True, metadata={"description": "The [n] in the answer"})
    title = fields.String(required=True)
    url = fields.String(allow_none=True, metadata={"description": "The official page, if any"})
    source_path = fields.String(required=True, metadata={"description": "e.g. content/faqs/..."})
    excerpt = fields.String(required=True, metadata={"description": "The start of the passage"})


class AnswerSchema(Schema):
    answer = fields.String(required=True)
    citations = fields.List(fields.Nested(CitationSchema), required=True)
    ask_a_ca = fields.Boolean(required=True, metadata={"description": "Suggest the marketplace"})
    ai_used = fields.Boolean(required=True, metadata={"description": "False: passages only"})


class ChatMessageSchema(Schema):
    id = fields.UUID(required=True)
    role = fields.String(validate=validate.OneOf(list(ChatRole)), required=True)
    content = fields.String(required=True)
    citations = fields.List(fields.Nested(CitationSchema), required=True)
    ask_a_ca = fields.Boolean(required=True)
    ai_used = fields.Boolean(required=True)
    created_at = fields.DateTime(required=True)


# --- Logic -------------------------------------------------------------------------------


log = logging.getLogger(__name__)

CONTENT_DIR = REPO_ROOT / "content"
MAX_CHUNK = 1500  # characters: about one section of a guide or a few FAQ answers
TOP_K = 5  # chunks given to Gemini per question
# A chunk further away than this (cosine distance, 0 = same meaning) is not about the
# question. Measured on our content: on-topic questions 0.21-0.37, off-topic ones 0.44+.
MAX_DISTANCE = 0.40
HISTORY_SIZE = 50  # messages shown in the chat

# AS4: words that point to a question a professional should look at.
ASK_A_CA_WORDS = (
    "notice", "penalty", "penalties", "appeal", "scrutiny", "demand", "refund", "raid",
    "assessment", "prosecution", "dispute", "tribunal", "cancelled", "cancellation", "summons",
)  # fmt: skip
# Words that say nothing about the topic, left out of the keyword search.
COMMON_WORDS = {
    "what", "when", "where", "which", "who", "how", "why", "the", "and", "for", "are", "is",
    "can", "do", "does", "did", "my", "i", "a", "an", "to", "of", "in", "on", "it", "be",
    "if", "or", "with", "should", "have", "has", "need", "file", "form", "return", "this",
    "that", "there", "you", "your", "me", "we", "our", "about", "will", "would",
}  # fmt: skip


# ---------------------------------------------------------------------------
# AS1: building the knowledge base
# ---------------------------------------------------------------------------


def _knowledge_files() -> list:
    """Every file the assistant reads: our form guides, then the official FAQ copies."""
    files = []
    for folder in sorted((CONTENT_DIR / "forms").iterdir()):
        files.append(folder / "explanation.md")
        files.append(folder / "instructions.md")
    files.extend(sorted((CONTENT_DIR / "faqs").glob("*.md")))
    return files


def _read_file(path) -> tuple[dict, str]:
    """(front matter, Markdown body) of a content file, without the writers' <!-- notes -->."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        _, front_matter, text = text.split("---", 2)
        meta = yaml.safe_load(front_matter) or {}
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return meta, text.strip()


def _pack(pieces: list[str], separator: str) -> list[str]:
    """Join pieces into chunks of at most MAX_CHUNK characters (a longer piece is cut)."""
    chunks = []
    current = ""
    for piece in pieces:
        while len(piece) > MAX_CHUNK:  # a very long piece: cut it at the limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(piece[:MAX_CHUNK])
            piece = piece[MAX_CHUNK:]
        if current and len(current) + len(separator) + len(piece) > MAX_CHUNK:
            chunks.append(current)
            current = piece
        else:
            current = current + separator + piece if current else piece
    if current:
        chunks.append(current)
    return chunks


def _split(body: str) -> list[str]:
    """Cut a page into chunks: whole sections (from one heading to the next) where they fit,
    long sections cut at blank lines."""
    sections = [part.strip() for part in re.split(r"\n(?=#{1,6} )", body) if part.strip()]
    pieces = []
    for section in sections:
        if len(section) <= MAX_CHUNK:
            pieces.append(section)
        else:
            paragraphs = [part.strip() for part in section.split("\n\n") if part.strip()]
            pieces.extend(_pack(paragraphs, "\n\n"))
    return _pack(pieces, "\n\n")


def build_chunks() -> list[dict]:
    """The knowledge base as it should be: [{source_path, title, url, chunk_index, content}]."""
    chunks = []
    for path in _knowledge_files():
        meta, body = _read_file(path)
        source_path = str(path.relative_to(REPO_ROOT))
        heading = re.search(r"^#{1,6} (.+)$", body, flags=re.MULTILINE)
        title = meta.get("title") or (heading.group(1).strip() if heading else source_path)
        for index, content in enumerate(_split(body)):
            chunks.append(
                {
                    "source_path": source_path,
                    "title": str(title)[:300],
                    "url": meta.get("source"),
                    "chunk_index": index,
                    "content": content,
                }
            )
    return chunks


def ingest_knowledge() -> dict:
    """Bring kb_chunks in line with content/ (AS1; `flask assistant ingest`). One commit.

    Only new or changed chunks are embedded, so running it again is cheap; chunks whose
    text is gone are deleted (reference data, not an entity). Needs Gemini for the
    embeddings: 503 GEMINI_UNAVAILABLE changes nothing.
    Returns {"chunks": total, "embedded": new or changed, "removed": deleted}.
    """
    chunks = build_chunks()
    existing = {}
    for row in db.session.scalars(select(KbChunk)):
        existing[(row.source_path, row.chunk_index)] = row

    changed = []
    for chunk in chunks:
        row = existing.get((chunk["source_path"], chunk["chunk_index"]))
        same = row is not None and (row.content, row.title, row.url) == (
            chunk["content"],
            chunk["title"],
            chunk["url"],
        )
        if not same:
            changed.append(chunk)

    # The page title goes into the vector too, so "GSTR-3B" questions find GSTR-3B pages.
    vectors = []
    if changed:
        texts = [chunk["title"] + "\n\n" + chunk["content"] for chunk in changed]
        vectors = utils.embed_texts(texts)
    for chunk, vector in zip(changed, vectors, strict=True):
        row = existing.get((chunk["source_path"], chunk["chunk_index"]))
        if row is None:
            db.session.add(KbChunk(**chunk, embedding=vector))
        else:
            row.title, row.url, row.content = chunk["title"], chunk["url"], chunk["content"]
            row.embedding = vector

    wanted = {(chunk["source_path"], chunk["chunk_index"]) for chunk in chunks}
    removed = 0
    for key, row in existing.items():
        if key not in wanted:
            db.session.delete(row)
            removed += 1
    db.session.commit()
    log.info(
        "Knowledge base: %d chunks, %d embedded, %d removed", len(chunks), len(changed), removed
    )
    return {"chunks": len(chunks), "embedded": len(changed), "removed": removed}


# ---------------------------------------------------------------------------
# AS2: search
# ---------------------------------------------------------------------------


def _keyword_search(question: str) -> list[KbChunk]:
    """The chunks that share the most words with the question (without Gemini)."""
    words = {
        word
        for word in re.findall(r"[a-z0-9]+", question.lower())
        if word not in COMMON_WORDS and len(word) > 1
    }
    scored = []
    for chunk in db.session.scalars(
        select(KbChunk).order_by(KbChunk.source_path, KbChunk.chunk_index)
    ):
        text = (chunk.title + " " + chunk.content).lower()
        score = sum(1 for word in words if re.search(rf"\b{re.escape(word)}", text))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: -pair[0])  # sort() keeps the file order for equal scores
    return [chunk for _, chunk in scored[:TOP_K]]


def search(question: str) -> tuple[list[KbChunk], bool]:
    """(the TOP_K chunks closest to the question, whether the AI search was used)."""
    try:
        vector = utils.embed_texts([question], for_question=True)[0]
    except ApiError as error:
        if error.code != "GEMINI_UNAVAILABLE":
            raise
        return _keyword_search(question), False
    distance = KbChunk.embedding.cosine_distance(vector)
    closest = select(KbChunk).where(distance <= MAX_DISTANCE).order_by(distance).limit(TOP_K)
    return list(db.session.scalars(closest)), True


# ---------------------------------------------------------------------------
# AS3: what the assistant may know about the user (categories only, rule 1)
# ---------------------------------------------------------------------------


def user_context(user: User) -> str:
    """Category-level facts about the user for the prompt: never a name, PAN, GSTIN,
    address, amount or document content."""
    if user.role == UserRole.CA:
        return "The user is a Chartered Accountant who uses the app for their clients."
    business = onboarding.business_of_user(user)
    if business is None:
        return "The user is a business owner who has not registered their business in the app yet."
    profile = onboarding.get_my_business(business)["profile"]
    facts = [f"entity type: {business.entity_type}"]
    if profile is not None:
        facts.append(f"MSME tier: {profile.msme_tier}")
        facts.append(f"GST scheme: {profile.gst_scheme}")
        facts.append(f"income tax return form: {profile.itr_form}")
        facts.append(f"presumptive scheme: {'yes' if profile.presumptive_eligible else 'no'}")
        facts.append(f"tax audit: {'yes' if profile.audit_applicable else 'no'}")
        tds = [
            name
            for name, files in (("24Q", profile.files_24q), ("26Q", profile.files_26q))
            if files
        ]
        facts.append(f"TDS returns: {', '.join(tds) or 'none'}")
    today = today_in_india()
    upcoming = []
    for filing in compliance.list_filings(business, due_from=today):
        if filing.status not in compliance.DONE_STATUSES and len(upcoming) < 3:
            upcoming.append(f"{filing.form_code} {filing.period_label} due {filing.due_date}")
    facts.append(f"next filings: {'; '.join(upcoming) or 'none'}")
    return "About the user's business (categories only): " + ", ".join(facts) + "."


# ---------------------------------------------------------------------------
# AS2 + AS4: the answer
# ---------------------------------------------------------------------------

PROMPT = """You are the help assistant of CA Helper, an app that helps small Indian businesses
understand their GST, income-tax and TDS filings. The app never files returns itself.

Answer the question using ONLY the numbered sources below.
- Use plain, simple English for a small-business owner, in at most about 150 words.
- Cite the sources you used with their numbers in square brackets, like [2].
- If the sources do not answer the question, say so honestly and suggest asking a CA. Do not guess.
- Never give an amount, rate, limit or due date that is not in the sources. The user's own due
  dates are in the app's Compliance calendar.
- Do not ask for or repeat personal details.
- Set "ask_a_ca" to true when the question needs a professional's judgment (a notice, a dispute,
  a penalty, tax planning) or the sources are not enough.

{context}

Sources:
{sources}

Question: {question}

Reply with JSON only, in this shape:
{{"answer": "...", "sources": [the numbers you cited], "ask_a_ca": true or false}}"""


def _numbered(chunks: list[KbChunk]) -> str:
    return "\n\n".join(
        f"[{number}] {chunk.title}\n{chunk.content}" for number, chunk in enumerate(chunks, 1)
    )


def _parse_reply(reply: str, source_count: int) -> tuple[str, list[int], bool]:
    """(answer, cited source numbers, ask_a_ca) from Gemini's JSON (or plain text) reply."""
    try:
        data = json.loads(reply)
        answer = str(data.get("answer", "")).strip()
        cited = [int(n) for n in data.get("sources", []) if str(n).isdigit()]
        ask_a_ca = bool(data.get("ask_a_ca"))
    except (ValueError, AttributeError):  # not JSON after all: use the text as it is
        answer, cited, ask_a_ca = reply.strip(), [], False
    cited += [int(n) for n in re.findall(r"\[(\d+)\]", answer)]  # numbers written in the text
    numbers = sorted({n for n in cited if 1 <= n <= source_count})
    return answer, numbers, ask_a_ca


def _citation(number: int, chunk: KbChunk) -> dict:
    return {
        "number": number,
        "title": chunk.title,
        "url": chunk.url,
        "source_path": chunk.source_path,
        "excerpt": chunk.content[:400],
    }


def answer_question(question: str, context: str) -> dict:
    """Answer a question from the knowledge base, with its sources (AS2, AS4). Saves nothing.

    `context` is what the prompt may say about the user (user_context()). Returns {answer,
    citations [{number, title, url, source_path, excerpt}], ask_a_ca, ai_used}. Used by
    ask() and by the evaluation script (eval/assistant/evaluate.py).
    """
    chunks, _ = search(question)
    ai_used = False
    if not chunks:
        answer = (
            "I could not find this in our guides or the official FAQs I use. I can help with "
            "GST, income-tax and TDS filings; for other tax questions, a CA can help."
        )
        numbers, ask_a_ca = [], True
    else:
        prompt = PROMPT.format(context=context, sources=_numbered(chunks), question=question)
        try:
            reply = utils.ask_gemini(prompt, want_json=True)
            answer, numbers, ask_a_ca = _parse_reply(reply, len(chunks))
            ai_used = bool(answer)
        except ApiError as error:
            if error.code != "GEMINI_UNAVAILABLE":
                raise
        if not ai_used:  # no Gemini (or an empty reply): show the passages found
            answer = (
                "The AI assistant cannot write an answer right now. "
                "These parts of our guides and the official FAQs match your question:"
            )
            numbers, ask_a_ca = list(range(1, len(chunks) + 1)), False

    lowered = question.lower()
    ask_a_ca = ask_a_ca or any(re.search(rf"\b{word}\b", lowered) for word in ASK_A_CA_WORDS)
    citations = [_citation(number, chunks[number - 1]) for number in numbers]
    return {"answer": answer, "citations": citations, "ask_a_ca": ask_a_ca, "ai_used": ai_used}


def ask(user: User, question: str) -> dict:
    """answer_question() for this user, saved in their history (AS3, AS5). One commit."""
    question = question.strip()
    result = answer_question(question, user_context(user))

    db.session.add(ChatMessage(user_id=user.id, role=ChatRole.USER, content=question))
    db.session.flush()  # the question gets the earlier time, so it is listed first
    db.session.add(
        ChatMessage(
            user_id=user.id,
            role=ChatRole.ASSISTANT,
            content=result["answer"],
            citations={
                "sources": result["citations"],
                "ask_a_ca": result["ask_a_ca"],
                "ai_used": result["ai_used"],
            },
        )
    )
    db.session.commit()
    return result


# ---------------------------------------------------------------------------
# AS5: history
# ---------------------------------------------------------------------------


def list_history(user: User) -> list[dict]:
    """The user's last HISTORY_SIZE messages, oldest first."""
    rows = db.session.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_SIZE)
    ).all()
    messages = []
    for row in reversed(rows):
        extra = row.citations or {}
        messages.append(
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "citations": extra.get("sources", []),
                "ask_a_ca": extra.get("ask_a_ca", False),
                "ai_used": extra.get("ai_used", False),
                "created_at": row.created_at,
            }
        )
    return messages


def clear_history(user: User) -> None:
    """Delete the user's messages. One commit."""
    db.session.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
    db.session.commit()


# --- Routes ------------------------------------------------------------------------------


blp = Blueprint("assistant", __name__, description="AI assistant with sources")


# Ask a question. The answer cites our guides and official FAQs; no personal data goes to Gemini.
@blp.route("/assistant/ask", methods=["POST"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.arguments(QuestionSchema)
@blp.response(200, AnswerSchema)
def ask_view(data):
    return ask(current_user(), data["question"])


# The user's conversation, oldest first.
@blp.route("/assistant/history", methods=["GET"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(200, ChatMessageSchema(many=True))
def history():
    return list_history(current_user())


# Clear the conversation.
@blp.route("/assistant/history", methods=["DELETE"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(204)
def clear_history_view():
    clear_history(current_user())


# `flask assistant ingest` (make assistant-ingest): build the knowledge base. Needs GEMINI_API_KEY.
@blp.cli.command("ingest")
def ingest_command():
    """Read content/forms and content/faqs, embed new or changed chunks, save them."""
    counts = ingest_knowledge()
    click.echo(
        f"Knowledge base: {counts['chunks']} chunks ({counts['embedded']} embedded now, "
        f"{counts['removed']} removed)."
    )
