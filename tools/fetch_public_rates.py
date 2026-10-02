#!/usr/bin/env python3
"""Fetch official no-key Treasury and New York Fed rate/liquidity data.

Outputs normalized rows and records per-source failures so one outage does not erase
other datasets. No vendor credentials are required.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "market-research-terminal/1.0 (public research; GitHub Actions)"


def get_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def to_float(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in {"N/A", "null", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def treasury_yield_curve(year: int):
    # Official Treasury XML Atom feed. One request per year keeps the parser simple and auditable.
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?"
        + urllib.parse.urlencode({"data": "daily_treasury_yield_curve", "field_tdr_date_value": str(year)})
    )
    root = ET.fromstring(get_text(url))
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    }
    field_map = {
        "BC_1MONTH": "1m", "BC_1_5MONTH": "1_5m", "BC_2MONTH": "2m", "BC_3MONTH": "3m",
        "BC_4MONTH": "4m", "BC_6MONTH": "6m", "BC_1YEAR": "1y", "BC_2YEAR": "2y",
        "BC_3YEAR": "3y", "BC_5YEAR": "5y", "BC_7YEAR": "7y", "BC_10YEAR": "10y",
        "BC_20YEAR": "20y", "BC_30YEAR": "30y",
    }
    rows = []
    for entry in root.findall("atom:entry", ns):
        props = entry.find("atom:content/m:properties", ns)
        if props is None:
            continue
        raw = {child.tag.split("}")[-1]: child.text for child in list(props)}
        date = raw.get("NEW_DATE") or raw.get("Date")
        if date:
            date = date[:10]
        yields = {dst: to_float(raw.get(src)) for src, dst in field_map.items()}
        if date and any(v is not None for v in yields.values()):
            rows.append({"date": date, **yields})
    return rows, url


def nyfed_reference_rates(start_date="2019-01-01"):
    # Official New York Fed Markets Data API. Search endpoint returns public reference-rate history.
    params = {"startDate": start_date, "type": "rate"}
    url = "https://markets.newyorkfed.org/api/rates/all/search.json?" + urllib.parse.urlencode(params)
    raw = json.loads(get_text(url))
    data = raw.get("refRates") or raw.get("referenceRates") or raw.get("data") or []
    rows = []
    for r in data:
        date = r.get("effectiveDate") or r.get("effective_date") or r.get("date")
        rate_type = r.get("type") or r.get("rateType") or r.get("rate_type")
        rate = to_float(r.get("percentRate") or r.get("rate") or r.get("percent_rate"))
        volume = to_float(r.get("volumeInBillions") or r.get("volume") or r.get("volume_in_billions"))
        if date and rate_type and rate is not None:
            rows.append({"date": str(date)[:10], "type": str(rate_type), "rate": rate, "volume_billions": volume})
    return rows, url


def main():
    now = datetime.now(timezone.utc)
    out = {
        "schema_version": "1.0",
        "generated_at": now.isoformat(),
        "datasets": {},
        "source_status": {},
    }

    treasury_rows = []
    treasury_urls = []
    try:
        for year in range(2019, now.year + 1):
            rows, url = treasury_yield_curve(year)
            treasury_rows.extend(rows)
            treasury_urls.append(url)
        treasury_rows.sort(key=lambda x: x["date"])
        out["datasets"]["treasury_par_yield_curve"] = {
            "provider": "U.S. Department of the Treasury",
            "frequency": "daily_business_days",
            "unit": "%",
            "source_urls": treasury_urls,
            "rows": treasury_rows,
        }
        out["source_status"]["treasury_par_yield_curve"] = {"ok": True, "rows": len(treasury_rows)}
    except Exception as e:
        out["source_status"]["treasury_par_yield_curve"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        rows, url = nyfed_reference_rates()
        out["datasets"]["nyfed_reference_rates"] = {
            "provider": "Federal Reserve Bank of New York",
            "frequency": "business_days",
            "unit": "%",
            "source_url": url,
            "rows": rows,
        }
        out["source_status"]["nyfed_reference_rates"] = {"ok": True, "rows": len(rows)}
    except Exception as e:
        out["source_status"]["nyfed_reference_rates"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    if not any(x.get("ok") for x in out["source_status"].values()):
        raise SystemExit("No official rate source succeeded")

    p = Path("docs/data/rates_public.json")
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
