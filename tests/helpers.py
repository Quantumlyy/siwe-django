from __future__ import annotations

import json
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_defunct
from siwe import SiweMessage


def iso_now() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_message(
    account,
    nonce: str,
    *,
    domain: str = "testserver",
    uri: str = "http://testserver/",
    chain_id: int = 1,
    issued_at: str | None = None,
    expiration_time: str | None = None,
    not_before: str | None = None,
    request_id: str | None = None,
    resources: list[str] | None = None,
) -> str:
    message = SiweMessage(
        domain=domain,
        address=account.address,
        uri=uri,
        version="1",
        chain_id=chain_id,
        nonce=nonce,
        issued_at=issued_at or iso_now(),
        expiration_time=expiration_time,
        not_before=not_before,
        request_id=request_id,
        resources=resources,
    )
    return message.prepare_message()


def sign_message(account, message: str) -> str:
    signature = account.sign_message(encode_defunct(text=message)).signature.hex()
    return signature if signature.startswith("0x") else f"0x{signature}"


def signed_payload(client, account=None, **message_kwargs):
    account = account or Account.create()
    nonce_response = client.get("/siwe/nonce/")
    nonce = nonce_response.json()["nonce"]
    message = build_message(account, nonce, **message_kwargs)
    return {
        "account": account,
        "message": message,
        "signature": sign_message(account, message),
    }


def post_json(client, path: str, payload: dict):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
    )
