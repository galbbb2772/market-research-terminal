#!/usr/bin/env python3
"""Build the public structure lab with the same Range Template V2 used by Stock Terminal.

This is the canonical public range detector. It deliberately rejects short pauses in
trends, requires separated visits to both boundaries, waits for multiple closes to
confirm a breakout, merges nearby highly-overlapping ranges, and prunes redundant
small ranges buried in the middle of a larger structure.

The output remains descriptive research data. Scores are not trading signals.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import tools.build_structure_lab as base

PUBLISHABLE = base.PUBLISHABLE
CFG: dict[str, dict[str, float | int]] = {
    "small": {
        "window": 45,
        "min_days": 30,
        "max_width_pct": 18.0,
        "band": 0.09,
        "min_gap": 5,
        "min_visits": 2,
        "min_switches": 2,
        "max_eff": 0.46,
        "max_slope": 0.68,
        "break_confirm": 3,
        "cooldown": 15,
        "merge_gap": 20,
    },
    "large": {
        "window": 120,
        "min_days": 80,
        "max_width_pct": 45.0,
        "band": 0.08,
        "min_gap": 10,
        "min_visits": 2,
        "min_switches": 1,
        "max_eff": 0.76,
        "max_slope": 1.35,
        "break_confirm": 4,
        "cooldown": 30,
        "merge_gap": 45,
    },
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def quantile(values: list[float], q: float) -> float | None:
    xs = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not xs:
        return None
    p = (len(xs) - 1) * q
    i = math.floor(p)
    f = p - i
    j = min(i + 1, len(xs) - 1)
    return xs[i] + (xs[j] - xs[i]) * f


def visit_events(
    bars: list[list[Any]], side: str, level: float, band: float, min_gap: int
) -> list[int]:
    out: list[int] = []
    armed = True
    last = -10**9
    for i, b in enumerate(bars):
        high, low = float(b[2]), float(b[3])
        hit = high >= level - band if side == "upper" else low <= level + band
        away = low < level - 2 * band if side == "upper" else high > level + 2 * band
        if hit and armed and i - last >= min_gap:
            out.append(i)
            last = i
            armed = False
        if not hit and away:
            armed = True
    return out


def visit_stats(
    bars: list[list[Any]], upper: float, lower: float, cfg: dict[str, float | int]
) -> dict[str, Any]:
    height = max(upper - lower, 1e-9)
    band = height * float(cfg["band"])
    min_gap = int(cfg["min_gap"])
    upper_hits = visit_events(bars, "upper", upper, band, min_gap)
    lower_hits = visit_events(bars, "lower", lower, band, min_gap)
    seq = sorted(
        ([{"i": i, "s": "U"} for i in upper_hits] + [{"i": i, "s": "L"} for i in lower_hits]),
        key=lambda x: x["i"],
    )
    compressed: list[dict[str, Any]] = []
    for event in seq:
        previous = compressed[-1] if compressed else None
        if previous is None or previous["s"] != event["s"]:
            compressed.append(event)
        elif event["i"] - previous["i"] >= min_gap * 2:
            compressed.append(event)
    switches = sum(
        compressed[i]["s"] != compressed[i - 1]["s"]
        for i in range(1, len(compressed))
    )
    first = seq[0]["i"] if seq else None
    last = seq[-1]["i"] if seq else None
    span = 0 if first is None or last is None else last - first
    return {
        "upper": upper_hits,
        "lower": lower_hits,
        "sequence": seq,
        "compressed": compressed,
        "switches": switches,
        "span": span,
    }


def trend_stats(bars: list[list[Any]], upper: float, lower: float) -> dict[str, float]:
    closes = [float(b[4]) for b in bars]
    path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    efficiency = abs(closes[-1] - closes[0]) / path if path else 1.0
    n = len(closes)
    mx = (n - 1) / 2.0
    my = mean(closes)
    numerator = sum((i - mx) * (v - my) for i, v in enumerate(closes))
    denominator = sum((i - mx) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0.0
    height = max(upper - lower, 1e-9)
    slope_ratio = abs(slope) * (n - 1) / height
    return {"efficiency": efficiency, "slope_ratio": slope_ratio}


def candidate(bars: list[list[Any]], cfg: dict[str, float | int]) -> dict[str, Any] | None:
    if len(bars) < int(cfg["window"]):
        return None
    upper = quantile([float(b[2]) for b in bars], 0.90)
    lower = quantile([float(b[3]) for b in bars], 0.10)
    if upper is None or lower is None or not (lower > 0 and upper > lower):
        return None
    width = (upper / lower - 1.0) * 100.0
    if width > float(cfg["max_width_pct"]):
        return None
    visits = visit_stats(bars, upper, lower, cfg)
    trend = trend_stats(bars, upper, lower)
    need_span = max(math.floor(float(cfg["min_days"]) * 0.55), int(cfg["min_gap"]) * 3)
    if len(visits["upper"]) < int(cfg["min_visits"]):
        return None
    if len(visits["lower"]) < int(cfg["min_visits"]):
        return None
    if int(visits["switches"]) < int(cfg["min_switches"]):
        return None
    if int(visits["span"]) < need_span:
        return None
    if trend["efficiency"] > float(cfg["max_eff"]):
        return None
    if trend["slope_ratio"] > float(cfg["max_slope"]):
        return None
    return {"upper": upper, "lower": lower, "width": width, "visits": visits, "trend": trend}


def box_score(
    life: list[list[Any]], upper: float, lower: float,
    cfg: dict[str, float | int], visits: dict[str, Any], trend: dict[str, float]
) -> dict[str, float]:
    width = (upper / lower - 1.0) * 100.0
    tight = 1.0 - clamp(width / float(cfg["max_width_pct"]))
    visit = clamp(min(len(visits["upper"]), len(visits["lower"])) / 3.0)
    span = clamp(int(visits["span"]) / max(1, int(cfg["window"]) - 1))
    formation = 10.0 * (0.35 * tight + 0.35 * visit + 0.30 * span)

    height = max(upper - lower, 1e-9)
    inside = sum(
        lower - height * 0.04 <= float(b[4]) <= upper + height * 0.04 for b in life
    ) / max(1, len(life))
    stability = 10.0 * (
        0.50 * inside
        + 0.25 * (1.0 - clamp(trend["efficiency"] / float(cfg["max_eff"])))
        + 0.25 * (1.0 - clamp(trend["slope_ratio"] / float(cfg["max_slope"])))
    )
    daily = mean([(float(b[2]) - float(b[3])) / height for b in life])
    difficulty = 10.0 * clamp(0.55 * daily + 0.45 * trend["efficiency"])
    composite = 0.45 * formation + 0.35 * stability + 0.20 * (10.0 - difficulty)
    return {
        "formation": round(formation, 2),
        "stability": round(stability, 2),
        "difficulty": round(difficulty, 2),
        "composite": round(composite, 2),
    }


def finalize_box(
    bars: list[list[Any]], scale: str, cfg: dict[str, float | int], active: dict[str, Any],
    end_idx: int, break_idx: int | None
) -> dict[str, Any]:
    life = bars[active["start_idx"]: end_idx + 1]
    visits = visit_stats(life, active["upper"], active["lower"], cfg)
    trend = trend_stats(life, active["upper"], active["lower"])
    scores = box_score(life, active["upper"], active["lower"], cfg, visits, trend)
    box: dict[str, Any] = {
        "scale": scale,
        "start_at": bars[active["start_idx"]][0],
        "detected_at": bars[active["detected_idx"]][0],
        "end_at": bars[end_idx][0] if break_idx is not None else None,
        "breakout_at": bars[break_idx][0] if break_idx is not None else None,
        "last_observed_at": bars[end_idx][0] if break_idx is None else None,
        "days": end_idx - active["start_idx"] + 1,
        "upper": round(float(active["upper"]), 8),
        "lower": round(float(active["lower"]), 8),
        "width_pct": round((float(active["upper"]) / float(active["lower"]) - 1.0) * 100.0, 4),
        "touches": {
            "upper": len(visits["upper"]),
            "lower": len(visits["lower"]),
            "switches": int(visits["switches"]),
            "span": int(visits["span"]),
        },
        "trend": {
            "efficiency": round(trend["efficiency"], 8),
            "slope_ratio": round(trend["slope_ratio"], 8),
        },
        "scores": scores,
        "_start_idx": int(active["start_idx"]),
        "_end_idx": int(end_idx),
    }
    return box


def price_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    inter = max(0.0, min(float(a["upper"]), float(b["upper"])) - max(float(a["lower"]), float(b["lower"])))
    den = max(1e-9, min(float(a["upper"]) - float(a["lower"]), float(b["upper"]) - float(b["lower"])))
    return inter / den


def merge_similar(
    boxes: list[dict[str, Any]], bars: list[list[Any]], cfg: dict[str, float | int]
) -> list[dict[str, Any]]:
    if len(boxes) < 2:
        return boxes
    out: list[dict[str, Any]] = []
    for box in boxes:
        previous = out[-1] if out else None
        if previous is None:
            out.append(box)
            continue
        gap = int(box["_start_idx"]) - int(previous["_end_idx"]) - 1
        overlap = price_overlap(previous, box)
        if gap <= int(cfg["merge_gap"]) and overlap >= 0.72:
            start_idx = min(int(previous["_start_idx"]), int(box["_start_idx"]))
            end_idx = max(int(previous["_end_idx"]), int(box["_end_idx"]))
            total_days = max(1, int(previous["days"]) + int(box["days"]))
            weight = int(previous["days"]) / total_days
            upper = float(previous["upper"]) * weight + float(box["upper"]) * (1.0 - weight)
            lower = float(previous["lower"]) * weight + float(box["lower"]) * (1.0 - weight)
            width = (upper / lower - 1.0) * 100.0
            if width <= float(cfg["max_width_pct"]) * 1.12:
                active = {
                    "start_idx": start_idx,
                    "detected_idx": max(int(previous["_start_idx"]), int(box["_start_idx"])),
                    "upper": upper,
                    "lower": lower,
                }
                break_idx = None if box.get("end_at") is None else min(len(bars) - 1, int(box["_end_idx"]) + 1)
                merged = finalize_box(bars, str(previous["scale"]), cfg, active, end_idx, break_idx)
                if box.get("end_at") is None:
                    merged["end_at"] = None
                    merged["breakout_at"] = None
                    merged["last_observed_at"] = bars[end_idx][0]
                out[-1] = merged
                continue
        out.append(box)
    return out


def detect_scale(bars: list[list[Any]], scale: str, cfg: dict[str, float | int]) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    last_break = -10**9
    window = int(cfg["window"])
    for idx in range(window - 1, len(bars)):
        if active is not None:
            height = float(active["upper"]) - float(active["lower"])
            tolerance = height * 0.04
            close = float(bars[idx][4])
            direction = 1 if close > float(active["upper"]) + tolerance else -1 if close < float(active["lower"]) - tolerance else 0
            if direction and (not active.get("break_dir") or active.get("break_dir") == direction):
                active["break_dir"] = direction
                active["outside"] = int(active.get("outside", 0)) + 1
            elif direction:
                active["break_dir"] = direction
                active["outside"] = 1
            else:
                active["break_dir"] = 0
                active["outside"] = 0
            if int(active.get("outside", 0)) >= int(cfg["break_confirm"]):
                end_idx = max(int(active["start_idx"]), idx - int(cfg["break_confirm"]))
                boxes.append(finalize_box(bars, scale, cfg, active, end_idx, idx))
                active = None
                last_break = idx
            else:
                continue
        if idx - last_break < int(cfg["cooldown"]):
            continue
        start_idx = idx - window + 1
        cand = candidate(bars[start_idx: idx + 1], cfg)
        if cand is not None:
            active = {
                "start_idx": start_idx,
                "detected_idx": idx,
                "upper": cand["upper"],
                "lower": cand["lower"],
                "outside": 0,
                "break_dir": 0,
            }
    if active is not None:
        boxes.append(finalize_box(bars, scale, cfg, active, len(bars) - 1, None))
    return merge_similar(boxes, bars, cfg)


def time_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    start = max(int(a["_start_idx"]), int(b["_start_idx"]))
    end = min(int(a["_end_idx"]), int(b["_end_idx"]))
    return max(0, end - start + 1) / max(1, int(a["_end_idx"]) - int(a["_start_idx"]) + 1)


def prune_nested(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    large = [b for b in boxes if b["scale"] == "large"]
    out: list[dict[str, Any]] = []
    for box in boxes:
        if box["scale"] == "large":
            out.append(box)
            continue
        parent = next((
            big for big in large
            if time_overlap(box, big) >= 0.60
            and float(box["lower"]) >= float(big["lower"]) - (float(big["upper"]) - float(big["lower"])) * 0.04
            and float(box["upper"]) <= float(big["upper"]) + (float(big["upper"]) - float(big["lower"])) * 0.04
        ), None)
        if parent is None:
            out.append(box)
            continue
        position = ((float(box["lower"]) + float(box["upper"])) / 2.0 - float(parent["lower"])) / max(1e-9, float(parent["upper"]) - float(parent["lower"]))
        if position <= 0.32 or position >= 0.68 or box.get("end_at") is None:
            out.append(box)
    return out


def detect_boxes(bars: list[list[Any]]) -> list[dict[str, Any]]:
    all_boxes: list[dict[str, Any]] = []
    for scale, cfg in CFG.items():
        all_boxes.extend(detect_scale(bars, scale, cfg))
    all_boxes = prune_nested(all_boxes)
    all_boxes = [b for b in all_boxes if b.get("end_at") is None or float(b.get("scores", {}).get("composite", 0)) >= 5.0]
    all_boxes.sort(key=lambda b: (int(b["_start_idx"]), str(b["scale"])))
    serial = {"small": 0, "large": 0}
    clean: list[dict[str, Any]] = []
    for box in all_boxes:
        scale = str(box["scale"])
        serial[scale] += 1
        box = dict(box)
        box["id"] = f"{'L' if scale == 'large' else 'S'}{serial[scale]:03d}"
        for key in list(box):
            if key.startswith("_"):
                box.pop(key, None)
        clean.append(box)
    return clean


def build(history: dict[str, Any], universe: dict[str, Any], news: dict[str, Any] | None = None) -> dict[str, Any]:
    original = base.detect_boxes
    try:
        base.detect_boxes = detect_boxes
        obj = base.build(history, universe, news)
    finally:
        base.detect_boxes = original
    obj["parameters"] = {
        "template": "RANGE-TEMPLATE-V2",
        "small": CFG["small"],
        "large": CFG["large"],
        "boundary_model": "90th percentile high / 10th percentile low",
        "boundary_confirmation": "separated repeated visits to both sides plus side switches",
        "trend_filter": "path efficiency and normalized regression slope",
        "break_rule": "3 small / 4 large consecutive closes outside bounds plus 4% of box-height tolerance",
        "merge_rule": "merge nearby ranges when price overlap >=72% and merged width stays within tolerance",
        "nested_rule": "prune ended small ranges buried in the middle 36% of a qualifying large range",
        "score_status": "descriptive_not_return_validated",
    }
    obj["notes"] = [
        "Range Template V2 is shared with the personal Stock Terminal.",
        "Short trend pauses are rejected by duration, separated-boundary, side-switch and trend-efficiency filters.",
        "A breakout is not accepted on one stray close; consecutive closes are required before a range ends.",
        "Nearby highly-overlapping ranges are merged and redundant nested middle ranges are pruned to reduce chart clutter.",
        "Closed-range final scores are ex-post structural descriptions and must not be treated as point-in-time trading inputs.",
        "Sector activity is a turnover/range percentile proxy, not fund flow or social/news attention.",
        "Index volume remains null when the provider does not supply an economically meaningful volume series.",
    ]
    return obj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="already acquired MARKET-HISTORY-V1 JSON")
    ap.add_argument("--universe", default="docs/data/market_universe.json")
    ap.add_argument("--news", default="docs/data/news_history.json")
    ap.add_argument("--output", default="/tmp/structure_lab.json")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args(argv)
    history = base.load(args.input)
    universe = base.load(args.universe)
    news = base.load(args.news) if args.news and Path(args.news).exists() else None
    target = Path(args.output)
    public_tree = target.resolve().is_relative_to(Path("docs/data").resolve())
    if public_tree and not args.publish:
        ap.error("output inside docs/data requires --publish")
    if args.publish and not public_tree:
        ap.error("--publish must target docs/data")
    if args.publish and history.get("rights_status") != PUBLISHABLE:
        ap.error("refusing publish: market history is not verified_publishable")
    obj = build(history, universe, news)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    count = sum(len(x.get("boxes", [])) for x in obj["instruments"].values())
    print(f"wrote {target}: {len(obj['instruments'])} instruments, {count} V2 ranges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
