from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings
from eth_account import Account

from siwe_django.models import SiweWallet

from .helpers import post_json, signed_payload


@pytest.mark.django_db
@override_settings(SIWE_DJANGO={"ALLOWED_CHAIN_IDS": [1]})
def test_disallowed_chain_id_is_rejected(client):
    payload = signed_payload(client, chain_id=11155111)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


@pytest.mark.django_db
@override_settings(SIWE_DJANGO={"AUTO_CREATE_USERS": False})
def test_auto_create_users_false_rejects_unknown_wallet(client, django_user_model):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 403
    assert response.json()["error"] == "user_creation_disabled"
    assert django_user_model.objects.count() == 0


@pytest.mark.django_db
@override_settings(SIWE_DJANGO={"AUTO_CREATE_USERS": False})
def test_auto_create_users_false_allows_existing_wallet(client, django_user_model):
    account = Account.create()
    user = django_user_model.objects.create_user(username="known")
    SiweWallet.objects.create(
        user=user,
        address=account.address,
        chain_id=1,
        is_primary=True,
    )

    payload = signed_payload(client, account)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "known"


@pytest.mark.django_db
def test_inactive_existing_user_is_rejected(client, django_user_model):
    account = Account.create()
    user = django_user_model.objects.create_user(username="inactive", is_active=False)
    SiweWallet.objects.create(
        user=user,
        address=account.address,
        chain_id=1,
        is_primary=True,
    )

    payload = signed_payload(client, account)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "inactive_user"


@pytest.mark.django_db
@override_settings(SIWE_DJANGO={"RATE_LIMITS": {"nonce": "1/m"}})
def test_nonce_rate_limit(client):
    cache.clear()

    assert client.get("/siwe/nonce/").status_code == 200
    response = client.get("/siwe/nonce/")

    assert response.status_code == 429
    assert response.json()["error"] == "rate_limited"
