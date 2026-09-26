"""app/utils/email.py: templates, the test outbox and the SMTP path."""

import logging
import smtplib

import pytest

from app.utils.email import send_email


def test_send_email_renders_the_template(app, mailbox):
    sent = send_email(
        "owner@example.com", "Your code", "verify_email", name="Asha", code="123456", minutes=10
    )

    assert sent is True
    [message] = mailbox
    assert message["To"] == "owner@example.com"
    assert message["From"] == app.config["MAIL_DEFAULT_SENDER"]
    assert message["Subject"] == "Your code"
    body = message.get_content()
    assert "Hello Asha" in body
    assert "123456" in body
    assert "10 minutes" in body


class FakeSMTP:
    """Stands in for smtplib.SMTP and remembers what it was asked to do."""

    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout):
        self.address = (host, port)
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture()
def real_sending(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_SUPPRESS_SEND", False)
    monkeypatch.setitem(app.config, "MAIL_SERVER", "mail.test")
    monkeypatch.setitem(app.config, "MAIL_PORT", 2525)
    FakeSMTP.instances = []


def test_send_email_hands_the_message_to_the_smtp_server(real_sending, monkeypatch, mailbox):
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    sent = send_email("owner@example.com", "Changed", "password_changed", name="Asha")

    assert sent is True
    [smtp] = FakeSMTP.instances
    assert smtp.address == ("mail.test", 2525)
    assert smtp.sent[0]["To"] == "owner@example.com"
    assert mailbox == []  # the outbox is only for suppressed sending


def test_send_email_failure_is_logged_without_the_address(real_sending, monkeypatch, caplog):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("owner@example.com")

    monkeypatch.setattr(smtplib, "SMTP", refuse)

    with caplog.at_level(logging.ERROR):
        sent = send_email("owner@example.com", "Changed", "password_changed", name="Asha")

    assert sent is False
    assert "ConnectionRefusedError" in caplog.text
    assert "owner@example.com" not in caplog.text
