"""Email templates and the Resend call, with Resend replaced by a fake (no network)."""

import pytest
import resend
from resend.exceptions import ResendError

from services import email_service

EMAIL = "ada@test.com"


@pytest.fixture
def sent(monkeypatch):
    """Capture what would go to Resend."""
    calls = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: calls.append(params))
    return calls


def test_welcome_template_fills_in_the_name_html_escaped():
    html = email_service._render("welcome", user_name="<b>Ada</b>")
    assert "&lt;b&gt;Ada&lt;/b&gt;" in html
    assert "<b>Ada</b>" not in html
    assert "{{" not in html


def test_nothing_is_sent_without_an_api_key(sent, monkeypatch):
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "")
    email_service.send_welcome_email(EMAIL, "Ada")
    assert sent == []


def test_welcome_email_goes_to_resend(sent, monkeypatch):
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(email_service, "FROM_EMAIL", "hello@test.com")
    email_service.send_welcome_email(EMAIL, None)
    assert sent == [
        {
            "from": "Quantaid <hello@test.com>",
            "to": [EMAIL],
            "subject": "Welcome to Quantaid",
            "html": email_service._render("welcome", user_name="there"),
        }
    ]


def test_a_resend_error_is_logged_not_raised(monkeypatch, caplog):
    def fail(_params):
        raise ResendError(code=500, error_type="application_error", message="down", suggested_action="")

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(resend.Emails, "send", fail)
    email_service.send_welcome_email(EMAIL, "Ada")
    assert "Sending email 'Welcome to Quantaid' failed" in caplog.text
