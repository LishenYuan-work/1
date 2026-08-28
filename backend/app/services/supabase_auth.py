"""Small HTTP adapter for Supabase Auth's user endpoint.

The service role key is kept server-side. The anon key is preferred when it is
configured, because it is the key intended for Auth API calls from clients.
"""

import json
import urllib.error
import urllib.request

from app.core.config import settings


class SupabaseAuthError(RuntimeError):
    pass


def get_user(access_token: str) -> dict:
    if not settings.supabase_url:
        raise SupabaseAuthError("SUPABASE_URL is not configured")
    api_key = settings.supabase_anon_key or settings.supabase_service_role_key
    if not api_key:
        raise SupabaseAuthError("SUPABASE_ANON_KEY is not configured")
    request = urllib.request.Request(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={"apikey": api_key, "Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SupabaseAuthError("Supabase session was rejected") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SupabaseAuthError("Supabase Auth is unavailable") from exc
    if not isinstance(payload, dict) or not payload.get("id") or not payload.get("email"):
        raise SupabaseAuthError("Supabase returned an incomplete user")
    return payload
