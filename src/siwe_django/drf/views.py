from __future__ import annotations

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from siwe_django.models import SiweWallet
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
)
from siwe_django.settings import get_setting
from siwe_django.views import SIWE_BACKEND

from .serializers import SiweVerifySerializer


def _error(error: SiweAuthError) -> Response:
    return Response(
        {"success": False, "error": error.code, "message": str(error)},
        status=error.status_code,
    )


class NonceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        nonce = issue_nonce(request)
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
            return _error(exc)
        auth_login(request, result.user, backend=SIWE_BACKEND)
        return Response(
            {
                "success": True,
                "user": serialize_user(result.user),
                "wallet": serialize_wallet(result.wallet),
            }
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


class LogoutView(APIView):
    def post(self, request):
        auth_logout(request)
        return Response({"success": True})


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
            return _error(exc)
        return Response({"success": True, "wallet": serialize_wallet(wallet)})


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
        return Response({"success": True})


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
