#!/usr/bin/env python3
"""Summarize data availability for the static website."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FILES = {
    "macro_public": "docs/data/macro_public.json",
    "news_public": "docs/data/news_public.json",
    "market_history": "docs/data/market_history.json",
    "market_snapshot": "docs/data/market_snapshot.json",
    "structure_lab": "docs/data/structure_lab.json",
}


def inspect(path: str):
    p = Path(path)
    if not p.exists():
        return {"available": False, "path": path}
    info = {"available": True, "path": path, "bytes": p.stat().st_size}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("generated_at", "schema_version", "provider"):
                if key in data:
                    info[key] = data[key]
            if isinstance(data.get("source_status"), dict):
                statuses = data["source_status"].values()
                info["sources_ok"] = sum(1 for x in statuses if isinstance(x, dict) and x.get("ok"))
                info["sources_total"] = len(data["source_status"])
    except Exception as exc:
        info["parse_error"] = f"{type(exc).__name__}: {exc}"
    return info


def main():
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {name: inspect(path) for name, path in FILES.items()},
    }
    out = Path("docs/data/data_status.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
