import pytest
from rest_framework.test import APIClient

from siwe_django.models import SiweWallet

from .helpers import build_message, sign_message


@pytest.mark.django_db
def test_drf_nonce_and_verify():
    client = APIClient()
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]

    from eth_account import Account

    account = Account.create()
    message = build_message(account, nonce)
    response = client.post(
        "/siwe-drf/verify/",
        {"message": message, "signature": sign_message(account, message)},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["wallet"]["address"] == account.address
    assert SiweWallet.objects.count() == 1


@pytest.mark.django_db
def test_drf_me_requires_authentication():
    client = APIClient()
    response = client.get("/siwe-drf/me/")

    assert response.status_code == 401
