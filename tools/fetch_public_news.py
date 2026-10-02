#!/usr/bin/env python3
"""Build a small GDELT-derived public news-tension archive without an API key.

This stores aggregate counts/tones only, not article text, so the public site can plot
historical news activity without redistributing publishers' copyrighted content.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

UA = "market-research-terminal/1.0 (public research; GitHub Actions)"


def get_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def timeline(query: str, start: str, end: str):
    params = {
        "query": query,
        "mode": "timelinevolraw",
        "format": "json",
        "maxrecords": "250",
        "startdatetime": start,
        "enddatetime": end,
    }
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    return get_json(url), url


def main():
    # DOC API is best for recent/high-level aggregate monitoring. Keep a rolling window;
    # deeper historical research can later use GDELT 2.1 event/GKG bulk files.
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=90)
    start = start_dt.strftime("%Y%m%d%H%M%S")
    end = end_dt.strftime("%Y%m%d%H%M%S")

    baskets = {
        "market_risk": '(economy OR markets OR stocks OR bonds) (risk OR selloff OR volatility OR recession)',
        "geopolitical": '(war OR conflict OR sanctions OR missile OR invasion OR ceasefire)',
        "inflation_rates": '(inflation OR interest rates OR Federal Reserve OR central bank)',
        "ai_technology": '(artificial intelligence OR AI) (investment OR valuation OR bubble OR earnings)',
    }

    payload = {
        "schema_version": "1.0",
        "generated_at": end_dt.isoformat(),
        "window": {"start": start_dt.date().isoformat(), "end": end_dt.date().isoformat()},
        "provider": "GDELT Project DOC 2.0 API",
        "method": "Aggregate timeline only; no article text is republished.",
        "baskets": {},
        "source_status": {},
    }

    for name, q in baskets.items():
        try:
            raw, url = timeline(q, start, end)
            # Keep only timeline records and metadata needed for reproducibility.
            timeline_data = raw.get("timeline", raw)
            payload["baskets"][name] = {"query": q, "source_url": url, "timeline": timeline_data}
            payload["source_status"][name] = {"ok": True}
        except Exception as e:
            payload["source_status"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    ok = sum(1 for x in payload["source_status"].values() if x.get("ok"))
    if ok < 2:
        raise SystemExit(f"Only {ok} GDELT baskets succeeded; refusing to publish")

    out = Path("docs/data/news_public.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} with {ok}/{len(baskets)} baskets")


if __name__ == "__main__":
    main()
