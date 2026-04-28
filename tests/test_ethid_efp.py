from __future__ import annotations

import io
import json

import pytest

from siwe_django.ethid import (
    fetch_efp_follower_state,
    fetch_efp_followers,
    fetch_efp_following,
    fetch_efp_stats,
    fetch_efp_tags,
    fetch_ens_record,
)


class _FakeResponse:
    def __init__(self, payload, *, status: int = 200):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _patch_urlopen(mocker, payload, *, status: int = 200):
    return mocker.patch(
        "siwe_django.ethid.urlopen",
        return_value=_FakeResponse(payload, status=status),
    )


def test_fetch_efp_stats_normalises_keys(mocker):
    _patch_urlopen(mocker, {"followers_count": 12, "following_count": 7})

    result = fetch_efp_stats("alice.eth")

    assert result == {"followers_count": 12, "following_count": 7}


def test_fetch_efp_stats_accepts_camel_case(mocker):
    _patch_urlopen(mocker, {"followersCount": 4, "followingCount": 1})

    assert fetch_efp_stats("alice.eth") == {
        "followers_count": 4,
        "following_count": 1,
    }


def test_fetch_efp_stats_returns_zeros_on_error(mocker):
    mocker.patch("siwe_django.ethid.urlopen", side_effect=OSError("boom"))

    assert fetch_efp_stats("alice.eth") == {
        "followers_count": 0,
        "following_count": 0,
    }


def test_fetch_efp_follower_state(mocker):
    _patch_urlopen(mocker, {"follow": True, "block": False, "mute": False})

    result = fetch_efp_follower_state("alice.eth", "bob.eth")

    assert result == {"follow": True, "block": False, "mute": False}


def test_fetch_efp_follower_state_defaults_to_false_on_missing(mocker):
    _patch_urlopen(mocker, {})

    result = fetch_efp_follower_state("alice.eth", "bob.eth")

    assert result == {"follow": False, "block": False, "mute": False}


def test_fetch_efp_followers_passes_limit_offset(mocker):
    follower = {"address": "0x0000000000000000000000000000000000000001"}
    patched = _patch_urlopen(mocker, [follower])

    result = fetch_efp_followers("hub.eth", limit=50, offset=100)

    assert result == [follower]
    request_arg = patched.call_args.args[0]
    assert "limit=50" in request_arg.full_url
    assert "offset=100" in request_arg.full_url


def test_fetch_efp_following_unwraps_dict_response(mocker):
    payload = {"following": [{"address": "0xabc"}], "next": None}
    _patch_urlopen(mocker, payload)

    result = fetch_efp_following("hub.eth")

    assert result == [{"address": "0xabc"}]


def test_fetch_efp_tags_filters_by_source(mocker):
    payload = [
        {"tag": "vip", "address": "0xHUB"},
        {"tag": "spammer", "address": "0xOTHER"},
    ]
    _patch_urlopen(mocker, payload)

    filtered = fetch_efp_tags("alice.eth", source="0xhub")

    assert filtered == [{"tag": "vip", "address": "0xHUB"}]


def test_fetch_ens_record(mocker):
    _patch_urlopen(mocker, {"name": "alice.eth", "avatar": "https://x"})

    record = fetch_ens_record("alice.eth")

    assert record["name"] == "alice.eth"


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (fetch_efp_followers, ("alice.eth",)),
        (fetch_efp_following, ("alice.eth",)),
        (fetch_efp_tags, ("alice.eth",)),
    ],
)
def test_list_helpers_return_empty_on_error(func, args, mocker):
    mocker.patch("siwe_django.ethid.urlopen", side_effect=OSError("boom"))

    assert func(*args) == []


def test_list_helpers_handle_non_json(mocker):
    response = io.BytesIO(b"not json")
    response.status = 200
    response.__enter__ = lambda self: self  # type: ignore[attr-defined]
    response.__exit__ = lambda self, *exc: False  # type: ignore[attr-defined]
    response.read = lambda: b"not json"  # type: ignore[attr-defined]
    mocker.patch("siwe_django.ethid.urlopen", return_value=response)

    assert fetch_efp_followers("alice.eth") == []
