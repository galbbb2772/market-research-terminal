#!/usr/bin/env python3
"""Fetch no-key official/public macro and financial-conditions series.

The script deliberately uses public endpoints that do not require credentials and writes
normalized observations for the static research site. Individual source failures are
recorded in source_status instead of aborting the entire refresh.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "market-research-terminal/1.0 (public research; GitHub Actions)"


def get_text(url: str, timeout: int = 40) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in {".", "NA", "N/A", "null"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fred_csv(series_id: str):
    # fredgraph.csv is a public CSV download and does not require an API key.
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": series_id})
    rows = list(csv.DictReader(io.StringIO(get_text(url))))
    out = []
    for r in rows:
        d = r.get("DATE") or r.get("observation_date")
        v = num(r.get(series_id))
        if d and v is not None:
            out.append({"date": d, "value": v})
    return out, url


def treasury_csv():
    # Treasury Fiscal Data API is official, no-key JSON.
    url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/"
        "accounting/od/avg_interest_rates?"
        "fields=record_date,security_desc,avg_interest_rate_amt&"
        "filter=security_desc:eq:Treasury Bills&sort=-record_date&page[size]=5000"
    )
    raw = json.loads(get_text(url))
    rows = []
    for r in raw.get("data", []):
        v = num(r.get("avg_interest_rate_amt"))
        if v is not None:
            rows.append({"date": r.get("record_date"), "value": v})
    return rows, url


SERIES = {
    # Labor / inflation / activity
    "unemployment_rate": ("UNRATE", "%", "monthly"),
    "cpi_all_urban": ("CPIAUCSL", "index", "monthly"),
    "core_cpi": ("CPILFESL", "index", "monthly"),
    "payrolls": ("PAYEMS", "thousands", "monthly"),
    "industrial_production": ("INDPRO", "index", "monthly"),
    "capacity_utilization": ("TCU", "%", "monthly"),
    # Rates / financial conditions
    "fed_funds_effective": ("DFF", "%", "daily"),
    "treasury_3m": ("DGS3MO", "%", "daily"),
    "treasury_2y": ("DGS2", "%", "daily"),
    "treasury_10y": ("DGS10", "%", "daily"),
    "treasury_30y": ("DGS30", "%", "daily"),
    "real_10y": ("DFII10", "%", "daily"),
    "breakeven_10y": ("T10YIE", "%", "daily"),
    "vix": ("VIXCLS", "index", "daily"),
    "chicago_nfci": ("NFCI", "index", "weekly"),
    "chicago_anfci": ("ANFCI", "index", "weekly"),
    "stl_financial_stress": ("STLFSI4", "index", "weekly"),
    # Credit / liquidity proxies
    "hy_oas": ("BAMLH0A0HYM2", "%", "daily"),
    "ig_oas": ("BAMLC0A0CM", "%", "daily"),
    "walcl": ("WALCL", "millions_usd", "weekly"),
    "reverse_repo": ("RRPONTSYD", "billions_usd", "daily"),
    "sofr": ("SOFR", "%", "daily"),
}


def main():
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series": {},
        "source_status": {},
        "notes": "Public/no-key normalized macro series. FRED graph CSV is used only for series whose redistribution/public display is appropriate for this research site; source provenance is retained.",
    }

    for name, (sid, unit, freq) in SERIES.items():
        try:
            obs, url = fred_csv(sid)
            payload["series"][name] = {
                "provider": "Federal Reserve Bank of St. Louis FRED public CSV",
                "provider_series": sid,
                "unit": unit,
                "frequency": freq,
                "source_url": url,
                "observations": obs,
            }
            payload["source_status"][name] = {"ok": True, "rows": len(obs)}
        except Exception as e:
            payload["source_status"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        obs, url = treasury_csv()
        payload["series"]["treasury_bill_average_interest_rate"] = {
            "provider": "U.S. Department of the Treasury Fiscal Data",
            "unit": "%",
            "frequency": "monthly",
            "source_url": url,
            "observations": obs,
        }
        payload["source_status"]["treasury_bill_average_interest_rate"] = {"ok": True, "rows": len(obs)}
    except Exception as e:
        payload["source_status"]["treasury_bill_average_interest_rate"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    out = Path("docs/data/macro_public.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Require at least a useful core set, but tolerate isolated upstream failures.
    ok = sum(1 for x in payload["source_status"].values() if x.get("ok"))
    if ok < 8:
        raise SystemExit(f"Only {ok} public macro sources succeeded; refusing to publish")
    print(f"wrote {out} with {ok}/{len(payload['source_status'])} successful series")


if __name__ == "__main__":
    main()
