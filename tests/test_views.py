from datetime import datetime, timedelta, timezone

import pytest
from django.test import Client, override_settings
from eth_account import Account

from siwe_django.models import SiweNonce, SiweWallet

from .helpers import build_message, post_json, sign_message, signed_payload


@pytest.mark.django_db
def test_verify_logs_in_and_creates_user_wallet(client, django_user_model):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["wallet"]["address"] == payload["account"].address
    assert django_user_model.objects.count() == 1
    assert SiweWallet.objects.count() == 1

    me = client.get("/siwe/me/")
    assert me.status_code == 200
    assert me.json()["wallet"]["caip10"].startswith("eip155:1:")


@pytest.mark.django_db
def test_nonce_is_single_use(client):
    payload = signed_payload(client)
    body = {"message": payload["message"], "signature": payload["signature"]}

    assert post_json(client, "/siwe/verify/", body).status_code == 200
    second = post_json(client, "/siwe/verify/", body)

    assert second.status_code == 401
    assert second.json()["error"] == "invalid_nonce"
    assert SiweNonce.objects.get(
        nonce=payload["message"].split("Nonce: ")[1].split("\n")[0]
    ).is_consumed


@pytest.mark.django_db
def test_nonce_is_bound_to_session(client):
    account = Account.create()
    nonce = client.get("/siwe/nonce/").json()["nonce"]
    message = build_message(account, nonce)
    signature = sign_message(account, message)

    other_client = Client()
    response = post_json(
        other_client,
        "/siwe/verify/",
        {"message": message, "signature": signature},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_nonce"


@pytest.mark.django_db
def test_wrong_domain_fails(client):
    payload = signed_payload(client, domain="evil.example")
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


@pytest.mark.django_db
def test_expired_message_fails(client):
    expired = (
        (datetime.now(tz=timezone.utc) - timedelta(minutes=1))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    payload = signed_payload(client, expiration_time=expired)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


@pytest.mark.django_db
def test_malformed_signature_fails(client):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": "0x00"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


@pytest.mark.django_db
def test_link_and_unlink_wallet(client):
    first = signed_payload(client)
    assert (
        post_json(
            client,
            "/siwe/verify/",
            {"message": first["message"], "signature": first["signature"]},
        ).status_code
        == 200
    )

    second = signed_payload(client)
    link_response = post_json(
        client,
        "/siwe/link/",
        {"message": second["message"], "signature": second["signature"]},
    )
    assert link_response.status_code == 200
    assert len(client.get("/siwe/wallets/").json()["wallets"]) == 2

    wallet_id = link_response.json()["wallet"]["id"]
    delete_response = client.delete(f"/siwe/wallets/{wallet_id}/")
    assert delete_response.status_code == 200
    assert len(client.get("/siwe/wallets/").json()["wallets"]) == 1


@pytest.mark.django_db
def test_unlink_primary_promotes_next_wallet(client):
    first = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {"message": first["message"], "signature": first["signature"]},
    )
    second = signed_payload(client)
    post_json(
        client,
        "/siwe/link/",
        {"message": second["message"], "signature": second["signature"]},
    )

    wallets = client.get("/siwe/wallets/").json()["wallets"]
    primary_id = next(wallet["id"] for wallet in wallets if wallet["isPrimary"])

    delete_response = client.delete(f"/siwe/wallets/{primary_id}/")

    assert delete_response.status_code == 200
    remaining = client.get("/siwe/wallets/").json()["wallets"]
    assert len(remaining) == 1
    assert remaining[0]["isPrimary"] is True


@pytest.mark.django_db
def test_link_conflict_returns_409(client):
    first_user_wallet = signed_payload(client)
    post_json(
        client,
        "/siwe/verify/",
        {
            "message": first_user_wallet["message"],
            "signature": first_user_wallet["signature"],
        },
    )
    linked = signed_payload(client)
    post_json(
        client,
        "/siwe/link/",
        {"message": linked["message"], "signature": linked["signature"]},
    )

    other_client = Client()
    other_login = signed_payload(other_client)
    post_json(
        other_client,
        "/siwe/verify/",
        {"message": other_login["message"], "signature": other_login["signature"]},
    )

    nonce = other_client.get("/siwe/nonce/").json()["nonce"]
    message = build_message(linked["account"], nonce)
    response = post_json(
        other_client,
        "/siwe/link/",
        {"message": message, "signature": sign_message(linked["account"], message)},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "wallet_conflict"


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "USER_FACTORY": "tests.factories.named_user_factory",
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
    }
)
def test_user_factory_override(client, django_user_model):
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    user = django_user_model.objects.get()
    assert user.first_name == "SIWE"
    assert user.username.startswith("custom_")


@pytest.mark.django_db
def test_csrf_is_enforced_for_verify():
    client = Client(enforce_csrf_checks=True)
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 403
