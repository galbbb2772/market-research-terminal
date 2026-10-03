#!/usr/bin/env python3
"""Publish HFDL ETF history while honoring provider-specific availability metadata.

Canonical ETFs remain in market_universe.json and are still attempted. A symbol with
hfdl_required=false is provider-unavailable/non-blocking for this HFDL publication
path only; it is never replaced or relabeled as another ETF.
"""
from __future__ import annotations

import sys
from typing import Any

import fetch_open_etfs_hfdl as base
import fetch_open_etfs_hfdl_compat as compat

_ORIGINAL_CANONICAL_ETFS = base.canonical_etfs


def canonical_etfs_for_hfdl(universe: dict[str, Any]) -> tuple[list[str], set[str]]:
    all_etfs, essential = _ORIGINAL_CANONICAL_ETFS(universe)
    nonblocking: set[str] = set()
    for system in universe.get("sector_systems", {}).values():
        for item in system.get("items", []):
            if item.get("id") and item.get("hfdl_required") is False:
                nonblocking.add(str(item["id"]).upper())
    return all_etfs, essential - nonblocking


def main() -> int:
    base.canonical_etfs = canonical_etfs_for_hfdl
    return compat.main()


if __name__ == "__main__":
    sys.exit(main())
