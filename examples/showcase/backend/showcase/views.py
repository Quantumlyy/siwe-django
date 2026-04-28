from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseNotFound,
    JsonResponse,
)
from django.views.decorators.http import require_http_methods

from siwe_django.gates import sync_wallet_groups
from siwe_django.models import SiweWallet
from siwe_django.services import (
    primary_wallet_for_user,
    serialize_user,
    serialize_wallet,
)
from siwe_django.settings import get_setting


def _gate_payload(group_names: set[str]) -> list[dict]:
    gates = []
    for gate in get_setting("TOKEN_GATES") or []:
        group = str(gate.get("group") or gate.get("name") or "")
        if not group:
            continue
        gates.append(
            {
                "name": str(gate.get("name") or group),
                "label": str(gate.get("label") or group),
                "description": str(gate.get("description") or ""),
                "group": group,
                "active": group in group_names,
            }
        )
    return gates


def _empty_session() -> dict:
    return {
        "authenticated": False,
        "user": None,
        "wallet": None,
        "wallets": [],
        "groups": [],
        "gates": _gate_payload(set()),
    }


def _index_path() -> Path | None:
    candidates = [
        Path(directory) / "index.html"
        for directory in getattr(settings, "STATICFILES_DIRS", [])
    ]
    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        candidates.append(Path(static_root) / "index.html")
    return next((path for path in candidates if path.exists()), None)


@require_http_methods(["GET"])
def spa(request: HttpRequest, path: str = "") -> HttpResponse:
    """Serve the built React app for any unmatched path.

    Returns 404 in dev (no built frontend present) so the Vite dev server is
    the canonical SPA host during local development.
    """
    index = _index_path()
    if index is None:
        return HttpResponseNotFound("Frontend bundle not found.")
    return FileResponse(index.open("rb"), content_type="text/html")


@require_http_methods(["GET"])
def session(request: HttpRequest) -> JsonResponse:
    user = request.user
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return JsonResponse(_empty_session())

    wallet = primary_wallet_for_user(user)
    if wallet is not None and get_setting("SYNC_TOKEN_GATES_ON_LOGIN"):
        sync_wallet_groups(wallet)

    groups = sorted(user.groups.values_list("name", flat=True))
    group_names = set(groups)
    wallets = SiweWallet.objects.filter(user=user)
    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(user),
            "wallet": serialize_wallet(wallet) if wallet else None,
            "wallets": [serialize_wallet(item) for item in wallets],
            "groups": groups,
            "gates": _gate_payload(group_names),
        }
    )
