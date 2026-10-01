#!/usr/bin/env python3
"""Create a local Tiingo EOD bundle for Market Research Terminal.

The Tiingo token is read interactively and is never written to the output file.
Uses only Python's standard library.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

TICKERS = [
    "SPY", "QQQ", "DIA",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SMH", "BOTZ", "SKYY", "CIBR", "FINX", "DRIV", "LIT", "ICLN", "TAN", "URA", "ITA", "XBI", "ARKG", "ESPO", "PAVE",
]


def fetch_symbol(symbol: str, token: str, start: str, end: str):
    query = urllib.parse.urlencode({"startDate": start, "endDate": end, "format": "json"})
    url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Token {token}",
            "Accept": "application/json",
            "User-Agent": "MarketResearchTerminal-Personal/1.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{symbol}: HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{symbol}: network error: {exc.reason}") from exc
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"{symbol}: no EOD rows returned")
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="Download Tiingo EOD data into a browser-importable personal bundle.")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--output", default="tiingo_personal_bundle.json")
    args = p.parse_args()
    if args.start > args.end:
        p.error("--start must be <= --end")

    token = getpass.getpass("Tiingo API Token (hidden, never saved): ").strip()
    if not token:
        print("No token entered.", file=sys.stderr)
        return 2

    data = {}
    for i, symbol in enumerate(TICKERS, 1):
        print(f"[{i:02d}/{len(TICKERS)}] {symbol} ...", flush=True)
        data[symbol] = fetch_symbol(symbol, token, args.start, args.end)

    out = {
        "schema": "MRT-TIINGO-PERSONAL-BUNDLE-V1",
        "provider": "Tiingo EOD",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start": args.start,
        "end": args.end,
        "symbols": TICKERS,
        "data": data,
    }
    path = Path(args.output).expanduser().resolve()
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\nDone: {path}")
    print("Token was not written to the bundle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
