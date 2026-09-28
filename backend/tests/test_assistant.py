"""The AI assistant (B3): knowledge base (AS1), answers with sources (AS2), category-level
context (AS3), "Ask a CA" (AS4) and history (AS5).

Gemini is faked: `_send_embeddings` gives each text a vector for its topic (GSTR-3B, GSTR-2B
or anything else), so a question finds the chunks of its own topic at distance 0 and other
topics at distance 1; `_send_to_gemini` returns a fixed JSON reply and records the prompt.
The knowledge base is built from a small temporary content/ folder.
"""

import json

import pytest

from app.errors import ApiError
from app.models import ChatMessage, KbChunk, RegulatoryProfile, User
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.onboarding import GstScheme, ItrForm, MsmeTier
from app.services import assistant_service
from app.utils import gemini_client

ASK = "/api/v1/assistant/ask"
HISTORY = "/api/v1/assistant/history"
TOPICS = ["3b", "2b"]


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * 768
    words = text.lower()
    for index, topic in enumerate(TOPICS):
        if f"gstr-{topic}" in words or f"gstr {topic}" in words or f"gstr{topic}" in words:
            vector[index] = 1.0
            return vector
    vector[767] = 1.0  # everything else
    return vector


@pytest.fixture()
def content(tmp_path, monkeypatch):
    """A small content/ folder: one form's two pages and one official FAQ page."""
    form = tmp_path / "content" / "forms" / "GSTR-3B"
    form.mkdir(parents=True)
    (form / "explanation.md").write_text(
        "---\nform: GSTR-3B\nstatus: DRAFT\n---\n\n# GSTR-3B: what it is\n\n"
        "<!-- a note for writers -->\nGSTR-3B is the summary return in which you pay GST.\n"
    )
    (form / "instructions.md").write_text(
        "---\nform: GSTR-3B\nstatus: DRAFT\n---\n\n# How to file GSTR-3B yourself\n\n"
        "1. Log in to the portal.\n2. File GSTR-3B.\n"
    )
    faqs = tmp_path / "content" / "faqs"
    faqs.mkdir()
    (faqs / "gstr-2b.md").write_text(
        '---\ntitle: "GSTR-2B (official FAQs)"\nsource: https://example.gov.in/gstr2b\n---\n\n'
        "## What is GSTR-2B?\n\nGSTR-2B is a statement of input tax credit.\n\n"
        "## When is GSTR-2B made?\n\nGSTR-2B is made every month.\n"
    )
    monkeypatch.setattr(assistant_service, "CONTENT_DIR", tmp_path / "content")
    monkeypatch.setattr(assistant_service, "REPO_ROOT", tmp_path)
    return tmp_path / "content"


@pytest.fixture()
def gemini(monkeypatch):
    """Gemini "works": embeddings by topic, and a reply that cites source [1]."""
    sent = {"prompts": [], "embedded": [], "reply": None}
    monkeypatch.setattr(gemini_client, "gemini_available", lambda: True)

    def embed(texts, for_question):
        sent["embedded"].extend(texts)
        return [fake_vector(text) for text in texts]

    def answer(prompt, want_json):
        sent["prompts"].append(prompt)
        return sent["reply"] or json.dumps(
            {"answer": "GSTR-3B is the summary return [1].", "sources": [1], "ask_a_ca": False}
        )

    monkeypatch.setattr(gemini_client, "_send_embeddings", embed)
    monkeypatch.setattr(gemini_client, "_send_to_gemini", answer)
    return sent


@pytest.fixture()
def knowledge(content, gemini, database):
    assistant_service.ingest_knowledge()
    gemini["embedded"].clear()
    return content


@pytest.fixture()
def owner(business_with_filings, database):
    return database.session.get(User, business_with_filings.user_id)


# --- AS1: the knowledge base -----------------------------------------------------------


def test_chunks_have_titles_sources_and_no_writer_notes(content):
    chunks = assistant_service.build_chunks()

    assert {chunk["source_path"] for chunk in chunks} == {
        "content/forms/GSTR-3B/explanation.md",
        "content/forms/GSTR-3B/instructions.md",
        "content/faqs/gstr-2b.md",
    }
    faq = next(chunk for chunk in chunks if chunk["source_path"] == "content/faqs/gstr-2b.md")
    assert faq["title"] == "GSTR-2B (official FAQs)"
    assert faq["url"] == "https://example.gov.in/gstr2b"
    explanation = chunks[0]
    assert explanation["title"] == "GSTR-3B: what it is"
    assert "<!--" not in explanation["content"] and "status:" not in explanation["content"]


def test_a_long_page_is_cut_into_chunks_at_most_max_chunk_long(content):
    long_page = "---\ntitle: Long\n---\n\n" + "\n\n".join(
        f"## Question {n}\n\n" + "word " * 150 for n in range(10)
    )
    (content / "faqs" / "long.md").write_text(long_page)

    chunks = [c for c in assistant_service.build_chunks() if c["source_path"].endswith("long.md")]

    assert len(chunks) > 1
    assert all(len(chunk["content"]) <= assistant_service.MAX_CHUNK for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))


def test_ingest_embeds_only_what_changed(content, gemini, database):
    first = assistant_service.ingest_knowledge()
    assert first == {"chunks": 3, "embedded": 3, "removed": 0}
    assert database.session.query(KbChunk).count() == 3

    assert assistant_service.ingest_knowledge() == {"chunks": 3, "embedded": 0, "removed": 0}

    (content / "faqs" / "gstr-2b.md").unlink()
    assert assistant_service.ingest_knowledge() == {"chunks": 2, "embedded": 0, "removed": 1}


def test_ingest_needs_gemini_and_then_changes_nothing(content, database):
    with pytest.raises(ApiError) as error:
        assistant_service.ingest_knowledge()

    assert error.value.code == "GEMINI_UNAVAILABLE"
    assert database.session.query(KbChunk).count() == 0


def test_the_real_content_folder_builds(database):
    """The repo's own content/ (forms + official FAQs) cuts into chunks without errors."""
    chunks = assistant_service.build_chunks()

    assert len(chunks) > 20
    assert any(chunk["source_path"].startswith("content/faqs/") for chunk in chunks)
    assert all(chunk["url"] for chunk in chunks if chunk["source_path"].startswith("content/faqs/"))


# --- AS2: answers with sources ---------------------------------------------------------


def test_answer_cites_the_sources_it_used(knowledge, gemini, owner):
    result = assistant_service.ask(owner, "What is GSTR-3B?")

    assert result["answer"] == "GSTR-3B is the summary return [1]."
    assert result["ai_used"] is True
    assert [citation["number"] for citation in result["citations"]] == [1]
    assert "GSTR-3B" in result["citations"][0]["title"]
    # Only the GSTR-3B chunks were close enough to be given to Gemini.
    assert "GSTR-2B" not in gemini["prompts"][0].split("Sources:")[1].split("Question:")[0]


def test_the_prompt_has_categories_but_no_personal_data(
    knowledge, gemini, owner, business_with_filings, database
):
    database.session.add(
        RegulatoryProfile(
            business_id=business_with_filings.id,
            msme_tier=MsmeTier.MICRO,
            gst_scheme=GstScheme.REGULAR_QRMP,
            gst_registration_suggested=False,
            itr_form=ItrForm.ITR_4,
            presumptive_eligible=True,
            audit_applicable=False,
            files_24q=False,
            files_26q=True,
            roc_not_tracked=False,
            explanations={},
            rule_version="v1",
            computed_at=utcnow(),
        )
    )
    database.session.commit()

    assistant_service.ask(owner, "What is GSTR-3B? My PAN is ABCDE1234F")

    prompt = gemini["prompts"][0]
    assert "entity type: proprietorship" in prompt and "GST scheme: regular_qrmp" in prompt
    assert "MSME tier: micro" in prompt and "TDS returns: 26Q" in prompt
    assert "next filings:" in prompt
    assert "ABCDE1234F" not in prompt and "[PAN]" in prompt  # scrubbed by gemini_client
    assert business_with_filings.legal_name not in prompt
    assert owner.full_name not in prompt and owner.email not in prompt


def test_a_ca_gets_a_ca_context(knowledge, gemini, make_user):
    ca = make_user(role=UserRole.CA)

    assistant_service.ask(ca, "What is GSTR-3B?")

    assert "Chartered Accountant" in gemini["prompts"][0]


def test_nothing_relevant_found(knowledge, gemini, owner):
    result = assistant_service.ask(owner, "What is the capital of France?")

    assert result["citations"] == []
    assert result["answer"].startswith("I could not find this")
    assert gemini["prompts"] == []  # Gemini is not asked without sources


def test_without_gemini_the_passages_are_shown(knowledge, gemini, owner, monkeypatch):
    def unavailable(prompt, want_json):
        raise RuntimeError("503 high demand")

    monkeypatch.setattr(gemini_client, "_send_to_gemini", unavailable)

    result = assistant_service.ask(owner, "What is GSTR-3B?")

    assert result["ai_used"] is False
    assert result["answer"].startswith("The AI assistant cannot write an answer right now")
    assert len(result["citations"]) == 2  # both GSTR-3B chunks, with their text
    assert result["citations"][0]["excerpt"]


def test_without_embeddings_the_keyword_search_is_used(knowledge, gemini, owner, monkeypatch):
    monkeypatch.setattr(gemini_client, "gemini_available", lambda: False)

    chunks, ai_search = assistant_service.search("When is GSTR-2B made?")

    assert ai_search is False
    assert chunks[0].source_path == "content/faqs/gstr-2b.md"


def test_citation_numbers_outside_the_sources_are_ignored(knowledge, gemini, owner):
    gemini["reply"] = json.dumps(
        {"answer": "See [1] and [9].", "sources": [1, 7], "ask_a_ca": False}
    )

    result = assistant_service.ask(owner, "What is GSTR-3B?")

    assert [citation["number"] for citation in result["citations"]] == [1]


# --- AS4: Ask a CA ---------------------------------------------------------------------


def test_gemini_can_suggest_a_ca(knowledge, gemini, owner):
    gemini["reply"] = json.dumps({"answer": "It depends [1].", "sources": [1], "ask_a_ca": True})

    assert assistant_service.ask(owner, "Should I choose GSTR-3B monthly?")["ask_a_ca"] is True


def test_words_like_notice_suggest_a_ca(knowledge, gemini, owner):
    assert assistant_service.ask(owner, "I got a notice about GSTR-3B")["ask_a_ca"] is True
    assert assistant_service.ask(owner, "What is GSTR-3B?")["ask_a_ca"] is False


# --- AS5 and the routes ----------------------------------------------------------------


def test_history_is_saved_listed_and_cleared(
    client, knowledge, gemini, owner, auth_headers, make_user
):
    headers = auth_headers(owner)
    client.post(ASK, json={"question": "What is GSTR-3B?"}, headers=headers)

    history = client.get(HISTORY, headers=headers).get_json()
    assert [(message["role"], message["content"][:18]) for message in history] == [
        ("user", "What is GSTR-3B?"),
        ("assistant", "GSTR-3B is the sum"),
    ]
    assert history[1]["citations"][0]["number"] == 1
    other = auth_headers(make_user(role=UserRole.BUSINESS))
    assert client.get(HISTORY, headers=other).get_json() == []

    assert client.delete(HISTORY, headers=headers).status_code == 204
    assert client.get(HISTORY, headers=headers).get_json() == []
    assert (
        client.application.extensions["sqlalchemy"].session.query(ChatMessage).count() == 2
    )  # soft delete


def test_the_ask_route(client, knowledge, gemini, owner, auth_headers):
    response = client.post(ASK, json={"question": "What is GSTR-3B?"}, headers=auth_headers(owner))

    assert response.status_code == 200
    assert set(response.get_json()) == {"answer", "citations", "ask_a_ca", "ai_used"}


def test_route_checks(client, make_user, auth_headers, database):
    business = auth_headers(make_user(role=UserRole.BUSINESS))
    admin = auth_headers(make_user(role=UserRole.ADMIN))

    assert client.post(ASK, json={"question": "hi"}, headers=business).status_code == 422
    assert client.post(ASK, json={"question": "What is GSTR-3B?"}, headers=admin).status_code == 403
    assert client.post(ASK, json={"question": "What is GSTR-3B?"}).status_code == 401


def test_embed_texts_scrubs_personal_data(gemini):
    gemini_client.embed_texts(["Mail me at asha@example.com about GSTR-3B"], for_question=True)

    assert gemini["embedded"] == ["Mail me at [EMAIL] about GSTR-3B"]
