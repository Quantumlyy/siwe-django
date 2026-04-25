from __future__ import annotations

from .models import SiweWallet, caip10_subject, checksum_address


def subject_for_wallet(chain_id: int, address: str) -> str:
    return caip10_subject(chain_id, checksum_address(address))


def claims_for_wallet(wallet: SiweWallet, *, include_siwe: dict | None = None) -> dict:
    claims = {
        "sub": wallet.caip10,
        "preferred_username": wallet.ens_name or wallet.address,
        "picture": wallet.ens_avatar or "",
    }
    if include_siwe:
        claims["siwe_message"] = include_siwe.get("message", "")
        claims["siwe_signature"] = include_siwe.get("signature", "")
    return claims
