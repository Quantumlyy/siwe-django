import pytest
from eth_account import Account
from rest_framework.test import APIClient

from siwe_django.ethid import EthIDProfile
from siwe_django.models import SiweAuthEvent, SiweWallet

from .helpers import build_message, sign_message


@pytest.mark.django_db
def test_drf_nonce_and_verify():
    client = APIClient()
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]

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
def test_drf_verify_enforces_csrf():
    client = APIClient(enforce_csrf_checks=True)
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]

    account = Account.create()
    message = build_message(account, nonce)
    response = client.post(
        "/siwe-drf/verify/",
        {"message": message, "signature": sign_message(account, message)},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_drf_verify_accepts_csrf_token_from_nonce():
    client = APIClient(enforce_csrf_checks=True)
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]
    csrf_token = client.cookies["csrftoken"].value

    account = Account.create()
    message = build_message(account, nonce)
    response = client.post(
        "/siwe-drf/verify/",
        {"message": message, "signature": sign_message(account, message)},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200
    assert response.json()["wallet"]["address"] == account.address


@pytest.mark.django_db
def test_drf_me_requires_authentication():
    client = APIClient()
    response = client.get("/siwe-drf/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_drf_reauth_rejects_other_wallet_with_audit_event():
    client = APIClient()
    account = Account.create()
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]
    message = build_message(account, nonce)
    client.post(
        "/siwe-drf/verify/",
        {"message": message, "signature": sign_message(account, message)},
        format="json",
    )

    other = Account.create()
    nonce = client.get("/siwe-drf/nonce/").json()["nonce"]
    message = build_message(other, nonce)
    response = client.post(
        "/siwe-drf/reauth/",
        {"message": message, "signature": sign_message(other, message)},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "wallet_not_linked"
    failure = SiweAuthEvent.objects.filter(
        event=SiweAuthEvent.EVENT_VERIFY_FAILURE,
        error_code="wallet_not_linked",
    ).get()
    assert failure.address == other.address
    assert failure.success is False
    assert failure.metadata == {"stepup": True}


@pytest.mark.django_db
def test_drf_profile_endpoint(mocker):
    client = APIClient()
    mocker.patch(
        "siwe_django.services.fetch_ethid_profile",
        return_value=EthIDProfile(
            address="0x0000000000000000000000000000000000000001",
            display_name="alice.eth",
        ),
    )

    response = client.get("/siwe-drf/profile/alice.eth/")

    assert response.status_code == 200
    assert response.json()["profile"]["displayName"] == "alice.eth"
