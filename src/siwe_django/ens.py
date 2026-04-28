from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from web3 import HTTPProvider, Web3

from .ethid import EthIDProfile, fetch_ethid_profile
from .settings import get_setting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ENSProfile:
    name: str = ""
    avatar: str = ""
    description: str = ""
    header: str = ""
    records: dict[str, Any] | None = None
    display_name: str = ""
    identity_avatar: str = ""
    identity_url: str = ""
    followers_count: int = 0
    following_count: int = 0
    raw: dict[str, Any] | None = None


def _from_ethid(profile: EthIDProfile) -> ENSProfile:
    return ENSProfile(
        name=profile.ens_name,
        avatar=profile.ens_avatar or profile.avatar,
        description=profile.ens_description,
        header=profile.ens_header,
        records=profile.ens_records,
        display_name=profile.display_name,
        identity_avatar=profile.avatar,
        identity_url=profile.url,
        followers_count=profile.followers_count,
        following_count=profile.following_count,
        raw=profile.raw,
    )


def resolve_ens_profile(address: str) -> ENSProfile:
    if get_setting("ETHID_ENABLED"):
        ethid_profile = fetch_ethid_profile(address)
        if not ethid_profile.is_empty:
            return _from_ethid(ethid_profile)

    if not get_setting("ENS_ENABLED"):
        return ENSProfile()
    rpc_url = get_setting("ENS_RPC_URL")
    if not rpc_url:
        logger.info("ENS lookup skipped because SIWE_DJANGO['ENS_RPC_URL'] is unset.")
        return ENSProfile()

    try:
        web3 = Web3(HTTPProvider(rpc_url))
        ens = getattr(web3, "ens", None)
        if ens is None:
            return ENSProfile()
        name = ens.name(address) or ""
        avatar = ""
        if name and hasattr(ens, "get_text"):
            avatar = ens.get_text(name, "avatar") or ""
        return ENSProfile(name=name, avatar=avatar)
    except Exception:
        logger.exception("ENS lookup failed for %s.", address)
        return ENSProfile()
