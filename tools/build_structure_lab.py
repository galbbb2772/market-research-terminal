#!/usr/bin/env python3
"""Build STRUCTURE-LAB-V1 from already acquired MARKET-HISTORY-V1 data.

The builder never downloads observations. It derives descriptive 20-session (small)
and 60-session (large) anchored boxes, sector-ETF activity percentiles, and the short
archived news-tension alignment used by the static research website.

Box parameters are preregistered research heuristics, not optimized trading rules:
- small: 20 sessions, maximum width 14%
- large: 60 sessions, maximum width 28%
- at least two touches near each boundary
- boundary touch band = 12% of the candidate box height
- detection is online: a box is first known only at detected_at; bounds then remain fixed
- a box ends when a later daily close exits the fixed bounds

Closed-box scores are descriptive ex-post summaries. They are not point-in-time signals.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

PUBLISHABLE = 'verified_publishable'
SCALES = {
    'small': {'window': 20, 'max_width_pct': 14.0},
    'large': {'window': 60, 'max_width_pct': 28.0},
}
MIN_TOUCHES = 2
TOUCH_BAND_FRACTION = 0.12


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def canonical_meta(universe):
    out = {}
    for row in universe.get('benchmarks', []):
        if row.get('id'):
            out[row['id']] = {**row, 'group': 'benchmark'}
    for row in universe.get('major_indices', []):
        if row.get('id'):
            out[row['id']] = {**row, 'group': 'index'}
    for system_id, system in universe.get('sector_systems', {}).items():
        for row in system.get('items', []):
            if not row.get('id'):
                continue
            kind = str(row.get('kind', '')).upper()
            group = 'sector' if kind == 'ETF' else 'sector_index'
            out[row['id']] = {**row, 'group': group, 'sector_system': system_id,
                              'sector_system_label': system.get('label')}
    return out


def normalize_bars(raw, symbol):
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(f'{symbol}: missing real daily history')
    bars = []
    dates = []
    for row in raw:
        if not isinstance(row, list) or len(row) < 5:
            raise ValueError(f'{symbol}: malformed OHLC row')
        day = str(row[0])
        o, h, l, c = map(float, row[1:5])
        volume = row[5] if len(row) > 5 else None
        if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)):
            raise ValueError(f'{symbol}: invalid OHLC on {day}')
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f'{symbol}: inconsistent OHLC on {day}')
        if volume is not None:
            if not finite_number(volume) or float(volume) < 0:
                raise ValueError(f'{symbol}: invalid volume on {day}')
            volume = float(volume)
        bars.append([day, o, h, l, c, volume])
        dates.append(day)
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError(f'{symbol}: dates must be unique ascending')
    return bars


def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def candidate(window_bars, max_width_pct):
    upper = max(b[2] for b in window_bars)
    lower = min(b[3] for b in window_bars)
    if lower <= 0 or upper <= lower:
        return None
    width_pct = (upper / lower - 1.0) * 100.0
    if width_pct > max_width_pct:
        return None
    height = upper - lower
    band = height * TOUCH_BAND_FRACTION
    upper_touches = sum(1 for b in window_bars if b[2] >= upper - band)
    lower_touches = sum(1 for b in window_bars if b[3] <= lower + band)
    if upper_touches < MIN_TOUCHES or lower_touches < MIN_TOUCHES:
        return None
    return {
        'upper': upper,
        'lower': lower,
        'width_pct': width_pct,
        'upper_touches': upper_touches,
        'lower_touches': lower_touches,
    }


def scores_for_box(bars, start_idx, end_idx, detected_idx, upper, lower, width_pct,
                   max_width_pct, upper_touches, lower_touches):
    lifetime = bars[start_idx:end_idx + 1]
    tightness = 1.0 - clamp(width_pct / max_width_pct)
    touch_depth = clamp(min(upper_touches, lower_touches) / 4.0)
    formation = 10.0 * (0.65 * tightness + 0.35 * touch_depth)

    box_height = max(upper - lower, 1e-12)
    closes = [b[4] for b in lifetime]
    center_dispersion = statistics.pstdev(closes) / (box_height / 2.0) if len(closes) > 1 else 0.0
    excursion = sum(1 for b in lifetime if b[2] > upper or b[3] < lower) / max(1, len(lifetime))
    stability = 10.0 * (0.65 * (1.0 - clamp(center_dispersion)) + 0.35 * (1.0 - clamp(excursion)))

    span_ratio = statistics.fmean((b[2] - b[3]) / box_height for b in lifetime)
    moves = []
    for a, b in zip(closes, closes[1:]):
        delta = b - a
        moves.append(1 if delta > 0 else -1 if delta < 0 else 0)
    nonzero = [m for m in moves if m]
    flips = sum(a != b for a, b in zip(nonzero, nonzero[1:])) / max(1, len(nonzero) - 1) if len(nonzero) > 1 else 0.0
    difficulty = 10.0 * clamp(0.6 * clamp(span_ratio) + 0.4 * flips)

    composite = 0.45 * formation + 0.35 * stability + 0.20 * (10.0 - difficulty)
    return {
        'formation': round(clamp(formation / 10.0) * 10.0, 2),
        'stability': round(clamp(stability / 10.0) * 10.0, 2),
        'difficulty': round(clamp(difficulty / 10.0) * 10.0, 2),
        'composite': round(clamp(composite / 10.0) * 10.0, 2),
    }


def detect_scale(bars, scale, window, max_width_pct):
    boxes = []
    active = None
    serial = 0
    for idx in range(window - 1, len(bars)):
        close = bars[idx][4]
        if active is not None:
            if close < active['lower'] or close > active['upper']:
                end_idx = idx - 1
                serial += 1
                scores = scores_for_box(
                    bars, active['start_idx'], end_idx, active['detected_idx'],
                    active['upper'], active['lower'], active['width_pct'], max_width_pct,
                    active['upper_touches'], active['lower_touches'])
                boxes.append({
                    'id': f'{scale[0].upper()}{serial:03d}', 'scale': scale,
                    'start_at': bars[active['start_idx']][0],
                    'detected_at': bars[active['detected_idx']][0],
                    'end_at': bars[end_idx][0], 'breakout_at': bars[idx][0],
                    'days': end_idx - active['start_idx'] + 1,
                    'upper': round(active['upper'], 8), 'lower': round(active['lower'], 8),
                    'width_pct': round(active['width_pct'], 4),
                    'touches': {'upper': active['upper_touches'], 'lower': active['lower_touches']},
                    'scores': scores,
                })
                active = None
            else:
                continue
        c = candidate(bars[idx - window + 1:idx + 1], max_width_pct)
        if c is None:
            continue
        active = {'start_idx': idx - window + 1, 'detected_idx': idx, **c}
    if active is not None:
        serial += 1
        end_idx = len(bars) - 1
        scores = scores_for_box(
            bars, active['start_idx'], end_idx, active['detected_idx'],
            active['upper'], active['lower'], active['width_pct'], max_width_pct,
            active['upper_touches'], active['lower_touches'])
        boxes.append({
            'id': f'{scale[0].upper()}{serial:03d}', 'scale': scale,
            'start_at': bars[active['start_idx']][0], 'detected_at': bars[active['detected_idx']][0],
            'end_at': None, 'breakout_at': None, 'last_observed_at': bars[end_idx][0],
            'days': end_idx - active['start_idx'] + 1,
            'upper': round(active['upper'], 8), 'lower': round(active['lower'], 8),
            'width_pct': round(active['width_pct'], 4),
            'touches': {'upper': active['upper_touches'], 'lower': active['lower_touches']},
            'scores': scores,
        })
    return boxes


def detect_boxes(bars):
    out = []
    for scale, cfg in SCALES.items():
        out.extend(detect_scale(bars, scale, cfg['window'], cfg['max_width_pct']))
    out.sort(key=lambda b: (b['detected_at'], b['scale'], b['id']))
    return out


def percentile(value, prior):
    vals = [float(v) for v in prior if finite_number(v)]
    if not vals or not finite_number(value):
        return None
    return 100.0 * sum(v <= float(value) for v in vals) / len(vals)


def sector_activity(bars):
    history = []
    turnover = []
    ranges = []
    for i, b in enumerate(bars):
        c, h, l, volume = b[4], b[2], b[3], b[5]
        t = c * volume if volume is not None else None
        r = ((h - l) / c * 100.0) if c > 0 else None
        turnover.append(t)
        ranges.append(r)
        if i < 60 or t is None:
            continue
        tr = percentile(t, turnover[i - 60:i])
        rr = percentile(r, ranges[i - 60:i])
        if tr is None or rr is None:
            continue
        act = (tr + rr) / 2.0
        day_ret = (c / bars[i - 1][4] - 1.0) * 100.0 if i else None
        history.append([b[0], round(act, 4), round(tr, 4), round(rr, 4), round(day_ret, 4)])
    if not history:
        return None, []
    last = history[-1]
    return {
        'date': last[0], 'activity': last[1], 'turnover_rank': last[2],
        'range_rank': last[3], 'day_return_pct': last[4],
    }, history


def news_alignment(news, instruments):
    if not isinstance(news, dict):
        return []
    index_maps = {}
    for symbol in ('SP500', 'NASDAQ_COMPOSITE', 'DJIA'):
        bars = instruments.get(symbol, {}).get('bars', [])
        retmap = {}
        for a, b in zip(bars, bars[1:]):
            if a[4]:
                retmap[b[0]] = (b[4] / a[4] - 1.0) * 100.0
        index_maps[symbol] = retmap
    out = []
    for row in news.get('history', []):
        values = [float(v) for v in (row.get('reaction_adjusted') or {}).values() if finite_number(v)]
        if not values:
            continue
        day = row.get('date')
        out.append({
            'date': day,
            'tension': round(statistics.fmean(values), 4),
            'index_returns': {
                'sp500': index_maps['SP500'].get(day),
                'nasdaq': index_maps['NASDAQ_COMPOSITE'].get(day),
                'dow': index_maps['DJIA'].get(day),
            },
        })
    return out


def build(history, universe, news=None):
    if history.get('schema') != 'MARKET-HISTORY-V1':
        raise ValueError('history schema must be MARKET-HISTORY-V1')
    meta = canonical_meta(universe)
    raw_instruments = history.get('instruments') or {}
    if not raw_instruments:
        raise ValueError('history has no instruments')
    unknown = set(raw_instruments) - set(meta)
    if unknown:
        raise ValueError(f'non-canonical instruments: {sorted(unknown)}')
    instruments = {}
    for symbol, source in raw_instruments.items():
        bars = normalize_bars(source.get('bars'), symbol)
        info = meta[symbol]
        item = {
            'name': info.get('name') or info.get('sector') or symbol,
            'type': info.get('type') or info.get('kind'),
            'group': info.get('group'),
            'sector': info.get('sector'),
            'sector_system': info.get('sector_system'),
            'source_status': source.get('source_status') or source.get('provider') or history.get('provider'),
            'start': bars[0][0], 'end': bars[-1][0], 'bars': bars,
            'boxes': detect_boxes(bars),
        }
        if info.get('group') == 'sector':
            latest, series = sector_activity(bars)
            item['sector_activity'] = latest
            item['sector_history'] = series
        instruments[symbol] = item
    return {
        'schema': 'STRUCTURE-LAB-V1',
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'rights_status': history.get('rights_status', 'pending_review'),
        'provider': history.get('provider'),
        'parameters': {
            'small': SCALES['small'], 'large': SCALES['large'],
            'min_boundary_touches': MIN_TOUCHES,
            'touch_band_fraction_of_box_height': TOUCH_BAND_FRACTION,
            'break_rule': 'first later daily close outside fixed detected bounds',
            'score_status': 'descriptive_not_return_validated',
        },
        'instruments': instruments,
        'news_tension': news_alignment(news, instruments),
        'macro': {},
        'cycle_research': {'status': 'research_only'},
        'notes': [
            'detected_at is the first close when the rolling candidate met preregistered rules; no future end date is used for detection.',
            'Closed-box final scores are ex-post structural descriptions and must not be treated as point-in-time trading inputs.',
            'Sector activity is a turnover/range percentile proxy, not fund flow or social/news attention.',
            'Index volume remains null when the provider does not supply an economically meaningful volume series.',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, help='already acquired MARKET-HISTORY-V1 JSON')
    ap.add_argument('--universe', default='docs/data/market_universe.json')
    ap.add_argument('--news', default='docs/data/news_history.json')
    ap.add_argument('--output', default='/tmp/structure_lab.json')
    ap.add_argument('--publish', action='store_true')
    args = ap.parse_args(argv)
    history = load(args.input)
    universe = load(args.universe)
    news = load(args.news) if args.news and Path(args.news).exists() else None
    target = Path(args.output)
    public_tree = target.resolve().is_relative_to(Path('docs/data').resolve())
    if public_tree and not args.publish:
        ap.error('output inside docs/data requires --publish')
    if args.publish and not public_tree:
        ap.error('--publish must target docs/data')
    if args.publish and history.get('rights_status') != PUBLISHABLE:
        ap.error('refusing publish: market history is not verified_publishable')
    obj = build(history, universe, news)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    count = sum(len(x.get('boxes', [])) for x in obj['instruments'].values())
    print(f'wrote {target}: {len(obj["instruments"])} instruments, {count} boxes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
