"""Email delivery adapter. Console delivery keeps local development self-contained."""

import json
import urllib.request

from app.core.config import settings


def send_email(to: str, subject: str, html: str) -> None:
    if settings.email_provider == "resend" and settings.resend_api_key:
        payload = json.dumps({"from": settings.email_from, "to": [to], "subject": subject, "html": html}).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15):
            return
    print(f"[email:{to}] {subject}\n{html}")
