from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import Group
from django.utils.module_loading import import_string
from web3 import HTTPProvider, Web3

from .ethid import (
    fetch_efp_follower_state,
    fetch_efp_stats,
    fetch_efp_tags,
    fetch_ens_record,
)
from .models import SiweWallet
from .settings import get_setting

logger = logging.getLogger(__name__)

EFP_GATE_TYPES = frozenset(
    {
        "efp_follower_of",
        "efp_followed_by",
        "efp_mutual",
        "efp_min_followers",
        "efp_tag",
        "efp_not_blocked_by",
        "ens_required",
    }
)

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "owner", "type": "address"}],
        "type": "function",
    },
]

ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]


def _rpc_url_for_chain(chain_id: int) -> str | None:
    rpc_urls = get_setting("RPC_URLS") or {}
    if not isinstance(rpc_urls, Mapping):
        return None
    return rpc_urls.get(chain_id) or rpc_urls.get(str(chain_id))


def _web3_for_chain(chain_id: int) -> Web3 | None:
    rpc_url = _rpc_url_for_chain(chain_id)
    if not rpc_url:
        logger.warning(
            "Token gate check failed closed: no RPC URL for chain %s.", chain_id
        )
        return None
    return Web3(HTTPProvider(rpc_url))


def _contract(web3: Web3, gate: Mapping[str, Any], abi: list[dict]) -> Any:
    return web3.eth.contract(
        address=Web3.to_checksum_address(str(gate["contract"])),
        abi=abi,
    )


def _min_balance(gate: Mapping[str, Any]) -> int:
    raw = gate.get("min_balance", 1)
    decimals = int(gate.get("decimals", 0))
    return int(Decimal(str(raw)) * (Decimal(10) ** decimals))


def check_gate(wallet: SiweWallet, gate: Mapping[str, Any]) -> bool:
    gate_type = str(gate.get("type", "")).lower()

    if gate_type in EFP_GATE_TYPES:
        return _check_efp_gate(wallet, gate, gate_type)

    chain_id = int(gate.get("chain_id") or wallet.chain_id)
    if chain_id != wallet.chain_id:
        return False

    if gate_type == "custom":
        checker = import_string(str(gate["checker"]))
        return bool(checker(wallet=wallet, gate=gate))

    web3 = _web3_for_chain(chain_id)
    if web3 is None:
        return False

    try:
        if gate_type == "erc20":
            contract = _contract(web3, gate, ERC20_ABI)
            return contract.functions.balanceOf(wallet.address).call() >= _min_balance(
                gate
            )
        if gate_type == "erc721":
            contract = _contract(web3, gate, ERC721_ABI)
            token_id = gate.get("token_id")
            if token_id is not None:
                owner = contract.functions.ownerOf(int(token_id)).call()
                return str(owner).lower() == wallet.address.lower()
            return contract.functions.balanceOf(wallet.address).call() >= _min_balance(
                gate
            )
        if gate_type == "erc1155":
            contract = _contract(web3, gate, ERC1155_ABI)
            token_id = int(gate["token_id"])
            return contract.functions.balanceOf(
                wallet.address, token_id
            ).call() >= _min_balance(gate)
    except Exception:
        logger.exception(
            "Token gate %s failed closed for %s.", gate.get("name"), wallet
        )
        return False

    logger.warning("Unknown token gate type %r; failing closed.", gate_type)
    return False


def _check_efp_gate(
    wallet: SiweWallet, gate: Mapping[str, Any], gate_type: str
) -> bool:
    address = wallet.address
    try:
        if gate_type == "efp_follower_of":
            target = str(gate["target"])
            return fetch_efp_follower_state(address, target).get("follow", False)
        if gate_type == "efp_followed_by":
            source = str(gate["source"])
            return fetch_efp_follower_state(source, address).get("follow", False)
        if gate_type == "efp_mutual":
            hub = str(gate["hub"])
            user_to_hub = fetch_efp_follower_state(address, hub).get("follow", False)
            hub_to_user = fetch_efp_follower_state(hub, address).get("follow", False)
            return user_to_hub and hub_to_user
        if gate_type == "efp_min_followers":
            threshold = int(gate["threshold"])
            stats = fetch_efp_stats(address)
            return stats.get("followers_count", 0) >= threshold
        if gate_type == "efp_not_blocked_by":
            source = str(gate["source"])
            state = fetch_efp_follower_state(source, address)
            return not (state.get("block") or state.get("mute"))
        if gate_type == "efp_tag":
            source = str(gate["source"])
            wanted = str(gate["tag"]).lower()
            tags = fetch_efp_tags(address, source=source)
            return any(str(item.get("tag") or "").lower() == wanted for item in tags)
        if gate_type == "ens_required":
            record = fetch_ens_record(address)
            return bool(record.get("name"))
    except (KeyError, ValueError, TypeError):
        logger.exception(
            "EFP gate %r is misconfigured for %s.", gate.get("name"), wallet
        )
        return False
    return False


def sync_wallet_groups(wallet: SiweWallet) -> None:
    for gate in get_setting("TOKEN_GATES") or []:
        group_name = gate.get("group") or gate.get("name")
        if not group_name:
            logger.warning("Token gate without group/name skipped.")
            continue
        group, _ = Group.objects.get_or_create(name=str(group_name))
        if check_gate(wallet, gate):
            wallet.user.groups.add(group)
        else:
            wallet.user.groups.remove(group)
