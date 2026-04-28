from __future__ import annotations

import base64
import json

import pytest

from siwe_django.recap import (
    RECAP_URI_PREFIX,
    build_recap_statement,
    decode_recap,
    encode_recap,
    find_recap_in_resources,
)


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def test_encode_recap_round_trips():
    att = {
        "https://example.com": {
            "crud/read": [{}],
            "crud/update": [{"max": 5}],
        }
    }

    uri = encode_recap(att)

    assert uri.startswith(RECAP_URI_PREFIX)
    decoded = decode_recap(uri)
    assert decoded == {"att": dict(att)}


def test_encode_recap_includes_prf():
    att = {"https://example.com": {"crud/read": [{}]}}
    proofs = ["ipfs://baf..."]

    uri = encode_recap(att, prf=proofs)
    decoded = decode_recap(uri)

    assert decoded is not None
    assert decoded["prf"] == proofs


def test_encode_recap_uses_unpadded_base64url():
    att = {"https://example.com": {"a/b": [{}]}}

    uri = encode_recap(att)
    token = uri[len(RECAP_URI_PREFIX) :]

    assert "=" not in token
    payload = json.loads(_b64url_decode(token).decode("utf-8"))
    assert payload["att"]["https://example.com"]["a/b"] == [{}]


def test_encode_recap_rejects_empty_att():
    with pytest.raises(ValueError, match="at least one resource"):
        encode_recap({})


def test_decode_recap_returns_none_for_non_recap_uri():
    assert decode_recap("https://example.com") is None
    assert decode_recap("urn:other:abc") is None


def test_decode_recap_returns_none_for_invalid_payload():
    assert decode_recap(f"{RECAP_URI_PREFIX}!!!notbase64!!!") is None
    bad = base64.urlsafe_b64encode(b'{"missing": "att"}').rstrip(b"=").decode()
    assert decode_recap(f"{RECAP_URI_PREFIX}{bad}") is None


def test_find_recap_in_resources_returns_last_entry():
    other = "https://example.com/scope"
    att = {"https://example.com": {"crud/read": [{}]}}
    recap_uri = encode_recap(att)

    assert find_recap_in_resources([other, recap_uri]) == {"att": dict(att)}


def test_find_recap_in_resources_returns_none_when_last_is_not_recap():
    att = {"https://example.com": {"crud/read": [{}]}}
    recap_uri = encode_recap(att)

    assert find_recap_in_resources([recap_uri, "https://example.com"]) is None
    assert find_recap_in_resources(None) is None
    assert find_recap_in_resources([]) is None


def test_build_recap_statement_lists_abilities_in_sorted_order():
    att = {
        "https://example.com": {
            "crud/update": [{}],
            "crud/read": [{}],
        }
    }

    statement = build_recap_statement(att)

    assert "I further authorize" in statement
    assert "(1) https://example.com: crud/read, crud/update." in statement


def test_build_recap_statement_empty_when_no_abilities():
    assert build_recap_statement({}) == ""
    assert build_recap_statement({"https://example.com": {}}) == ""
