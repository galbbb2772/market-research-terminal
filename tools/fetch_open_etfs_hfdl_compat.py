#!/usr/bin/env python3
"""Compatibility/diagnostic launcher for the HF Data Library ETF adapter.

The current HF API reference documents X-API-Key for download-token requests,
while one official AI-tools example shows Authorization: Bearer for the same
signed-URL flow. This launcher tries both without ever printing the key and,
when access is denied, surfaces the provider response body so account/profile
problems can be distinguished from GitHub Actions/network problems.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

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
    # Never echo authorization material even if an upstream proxy reflects it.
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


def main() -> int:
    base.signed_csv_url = signed_csv_url_compat
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
