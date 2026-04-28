from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .settings import get_setting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EthIDProfile:
    address: str = ""
    display_name: str = ""
    avatar: str = ""
    url: str = ""
    followers_count: int = 0
    following_count: int = 0
    ens_name: str = ""
    ens_avatar: str = ""
    ens_description: str = ""
    ens_header: str = ""
    ens_records: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not any(
            [
                self.address,
                self.display_name,
                self.avatar,
                self.ens_name,
                self.ens_records,
            ]
        )


def _api_base_url() -> str:
    return str(get_setting("ETHID_API_BASE_URL")).rstrip("/")


def _timeout() -> float:
    return float(get_setting("ETHID_TIMEOUT_SECONDS"))


def _fresh_requested(fresh: bool | None) -> bool:
    return bool(get_setting("ETHID_CACHE_FRESH") if fresh is None else fresh)


def _fetch_json(path: str, *, fresh: bool | None = None) -> dict[str, Any]:
    params = {"cache": "fresh"} if _fresh_requested(fresh) else {}
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{_api_base_url()}/{path.lstrip('/')}{query}",
        headers={"Accept": "application/json", "User-Agent": "siwe-django"},
    )
    with urlopen(request, timeout=_timeout()) as response:
        if response.status >= 400:
            return {}
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _fetch_profile_part(path: str, *, fresh: bool | None = None) -> dict[str, Any]:
    try:
        return _fetch_json(path, fresh=fresh)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        logger.exception("EthID profile part lookup failed for %s.", path)
        return {}


def _fetch_list_endpoint(
    path: str,
    *,
    list_key: str,
    params: dict[str, Any] | None = None,
    fresh: bool | None = None,
) -> list[dict[str, Any]]:
    extra = {**({"cache": "fresh"} if _fresh_requested(fresh) else {})}
    if params:
        extra.update({k: str(v) for k, v in params.items() if v is not None})
    query = f"?{urlencode(extra)}" if extra else ""
    request = Request(
        f"{_api_base_url()}/{path.lstrip('/')}{query}",
        headers={"Accept": "application/json", "User-Agent": "siwe-django"},
    )
    try:
        with urlopen(request, timeout=_timeout()) as response:
            if response.status >= 400:
                return []
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        logger.exception("EthID list lookup failed for %s.", path)
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get(list_key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def fetch_efp_stats(address_or_name: str) -> dict[str, int]:
    """Return ``{followers_count, following_count}`` for an address or ENS name.

    Returns an empty dict on lookup failure so callers can decide how to handle
    transient EthID outages without exception handling.
    """
    encoded = quote(address_or_name, safe="")
    data = _fetch_profile_part(f"users/{encoded}/stats")
    return {
        "followers_count": _as_int(
            data.get("followers_count") or data.get("followersCount")
        ),
        "following_count": _as_int(
            data.get("following_count") or data.get("followingCount")
        ),
    }


def fetch_efp_follower_state(
    viewer: str, target: str
) -> dict[str, bool]:
    """Return ``{follow, block, mute}`` for "does ``viewer`` follow ``target``"."""
    viewer_q = quote(viewer, safe="")
    target_q = quote(target, safe="")
    data = _fetch_profile_part(f"users/{viewer_q}/follower-state/{target_q}")
    return {
        "follow": bool(data.get("follow")),
        "block": bool(data.get("block")),
        "mute": bool(data.get("mute")),
    }


def fetch_efp_followers(
    address_or_name: str, *, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    encoded = quote(address_or_name, safe="")
    return _fetch_list_endpoint(
        f"users/{encoded}/followers",
        list_key="followers",
        params={"limit": limit, "offset": offset},
    )


def fetch_efp_following(
    address_or_name: str, *, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    encoded = quote(address_or_name, safe="")
    return _fetch_list_endpoint(
        f"users/{encoded}/following",
        list_key="following",
        params={"limit": limit, "offset": offset},
    )


def fetch_efp_tags(
    address_or_name: str, *, source: str | None = None
) -> list[dict[str, Any]]:
    """Return the tags applied to ``address_or_name``.

    ``source``, when set, filters the response to tags applied by the given
    address or ENS name (commonly the relying party's "hub" account).
    """
    encoded = quote(address_or_name, safe="")
    tags = _fetch_list_endpoint(f"users/{encoded}/tags", list_key="tags")
    if source is None:
        return tags
    source_lc = source.lower()
    return [
        tag
        for tag in tags
        if str(tag.get("address") or tag.get("source") or "").lower() == source_lc
    ]


def fetch_ens_record(address_or_name: str) -> dict[str, Any]:
    """Return the EthID ENS record (primary name + avatar + records)."""
    encoded = quote(address_or_name, safe="")
    return _fetch_profile_part(f"users/{encoded}/ens")


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extract_ens(data: dict[str, Any]) -> dict[str, Any]:
    ens = data.get("ens")
    return ens if isinstance(ens, dict) else {}


def _records_from_ens(ens: dict[str, Any]) -> dict[str, Any]:
    records = ens.get("records")
    return records if isinstance(records, dict) else {}


def _merge_profile(
    simple: dict[str, Any], details: dict[str, Any], ens_response: dict[str, Any]
) -> EthIDProfile:
    details_ens = _extract_ens(details)
    direct_ens = _extract_ens(ens_response)
    ens = details_ens or direct_ens
    records = _records_from_ens(ens)
    address = str(
        simple.get("address")
        or details.get("address")
        or ens.get("address")
        or direct_ens.get("address")
        or ""
    )
    display_name = str(
        simple.get("display_name")
        or records.get("name")
        or ens.get("name")
        or address
        or ""
    )
    avatar = str(
        simple.get("avatar") or ens.get("avatar") or records.get("avatar") or ""
    )
    return EthIDProfile(
        address=address,
        display_name=display_name,
        avatar=avatar,
        url=str(simple.get("url") or ""),
        followers_count=_as_int(simple.get("followers_count")),
        following_count=_as_int(simple.get("following_count")),
        ens_name=str(ens.get("name") or ""),
        ens_avatar=str(ens.get("avatar") or records.get("avatar") or ""),
        ens_description=str(records.get("description") or ""),
        ens_header=str(records.get("header") or ""),
        ens_records=records,
        raw={"simple_profile": simple, "details": details, "ens": ens_response},
    )


def fetch_ethid_profile(
    address_or_name: str, *, fresh: bool | None = None
) -> EthIDProfile:
    encoded = quote(address_or_name, safe="")
    simple = _fetch_profile_part(f"users/{encoded}/simple-profile", fresh=fresh)
    details = _fetch_profile_part(f"users/{encoded}/details", fresh=fresh)
    ens = _fetch_profile_part(f"users/{encoded}/ens", fresh=fresh)
    return _merge_profile(simple, details, ens)


def serialize_ethid_profile(profile: EthIDProfile) -> dict[str, Any]:
    return {
        "address": profile.address,
        "displayName": profile.display_name,
        "avatar": profile.avatar,
        "url": profile.url,
        "followersCount": profile.followers_count,
        "followingCount": profile.following_count,
        "ens": {
            "name": profile.ens_name,
            "avatar": profile.ens_avatar,
            "description": profile.ens_description,
            "header": profile.ens_header,
            "records": profile.ens_records,
        },
        "raw": profile.raw,
    }
