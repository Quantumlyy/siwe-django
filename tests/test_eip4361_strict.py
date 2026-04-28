from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.test import RequestFactory, override_settings
from eth_account import Account

from siwe_django.services import (
    InvalidSignature,
    eth_identity_kit_nonce_payload,
    issue_nonce,
    verify_siwe_message,
)

from .helpers import build_message, sign_message


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _request_with_session():
    request = RequestFactory().get("/")
    from django.contrib.sessions.backends.db import SessionStore

    session = SessionStore()
    session.create()
    request.session = session
    return request


@pytest.mark.django_db
def test_resources_subset_passes():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(
        request, resources=["https://example.com/a", "https://example.com/b"]
    )
    message = build_message(
        account,
        nonce.nonce,
        resources=["https://example.com/a"],
    )
    signature = sign_message(account, message)

    identity = verify_siwe_message(message, signature, request)

    assert identity.address == account.address


@pytest.mark.django_db
def test_resources_outside_issued_fails():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request, resources=["https://example.com/a"])
    message = build_message(
        account,
        nonce.nonce,
        resources=["https://example.com/c"],
    )
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature, match="resources are not authorized"):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
def test_resources_omitted_when_required_fails():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request, resources=["https://example.com/a"])
    message = build_message(account, nonce.nonce)
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature, match="resources are not authorized"):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
def test_request_id_mismatch_fails():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request, request_id="req-123")
    message = build_message(account, nonce.nonce, request_id="req-999")
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
def test_request_id_match_passes():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request, request_id="req-123")
    message = build_message(account, nonce.nonce, request_id="req-123")
    signature = sign_message(account, message)

    identity = verify_siwe_message(message, signature, request)

    assert identity.address == account.address


@pytest.mark.django_db
def test_not_before_mismatch_fails():
    account = Account.create()
    request = _request_with_session()
    bound = datetime(2026, 4, 28, tzinfo=timezone.utc)
    nonce = issue_nonce(request, not_before=bound)
    message = build_message(
        account,
        nonce.nonce,
        not_before=_iso(datetime(2026, 5, 1, tzinfo=timezone.utc)),
    )
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature, match="Not Before"):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
def test_not_before_missing_when_required_fails():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(
        request, not_before=datetime(2026, 4, 28, tzinfo=timezone.utc)
    )
    message = build_message(account, nonce.nonce)
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature, match="Not Before"):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
@override_settings(SIWE_DJANGO={"DOMAIN": "testserver", "URI": "http://testserver/"})
def test_clock_skew_tolerance_default_60s():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request)
    issued_at = datetime.now(tz=timezone.utc) - timedelta(seconds=120)
    expiration = datetime.now(tz=timezone.utc) - timedelta(seconds=30)
    message = build_message(
        account,
        nonce.nonce,
        issued_at=_iso(issued_at),
        expiration_time=_iso(expiration),
    )
    signature = sign_message(account, message)

    identity = verify_siwe_message(message, signature, request)

    assert identity.address == account.address


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "CLOCK_SKEW_SECONDS": 0,
    }
)
def test_clock_skew_zero_rejects_just_expired():
    account = Account.create()
    request = _request_with_session()
    nonce = issue_nonce(request)
    issued_at = datetime.now(tz=timezone.utc) - timedelta(seconds=120)
    expiration = datetime.now(tz=timezone.utc) - timedelta(seconds=5)
    message = build_message(
        account,
        nonce.nonce,
        issued_at=_iso(issued_at),
        expiration_time=_iso(expiration),
    )
    signature = sign_message(account, message)

    with pytest.raises(InvalidSignature):
        verify_siwe_message(message, signature, request)


@pytest.mark.django_db
def test_eth_identity_kit_payload_includes_optional_fields():
    request = _request_with_session()
    nonce = issue_nonce(
        request,
        resources=["https://example.com/scope"],
        request_id="req-42",
        not_before=datetime(2026, 4, 28, tzinfo=timezone.utc),
    )

    payload = eth_identity_kit_nonce_payload(nonce)

    params = payload["messageParams"]
    assert params["resources"] == ["https://example.com/scope"]
    assert params["requestId"] == "req-42"
    assert params["notBefore"].startswith("2026-04-28")


@pytest.mark.django_db
def test_eth_identity_kit_payload_omits_unset_optional_fields():
    request = _request_with_session()
    nonce = issue_nonce(request)

    payload = eth_identity_kit_nonce_payload(nonce)

    params = payload["messageParams"]
    assert "resources" not in params
    assert "requestId" not in params
    assert "notBefore" not in params
