from __future__ import annotations

from .models import SiweWallet, caip10_subject, checksum_address


def subject_for_wallet(chain_id: int, address: str) -> str:
    return caip10_subject(chain_id, checksum_address(address))


def claims_for_wallet(wallet: SiweWallet, *, include_siwe: dict | None = None) -> dict:
    claims = {
        "sub": wallet.caip10,
        "preferred_username": wallet.identity_display_name
        or wallet.ens_name
        or wallet.address,
        "picture": wallet.identity_avatar or wallet.ens_avatar or "",
        "profile": wallet.identity_url or "",
        "followers_count": wallet.followers_count,
        "following_count": wallet.following_count,
    }
    if include_siwe:
        claims["siwe_message"] = include_siwe.get("message", "")
        claims["siwe_signature"] = include_siwe.get("signature", "")
    return claims
