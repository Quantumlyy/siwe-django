"""ERC-5573 SIWE-ReCap helpers.

ReCap (Resource Capability) is a SIWE extension that lets a relying party
request scoped capabilities by appending a single `urn:recap:<base64url-json>`
entry to the SIWE message's ``Resources`` list. The encoded JSON has an ``att``
dictionary (resource URI -> ability namespace -> list of caveat objects) and an
optional ``prf`` proofs list.

This module implements just the encoding / decoding / statement-rendering
primitives. Verifying that the signed ReCap matches what was issued is handled
in :func:`siwe_django.services.verify_siwe_message` via the ``Resources`` subset
check.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Mapping
from typing import Any

RECAP_URI_PREFIX = "urn:recap:"

CaveatList = list[Mapping[str, Any]]
AbilityMap = Mapping[str, CaveatList]
AttMap = Mapping[str, AbilityMap]


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + padding)


def encode_recap(att: AttMap, prf: Iterable[str] | None = None) -> str:
    """Return the ``urn:recap:<base64url(json)>`` URI for the given capabilities.

    ``att`` maps a resource URI to an ability namespace map. ``prf`` is an
    optional list of proof URIs (e.g. CIDs) that delegate from another grant.
    """
    if not att:
        raise ValueError("ReCap att map must contain at least one resource.")
    payload: dict[str, Any] = {"att": {str(k): dict(v) for k, v in att.items()}}
    if prf:
        payload["prf"] = [str(p) for p in prf]
    encoded = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{RECAP_URI_PREFIX}{encoded}"


def decode_recap(uri: str) -> dict[str, Any] | None:
    """Inverse of :func:`encode_recap`. Returns ``None`` if ``uri`` is not a
    valid ReCap URI rather than raising.
    """
    if not isinstance(uri, str) or not uri.startswith(RECAP_URI_PREFIX):
        return None
    token = uri[len(RECAP_URI_PREFIX) :]
    try:
        decoded = _b64url_decode(token)
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or "att" not in payload:
        return None
    return payload


def find_recap_in_resources(
    resources: Iterable[str] | None,
) -> dict[str, Any] | None:
    """Return the decoded ReCap payload from the last entry of ``resources``.

    Per EIP-5573 a ReCap, when present, is the *last* entry of the SIWE
    message's ``Resources`` list. Earlier entries are ignored.
    """
    if not resources:
        return None
    items = list(resources)
    if not items:
        return None
    return decode_recap(str(items[-1]))


def build_recap_statement(att: AttMap) -> str:
    """Render a human-readable statement summarising ``att``.

    The statement is intentionally compact; relying parties that need a fully
    spec-compliant rendering should compose their own and call
    :func:`encode_recap` separately.
    """
    if not att:
        return ""
    lines: list[str] = []
    for index, (resource, abilities) in enumerate(att.items(), start=1):
        if not abilities:
            continue
        ordered = sorted(abilities.keys())
        lines.append(f"({index}) {resource}: {', '.join(ordered)}.")
    if not lines:
        return ""
    return (
        "I further authorize the stated URI to perform the following actions"
        " on my behalf:\n" + "\n".join(lines)
    )
