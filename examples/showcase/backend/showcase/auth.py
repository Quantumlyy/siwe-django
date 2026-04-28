from __future__ import annotations

from django.contrib.auth import get_user_model


def demo_user_factory(identity, request=None):
    UserModel = get_user_model()
    username = f"demo_{identity.address[2:14].lower()}"
    user, created = UserModel.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
        user.first_name = identity.identity_display_name or identity.ens_name or "SIWE"
        user.save(update_fields=["password", "first_name"])
    return user
