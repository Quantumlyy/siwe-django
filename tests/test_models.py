import pytest
from eth_account import Account

from siwe_django.models import EthereumUser, SiweNonce, SiweWallet, caip10_subject
from siwe_django.services import issue_nonce


@pytest.mark.django_db
def test_nonce_expiry_and_session_binding(client):
    response = client.get("/siwe/nonce/")
    data = response.json()
    nonce = SiweNonce.objects.get(nonce=data["nonce"])

    assert response.status_code == 200
    assert nonce.session_key == client.session.session_key
    assert not nonce.is_consumed
    assert not nonce.is_expired
    assert nonce.is_usable_for_session(client.session.session_key)
    assert not nonce.is_usable_for_session("other-session")


@pytest.mark.django_db
def test_issue_nonce_without_request():
    nonce = issue_nonce()

    assert nonce.nonce
    assert nonce.session_key == ""


@pytest.mark.django_db
def test_wallet_checksum_and_caip10(django_user_model):
    account = Account.create()
    user = django_user_model.objects.create_user(username="alice")
    wallet = SiweWallet.objects.create(
        user=user,
        address=account.address.lower(),
        chain_id=1,
        is_primary=True,
    )

    assert wallet.address == account.address
    assert wallet.caip10 == caip10_subject(1, account.address)


@pytest.mark.django_db
def test_ethereum_user_manager_creates_wallet_native_user():
    account = Account.create()
    user = EthereumUser.objects.create_user(account.address.lower())

    assert user.ethereum_address == account.address
    assert user.has_usable_password() is False
    assert user.caip10_subject == caip10_subject(1, account.address)
