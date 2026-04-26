import pytest
from django.test import override_settings

from siwe_django.ens import ENSProfile
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
