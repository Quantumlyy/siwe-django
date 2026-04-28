"""``siwe-django doctor`` — diagnose an existing siwe-django installation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_ETHID_HEALTH = "https://api.ethfollow.xyz/api/v1/leaderboard/count"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str

    @property
    def is_blocking(self) -> bool:
        return self.severity == "error"


def _http_ok(url: str, *, timeout: float = 3.0) -> bool:
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "siwe-django-doctor"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


def diagnose(siwe_settings: Mapping[str, Any]) -> list[Finding]:
    """Inspect a SIWE_DJANGO settings dict and return a list of findings.

    The ``Finding.severity`` values are ``"error"`` (must fix) and ``"warning"``
    (advisory).
    """
    findings: list[Finding] = []

    domain = siwe_settings.get("DOMAIN")
    uri = siwe_settings.get("URI")
    if not domain:
        findings.append(
            Finding(
                "warning",
                "DOMAIN is unset — falling back to request host."
                " Set explicitly behind a proxy.",
            )
        )
    if not uri:
        findings.append(
            Finding(
                "warning",
                "URI is unset — falling back to request root URI."
                " Set explicitly to the canonical URI.",
            )
        )

    rpcs = siwe_settings.get("RPC_URLS") or {}
    if rpcs:
        for chain_id, url in dict(rpcs).items():
            if not _http_ok(url):
                findings.append(
                    Finding(
                        "error",
                        f"RPC for chain {chain_id} unreachable: {url}",
                    )
                )

    chain_ids = siwe_settings.get("ALLOWED_CHAIN_IDS")
    if isinstance(chain_ids, Iterable) and not isinstance(chain_ids, (str, bytes)):
        configured_chains = {int(c) for c in chain_ids}
        rpc_chains = {int(c) for c in rpcs}
        missing = configured_chains - rpc_chains
        if missing:
            findings.append(
                Finding(
                    "warning",
                    "ALLOWED_CHAIN_IDS includes chains without an RPC URL "
                    f"({sorted(missing)}); contract wallets on those chains "
                    "cannot be verified.",
                )
            )

    if siwe_settings.get("ETHID_ENABLED"):
        api_base = str(
            siwe_settings.get("ETHID_API_BASE_URL")
            or "https://api.ethfollow.xyz/api/v1"
        ).rstrip("/")
        if not _http_ok(f"{api_base}/leaderboard/count"):
            findings.append(
                Finding(
                    "error",
                    f"EthID API unreachable at {api_base}.",
                )
            )

    return findings


def to_json(findings: Iterable[Finding]) -> str:
    return json.dumps(
        [{"severity": f.severity, "message": f.message} for f in findings],
        indent=2,
    )


def has_blocking(findings: Iterable[Finding]) -> bool:
    return any(f.is_blocking for f in findings)


def settings_from_env(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Reconstruct a minimal SIWE_DJANGO mapping from environment variables.

    Used when the doctor command is invoked outside a configured Django process
    (e.g. in CI before ``manage.py`` is available).
    """
    env = env or os.environ
    rpcs: dict[int, str] = {}
    for key, value in env.items():
        if key.startswith("SIWE_RPC_") and value:
            chain_name = key[len("SIWE_RPC_") :]
            try:
                rpcs[int(chain_name)] = value
            except ValueError:
                continue
    return {
        "DOMAIN": env.get("SIWE_DOMAIN") or "",
        "URI": env.get("SIWE_URI") or "",
        "RPC_URLS": rpcs,
        "ETHID_ENABLED": env.get("SIWE_ETHID_ENABLED", "").lower() in {"1", "true"},
    }
