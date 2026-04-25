from __future__ import annotations

import logging
from dataclasses import dataclass

from web3 import HTTPProvider, Web3

from .settings import get_setting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ENSProfile:
    name: str = ""
    avatar: str = ""


def resolve_ens_profile(address: str) -> ENSProfile:
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
