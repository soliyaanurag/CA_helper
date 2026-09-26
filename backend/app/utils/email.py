"""Sending email: plain text, rendered from a template in app/templates/email/.

    send_email("owner@example.com", "Verify your email", "verify_email", name="Asha", code="123456")

- The body is `app/templates/email/<template>.txt`, a Jinja template (Flask's
  render_template) filled with the keyword arguments.
- It goes to the SMTP server in MAIL_SERVER / MAIL_PORT. In development that is
  Mailpit (`make infra`): nothing leaves your machine; read the mail at
  http://localhost:8025.
- With MAIL_SUPPRESS_SEND (tests) nothing is sent: the message is appended to `outbox`.
- A failure to send is logged and returns False; it never fails the request, so
  the user can simply ask for the email again.
"""

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app, render_template

log = logging.getLogger(__name__)

# Messages "sent" while MAIL_SUPPRESS_SEND is on (tests read and clear this list).
outbox: list[EmailMessage] = []


def send_email(to: str, subject: str, template: str, **context) -> bool:
    """Send one plain-text email. Returns True if it was handed to the SMTP server."""
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(render_template(f"email/{template}.txt", **context))

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
