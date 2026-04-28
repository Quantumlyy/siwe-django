"""Helpers for the SIWE auth event audit log.

Views call :func:`record_event` after each auth-relevant action with the
request context (so we can capture IP and User-Agent without coupling the
service layer to HTTP concerns).
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .models import SiweAuthEvent
from .settings import get_setting


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded and get_setting("RATE_LIMIT_TRUST_X_FORWARDED_FOR"):
        return forwarded.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _user_agent(request: HttpRequest) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:512]


def record_event(
    request: HttpRequest | None,
    event: str,
    *,
    address: str = "",
    user: Any = None,
    success: bool = True,
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> SiweAuthEvent | None:
    """Persist an audit event. Returns the model or ``None`` when audit is off.

    Audit logging respects ``SIWE_DJANGO["AUDIT_ENABLED"]`` (default ``True``).
    Disabling skips writes entirely so apps that route audit data through a
    different sink (e.g. a SIEM) can avoid the DB cost.
    """
    if not get_setting("AUDIT_ENABLED"):
        return None
    ip = _client_ip(request) if request is not None else None
    ua = _user_agent(request) if request is not None else ""
    user_obj = user if user is not None and getattr(user, "pk", None) else None
    return SiweAuthEvent.objects.create(
        event=event,
        address=address or "",
        user=user_obj,
        ip=ip,
        user_agent=ua,
        success=success,
        error_code=error_code or "",
        metadata=metadata or {},
    )
