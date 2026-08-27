"""Email delivery adapter. Console delivery keeps local development self-contained."""

import json
import urllib.request
import urllib.error

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when the configured provider rejects or cannot deliver a message."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def send_email(to: str, subject: str, html: str) -> None:
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            raise EmailDeliveryError("RESEND_API_KEY is not configured")
        payload = json.dumps({"from": settings.email_from, "to": [to], "subject": subject, "html": html}).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15):
                return
        except urllib.error.HTTPError as exc:
            # Keep provider details out of the response; the status is enough to diagnose configuration.
            try:
                provider_body = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                provider_body = ""
            detail = f" ({provider_body})" if provider_body else ""
            raise EmailDeliveryError(
                f"email provider rejected the request with HTTP {exc.code}{detail}",
                status_code=exc.code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EmailDeliveryError("email provider is unreachable") from exc
    print(f"[email:{to}] {subject}\n{html}")
