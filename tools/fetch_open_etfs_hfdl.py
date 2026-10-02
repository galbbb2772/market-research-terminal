#!/usr/bin/env python3
"""Fetch canonical ETF daily history from HF Data Library (CC BY 4.0).

Why this adapter exists
-----------------------
The public website needs redistributable ETF history. HF Data Library publishes its
U.S. equity/ETF dataset under CC BY 4.0. Its source changes in March 2022:
pre-2022 is PiTrading consolidated-tape data; post-2022 is IEX Exchange HIST only.
The latter is a small single-exchange sample, so it MUST NOT be described as
consolidated U.S. market OHLCV.

Authentication
--------------
The API key is used only to obtain a short-lived signed download URL and is never
written to output. HF Data Library currently issues free keys that expire every
30 days. Put the key in HFDL_API_KEY (GitHub Actions secret or local environment).

Publication
-----------
Output is MARKET-HISTORY-V1 with rights_status=verified_publishable because the
provider publishes the dataset under CC BY 4.0. Attribution and the IEX HIST notice
are embedded in the JSON and must remain visible on the website.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

API_BASE = "https://api.hfdatalibrary.com/v1"
UNIVERSE = Path("docs/data/market_universe.json")
USER_AGENT = "MarketResearchTerminal/1.0 (+https://github.com/galbbb2772/market-research-terminal)"

HF_LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
HF_CITATION = (
    "Elkassabgi, A. (2026). HF Data Library: Free 1-Minute Intraday U.S. Equity Data. "
    "Zenodo. https://doi.org/10.5281/zenodo.19501605"
)
IEX_ATTRIBUTION = (
    "Data provided for free by IEX. By accessing or using IEX Historical Data, "
    "you agree to the IEX Historical Data Terms of Use."
)
HF_TERMS_URL = "https://hfdatalibrary.com/pages/terms"
HF_DOCS_URL = "https://hfdatalibrary.com/pages/docs"
HF_API_URL = "https://hfdatalibrary.com/pages/api"
IEX_TERMS_URL = "https://iextrading.com/api-exhibit-a/"


def canonical_etfs(universe: dict[str, Any]) -> tuple[list[str], set[str]]:
    """Return (all canonical ETFs, essential public-structure ETFs).

    Essential = benchmark ETFs + the complete S&P 500 Select Sector ETF family.
    Additional verified ETF proxies (currently QTEC) are optional so one auxiliary
    symbol cannot block the core public structure site.
    """
    all_etfs: list[str] = []
    essential: set[str] = set()
    for item in universe.get("benchmarks", []):
        if str(item.get("type", "")).lower() == "etf" and item.get("id"):
            symbol = str(item["id"]).upper()
            all_etfs.append(symbol)
            essential.add(symbol)
    for system_id, system in universe.get("sector_systems", {}).items():
        for item in system.get("items", []):
            if str(item.get("kind", "")).upper() != "ETF" or not item.get("id"):
                continue
            symbol = str(item["id"]).upper()
            all_etfs.append(symbol)
            if system_id == "sp500":
                essential.add(symbol)
    # stable unique order
    seen: set[str] = set()
    ordered = []
    for symbol in all_etfs:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return ordered, essential


def _request(url: str, *, api_key: str | None = None, timeout: int = 45) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def signed_csv_url(symbol: str, api_key: str) -> str:
    params = urllib.parse.urlencode({"timeframe": "daily", "format": "csv", "version": "clean"})
    url = f"{API_BASE}/download-token/{urllib.parse.quote(symbol, safe='')}?{params}"
    raw = _request(url, api_key=api_key, timeout=30)
    obj = json.loads(raw.decode("utf-8-sig"))
    signed = obj.get("url") if isinstance(obj, dict) else None
    if not isinstance(signed, str) or not signed.startswith("https://"):
        raise ValueError(f"{symbol}: download-token response did not contain a signed HTTPS URL")
    return signed


def _first(row: dict[str, str], *names: str) -> str | None:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = lower.get(name.lower())
        if value not in (None, ""):
            return str(value).strip()
    return None


def _number(value: str | None, *, required: bool = True) -> float | None:
    if value in (None, ""):
        if required:
            raise ValueError("missing numeric value")
        return None
    out = float(str(value).replace(",", "").strip())
    if not math.isfinite(out):
        raise ValueError("non-finite numeric value")
    return out


def parse_daily_csv(raw: bytes, symbol: str, start: str, end: str) -> tuple[list[list[Any]], dict[str, Any]]:
    """Normalize a HF Data Library daily CSV to MARKET-HISTORY-V1 bar rows."""
    text = raw.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError(f"{symbol}: CSV has no header")
    bars: list[list[Any]] = []
    sources: Counter[str] = Counter()
    source_dates: dict[str, list[str]] = {}
    seen: set[str] = set()

    start_d = dt.date.fromisoformat(start)
    end_d = dt.date.fromisoformat(end)
    for row in reader:
        raw_date = _first(row, "datetime", "date", "timestamp", "time")
        if not raw_date:
            continue
        day = raw_date[:10]
        try:
            day_d = dt.date.fromisoformat(day)
        except ValueError:
            continue
        if day_d < start_d or day_d > end_d:
            continue
        if day in seen:
            raise ValueError(f"{symbol}: duplicate daily date {day}")

        o = _number(_first(row, "open"))
        h = _number(_first(row, "high"))
        l = _number(_first(row, "low"))
        c = _number(_first(row, "close"))
        volume = _number(_first(row, "volume"), required=False)
        assert o is not None and h is not None and l is not None and c is not None
        if min(o, h, l, c) <= 0:
            raise ValueError(f"{symbol}: non-positive OHLC on {day}")
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"{symbol}: inconsistent OHLC on {day}")
        if volume is not None and volume < 0:
            raise ValueError(f"{symbol}: negative volume on {day}")

        # HFDL documents its prices as split/dividend adjusted. Keep adjusted_close
        # equal to close so downstream return calculations do not mix raw/adjusted.
        bars.append([day, o, h, l, c, volume, c])
        seen.add(day)

        source = (_first(row, "source") or "unspecified").lower()
        sources[source] += 1
        source_dates.setdefault(source, []).append(day)

    bars.sort(key=lambda x: x[0])
    if len(bars) < 30:
        raise ValueError(f"{symbol}: only {len(bars)} daily observations in requested window")
    provenance = {
        "source_counts": dict(sources),
        "source_ranges": {
            src: {"start": min(days), "end": max(days), "observations": len(days)}
            for src, days in source_dates.items() if days
        },
    }
    return bars, provenance


def fetch_symbol(symbol: str, start: str, end: str, api_key: str) -> dict[str, Any]:
    signed = signed_csv_url(symbol, api_key)
    raw = _request(signed, timeout=60)
    bars, provenance = parse_daily_csv(raw, symbol, start, end)
    return {
        "provider_symbol": symbol,
        "source_status": "actual_open_licensed_provider_response",
        "start": bars[0][0],
        "end": bars[-1][0],
        "bars": bars,
        "provenance": provenance,
        "source_break_note": (
            "HF Data Library documents a March-2022 source break: earlier history is PiTrading "
            "consolidated tape; later history is IEX Exchange only and is not consolidated-market OHLCV."
        ),
    }


def build_history(
    selected: list[str], universe: dict[str, Any], start: str, end: str, api_key: str,
    *, pause: float = 0.15,
) -> dict[str, Any]:
    allowed, essential = canonical_etfs(universe)
    allowed_set = set(allowed)
    invalid = set(selected) - allowed_set
    if invalid:
        raise ValueError(f"non-canonical ETF symbols requested: {sorted(invalid)}")
    missing_essential_requested = essential - set(selected)
    if missing_essential_requested:
        raise ValueError(f"essential public-structure ETFs omitted: {sorted(missing_essential_requested)}")

    instruments: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for symbol in selected:
        try:
            instruments[symbol] = fetch_symbol(symbol, start, end, api_key)
            print(f"{symbol}: ok ({len(instruments[symbol]['bars'])} daily bars)", flush=True)
        except Exception as exc:
            failures[symbol] = f"{type(exc).__name__}: {str(exc)[:260]}"
            print(f"{symbol}: error {failures[symbol]}", flush=True)
        if pause:
            time.sleep(pause)

    missing_essential = sorted(essential - set(instruments))
    if missing_essential:
        raise RuntimeError(
            "essential HF Data Library coverage failed for " + ", ".join(missing_essential)
            + "; refusing to publish a partial S&P sector structure universe"
        )

    return {
        "schema": "MARKET-HISTORY-V1",
        "provider": "HF Data Library daily clean",
        "rights_status": "verified_publishable",
        "license_reference": HF_LICENSE,
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "adjustment": "HF Data Library clean prices are split/dividend adjusted; adjusted_close equals close",
        "instruments": instruments,
        "failed_optional_instruments": failures,
        "attribution": {
            "hf_data_library": HF_CITATION,
            "hf_license": HF_LICENSE,
            "hf_terms": HF_TERMS_URL,
            "hf_methodology": HF_DOCS_URL,
            "hf_api": HF_API_URL,
            "iex_notice": IEX_ATTRIBUTION,
            "iex_terms": IEX_TERMS_URL,
        },
        "data_limitations": [
            "March 2022 is a documented source-regime break.",
            "Pre-March-2022 observations are based on PiTrading consolidated-tape data.",
            "Post-March-2022 observations are IEX Exchange only (a small subset of U.S. trading), not consolidated OHLCV.",
            "Volume and OHLC can therefore differ materially from consolidated feeds after the source break.",
            "The HFDL universe is not a point-in-time reconstructed universe and must not be used to claim survivorship-free stock-universe research.",
        ],
        "notes": [
            "This public feed intentionally covers canonical ETFs only; proprietary headline index series are not synthesized.",
            "SPY/QQQ/DIA are ETF proxies and must not be relabeled as the S&P 500, Nasdaq-100, or DJIA index series themselves.",
            "Data supplied under CC BY 4.0; preserve attribution in redistributions and derivative works.",
            IEX_ATTRIBUTION,
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe", default=str(UNIVERSE))
    ap.add_argument("--symbols", default="", help="comma-separated canonical ETFs; default = every canonical ETF")
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--output", default="/tmp/hfdl_market_history.json")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args(argv)

    start_d = dt.date.fromisoformat(args.start)
    end_d = dt.date.fromisoformat(args.end)
    if start_d > end_d:
        ap.error("--start must precede --end")

    target = Path(args.output)
    public_tree = target.resolve().is_relative_to(Path("docs/data").resolve())
    if public_tree and not args.publish:
        ap.error("output inside docs/data requires --publish")
    if args.publish and not public_tree:
        ap.error("--publish must target docs/data")

    api_key = os.getenv("HFDL_API_KEY", "").strip()
    if not api_key:
        ap.error("HFDL_API_KEY missing; store it in GitHub Actions Secrets, never in the repository")

    universe = json.loads(Path(args.universe).read_text(encoding="utf-8"))
    default_symbols, _essential = canonical_etfs(universe)
    selected = (
        [x.strip().upper() for x in args.symbols.split(",") if x.strip()]
        if args.symbols.strip() else default_symbols
    )
    history = build_history(selected, universe, args.start, args.end, api_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {target}: {len(history['instruments'])} canonical ETFs; rights=verified_publishable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
