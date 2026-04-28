import pytest

from siwe_django.models import SiweWallet
from siwe_django.oidc import claims_for_wallet, subject_for_wallet


@pytest.mark.django_db
def test_subject_for_wallet_uses_caip10_checksum():
    subject = subject_for_wallet(1, "0x0000000000000000000000000000000000000001")

    assert subject == "eip155:1:0x0000000000000000000000000000000000000001"


@pytest.mark.django_db
def test_claims_for_wallet_prefers_ens_profile(django_user_model):
    user = django_user_model.objects.create_user(username="alice")
    wallet = SiweWallet.objects.create(
        user=user,
        address="0x0000000000000000000000000000000000000001",
        chain_id=1,
        ens_name="alice.eth",
        ens_avatar="https://example.com/alice.png",
        is_primary=True,
    )

    claims = claims_for_wallet(wallet)

    assert claims == {
        "sub": wallet.caip10,
        "preferred_username": "alice.eth",
        "picture": "https://example.com/alice.png",
        "profile": "",
        "followers_count": 0,
        "following_count": 0,
    }


@pytest.mark.django_db
def test_claims_for_wallet_prefers_ethid_profile(django_user_model):
    user = django_user_model.objects.create_user(username="alice")
    wallet = SiweWallet.objects.create(
        user=user,
        address="0x0000000000000000000000000000000000000001",
        chain_id=1,
        identity_display_name="Alice",
        identity_avatar="https://example.com/avatar.png",
        identity_url="https://efp.app/alice.eth",
        followers_count=5,
        following_count=2,
    )

    claims = claims_for_wallet(wallet)

    assert claims["preferred_username"] == "Alice"
    assert claims["picture"] == "https://example.com/avatar.png"
    assert claims["profile"] == "https://efp.app/alice.eth"
    assert claims["followers_count"] == 5
    assert claims["following_count"] == 2
