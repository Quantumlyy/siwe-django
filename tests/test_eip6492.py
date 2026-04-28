from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings
from eth_account import Account

from siwe_django.services import (
    InvalidSignature,
    issue_nonce,
    verify_siwe_message,
)

from .helpers import build_message, sign_message

EIP6492_MAGIC_SUFFIX = (
    "6492649264926492649264926492649264926492649264926492649264926492"
)


def _request_with_session():
    request = RequestFactory().get("/")
    from django.contrib.sessions.backends.db import SessionStore

    session = SessionStore()
    session.create()
    request.session = session
    return request


def _wrap_eip6492(signature_hex: str) -> str:
    raw = signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    return f"0x{raw}{EIP6492_MAGIC_SUFFIX}"


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "RPC_URLS": {1: "https://example.invalid/rpc"},
    }
)
def test_eip6492_wrapped_signature_uses_contract_path(mocker):
    account = Account.create()
    other_address = Account.create().address
    request = _request_with_session()
    nonce = issue_nonce(request)
    message = build_message(account, nonce.nonce)

    forged_message = message.replace(account.address, other_address)
    eoa_sig = sign_message(account, forged_message)
    contract_sig = _wrap_eip6492(eoa_sig)

    contract_check = mocker.patch(
        "siwe.siwe.check_contract_wallet_signature", return_value=True
    )

    identity = verify_siwe_message(forged_message, contract_sig, request)

    assert identity.address == other_address
    assert contract_check.called
    passed_sig = contract_check.call_args.kwargs.get(
        "signature"
    ) or contract_check.call_args.args[2]
    assert passed_sig == contract_sig


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={"DOMAIN": "testserver", "URI": "http://testserver/", "RPC_URLS": {}}
)
def test_eip6492_signature_without_rpc_fails():
    account = Account.create()
    other_address = Account.create().address
    request = _request_with_session()
    nonce = issue_nonce(request)
    message = build_message(account, nonce.nonce)

    forged_message = message.replace(account.address, other_address)
    eoa_sig = sign_message(account, forged_message)
    contract_sig = _wrap_eip6492(eoa_sig)

    with pytest.raises(InvalidSignature):
        verify_siwe_message(forged_message, contract_sig, request)


@pytest.mark.django_db
@override_settings(
    SIWE_DJANGO={
        "DOMAIN": "testserver",
        "URI": "http://testserver/",
        "RPC_URLS": {1: "https://example.invalid/rpc"},
    }
)
def test_eip6492_contract_check_failure_rejects(mocker):
    account = Account.create()
    other_address = Account.create().address
    request = _request_with_session()
    nonce = issue_nonce(request)
    message = build_message(account, nonce.nonce)

    forged_message = message.replace(account.address, other_address)
    eoa_sig = sign_message(account, forged_message)
    contract_sig = _wrap_eip6492(eoa_sig)

    mocker.patch("siwe.siwe.check_contract_wallet_signature", return_value=False)

    with pytest.raises(InvalidSignature):
        verify_siwe_message(forged_message, contract_sig, request)
