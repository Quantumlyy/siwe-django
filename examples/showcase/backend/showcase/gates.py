from __future__ import annotations

import os


def parse_address_list(raw: str | None = None) -> list[str]:
    value = raw if raw is not None else os.getenv("SIWE_DEMO_HOLDER_ADDRESSES", "")
    return [address.strip().lower() for address in value.split(",") if address.strip()]


def demo_holder_addresses() -> list[str]:
    return parse_address_list()


def demo_holder_gate(wallet, gate) -> bool:
    configured = gate.get("addresses")
    addresses = (
        [str(address).lower() for address in configured]
        if configured is not None
        else demo_holder_addresses()
    )
    return wallet.address.lower() in addresses
