from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from eth_account import Account

from siwe_django.gates import check_gate, sync_wallet_groups
from siwe_django.models import SiweWallet, caip10_subject


def _make_wallet(django_user_model):
    account = Account.create()
    user = django_user_model.objects.create_user(
        username=f"u_{account.address[2:8]}"
    )
    return SiweWallet.objects.create(
        user=user,
        address=account.address,
        chain_id=1,
        caip10=caip10_subject(1, account.address),
    )


@pytest.mark.django_db
def test_efp_follower_of_pass(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    mocker.patch(
        "siwe_django.gates.fetch_efp_follower_state",
        return_value={"follow": True, "block": False, "mute": False},
    )
    assert check_gate(
        wallet, {"type": "efp_follower_of", "target": "hub.eth"}
    )


@pytest.mark.django_db
def test_efp_follower_of_fail(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    mocker.patch(
        "siwe_django.gates.fetch_efp_follower_state",
        return_value={"follow": False},
    )
    assert not check_gate(
        wallet, {"type": "efp_follower_of", "target": "hub.eth"}
    )


@pytest.mark.django_db
def test_efp_followed_by_calls_with_source_first(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    spy = mocker.patch(
        "siwe_django.gates.fetch_efp_follower_state",
        return_value={"follow": True},
    )

    assert check_gate(
        wallet, {"type": "efp_followed_by", "source": "hub.eth"}
    )

    spy.assert_called_once_with("hub.eth", wallet.address)


@pytest.mark.django_db
def test_efp_mutual_requires_both_directions(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    side = iter([{"follow": True}, {"follow": False}])
    mocker.patch(
        "siwe_django.gates.fetch_efp_follower_state",
        side_effect=lambda *args, **kwargs: next(side),
    )

    assert not check_gate(wallet, {"type": "efp_mutual", "hub": "hub.eth"})


@pytest.mark.django_db
def test_efp_min_followers(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    mocker.patch(
        "siwe_django.gates.fetch_efp_stats",
        return_value={"followers_count": 50, "following_count": 1},
    )

    assert check_gate(
        wallet, {"type": "efp_min_followers", "threshold": 25}
    )
    assert not check_gate(
        wallet, {"type": "efp_min_followers", "threshold": 100}
    )


@pytest.mark.django_db
def test_efp_not_blocked_by(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    state = mocker.patch("siwe_django.gates.fetch_efp_follower_state")

    state.return_value = {"follow": False, "block": False, "mute": False}
    assert check_gate(
        wallet, {"type": "efp_not_blocked_by", "source": "hub.eth"}
    )

    state.return_value = {"follow": False, "block": True, "mute": False}
    assert not check_gate(
        wallet, {"type": "efp_not_blocked_by", "source": "hub.eth"}
    )

    state.return_value = {"follow": False, "block": False, "mute": True}
    assert not check_gate(
        wallet, {"type": "efp_not_blocked_by", "source": "hub.eth"}
    )


@pytest.mark.django_db
def test_efp_tag(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    mocker.patch(
        "siwe_django.gates.fetch_efp_tags",
        return_value=[{"tag": "vip", "address": "0xHUB"}],
    )

    assert check_gate(
        wallet, {"type": "efp_tag", "source": "0xhub", "tag": "VIP"}
    )


@pytest.mark.django_db
def test_ens_required(mocker, django_user_model):
    wallet = _make_wallet(django_user_model)
    record = mocker.patch("siwe_django.gates.fetch_ens_record")

    record.return_value = {"name": "alice.eth"}
    assert check_gate(wallet, {"type": "ens_required"})

    record.return_value = {"name": ""}
    assert not check_gate(wallet, {"type": "ens_required"})


@pytest.mark.django_db
def test_efp_gate_misconfigured_returns_false(django_user_model):
    wallet = _make_wallet(django_user_model)
    assert not check_gate(wallet, {"type": "efp_follower_of"})


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "TOKEN_GATES": [
            {
                "type": "efp_min_followers",
                "threshold": 10,
                "group": "popular",
            }
        ],
    }
)
def test_sync_wallet_groups_adds_group_when_efp_gate_passes(
    mocker, django_user_model
):
    wallet = _make_wallet(django_user_model)
    mocker.patch(
        "siwe_django.gates.fetch_efp_stats",
        return_value={"followers_count": 100, "following_count": 1},
    )

    sync_wallet_groups(wallet)

    assert wallet.user.groups.filter(name="popular").exists()


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "TOKEN_GATES": [
            {
                "type": "efp_min_followers",
                "threshold": 10,
                "group": "popular",
            }
        ],
    }
)
def test_sync_wallet_groups_removes_group_when_efp_gate_fails(
    mocker, django_user_model
):
    wallet = _make_wallet(django_user_model)
    group = Group.objects.create(name="popular")
    wallet.user.groups.add(group)
    mocker.patch(
        "siwe_django.gates.fetch_efp_stats",
        return_value={"followers_count": 1, "following_count": 1},
    )

    sync_wallet_groups(wallet)

    assert not wallet.user.groups.filter(name="popular").exists()
