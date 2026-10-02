#!/usr/bin/env python3
"""Fetch no-key CFTC Commitments of Traders positioning for market context.

This connector uses the CFTC Public Reporting Environment (Socrata) and keeps a
small set of explicitly pinned financial-futures contracts useful for descriptive
market research. Contract codes are pinned deliberately: broad text search can
otherwise match similarly named dividend products or the wrong Treasury maturity.
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

# CFTC contract-market codes from the official TFF Futures Only dataset.
# We intentionally choose the liquid mini/index contracts rather than a fuzzy
# commodity-name match. Expected labels are assertions against accidental remaps.
TARGETS = {
    "sp500": {"code": "13874A", "expected": "E-MINI S&P 500"},
    "nasdaq100": {"code": "209742", "expected": "NASDAQ MINI"},
    "dow": {"code": "124603", "expected": "DJIA x $5"},
    "russell2000": {"code": "239742", "expected": "RUSSELL E-MINI"},
    "usd_index": {"code": "098662", "expected": "USD INDEX"},
    "us10y": {"code": "043602", "expected": "UST 10Y NOTE"},
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
        "contract_code": row.get("cftc_contract_market_code"),
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


def query_contract_code(code: str) -> list[dict[str, Any]]:
    # Exact Socrata filter prevents a search for "10-year" from selecting 5Y or a
    # search for "Russell 2000" from selecting an annual-dividend derivative.
    params = urllib.parse.urlencode({
        "$limit": "3000",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$where": f"cftc_contract_market_code='{code}'",
    })
    obj = get_json(BASE + "?" + params)
    return [r for r in obj if isinstance(r, dict)] if isinstance(obj, list) else []


def fetch_target(name: str, spec: dict[str, str]) -> dict[str, Any]:
    code = spec["code"]
    expected = spec["expected"]
    try:
        raw = query_contract_code(code)
        rows = [compact(r) for r in raw]
        rows = [r for r in rows if r.get("date") and r.get("contract")]
        if not rows:
            raise ValueError(f"contract code {code} returned no usable rows")
        wrong_codes = sorted({str(r.get("contract_code")) for r in rows if str(r.get("contract_code")) != code})
        if wrong_codes:
            raise ValueError(f"contract-code filter leaked other codes: {wrong_codes[:5]}")
        latest_name = str(rows[0].get("contract") or "")
        if expected.upper() not in latest_name.upper():
            raise ValueError(
                f"contract code {code} latest label {latest_name!r} does not match expected {expected!r}"
            )
        by_date: dict[str, dict[str, Any]] = {}
        for row in rows:
            by_date[row["date"]] = row
        observations = [by_date[d] for d in sorted(by_date)]
        latest = observations[-1]
        return {
            "status": "ok",
            "contract_code": code,
            "selected_contract": latest.get("contract"),
            "expected_contract_label": expected,
            "observation_count": len(observations),
            "start": observations[0]["date"],
            "end": observations[-1]["date"],
            "latest": latest,
            "observations": observations,
        }
    except Exception as exc:
        return {
            "status": "error",
            "contract_code": code,
            "expected_contract_label": expected,
            "error": f"{type(exc).__name__}: {str(exc)[:260]}",
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/data/positioning_public.json")
    args = ap.parse_args()

    targets = {name: fetch_target(name, spec) for name, spec in TARGETS.items()}
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
            "Each target is pinned to a documented CFTC contract-market code; no fuzzy contract-name selection is used.",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if ok_count < len(TARGETS):
        failures = {k: v.get("error") for k, v in targets.items() if v.get("status") != "ok"}
        raise SystemExit(f"Only {ok_count}/{len(targets)} pinned CFTC targets succeeded: {failures}")
    print(f"Wrote {out}: {ok_count}/{len(targets)} pinned CFTC targets ok")


if __name__ == "__main__":
    main()
