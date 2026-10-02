#!/usr/bin/env python3
"""Fetch public news/event context without user API keys.

Primary source: GDELT DOC 2.0 aggregate timelines.  If that service is unavailable,
we still retain official Federal Reserve and BLS RSS headlines as policy/economic
release context.  No article bodies are republished.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "MarketResearchTerminal/1.0 (+https://github.com/galbbb2772/market-research-terminal)"
NOW = lambda: datetime.now(timezone.utc)
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
FED_RSS = "https://www.federalreserve.gov/feeds/press_all.xml"
BLS_RSS = "https://www.bls.gov/feed/bls_latest.rss"

TOPICS = {
    "geopolitical": ["war", "sanctions"],
    "systemic_risk": ["recession", "liquidity"],
    "fed_policy": ["Federal Reserve", "interest rates"],
    "ai_narrative": ["artificial intelligence", "AI investment"],
}


def request(url: str, *, timeout: int = 40, accept: str = "*/*") -> bytes:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def gdelt_one(query: str) -> tuple[list[dict[str, Any]], str]:
    errors = []
    for mode in ("timelinevolraw", "timelinevol"):
        params = urllib.parse.urlencode({
            "query": query,
            "mode": mode,
            "format": "json",
            "timespan": "3months",
            "maxrecords": "250",
        })
        url = GDELT + "?" + params
        try:
            obj = json.loads(request(url, accept="application/json").decode("utf-8-sig"))
            timeline = obj.get("timeline") or []
            if not timeline:
                errors.append(mode + ": empty timeline")
                continue
            data = timeline[0].get("data") or []
            rows = []
            for item in data:
                day = item.get("date")
                value = item.get("value")
                if day is None or not isinstance(value, (int, float)):
                    continue
                row = {"date": str(day), "value": float(value), "mode": mode}
                norm = item.get("norm")
                if isinstance(norm, (int, float)) and norm:
                    row["norm"] = float(norm)
                    if mode == "timelinevolraw":
                        row["share"] = float(value) / float(norm)
                rows.append(row)
            if rows:
                return rows, url
            errors.append(mode + ": no usable rows")
        except Exception as exc:
            errors.append(f"{mode}: {type(exc).__name__}: {str(exc)[:100]}")
    raise RuntimeError("; ".join(errors))


def fetch_gdelt() -> dict[str, Any]:
    series = {}
    failures = {}
    for topic, queries in TOPICS.items():
        got = None
        for q in queries:
            try:
                rows, url = gdelt_one(q)
                got = {"query": q, "source_url": url, "observations": rows}
                break
            except Exception as exc:
                failures.setdefault(topic, []).append(f"{q}: {type(exc).__name__}: {str(exc)[:180]}")
                time.sleep(0.4)
        if got:
            series[topic] = got
    return {
        "status": "ok" if series else "error",
        "provider": "GDELT Project DOC 2.0",
        "source_url": "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
        "window": "rolling 3 months",
        "series": series,
        "failures": failures,
        "note": "Aggregate coverage proxy only; not a validated sentiment or trading signal.",
    }


def text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def parse_feed(raw: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    out = []
    # RSS 2.0
    for item in root.findall(".//item"):
        title = text(item.find("title"))
        link = text(item.find("link"))
        date = text(item.find("pubDate")) or text(item.find("date"))
        if title:
            out.append({"title": title[:300], "url": link, "published": date})
    if out:
        return out[:100]
    # Atom fallback
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for item in root.findall(".//a:entry", ns):
        title = text(item.find("a:title", ns))
        link_node = item.find("a:link", ns)
        link = link_node.get("href") if link_node is not None else None
        date = text(item.find("a:updated", ns)) or text(item.find("a:published", ns))
        if title:
            out.append({"title": title[:300], "url": link, "published": date})
    return out[:100]


def fetch_feed(name: str, url: str) -> dict[str, Any]:
    try:
        rows = parse_feed(request(url, accept="application/rss+xml, application/xml, text/xml"))
        if not rows:
            raise ValueError("feed contained no parsable entries")
        return {"status": "ok", "provider": name, "source_url": url, "entries": rows}
    except Exception as exc:
        return {"status": "error", "provider": name, "source_url": url,
                "error": f"{type(exc).__name__}: {str(exc)[:240]}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/data/news_public.json")
    args = ap.parse_args()

    sources = {
        "gdelt": fetch_gdelt(),
        "federal_reserve_press": fetch_feed("Federal Reserve Board press releases", FED_RSS),
        "bls_latest": fetch_feed("U.S. Bureau of Labor Statistics", BLS_RSS),
    }
    ok_count = sum(1 for x in sources.values() if x.get("status") == "ok")
    payload = {
        "schema": "PUBLIC-NEWS-CONTEXT-V1",
        "generated_at": NOW().isoformat(),
        "source_count": len(sources),
        "ok_count": ok_count,
        "sources": sources,
        "notes": [
            "No API key is required.",
            "RSS output stores only headline, link and publication time; article bodies are not copied.",
            "GDELT values measure coverage volume/share, not market sentiment by themselves.",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if ok_count < 1:
        raise SystemExit("No public news source succeeded")
    print(f"Wrote {out}: {ok_count}/{len(sources)} news sources ok")


if __name__ == "__main__":
    main()
