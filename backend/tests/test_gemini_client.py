"""app/utils/gemini_client.py (ON11): personal data is removed before anything reaches Gemini.

The real Gemini is never called: _send_to_gemini is replaced by a fake.
"""

import logging

import pytest

from app.errors import ApiError
from app.utils import gemini_client
from app.utils.gemini_client import ask_gemini, scrub_pii


def test_scrub_replaces_each_kind_of_personal_data():
    text = (
        "PAN ABCDE1234F, GSTIN 27ABCDE1234F1Z5, mail asha@example.com, "
        "phone +91 98765 43210, aadhaar 1234 5678 9012"
    )

    clean, found = scrub_pii(text)

    assert clean == ("PAN [PAN], GSTIN [GSTIN], mail [EMAIL], phone [PHONE], aadhaar [AADHAAR]")
    assert found == ["GSTIN", "PAN", "EMAIL", "AADHAAR", "PHONE"]


def test_a_gstin_is_reported_once_not_also_as_a_pan():
    clean, found = scrub_pii("our gstin is 27abcde1234f1z5")

    assert clean == "our gstin is [GSTIN]"
    assert found == ["GSTIN"]


def test_normal_text_is_unchanged():
    text = "We bake biscuits and cakes and sell them in 3 shops since 2019."

    assert scrub_pii(text) == (text, [])


def test_ask_without_a_key_is_unavailable(app):
    with app.app_context(), pytest.raises(ApiError) as error:
        ask_gemini("hello")

    assert error.value.status == 503
    assert error.value.code == "GEMINI_UNAVAILABLE"


def test_ask_sends_the_scrubbed_prompt_and_logs_only_the_kinds(app, monkeypatch, caplog):
    sent = []

    def fake_send(prompt, want_json):
        sent.append((prompt, want_json))
        return '{"ok": true}'

    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client, "_send_to_gemini", fake_send)

    with app.app_context(), caplog.at_level(logging.WARNING):
        reply = ask_gemini("Shop run by asha@example.com, PAN ABCDE1234F", want_json=True)

    assert reply == '{"ok": true}'
    assert sent == [("Shop run by [EMAIL], PAN [PAN]", True)]
    assert "PAN, EMAIL" in caplog.text
    assert "asha@example.com" not in caplog.text
    assert "ABCDE1234F" not in caplog.text


def test_a_failed_call_is_unavailable(app, monkeypatch):
    def broken_send(prompt, want_json):
        raise TimeoutError("took too long")

    monkeypatch.setitem(app.config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client, "_send_to_gemini", broken_send)

    with app.app_context(), pytest.raises(ApiError) as error:
        ask_gemini("hello")

    assert error.value.status == 503
