"""HMAC-signed webhooks fired from audit events.

Apps subscribe via ``SIWE_DJANGO["WEBHOOKS"]`` — a list of dicts shaped::

    {
      "event": "verify_succeeded",
      "url": "https://hooks.example.com/siwe",
      "secret": "...",
    }

``event`` may be ``"*"`` to match every event. The body is the JSON payload
returned by :func:`event_payload`. The signature header is::

    X-Siwe-Signature: sha256=<hex>

where ``hex`` is ``hmac.new(secret, body, sha256).hexdigest()``.

Dispatch is synchronous and best-effort: a failing webhook logs the error
but never blocks the auth flow. Apps that want retries / async dispatch
should plug in Celery via the ``WEBHOOK_DISPATCHER`` setting.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Iterable, Mapping
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.utils.module_loading import import_string

from .settings import get_setting

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3.0
SIGNATURE_HEADER = "X-Siwe-Signature"


def event_payload(
    event: str,
    *,
    address: str = "",
    user_id: str | None = None,
    success: bool = True,
    error_code: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical JSON shape we send to webhook subscribers."""
    return {
        "event": event,
        "address": address,
        "user_id": user_id,
        "success": success,
        "error_code": error_code,
        "metadata": dict(metadata or {}),
    }


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def matching_subscriptions(event: str) -> list[dict[str, Any]]:
    configured: Iterable[Mapping[str, Any]] = get_setting("WEBHOOKS") or []
    matched: list[dict[str, Any]] = []
    for subscription in configured:
        sub_event = str(subscription.get("event") or "*")
        if sub_event in {"*", event}:
            matched.append(dict(subscription))
    return matched


def deliver(subscription: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
    url = str(subscription.get("url") or "")
    secret = str(subscription.get("secret") or "")
    if not url or not secret:
        logger.warning("Skipping webhook with missing url/secret.")
        return False
    try:
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError):
        logger.exception("Webhook payload for %s is not JSON-serializable.", url)
        return False
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "siwe-django-webhook",
        SIGNATURE_HEADER: sign_payload(secret, body),
    }
    timeout = float(subscription.get("timeout") or DEFAULT_TIMEOUT)
    request = urlrequest.Request(url, data=body, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            return response.status < 400
    except (HTTPError, URLError, OSError, TimeoutError):
        logger.exception("Webhook delivery to %s failed.", url)
        return False


def dispatch(event: str, payload: Mapping[str, Any]) -> int:
    """Deliver ``payload`` to every subscriber matching ``event``.

    Returns the number of successful deliveries. Failures are swallowed —
    callers must not depend on completion for correctness.
    """
    subscriptions = matching_subscriptions(event)
    if not subscriptions:
        return 0

    dispatcher_path = get_setting("WEBHOOK_DISPATCHER")
    if dispatcher_path:
        dispatcher = import_string(dispatcher_path)
        dispatcher(event, dict(payload), subscriptions)
        return len(subscriptions)

    delivered = 0
    for subscription in subscriptions:
        if deliver(subscription, payload):
            delivered += 1
    return delivered
