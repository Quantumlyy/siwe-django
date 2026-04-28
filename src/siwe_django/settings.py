from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    "DOMAIN": None,
    "URI": None,
    "STATEMENT": "Sign in with Ethereum.",
    "NONCE_TTL_SECONDS": 300,
    "CLOCK_SKEW_SECONDS": 60,
    "ALLOWED_CHAIN_IDS": None,
    "RPC_URLS": {},
    "ENS_ENABLED": False,
    "ENS_RPC_URL": None,
    "ETHID_ENABLED": False,
    "ETHID_PROFILE_PROXY_ENABLED": True,
    "ETHID_API_BASE_URL": "https://api.ethfollow.xyz/api/v1",
    "ETHID_TIMEOUT_SECONDS": 2,
    "ETHID_CACHE_FRESH": False,
    "AUTO_CREATE_USERS": True,
    "USER_FACTORY": "siwe_django.services.default_user_factory",
    "RATE_LIMITS": {},
    "RATE_LIMIT_TRUST_X_FORWARDED_FOR": False,
    "TOKEN_GATES": [],
    "SYNC_TOKEN_GATES_ON_LOGIN": True,
    "AUDIT_ENABLED": True,
    "NONCE_STORE": "siwe_django.nonce_store.DjangoOrmNonceStore",
    "REDIS_URL": None,
}


def siwe_settings() -> dict[str, Any]:
    configured = getattr(settings, "SIWE_DJANGO", {})
    if not isinstance(configured, Mapping):
        raise TypeError("SIWE_DJANGO must be a mapping.")
    merged = DEFAULTS.copy()
    merged.update(configured)
    return merged


def get_setting(name: str) -> Any:
    return siwe_settings()[name]


def allowed_chain_ids() -> set[int] | None:
    chain_ids = get_setting("ALLOWED_CHAIN_IDS")
    if chain_ids is None:
        return None
    return {int(chain_id) for chain_id in chain_ids}
