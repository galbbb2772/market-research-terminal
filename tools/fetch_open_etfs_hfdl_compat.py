#!/usr/bin/env python3
"""Compatibility/diagnostic launcher for the HF Data Library ETF adapter.

The preferred path asks HF Data Library for a signed daily-CSV URL. If that
provider path returns 404 after successful authentication, fall back to the
canonical /bars/{ticker} 1-minute parquet endpoint and aggregate those clean
bars to daily OHLCV locally. The fallback preserves the same provider, license,
source-regime notes and publication gates; it does not substitute another feed.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

import fetch_open_etfs_hfdl as base


def _token_request(url: str, api_key: str, header_name: str, header_value: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": base.USER_AGENT,
            "Accept": "application/json",
            header_name: header_value,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def _safe_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8-sig", errors="replace").strip()
    except Exception:
        return ""
    return body[:500]


def signed_csv_url_compat(symbol: str, api_key: str) -> str:
    params = urllib.parse.urlencode(
        {"timeframe": "daily", "format": "csv", "version": "clean"}
    )
    url = f"{base.API_BASE}/download-token/{urllib.parse.quote(symbol, safe='')}?{params}"

    attempts = (
        ("X-API-Key", "X-API-Key", api_key),
        ("Bearer", "Authorization", f"Bearer {api_key}"),
    )
    denied: list[str] = []
    for label, header_name, header_value in attempts:
        try:
            raw = _token_request(url, api_key, header_name, header_value)
        except urllib.error.HTTPError as exc:
            body = _safe_error_body(exc)
            if exc.code in (401, 403):
                denied.append(f"{label} HTTP {exc.code}: {body or '<empty response body>'}")
                continue
            raise

        obj = json.loads(raw.decode("utf-8-sig"))
        signed = obj.get("url") if isinstance(obj, dict) else None
        if isinstance(signed, str) and signed.startswith("https://"):
            print(f"{symbol}: HF token auth accepted via {label}", flush=True)
            return signed
        denied.append(f"{label}: response did not contain a signed HTTPS URL")

    detail = " | ".join(denied)
    raise PermissionError(
        f"{symbol}: HF Data Library rejected both API-key auth styles. {detail}. "
        "HF's API documentation says HTTP 403 means the account email is not verified "
        "or the required profile fields (institution, country, role) are incomplete."
    )


def _instrument_result(symbol: str, bars: list[list[Any]], provenance: dict[str, Any], mode: str) -> dict[str, Any]:
    return {
        "provider_symbol": symbol,
        "source_status": mode,
        "start": bars[0][0],
        "end": bars[-1][0],
        "bars": bars,
        "provenance": provenance,
        "source_break_note": (
            "HF Data Library documents a March-2022 source break: earlier history is PiTrading "
            "consolidated tape; later history is IEX Exchange only and is not consolidated-market OHLCV."
        ),
    }


def _fetch_1min_parquet_daily(symbol: str, start: str, end: str, api_key: str) -> dict[str, Any]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas/pyarrow are required for the HFDL canonical-bars fallback"
        ) from exc

    url = f"{base.API_BASE}/bars/{urllib.parse.quote(symbol, safe='')}?version=clean"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": base.USER_AGENT,
            "Accept": "application/octet-stream",
            "X-API-Key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body = _safe_error_body(exc)
        raise RuntimeError(
            f"{symbol}: canonical /bars endpoint HTTP {exc.code}: {body or '<binary/empty response>'}"
        ) from exc

    frame = pd.read_parquet(io.BytesIO(raw))
    if "datetime" not in frame.columns:
        idx_name = str(frame.index.name or "").lower()
        if idx_name == "datetime":
            frame = frame.reset_index()
        else:
            raise ValueError(f"{symbol}: parquet has no datetime column")

    lower_map = {str(c).lower(): c for c in frame.columns}
    required = ["datetime", "open", "high", "low", "close", "volume"]
    missing = [name for name in required if name not in lower_map]
    if missing:
        raise ValueError(f"{symbol}: parquet missing columns {missing}")

    rename = {lower_map[name]: name for name in required}
    if "source" in lower_map:
        rename[lower_map["source"]] = "source"
    frame = frame.rename(columns=rename)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.dropna(subset=["datetime"]).sort_values("datetime")
    frame["date"] = frame["datetime"].dt.strftime("%Y-%m-%d")
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)]
    if frame.empty:
        raise ValueError(f"{symbol}: no 1-minute observations in requested window")

    grouped = frame.groupby("date", sort=True)
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index()

    bars: list[list[Any]] = []
    for row in daily.itertuples(index=False):
        bars.append([
            str(row.date),
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            float(row.volume),
            float(row.close),
        ])
    if len(bars) < 30:
        raise ValueError(f"{symbol}: only {len(bars)} daily observations after 1-minute aggregation")

    provenance: dict[str, Any] = {"aggregation": "local daily OHLCV from HFDL clean 1-minute parquet"}
    if "source" in frame.columns:
        per_day_source = grouped["source"].agg(lambda s: str(s.dropna().iloc[0]).lower() if len(s.dropna()) else "unspecified")
        counts = Counter(per_day_source.tolist())
        ranges: dict[str, dict[str, Any]] = {}
        for src in counts:
            dates = list(per_day_source[per_day_source == src].index.astype(str))
            ranges[src] = {"start": min(dates), "end": max(dates), "observations": len(dates)}
        provenance["source_counts"] = dict(counts)
        provenance["source_ranges"] = ranges

    print(
        f"{symbol}: canonical /bars fallback ok ({len(frame):,} minute bars -> {len(bars)} daily bars)",
        flush=True,
    )
    return _instrument_result(
        symbol,
        bars,
        provenance,
        "actual_open_licensed_provider_response_aggregated_from_clean_1min",
    )


def fetch_symbol_compat(symbol: str, start: str, end: str, api_key: str) -> dict[str, Any]:
    signed = signed_csv_url_compat(symbol, api_key)
    try:
        raw = base._request(signed, timeout=90)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        body = _safe_error_body(exc)
        print(
            f"{symbol}: signed daily download returned HTTP 404 ({body or 'no body'}); "
            "falling back to canonical 1-minute parquet",
            flush=True,
        )
        return _fetch_1min_parquet_daily(symbol, start, end, api_key)

    bars, provenance = base.parse_daily_csv(raw, symbol, start, end)
    return _instrument_result(
        symbol,
        bars,
        provenance,
        "actual_open_licensed_provider_response_signed_daily_csv",
    )


def main() -> int:
    base.signed_csv_url = signed_csv_url_compat
    base.fetch_symbol = fetch_symbol_compat
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
