from __future__ import annotations

import json
import time
from collections.abc import Callable

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .audit import record_event
from .models import SiweAuthEvent, SiweWallet
from .services import (
    SiweAuthError,
    authenticate_siwe,
    eth_identity_kit_nonce_payload,
    get_public_identity_profile,
    issue_nonce,
    link_siwe_wallet,
    primary_wallet_for_user,
    serialize_user,
    serialize_wallet,
    unlink_wallet,
    verify_siwe_message,
)
from .settings import get_setting
from .stepup import mark_recent_siwe

SIWE_BACKEND = "siwe_django.backend.SiweBackend"


def _json_body(request: HttpRequest) -> dict:
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise SiweAuthError("Invalid JSON request body.") from exc
    if not isinstance(body, dict):
        raise SiweAuthError("JSON request body must be an object.")
    return body


def _error_response(error: SiweAuthError) -> JsonResponse:
    return JsonResponse(
        {"success": False, "error": error.code, "message": str(error)},
        status=error.status_code,
    )


def _client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded and get_setting("RATE_LIMIT_TRUST_X_FORWARDED_FOR"):
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _parse_rate(raw: str) -> tuple[int, int]:
    count, _, period = raw.partition("/")
    seconds = {"s": 1, "m": 60, "h": 3600}.get(period or "m", 60)
    return int(count), seconds


def _rate_limited(request: HttpRequest, scope: str) -> bool:
    rate = (get_setting("RATE_LIMITS") or {}).get(scope)
    if not rate:
        return False
    limit, seconds = _parse_rate(str(rate))
    bucket = int(time.time() // seconds)
    key = f"siwe:{scope}:{_client_ip(request)}:{bucket}"
    try:
        current = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=seconds + 1)
        current = 1
    return current > limit


def rate_limit(scope: str) -> Callable:
    def decorator(view):
        def wrapped(request: HttpRequest, *args, **kwargs):
            if _rate_limited(request, scope):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "rate_limited",
                        "message": "Too many requests.",
                    },
                    status=429,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


@ensure_csrf_cookie
@rate_limit("nonce")
@require_http_methods(["GET"])
def nonce(request: HttpRequest) -> JsonResponse:
    nonce_obj = issue_nonce(request)
    record_event(request, SiweAuthEvent.EVENT_NONCE_ISSUED)
    return JsonResponse(
        {
            "nonce": nonce_obj.nonce,
            "expiresAt": nonce_obj.expires_at.isoformat(),
            "domain": nonce_obj.domain,
            "uri": nonce_obj.uri,
            "statement": get_setting("STATEMENT"),
            "ethereumIdentityKit": eth_identity_kit_nonce_payload(nonce_obj),
        }
    )


@csrf_protect
@rate_limit("verify")
@require_http_methods(["POST"])
def verify(request: HttpRequest) -> JsonResponse:
    try:
        body = _json_body(request)
        result = authenticate_siwe(
            body.get("message", ""), body.get("signature", ""), request
        )
    except SiweAuthError as exc:
        record_event(
            request,
            SiweAuthEvent.EVENT_VERIFY_FAILURE,
            success=False,
            error_code=exc.code,
        )
        return _error_response(exc)

    auth_login(request, result.user, backend=SIWE_BACKEND)
    mark_recent_siwe(request)
    record_event(
        request,
        SiweAuthEvent.EVENT_VERIFY_SUCCESS,
        address=result.identity.address,
        user=result.user,
    )
    return JsonResponse(
        {
            "success": True,
            "user": serialize_user(result.user),
            "wallet": serialize_wallet(result.wallet),
        }
    )


@csrf_protect
@rate_limit("verify")
@require_http_methods(["POST"])
def reauth(request: HttpRequest) -> JsonResponse:
    """Re-verify a SIWE signature for the currently authenticated session."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "not_authenticated"},
            status=401,
        )
    try:
        body = _json_body(request)
        identity = verify_siwe_message(
            body.get("message", ""), body.get("signature", ""), request
        )
    except SiweAuthError as exc:
        record_event(
            request,
            SiweAuthEvent.EVENT_VERIFY_FAILURE,
            user=request.user,
            success=False,
            error_code=exc.code,
            metadata={"stepup": True},
        )
        return _error_response(exc)

    user_wallet_addresses = set(
        SiweWallet.objects.filter(user=request.user).values_list(
            "address", flat=True
        )
    )
    if identity.address not in user_wallet_addresses:
        record_event(
            request,
            SiweAuthEvent.EVENT_VERIFY_FAILURE,
            address=identity.address,
            user=request.user,
            success=False,
            error_code="wallet_not_linked",
            metadata={"stepup": True},
        )
        return JsonResponse(
            {
                "success": False,
                "error": "wallet_not_linked",
                "message": "Signed wallet is not linked to the current user.",
            },
            status=403,
        )

    mark_recent_siwe(request)
    record_event(
        request,
        SiweAuthEvent.EVENT_VERIFY_SUCCESS,
        address=identity.address,
        user=request.user,
        metadata={"stepup": True},
    )
    return JsonResponse({"success": True, "address": identity.address})


@require_http_methods(["GET"])
def me(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "not_authenticated"},
            status=401,
        )
    wallet = primary_wallet_for_user(request.user)
    return JsonResponse(
        {
            "success": True,
            "user": serialize_user(request.user),
            "wallet": serialize_wallet(wallet) if wallet else None,
        }
    )


@csrf_protect
@rate_limit("logout")
@require_http_methods(["POST"])
def logout(request: HttpRequest) -> JsonResponse:
    user = request.user if request.user.is_authenticated else None
    auth_logout(request)
    record_event(
        request,
        SiweAuthEvent.EVENT_LOGOUT,
        user=user,
    )
    return JsonResponse({"success": True})


@csrf_protect
@rate_limit("link")
@require_http_methods(["POST"])
def link(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "not_authenticated"},
            status=401,
        )
    try:
        body = _json_body(request)
        wallet = link_siwe_wallet(
            request.user,
            body.get("message", ""),
            body.get("signature", ""),
            request,
        )
    except SiweAuthError as exc:
        record_event(
            request,
            SiweAuthEvent.EVENT_LINK_FAILURE,
            user=request.user,
            success=False,
            error_code=exc.code,
        )
        return _error_response(exc)
    record_event(
        request,
        SiweAuthEvent.EVENT_LINK_SUCCESS,
        address=wallet.address,
        user=request.user,
    )
    return JsonResponse({"success": True, "wallet": serialize_wallet(wallet)})


@require_http_methods(["GET"])
def wallets(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "not_authenticated"},
            status=401,
        )
    return JsonResponse(
        {
            "success": True,
            "wallets": [
                serialize_wallet(wallet)
                for wallet in SiweWallet.objects.filter(user=request.user)
            ],
        }
    )


@rate_limit("profile")
@require_http_methods(["GET"])
def profile(request: HttpRequest, address_or_name: str) -> JsonResponse:
    fresh = request.GET.get("fresh") in {"1", "true", "yes"}
    try:
        profile_data = get_public_identity_profile(address_or_name, fresh=fresh)
    except SiweAuthError as exc:
        return _error_response(exc)
    return JsonResponse({"success": True, "profile": profile_data})


@csrf_protect
@require_http_methods(["DELETE"])
def wallet_detail(request: HttpRequest, wallet_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "not_authenticated"},
            status=401,
        )
    try:
        unlink_wallet(request.user, wallet_id)
    except SiweAuthError as exc:
        return _error_response(exc)
    record_event(
        request,
        SiweAuthEvent.EVENT_UNLINK,
        user=request.user,
        metadata={"wallet_id": wallet_id},
    )
    return JsonResponse({"success": True})
