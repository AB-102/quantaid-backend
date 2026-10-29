"""
Outbound email through Resend. Templates are HTML files in emails/, exported from quantaid-frontend/transactional/.
They hold {{placeholders}} that are filled in, HTML-escaped, at send time.
"""

import html
import logging
from pathlib import Path

import resend

from config import FROM_EMAIL, RESEND_API_KEY

logger = logging.getLogger(__name__)

resend.api_key = RESEND_API_KEY

EMAILS_DIR = Path(__file__).parent.parent / "emails"


def _render(name: str, **values: str) -> str:
    template = (EMAILS_DIR / f"{name}.html").read_text(encoding="utf-8")
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", html.escape(value))
    return template


def _send(to: str, subject: str, html_body: str) -> None:
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY is not set, so email %r was not sent", subject)
        return
    # The locked ty (0.0.26) doesn't infer the SDK's SendParams TypedDict from a dict literal; newer ty does,
    # so drop the ignore when upgrading ty
    params: resend.Emails.SendParams = {  # ty: ignore[invalid-assignment]
        "from": f"Quantaid <{FROM_EMAIL}>",
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    try:
        resend.Emails.send(params)
    except Exception:
        # Runs as a background task after the response has gone out, so log it instead of raising
        logger.exception("Sending email %r failed", subject)


def send_welcome_email(to: str, name: str | None) -> None:
    """Sent once, when an SSO sign-in creates a new account."""
    _send(to, "Welcome to Quantaid", _render("welcome", user_name=name or "there"))
