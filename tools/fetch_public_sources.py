#!/usr/bin/env python3
"""Fetch redistributable/public official data for the static research website.

This is website data plumbing, not a backtest or trading module.

Design:
- official/no-key sources only in the default job;
- fail-soft per source so one outage cannot fabricate or erase other sources;
- each record carries provenance and retrieval time;
- current/revised histories are never mislabeled as point-in-time vintages;
- no API keys are written into public JSON.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/galbbb2772/market-research-terminal"
USER_AGENT = f"MarketResearchTerminal/1.0 (+{REPO_URL})"
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", USER_AGENT)
NOW = lambda: datetime.now(timezone.utc)

BLS_SERIES = {
    "UNRATE": ("LNS14000000", "Civilian unemployment rate, seasonally adjusted", "%"),
    "CPI": ("CUSR0000SA0", "CPI-U all items, seasonally adjusted", "index"),
    "PAYROLLS": ("CES0000000001", "Total nonfarm payroll employment, seasonally adjusted", "thousands"),
    "AHE": ("CES0500000003", "Average hourly earnings, total private, seasonally adjusted", "USD/hour"),
    "LFPR": ("LNS11300000", "Civilian labor force participation rate, seasonally adjusted", "%"),
    "PPI_FINAL_DEMAND": ("WPUFD4", "PPI final demand", "index"),
}
BLS_KNOWN_UNAVAILABLE = {"UNRATE": ["2025-10"]}

TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&"
    "field_tdr_date_value={year}&page&_format=csv"
)
G17_URL = "https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
NYFED_SOFR = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/500.json"
NYFED_EFFR = "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/500.json"
SLOOS_URL = (
    "https://www.federalreserve.gov/datadownload/Output.aspx?"
    "filetype=csv&from=&label=include&lastobs=&layout=seriescolumn&rel=SLOOS&"
    "series=e64f07187815f0e7ed89237d8cb91eeb&to=&type=package"
)
OECD_CLI_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.STES,DSD_STES@DF_CLI/.M.LI...AA...H?"
    "startPeriod=2000-01&dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
)
WORLD_BANK = {
    "GDP_GROWTH": ("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"),
    "INFLATION_CPI": ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)"),
    "GFCF_SHARE_GDP": ("NE.GDI.FTOT.ZS", "Gross fixed capital formation (% of GDP)"),
}
GDELT_QUERIES = {
    "geopolitical": '(war OR conflict OR sanctions OR missile OR invasion OR ceasefire)',
    "systemic": '("bank failure" OR liquidity OR recession OR default OR "credit crisis")',
    "us_policy": '("Federal Reserve" OR tariff OR "White House" OR Congress OR regulation)',
    "ai_narrative": '("artificial intelligence" OR AI) (bubble OR risk OR regulation OR investment)',
}


def _request(url: str, *, method: str = "GET", data: bytes | None = None,
             headers: dict[str, str] | None = None, timeout: int = 30,
             retries: int = 2) -> bytes:
    hdr = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hdr, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.2 * (attempt + 1))
    assert last is not None
    raise last


def _get_json(url: str, *, headers: dict[str, str] | None = None,
              timeout: int = 30) -> Any:
    raw = _request(url, headers=headers, timeout=timeout)
    return json.loads(raw.decode("utf-8-sig"))


def _get_text(url: str, *, headers: dict[str, str] | None = None,
              timeout: int = 30) -> str:
    return _request(url, headers=headers, timeout=timeout).decode("utf-8-sig", errors="replace")


def _post_json(url: str, payload: dict[str, Any], *, timeout: int = 30) -> Any:
    raw = _request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=timeout,
    )
    return json.loads(raw.decode("utf-8-sig"))


def _ok(provider: str, source_url: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "provider": provider,
        "source_url": source_url,
        "retrieved_at": NOW().isoformat(),
        **kwargs,
    }


def _err(provider: str, source_url: str, exc: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "provider": provider,
        "source_url": source_url,
        "retrieved_at": NOW().isoformat(),
        "error": f"{type(exc).__name__}: {str(exc)[:260]}",
    }


def fetch_bls() -> dict[str, Any]:
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    try:
        year = NOW().year
        payload = {
            "seriesid": [x[0] for x in BLS_SERIES.values()],
            "startyear": str(year - 9),
            "endyear": str(year),
        }
        obj = _post_json(url, payload)
        if obj.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError("BLS status " + str(obj.get("status")))
        by_id = {s.get("seriesID"): s for s in obj.get("Results", {}).get("series", [])}
        series = {}
        for key, (sid, label, unit) in BLS_SERIES.items():
            rows = []
            for item in by_id.get(sid, {}).get("data", []):
                p = str(item.get("period", ""))
                if not re.fullmatch(r"M(0[1-9]|1[0-2])", p):
                    continue
                try:
                    val = float(item["value"])
                    day = f"{int(item['year']):04d}-{p[1:]}"
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append([day, val])
            rows.sort(key=lambda x: x[0])
            series[key] = {
                "series_id": sid,
                "name": label,
                "unit": unit,
                "frequency": "monthly",
                "observations": rows,
                "known_unavailable": BLS_KNOWN_UNAVAILABLE.get(key, []),
            }
        if not any(v["observations"] for v in series.values()):
            raise ValueError("BLS returned no usable monthly observations")
        return _ok(
            "U.S. Bureau of Labor Statistics",
            "https://www.bls.gov/developers/",
            point_in_time=False,
            history_type="current/revised official history, not vintage",
            series=series,
        )
    except Exception as exc:
        return _err("U.S. Bureau of Labor Statistics", url, exc)


def fetch_treasury(years: int = 10) -> dict[str, Any]:
    source = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
    try:
        current = NOW().year
        rows: dict[str, dict[str, Any]] = {}
        failed: list[str] = []
        keep = ["1 Mo", "3 Mo", "6 Mo", "1 Yr", "2 Yr", "5 Yr", "10 Yr", "20 Yr", "30 Yr"]
        for year in range(current - years + 1, current + 1):
            url = TREASURY_URL.format(year=year)
            try:
                text = _get_text(url, timeout=20)
                reader = csv.DictReader(io.StringIO(text))
                count = 0
                for r in reader:
                    try:
                        date = datetime.strptime(r["Date"].strip(), "%m/%d/%Y").date().isoformat()
                    except Exception:
                        continue
                    out: dict[str, Any] = {"date": date}
                    for k in keep:
                        try:
                            v = float((r.get(k) or "").strip())
                        except ValueError:
                            continue
                        if -5 < v < 30:
                            out[k] = v
                    if "10 Yr" in out and "3 Mo" in out:
                        out["10Y-3M"] = round(out["10 Yr"] - out["3 Mo"], 4)
                    if len(out) > 1:
                        rows[date] = out
                        count += 1
                if not count:
                    failed.append(str(year))
            except Exception:
                failed.append(str(year))
        data = [rows[k] for k in sorted(rows)]
        if not data:
            raise ValueError("Treasury returned no valid daily curve rows")
        return _ok(
            "U.S. Department of the Treasury",
            source,
            point_in_time=False,
            history_type="current official historical table; revisions/corrections may occur",
            frequency="daily",
            requested_years=years,
            failed_years=failed,
            rows=data,
            definition="Daily Treasury par yield curve. 10Y-3M is a direct arithmetic proxy and is not FRED T10Y3M.",
        )
    except Exception as exc:
        return _err("U.S. Department of the Treasury", source, exc)


_G17_ROW = re.compile(r'^\s*"B50001"\s+(\d{4})\s+(.+?)\s*$', re.MULTILINE)
_G17_HEADER = re.compile(r'^\s*"B50001:\s*Total index"\s*$', re.MULTILINE | re.IGNORECASE)


def parse_g17(raw: str) -> list[list[Any]]:
    if not _G17_HEADER.search(raw):
        raise ValueError("G17 B50001 header missing")
    obs: dict[str, float] = {}
    for match in _G17_ROW.finditer(raw):
        year = int(match.group(1))
        tokens = match.group(2).split()
        if not (1919 <= year <= 2100 and 1 <= len(tokens) <= 12):
            raise ValueError("invalid G17 annual row")
        for month, token in enumerate(tokens, 1):
            if token.upper() in {".", "NA", "ND", "N/A"}:
                continue
            value = float(token)
            if not 0 < value < 10000:
                raise ValueError("implausible G17 index value")
            key = f"{year:04d}-{month:02d}"
            if key in obs:
                raise ValueError("duplicate G17 observation " + key)
            obs[key] = round(value, 4)
    if not obs:
        raise ValueError("no G17 observations")
    return [[k, obs[k]] for k in sorted(obs)]


def fetch_g17() -> dict[str, Any]:
    try:
        raw = _get_text(G17_URL, timeout=25)
        if "<html" in raw[:400].lower():
            raise ValueError("G17 endpoint returned HTML")
        rows = parse_g17(raw)
        return _ok(
            "Federal Reserve Board G.17",
            G17_URL,
            point_in_time=False,
            history_type="revised current history, not as-first-released",
            frequency="monthly",
            series={
                "INDPRO_B50001": {
                    "name": "Industrial Production: Total index",
                    "series_code": "B50001",
                    "unit": "2017=100",
                    "seasonal_adjustment": "seasonally adjusted",
                    "observations": rows,
                }
            },
        )
    except Exception as exc:
        return _err("Federal Reserve Board G.17", G17_URL, exc)


def _nyfed_one(url: str, label: str) -> list[dict[str, Any]]:
    obj = _get_json(url)
    out = []
    for r in obj.get("refRates", []):
        day = r.get("effectiveDate")
        if not isinstance(day, str):
            continue
        item = {"date": day, "type": r.get("type", label)}
        for src, dst in (
            ("percentRate", "rate"),
            ("volumeInBillions", "volume_bn"),
            ("percentPercentile1", "p1"),
            ("percentPercentile25", "p25"),
            ("percentPercentile75", "p75"),
            ("percentPercentile99", "p99"),
            ("average30day", "avg30"),
            ("average90day", "avg90"),
            ("average180day", "avg180"),
            ("index", "index"),
        ):
            if isinstance(r.get(src), (int, float)):
                item[dst] = r[src]
        if r.get("revisionIndicator"):
            item["revision"] = r["revisionIndicator"]
        out.append(item)
    out.sort(key=lambda x: x["date"])
    return out


def fetch_nyfed() -> dict[str, Any]:
    source = "https://markets.newyorkfed.org/static/docs/markets-api.html"
    try:
        sofr = _nyfed_one(NYFED_SOFR, "SOFR")
        effr = _nyfed_one(NYFED_EFFR, "EFFR")
        if not sofr and not effr:
            raise ValueError("NY Fed returned no reference rates")
        return _ok(
            "Federal Reserve Bank of New York",
            source,
            point_in_time=False,
            frequency="business-day",
            series={
                "SOFR": {"name": "Secured Overnight Financing Rate", "unit": "%", "observations": sofr},
                "EFFR": {"name": "Effective Federal Funds Rate", "unit": "%", "observations": effr},
            },
        )
    except Exception as exc:
        return _err("Federal Reserve Bank of New York", source, exc)


def fetch_world_bank() -> dict[str, Any]:
    source = "https://api.worldbank.org/v2/"
    try:
        series = {}
        for key, (indicator, label) in WORLD_BANK.items():
            url = (
                f"https://api.worldbank.org/v2/country/USA/indicator/{indicator}"
                "?format=json&per_page=1000"
            )
            obj = _get_json(url)
            rows = []
            data = obj[1] if isinstance(obj, list) and len(obj) > 1 else []
            for r in data or []:
                value = r.get("value")
                date = r.get("date")
                if isinstance(value, (int, float)) and isinstance(date, str):
                    rows.append([date, float(value)])
            rows.sort(key=lambda x: x[0])
            series[key] = {
                "indicator": indicator,
                "name": label,
                "country": "USA",
                "frequency": "annual",
                "observations": rows,
            }
        if not any(v["observations"] for v in series.values()):
            raise ValueError("World Bank returned no usable data")
        return _ok(
            "World Bank",
            source,
            point_in_time=False,
            history_type="latest published database values, not vintage",
            series=series,
        )
    except Exception as exc:
        return _err("World Bank", source, exc)


def fetch_oecd_cli() -> dict[str, Any]:
    try:
        text = _get_text(OECD_CLI_URL, headers={"Accept": "text/csv"}, timeout=45)
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for r in reader:
            area = (r.get("REF_AREA") or r.get("Reference area") or r.get("LOCATION") or "").strip()
            if area.upper() not in {"USA", "UNITED STATES"} and "United States" not in area:
                continue
            period = (r.get("TIME_PERIOD") or r.get("Time period") or r.get("TIME") or "").strip()
            raw = r.get("OBS_VALUE") or r.get("Observation value") or r.get("Value")
            try:
                value = float(raw) if raw not in (None, "") else None
            except ValueError:
                continue
            if not period or value is None:
                continue
            rows.append({
                "date": period,
                "value": value,
                "measure": r.get("MEASURE") or r.get("Measure"),
                "unit": r.get("UNIT_MEASURE") or r.get("Unit of measure"),
                "subject": r.get("SUBJECT") or r.get("Subject"),
                "adjustment": r.get("ADJUSTMENT") or r.get("Adjustment"),
            })
        rows.sort(key=lambda x: x["date"])
        if not rows:
            raise ValueError("OECD CLI query returned no USA rows")
        return _ok(
            "OECD Data Explorer",
            OECD_CLI_URL,
            point_in_time=False,
            history_type="current OECD database, not reconstructed publication vintages",
            frequency="monthly",
            rows=rows[-1000:],
            note="CLI query follows OECD's documented SDMX Data Explorer example and is filtered to USA.",
        )
    except Exception as exc:
        return _err("OECD Data Explorer", OECD_CLI_URL, exc)


def fetch_sec() -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        obj = _get_json(
            SEC_TICKERS_URL,
            headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"},
            timeout=30,
        )
        fields = obj.get("fields") or []
        data = obj.get("data") or []
        if not fields or not data:
            raise ValueError("SEC ticker/exchange mapping empty")
        try:
            ix_exchange = fields.index("exchange")
        except ValueError:
            ix_exchange = 3 if len(fields) > 3 else None
        counts = Counter()
        if ix_exchange is not None:
            for row in data:
                if len(row) > ix_exchange:
                    counts[str(row[ix_exchange] or "Unspecified")] += 1
        public_file = {
            "schema": "SEC-TICKERS-V1",
            "retrieved_at": NOW().isoformat(),
            "source_url": SEC_TICKERS_URL,
            "fields": fields,
            "data": data,
            "note": "SEC states ticker/CIK/exchange association files are periodically updated and do not guarantee accuracy or scope.",
        }
        summary = _ok(
            "U.S. Securities and Exchange Commission",
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            point_in_time=False,
            ticker_count=len(data),
            exchange_counts=dict(counts.most_common()),
            generated_file="data/sec_tickers.json",
            api_note="data.sec.gov has no CORS; browser pages should consume staged static JSON rather than expose direct requests.",
        )
        return summary, public_file
    except Exception as exc:
        return _err("U.S. Securities and Exchange Commission", SEC_TICKERS_URL, exc), None


def parse_sloos_csv(text: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("empty SLOOS CSV")
    series_ids: dict[int, str] = {}
    descriptions: dict[int, str] = {}
    for row in rows[:20]:
        first = (row[0] if row else "").strip().lower()
        for idx, cell in enumerate(row[1:], 1):
            c = cell.strip()
            m = re.search(r"(SUBLP[A-Z0-9_]+\.Q)", c)
            if m:
                series_ids[idx] = m.group(1)
        if "series description" in first:
            for idx, cell in enumerate(row[1:], 1):
                descriptions[idx] = cell.strip()
    if not series_ids:
        for row in rows[:10]:
            for idx, cell in enumerate(row):
                m = re.search(r"(SUBLP[A-Z0-9_]+\.Q)", cell)
                if m:
                    series_ids[idx] = m.group(1)
    if not series_ids:
        raise ValueError("SLOOS series identifier row not found")
    series = {
        sid: {"name": descriptions.get(idx, sid), "frequency": "quarterly", "unit": "net percent", "observations": []}
        for idx, sid in series_ids.items()
    }
    for row in rows:
        if not row:
            continue
        period = row[0].strip()
        if not re.fullmatch(r"\d{4}Q[1-4]", period):
            continue
        for idx, sid in series_ids.items():
            if idx >= len(row):
                continue
            cell = row[idx].strip()
            if cell in {"", "ND", "NA", "N/A", "."}:
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            series[sid]["observations"].append([period, value])
    series = {k: v for k, v in series.items() if v["observations"]}
    if not series:
        raise ValueError("SLOOS parsed identifiers but no quarterly observations")
    return series


def fetch_sloos() -> dict[str, Any]:
    source = "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=SLOOS"
    try:
        text = _get_text(SLOOS_URL, timeout=35)
        if "<html" in text[:500].lower():
            raise ValueError("SLOOS output returned HTML instead of CSV")
        series = parse_sloos_csv(text)
        return _ok(
            "Federal Reserve Board SLOOS",
            source,
            point_in_time=False,
            history_type="current/revised survey history; survey quarter and release date are distinct",
            frequency="quarterly",
            series=series,
            primary_series="SUBLPDCILS_N.Q",
            primary_definition="Net percentage of domestic banks tightening standards for C&I loans to large and middle-market firms",
        )
    except Exception as exc:
        return _err("Federal Reserve Board SLOOS", source, exc)


def _gdelt_timeline(query: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "query": query,
        "mode": "timelinevolraw",
        "format": "json",
        "timespan": "3months",
        "maxrecords": "250",
    })
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + params
    obj = _get_json(url, timeout=45)
    timeline = obj.get("timeline") or []
    if not timeline:
        return []
    series = timeline[0]
    out = []
    for item in series.get("data") or []:
        day = item.get("date")
        value = item.get("value")
        norm = item.get("norm")
        if day is None or not isinstance(value, (int, float)):
            continue
        row = {"date": str(day), "articles": value}
        if isinstance(norm, (int, float)) and norm:
            row["all_articles"] = norm
            row["share"] = value / norm
        out.append(row)
    return out


def fetch_gdelt() -> dict[str, Any]:
    source = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    try:
        series = {}
        failures = {}
        for key, query in GDELT_QUERIES.items():
            try:
                rows = _gdelt_timeline(query)
                if rows:
                    series[key] = {"query": query, "frequency": "daily for >1 week windows", "observations": rows}
                else:
                    failures[key] = "empty"
            except Exception as exc:
                failures[key] = f"{type(exc).__name__}: {str(exc)[:120]}"
            time.sleep(0.25)
        if not series:
            raise ValueError("all GDELT queries failed or returned empty data")
        return _ok(
            "GDELT Project DOC 2.0",
            source,
            point_in_time=False,
            window="rolling 3 months",
            metric="raw matched article count plus monitored-all-articles normalization when supplied",
            caution="These are topic-coverage proxies, not a validated sentiment or trading signal.",
            series=series,
            failures=failures,
        )
    except Exception as exc:
        return _err("GDELT Project DOC 2.0", source, exc)


FETCHERS = {
    "bls": fetch_bls,
    "treasury": fetch_treasury,
    "fed_g17": fetch_g17,
    "nyfed": fetch_nyfed,
    "world_bank": fetch_world_bank,
    "oecd_cli": fetch_oecd_cli,
    "sloos": fetch_sloos,
    "gdelt": fetch_gdelt,
}


def build() -> tuple[dict[str, Any], dict[str, Any] | None]:
    sources: dict[str, Any] = {}
    for key, func in FETCHERS.items():
        sources[key] = func()
        print(f"{key}: {sources[key].get('status')}", flush=True)
    sec_summary, sec_file = fetch_sec()
    sources["sec"] = sec_summary
    print(f"sec: {sec_summary.get('status')}", flush=True)
    ok_count = sum(1 for x in sources.values() if x.get("status") == "ok")
    return {
        "schema": "OFFICIAL-PUBLIC-SOURCES-V1",
        "generated_at": NOW().isoformat(),
        "website": REPO_URL,
        "purpose": "public research website data plumbing; no backtest, no trading signal",
        "source_count": len(sources),
        "ok_count": ok_count,
        "sources": sources,
        "notes": [
            "No browser API keys are used.",
            "Current/revised histories are not publication-time vintages unless explicitly labeled otherwise.",
            "A source error is preserved as an error state; missing observations are never fabricated.",
        ],
    }, sec_file


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/data/official_sources.json")
    ap.add_argument("--sec-output", default="docs/data/sec_tickers.json")
    ap.add_argument("--require-min-ok", type=int, default=4,
                    help="fail deployment if fewer than this many independent sources succeeded")
    args = ap.parse_args()
    bundle, sec_file = build()
    write_json(Path(args.output), bundle)
    if sec_file is not None:
        write_json(Path(args.sec_output), sec_file)
    if bundle["ok_count"] < args.require_min_ok:
        raise SystemExit(
            f"Only {bundle['ok_count']}/{bundle['source_count']} sources succeeded; "
            f"minimum is {args.require_min_ok}"
        )
    print(f"Wrote {args.output}: {bundle['ok_count']}/{bundle['source_count']} sources ok")


if __name__ == "__main__":
    main()
