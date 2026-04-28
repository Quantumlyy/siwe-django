import pytest
from django.test import override_settings

from siwe_django.ens import ENSProfile
from siwe_django.ethid import EthIDProfile
from siwe_django.gates import sync_wallet_groups
from siwe_django.models import SiweWallet

from .helpers import post_json, signed_payload


@pytest.mark.django_db
def test_ens_profile_is_saved_on_login(client, mocker):
    mocker.patch(
        "siwe_django.services.resolve_ens_profile",
        return_value=ENSProfile(name="alice.eth", avatar="https://example.com/a.png"),
    )
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    wallet = SiweWallet.objects.get()
    assert wallet.ens_name == "alice.eth"
    assert wallet.ens_avatar == "https://example.com/a.png"


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "ETHID_ENABLED": True,
    }
)
def test_ethid_profile_is_saved_on_login(client, mocker):
    mocker.patch(
        "siwe_django.ens.fetch_ethid_profile",
        return_value=EthIDProfile(
            address="0x0000000000000000000000000000000000000001",
            display_name="alice.eth",
            avatar="https://example.com/avatar.png",
            url="https://efp.app/alice.eth",
            followers_count=10,
            following_count=3,
            ens_name="alice.eth",
            ens_avatar="https://example.com/avatar.png",
            ens_description="Builder",
            ens_header="https://example.com/header.png",
            ens_records={"com.github": "alice"},
            raw={"simple_profile": {"display_name": "alice.eth"}},
        ),
    )
    payload = signed_payload(client)
    response = post_json(
        client,
        "/siwe/verify/",
        {"message": payload["message"], "signature": payload["signature"]},
    )

    assert response.status_code == 200
    wallet = SiweWallet.objects.get()
    assert wallet.identity_display_name == "alice.eth"
    assert wallet.identity_url == "https://efp.app/alice.eth"
    assert wallet.followers_count == 10
    assert wallet.following_count == 3
    assert wallet.ens_records == {"com.github": "alice"}
    assert response.json()["wallet"]["profile"]["followersCount"] == 10


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "TOKEN_GATES": [
            {
                "type": "custom",
                "checker": "tests.gates.always_true",
                "group": "holders",
            },
            {
                "type": "custom",
                "checker": "tests.gates.always_false",
                "group": "not-holders",
            },
        ]
    }
)
def test_custom_token_gates_sync_groups(django_user_model):
    user = django_user_model.objects.create_user(username="alice")
    wallet = SiweWallet.objects.create(
        user=user,
        address="0x0000000000000000000000000000000000000001",
        chain_id=1,
        is_primary=True,
    )

    sync_wallet_groups(wallet)

    assert user.groups.filter(name="holders").exists()
    assert not user.groups.filter(name="not-holders").exists()


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "TOKEN_GATES": [
            {
                "type": "erc20",
                "contract": "0x0000000000000000000000000000000000000001",
                "group": "token-holders",
            }
        ],
        "RPC_URLS": {},
    }
)
def test_missing_rpc_token_gate_fails_closed(django_user_model):
    user = django_user_model.objects.create_user(username="alice")
    wallet = SiweWallet.objects.create(
        user=user,
        address="0x0000000000000000000000000000000000000001",
        chain_id=1,
        is_primary=True,
    )

    sync_wallet_groups(wallet)

    assert not user.groups.filter(name="token-holders").exists()


@pytest.mark.django_db
def test_public_profile_endpoint_uses_ethid(client, mocker):
    mock = mocker.patch(
        "siwe_django.services.fetch_ethid_profile",
        return_value=EthIDProfile(
            address="0x0000000000000000000000000000000000000001",
            display_name="vitalik.eth",
            avatar="https://example.com/v.png",
            followers_count=100,
            following_count=2,
            ens_name="vitalik.eth",
            ens_records={"name": "Vitalik"},
        ),
    )

    response = client.get("/siwe/profile/vitalik.eth/?fresh=1")

    assert response.status_code == 200
    assert response.json()["profile"]["displayName"] == "vitalik.eth"
    assert response.json()["profile"]["ens"]["records"] == {"name": "Vitalik"}
    mock.assert_called_once_with("vitalik.eth", fresh=True)
