#!/usr/bin/env python3
"""Fetch no-key U.S. liquidity / policy plumbing data for the public research site.

Sources are official U.S. Treasury / Federal Reserve / New York Fed endpoints. The
output is descriptive research data only; it does not generate trading signals.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "MarketResearchTerminal/1.0 (+https://github.com/galbbb2772/market-research-terminal)"
NOW = lambda: datetime.now(timezone.utc)

TGA_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
NYFED_RRP = "https://markets.newyorkfed.org/api/rp/reverserepo/all/results/last/250.json"
NYFED_REPO = "https://markets.newyorkfed.org/api/rp/repo/all/results/last/250.json"

FED_SERIES = {
    "WALCL": ("Federal Reserve total assets", "millions USD", "weekly"),
    "WRESBAL": ("Reserve balances with Federal Reserve Banks", "millions USD", "weekly"),
    "IORB": ("Interest rate on reserve balances", "%", "daily"),
    "DFEDTARU": ("Federal funds target range upper limit", "%", "daily"),
    "DFEDTARL": ("Federal funds target range lower limit", "%", "daily"),
}


def request_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def get_json(url: str, timeout: int = 45) -> Any:
    return json.loads(request_text(url, timeout=timeout))


def number(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def ok(provider: str, source_url: str, **kwargs):
    return {"status": "ok", "provider": provider, "source_url": source_url,
            "retrieved_at": NOW().isoformat(), **kwargs}


def err(provider: str, source_url: str, exc: Exception):
    return {"status": "error", "provider": provider, "source_url": source_url,
            "retrieved_at": NOW().isoformat(), "error": f"{type(exc).__name__}: {str(exc)[:260]}"}


def fetch_tga() -> dict[str, Any]:
    params = {
        "fields": "record_date,account_type,open_today_bal,close_today_bal",
        "filter": "record_date:gte:2019-01-01",
        "sort": "record_date",
        "page[size]": "10000",
    }
    url = TGA_URL + "?" + urllib.parse.urlencode(params)
    try:
        obj = get_json(url)
        rows = []
        for r in obj.get("data", []):
            close = number(r.get("close_today_bal"))
            opening = number(r.get("open_today_bal"))
            date = r.get("record_date")
            account = r.get("account_type")
            if date and account and (close is not None or opening is not None):
                rows.append({"date": date, "account_type": account,
                             "open_mn_usd": opening, "close_mn_usd": close})
        if not rows:
            raise ValueError("Treasury DTS returned no usable operating-cash rows")
        primary = [r for r in rows if "treasury general" in r["account_type"].lower()]
        if not primary:
            primary = [r for r in rows if "federal reserve" in r["account_type"].lower()]
        return ok("U.S. Treasury Fiscal Data", TGA_URL, frequency="business-day",
                  unit="millions USD", rows=rows, primary_rows=primary,
                  note="Daily Treasury Statement operating cash balance; values are rounded to the nearest million.")
    except Exception as exc:
        return err("U.S. Treasury Fiscal Data", TGA_URL, exc)


def _extract_rp_operations(obj: Any) -> list[dict[str, Any]]:
    candidates = []
    if isinstance(obj, dict):
        for k in ("repo", "reverseRepo", "reverse_repo", "rp"):
            v = obj.get(k)
            if isinstance(v, dict):
                for kk in ("operations", "results", "data"):
                    if isinstance(v.get(kk), list):
                        candidates.extend(v[kk])
        for k in ("operations", "results", "data"):
            if isinstance(obj.get(k), list):
                candidates.extend(obj[k])
    out = []
    for r in candidates:
        if not isinstance(r, dict):
            continue
        date = r.get("operationDate") or r.get("operation_date") or r.get("date")
        amount = None
        for key in ("totalAmtAccepted", "totalAmtAcceptedUsd", "amountAccepted", "acceptedAmount", "totalAmtSubmitted"):
            amount = number(r.get(key))
            if amount is not None:
                break
        rate = None
        for key in ("awardRate", "rate", "stopOutRate"):
            rate = number(r.get(key))
            if rate is not None:
                break
        item = {"date": str(date)[:10] if date else None,
                "operation_type": r.get("operationType") or r.get("operation_type"),
                "term": r.get("term"), "amount": amount, "rate": rate}
        if item["date"] or amount is not None:
            out.append(item)
    return out


def fetch_nyfed_rp(url: str, label: str) -> dict[str, Any]:
    try:
        obj = get_json(url)
        rows = _extract_rp_operations(obj)
        if not rows:
            raise ValueError(f"NY Fed {label} endpoint returned no parsable operations")
        return ok("Federal Reserve Bank of New York", url, frequency="operation-day",
                  rows=rows, note=f"{label} operation results from the NY Fed Markets Data API.")
    except Exception as exc:
        fallback = url.rsplit("/last/", 1)[0] + "/lastTwoWeeks.json"
        try:
            obj = get_json(fallback)
            rows = _extract_rp_operations(obj)
            if not rows:
                raise ValueError("fallback returned no parsable operations")
            return ok("Federal Reserve Bank of New York", fallback, frequency="operation-day",
                      rows=rows, fallback_from=url,
                      note=f"{label} operation results; large-history endpoint failed so the documented two-week fallback was used.")
        except Exception as exc2:
            return err("Federal Reserve Bank of New York", url, RuntimeError(f"primary={exc}; fallback={exc2}"))


def fetch_one_fed_series(series_id: str) -> tuple[list[list[Any]], str]:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": series_id})
    text = request_text(url)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows: list[list[Any]] = []
    for row in reader:
        date = row.get("DATE") or row.get("observation_date")
        value = number(row.get(series_id))
        if date and value is not None:
            rows.append([date, value])
    return rows, url


def fetch_fed_policy_series() -> dict[str, Any]:
    try:
        series = {}
        urls = {}
        failures = {}
        for sid, (name, unit, freq) in FED_SERIES.items():
            try:
                observations, url = fetch_one_fed_series(sid)
                urls[sid] = url
                if observations:
                    series[sid] = {"name": name, "unit": unit, "frequency": freq,
                                   "observations": observations}
                else:
                    failures[sid] = "empty"
            except Exception as exc:
                failures[sid] = f"{type(exc).__name__}: {str(exc)[:160]}"
        if not series:
            raise ValueError("No Federal Reserve policy series parsed")
        return ok("Federal Reserve public series distributed by FRED",
                  "https://fred.stlouisfed.org/",
                  point_in_time=False,
                  history_type="current/revised official Federal Reserve series, not vintage",
                  series=series, source_urls=urls, failures=failures,
                  rights_note="Only Federal Reserve-published series are requested here; third-party licensed FRED series are intentionally excluded.")
    except Exception as exc:
        return err("Federal Reserve public series distributed by FRED", "https://fred.stlouisfed.org/", exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/data/liquidity_public.json")
    args = ap.parse_args()

    sources = {
        "treasury_tga": fetch_tga(),
        "nyfed_reverse_repo": fetch_nyfed_rp(NYFED_RRP, "Reverse Repo"),
        "nyfed_repo": fetch_nyfed_rp(NYFED_REPO, "Repo / Standing Repo"),
        "fed_policy_balance_sheet": fetch_fed_policy_series(),
    }
    ok_count = sum(1 for x in sources.values() if x.get("status") == "ok")
    payload = {
        "schema": "PUBLIC-LIQUIDITY-V1",
        "generated_at": NOW().isoformat(),
        "source_count": len(sources),
        "ok_count": ok_count,
        "sources": sources,
        "notes": [
            "No API key is required.",
            "No third-party market-price series are redistributed.",
            "Source failures are recorded rather than replaced with fabricated data.",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if ok_count < 2:
        raise SystemExit(f"Only {ok_count}/{len(sources)} liquidity sources succeeded")
    print(f"Wrote {out}: {ok_count}/{len(sources)} sources ok")


if __name__ == "__main__":
    main()
