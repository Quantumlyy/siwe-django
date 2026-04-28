from __future__ import annotations

from django.contrib.auth.backends import BaseBackend

from .services import SiweAuthError, authenticate_siwe


class SiweBackend(BaseBackend):
    def authenticate(
        self, request, message: str | None = None, signature: str | None = None
    ):
        if not message or not signature:
            return None
        try:
            return authenticate_siwe(message, signature, request).user
        except SiweAuthError:
            return None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model

        UserModel = get_user_model()
        try:
            return UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
