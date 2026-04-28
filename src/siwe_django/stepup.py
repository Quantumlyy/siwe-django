"""Step-up authentication: re-verify a SIWE signature for sensitive actions.

The standard sign-in flow leaves a long-lived Django session. Some endpoints
(transfer funds, rotate API keys, link a wallet, …) want a stronger guarantee
that the user has *recently* signed a fresh SIWE message. This module adds:

- ``mark_recent_siwe(request)`` — call after a successful verify to stamp the
  session with the verification time.
- ``has_recent_siwe(request, seconds)`` — predicate for views.
- ``require_recent_siwe(seconds)`` — decorator that returns 403 when the
  session is missing a recent verification.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps

from django.http import HttpRequest, JsonResponse

SESSION_KEY = "siwe_last_verified_at"


def mark_recent_siwe(request: HttpRequest) -> None:
    """Stamp the current Django session with the verification timestamp."""
    request.session[SESSION_KEY] = datetime.now(tz=timezone.utc).isoformat()


def last_verified_at(request: HttpRequest) -> datetime | None:
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def has_recent_siwe(request: HttpRequest, seconds: int) -> bool:
    when = last_verified_at(request)
    if when is None:
        return False
    return datetime.now(tz=timezone.utc) - when <= timedelta(seconds=seconds)


def require_recent_siwe(seconds: int = 300) -> Callable:
    """Wrap a view to require a SIWE verify within the last ``seconds``.

    Returns 403 with ``error: "stepup_required"`` when the session is stale.
    """

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not has_recent_siwe(request, seconds):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "stepup_required",
                        "message": (
                            "This action requires a recent SIWE verification."
                        ),
                    },
                    status=403,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
