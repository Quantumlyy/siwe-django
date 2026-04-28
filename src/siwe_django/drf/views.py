from __future__ import annotations

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from siwe_django.audit import record_event
from siwe_django.drf.schema import SIWE_TAG, extend_schema
from siwe_django.models import SiweAuthEvent, SiweWallet
from siwe_django.services import (
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
from siwe_django.settings import get_setting
from siwe_django.stepup import mark_recent_siwe
from siwe_django.views import SIWE_BACKEND

from .serializers import SiweVerifySerializer


def _error(error: SiweAuthError) -> Response:
    return Response(
        {"success": False, "error": error.code, "message": str(error)},
        status=error.status_code,
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
@extend_schema(
    tags=[SIWE_TAG],
    summary="Issue a SIWE nonce",
    description=(
        "Returns a single-use nonce, the expected `domain` and `uri`, and the"
        " EthereumIdentityKit metadata clients should embed when preparing the"
        " EIP-4361 message."
    ),
)
class NonceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        nonce = issue_nonce(request)
        record_event(request, SiweAuthEvent.EVENT_NONCE_ISSUED)
        return Response(
            {
                "nonce": nonce.nonce,
                "expiresAt": nonce.expires_at.isoformat(),
                "domain": nonce.domain,
                "uri": nonce.uri,
                "statement": get_setting("STATEMENT"),
                "ethereumIdentityKit": eth_identity_kit_nonce_payload(nonce),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(
    tags=[SIWE_TAG],
    summary="Verify a SIWE message + signature",
    description=(
        "Verifies the EIP-4361 message against the bound nonce, logs the user"
        " in, syncs gates, and returns the user/wallet payload."
    ),
)
class VerifyView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SiweVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = authenticate_siwe(
                serializer.validated_data["message"],
                serializer.validated_data["signature"],
                request,
            )
        except SiweAuthError as exc:
            record_event(
                request,
                SiweAuthEvent.EVENT_VERIFY_FAILURE,
                success=False,
                error_code=exc.code,
            )
            return _error(exc)
        auth_login(request, result.user, backend=SIWE_BACKEND)
        mark_recent_siwe(request)
        record_event(
            request,
            SiweAuthEvent.EVENT_VERIFY_SUCCESS,
            address=result.identity.address,
            user=result.user,
        )
        return Response(
            {
                "success": True,
                "user": serialize_user(result.user),
                "wallet": serialize_wallet(result.wallet),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(
    tags=[SIWE_TAG],
    summary="Step-up: re-verify SIWE for the current user",
    description=(
        "Re-verifies a SIWE message for the authenticated user. Updates the"
        " session's `siwe_last_verified_at` so `@require_recent_siwe` can gate"
        " sensitive actions."
    ),
)
class ReauthView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": "not_authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = SiweVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            identity = verify_siwe_message(
                serializer.validated_data["message"],
                serializer.validated_data["signature"],
                request,
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
            return _error(exc)

        linked_addresses = set(
            SiweWallet.objects.filter(user=request.user).values_list(
                "address", flat=True
            )
        )
        if identity.address not in linked_addresses:
            return Response(
                {
                    "success": False,
                    "error": "wallet_not_linked",
                    "message": "Signed wallet is not linked to the current user.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        mark_recent_siwe(request)
        record_event(
            request,
            SiweAuthEvent.EVENT_VERIFY_SUCCESS,
            address=identity.address,
            user=request.user,
            metadata={"stepup": True},
        )
        return Response({"success": True, "address": identity.address})


@extend_schema(
    tags=[SIWE_TAG],
    summary="Current SIWE session",
)
class MeView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": "not_authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        wallet = primary_wallet_for_user(request.user)
        return Response(
            {
                "success": True,
                "user": serialize_user(request.user),
                "wallet": serialize_wallet(wallet) if wallet else None,
            }
        )


@extend_schema(tags=[SIWE_TAG], summary="Destroy the SIWE session")
class LogoutView(APIView):
    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        auth_logout(request)
        record_event(request, SiweAuthEvent.EVENT_LOGOUT, user=user)
        return Response({"success": True})


@extend_schema(
    tags=[SIWE_TAG], summary="Link an additional wallet to the current user"
)
class LinkView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": "not_authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = SiweVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            wallet = link_siwe_wallet(
                request.user,
                serializer.validated_data["message"],
                serializer.validated_data["signature"],
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
            return _error(exc)
        record_event(
            request,
            SiweAuthEvent.EVENT_LINK_SUCCESS,
            address=wallet.address,
            user=request.user,
        )
        return Response({"success": True, "wallet": serialize_wallet(wallet)})


@extend_schema(tags=[SIWE_TAG], summary="List wallets linked to the current user")
class WalletsView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": "not_authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(
            {
                "success": True,
                "wallets": [
                    serialize_wallet(wallet)
                    for wallet in SiweWallet.objects.filter(user=request.user)
                ],
            }
        )


@extend_schema(tags=[SIWE_TAG], summary="Unlink a wallet from the current user")
class WalletDetailView(APIView):
    def delete(self, request, wallet_id: int):
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "error": "not_authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            unlink_wallet(request.user, wallet_id)
        except SiweAuthError as exc:
            return _error(exc)
        record_event(
            request,
            SiweAuthEvent.EVENT_UNLINK,
            user=request.user,
            metadata={"wallet_id": wallet_id},
        )
        return Response({"success": True})


@extend_schema(
    tags=[SIWE_TAG],
    summary="Public Ethereum Identity Kit profile proxy",
)
class ProfileView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, address_or_name: str):
        fresh = request.query_params.get("fresh") in {"1", "true", "yes"}
        try:
            profile = get_public_identity_profile(address_or_name, fresh=fresh)
        except SiweAuthError as exc:
            return _error(exc)
        return Response({"success": True, "profile": profile})
