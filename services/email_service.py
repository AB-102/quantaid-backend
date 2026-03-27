import os

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@quantaid.rice.edu")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

resend.api_key = RESEND_API_KEY


def send_password_reset_email(to_email: str, token: str) -> bool:
    """
    Send a password reset email via Resend.
    Returns True on success, False on failure.
    """
    reset_link = f"{FRONTEND_URL}/#/reset-password?token={token}"

    try:
        params: resend.Emails.SendParams = {  # ty: ignore[invalid-assignment]
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Quantaid — Reset Your Password",
            "html": (
                "<p>Hi,</p>"
                "<p>You requested a password reset for your Quantaid account.</p>"
                f'<p><a href="{reset_link}">Click here to reset your password</a></p>'
                "<p>This link expires in 1 hour.</p>"
                "<p>If you did not request this, you can safely ignore this email.</p>"
            ),
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"Error sending password reset email to {to_email}: {e}")
        return False
