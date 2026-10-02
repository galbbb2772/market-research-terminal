#!/usr/bin/env python3
"""Fetch no-key CFTC Commitments of Traders positioning for market context.

This connector uses the CFTC Public Reporting Environment (Socrata) and keeps a
small set of financial-futures series useful for descriptive market research.
It does not create a trading signal and it does not use exchange price data.
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
UA = "MarketResearchTerminal/1.0 (+https://github.com/galbbb2772/market-research-terminal)"
NOW = lambda: datetime.now(timezone.utc)

TARGETS = {
    "sp500": ["S&P 500", "E-MINI S&P"],
    "nasdaq100": ["NASDAQ-100", "NASDAQ MINI"],
    "dow": ["DOW JONES INDUSTRIAL", "DJIA"],
    "russell2000": ["RUSSELL 2000"],
    "usd_index": ["U.S. DOLLAR INDEX", "USD INDEX"],
    "us10y": ["10-YEAR U.S. TREASURY", "10 YEAR U.S. TREASURY", "10-YEAR TREASURY"],
}


def get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def num(v: Any) -> float | None:
    try:
        x = float(str(v).replace(",", "").strip())
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def compact(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "date": str(row.get("report_date_as_yyyy_mm_dd") or "")[:10],
        "contract": row.get("contract_market_name") or row.get("market_and_exchange_names"),
        "commodity": row.get("commodity_name"),
        "open_interest": num(row.get("open_interest_all")),
    }
    prefixes = {
        "dealer": ("dealer_positions_long", "dealer_positions_short"),
        "asset_manager": ("asset_mgr_positions_long", "asset_mgr_positions_short"),
        "leveraged_money": ("lev_money_positions_long", "lev_money_positions_short"),
        "other_reportable": ("other_rept_positions_long", "other_rept_positions_short"),
        "nonreportable": ("nonrept_positions_long", "nonrept_positions_short"),
    }
    for label, (lp, sp) in prefixes.items():
        long_v = short_v = None
        for k, v in row.items():
            kl = k.lower()
            if long_v is None and kl.startswith(lp):
                long_v = num(v)
            if short_v is None and kl.startswith(sp):
                short_v = num(v)
        if long_v is not None:
            out[label + "_long"] = long_v
        if short_v is not None:
            out[label + "_short"] = short_v
        if long_v is not None and short_v is not None:
            out[label + "_net"] = long_v - short_v
    return out


def query(term: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "$limit": "3000",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$q": term,
    })
    obj = get_json(BASE + "?" + params)
    return [r for r in obj if isinstance(r, dict)] if isinstance(obj, list) else []


def choose_contract(rows: list[dict[str, Any]], aliases: list[str]) -> tuple[str | None, list[dict[str, Any]]]:
    prepared = [compact(r) for r in rows]
    prepared = [r for r in prepared if r.get("date") and r.get("contract")]
    if not prepared:
        return None, []

    matched = [r for r in prepared if any(a.upper() in str(r.get("contract", "")).upper() or
                                          a.upper() in str(r.get("commodity", "")).upper()
                                          for a in aliases)]
    pool = matched or prepared
    latest_by_contract: dict[str, dict[str, Any]] = {}
    for r in pool:
        name = str(r["contract"])
        old = latest_by_contract.get(name)
        if old is None or r["date"] > old["date"]:
            latest_by_contract[name] = r
    if not latest_by_contract:
        return None, []
    selected = max(latest_by_contract, key=lambda n: (latest_by_contract[n].get("open_interest") or -1.0))
    series = [r for r in pool if r.get("contract") == selected]
    by_date: dict[str, dict[str, Any]] = {}
    for r in series:
        by_date[r["date"]] = r
    out = [by_date[d] for d in sorted(by_date)]
    return selected, out


def fetch_target(name: str, aliases: list[str]) -> dict[str, Any]:
    errors = []
    merged: list[dict[str, Any]] = []
    # The first broad alias normally returns both standard and mini contracts.
    # Stop after the first non-empty search; local contract selection then chooses
    # the latest highest-open-interest match. Fallback aliases are only for misses.
    for term in aliases:
        try:
            rows = query(term)
            if rows:
                merged.extend(rows)
                break
        except Exception as exc:
            errors.append(f"{term}: {type(exc).__name__}: {str(exc)[:120]}")
    contract, rows = choose_contract(merged, aliases)
    if not rows:
        return {"status": "error", "errors": errors or ["no rows returned"]}
    latest = rows[-1]
    return {
        "status": "ok",
        "selected_contract": contract,
        "observation_count": len(rows),
        "start": rows[0]["date"],
        "end": rows[-1]["date"],
        "latest": latest,
        "observations": rows,
        "search_errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/data/positioning_public.json")
    args = ap.parse_args()

    targets = {name: fetch_target(name, aliases) for name, aliases in TARGETS.items()}
    ok_count = sum(1 for v in targets.values() if v.get("status") == "ok")
    payload = {
        "schema": "CFTC-POSITIONING-V1",
        "generated_at": NOW().isoformat(),
        "provider": "U.S. Commodity Futures Trading Commission",
        "source_url": "https://publicreporting.cftc.gov/",
        "dataset": "TFF Futures Only / CFTC Public Reporting Environment",
        "api_dataset_id": "gpe5-46if",
        "frequency": "weekly",
        "point_in_time": False,
        "history_type": "current CFTC historical database; report date is not the later public release timestamp",
        "target_count": len(targets),
        "ok_count": ok_count,
        "targets": targets,
        "notes": [
            "Position counts are futures contracts, not dollars and not ETF share flows.",
            "Long-minus-short values are descriptive positioning balances only.",
            "The highest-open-interest matching contract is selected instead of summing differently sized contracts.",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if ok_count < 2:
        raise SystemExit(f"Only {ok_count}/{len(targets)} CFTC targets succeeded")
    print(f"Wrote {out}: {ok_count}/{len(targets)} CFTC targets ok")


if __name__ == "__main__":
    main()
