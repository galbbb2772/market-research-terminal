#!/usr/bin/env python3
"""Enrich STRUCTURE-LAB-V1 with descriptive cycle/rotation research.

This module never downloads or invents observations. It uses only already validated
structure_lab.json contents. Outputs are descriptive statistics, not forecasts:
- weekly sector-ETF relative returns versus SPY and 1-26 week autocorrelation
- 4-week relative-to-SPY leadership history and leadership tenure/switch counts
- daily sector activity leadership and 1/5/20-session cross-sectional rank persistence
- completed small/large box duration distributions
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path

MIN_CORR_PAIRS = 20
MAX_LAG_WEEKS = 26
LEADERSHIP_LOOKBACK_WEEKS = 4
ACTIVITY_RANK_LAGS = (1, 5, 20)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def monday_key(day):
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def weekly_close(bars):
    out = {}
    for row in bars or []:
        if not isinstance(row, list) or len(row) < 5:
            continue
        day, close = str(row[0]), row[4]
        if not finite(close):
            continue
        key = monday_key(day)
        out[key] = {'date': day, 'close': float(close)}
    return out


def adjacent_weeks(keys):
    for a, b in zip(keys, keys[1:]):
        if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days == 7:
            yield a, b


def relative_weekly_returns(sector_bars, spy_bars):
    s = weekly_close(sector_bars)
    p = weekly_close(spy_bars)
    keys = sorted(set(s) & set(p))
    out = []
    for a, b in adjacent_weeks(keys):
        sa, sb, pa, pb = s[a]['close'], s[b]['close'], p[a]['close'], p[b]['close']
        if sa <= 0 or pa <= 0:
            continue
        rel = ((sb / sa - 1.0) - (pb / pa - 1.0)) * 100.0
        out.append([b, round(rel, 6)])
    return out


def pearson(a, b):
    if len(a) != len(b) or len(a) < 2:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    va = sum(x * x for x in da)
    vb = sum(x * x for x in db)
    if va <= 0 or vb <= 0:
        return None
    return sum(x * y for x, y in zip(da, db)) / math.sqrt(va * vb)


def autocorrelation_rows(series, max_lag=MAX_LAG_WEEKS):
    vals = [float(x[1]) for x in series]
    rows = []
    for lag in range(1, max_lag + 1):
        pairs = len(vals) - lag
        corr = pearson(vals[:-lag], vals[lag:]) if pairs >= MIN_CORR_PAIRS else None
        rows.append({
            'lag_weeks': lag,
            'correlation': round(corr, 6) if corr is not None else None,
            'pairs': max(0, pairs),
        })
    return rows


def sector_cycle(item, spy_bars):
    series = relative_weekly_returns(item.get('bars', []), spy_bars)
    if not series:
        return None
    return {
        'weeks': len(series),
        'start': series[0][0],
        'end': series[-1][0],
        'status': 'descriptive_relative_to_spy',
        'relative_weekly_returns': series,
        'lags': autocorrelation_rows(series),
    }


def four_week_relative_map(bars, spy_bars):
    s = weekly_close(bars)
    p = weekly_close(spy_bars)
    keys = sorted(set(s) & set(p))
    out = {}
    for key in keys:
        d = dt.date.fromisoformat(key)
        prev = (d - dt.timedelta(days=7 * LEADERSHIP_LOOKBACK_WEEKS)).isoformat()
        if prev not in s or prev not in p:
            continue
        sc, sp = s[key]['close'], s[prev]['close']
        pc, pp = p[key]['close'], p[prev]['close']
        if sp <= 0 or pp <= 0:
            continue
        out[key] = ((sc / sp - 1.0) - (pc / pp - 1.0)) * 100.0
    return out


def leadership_research(instruments, spy_bars):
    sector_maps = {}
    for symbol, item in instruments.items():
        if item.get('group') != 'sector':
            continue
        m = four_week_relative_map(item.get('bars', []), spy_bars)
        if m:
            sector_maps[symbol] = m
    if not sector_maps:
        return {'status': 'insufficient_sector_history', 'history': []}
    total = len(sector_maps)
    required = max(3, math.ceil(total * 0.7))
    all_weeks = sorted(set().union(*(set(m) for m in sector_maps.values())))
    history = []
    for week in all_weeks:
        values = [(symbol, m[week]) for symbol, m in sector_maps.items() if week in m]
        if len(values) < required:
            continue
        values.sort(key=lambda x: x[1], reverse=True)
        leader, rel = values[0]
        history.append({'week': week, 'leader': leader, 'relative_4w_pct': round(rel, 4), 'coverage': len(values)})
    if not history:
        return {'status': 'insufficient_cross_section', 'history': []}
    episodes = []
    cur = history[0]['leader']
    length = 1
    for prev, row in zip(history, history[1:]):
        consecutive = (dt.date.fromisoformat(row['week']) - dt.date.fromisoformat(prev['week'])).days == 7
        if consecutive and row['leader'] == cur:
            length += 1
        else:
            episodes.append({'leader': cur, 'weeks': length})
            cur, length = row['leader'], 1
    episodes.append({'leader': cur, 'weeks': length})
    switches = sum(a['leader'] != b['leader'] for a, b in zip(history, history[1:]))
    counts = {}
    for row in history:
        counts[row['leader']] = counts.get(row['leader'], 0) + 1
    return {
        'status': 'descriptive_4w_relative_to_spy',
        'lookback_weeks': LEADERSHIP_LOOKBACK_WEEKS,
        'sector_count': total,
        'required_weekly_coverage': required,
        'observations': len(history),
        'switch_count': switches,
        'switch_rate_pct': round(100.0 * switches / max(1, len(history) - 1), 2),
        'median_tenure_weeks': round(statistics.median([e['weeks'] for e in episodes]), 2),
        'latest': history[-1],
        'leader_counts': counts,
        'episodes': episodes,
        'history': history,
    }


def average_ranks(values):
    pairs = sorted(values.items(), key=lambda x: x[1])
    out = {}
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][1] == pairs[i][1]:
            j += 1
        rank = ((i + 1) + j) / 2.0
        for k in range(i, j):
            out[pairs[k][0]] = rank
        i = j
    return out


def activity_maps(instruments):
    maps = {}
    for symbol, item in instruments.items():
        if item.get('group') != 'sector':
            continue
        m = {}
        for row in item.get('sector_history') or []:
            if isinstance(row, list) and len(row) >= 2 and finite(row[1]):
                m[str(row[0])] = float(row[1])
        if m:
            maps[symbol] = m
    return maps


def activity_rotation(instruments):
    maps = activity_maps(instruments)
    if not maps:
        return {'status': 'insufficient_activity_history', 'history': [], 'rank_persistence': []}
    total = len(maps)
    required = max(3, math.ceil(total * 0.7))
    dates = sorted(set().union(*(set(m) for m in maps.values())))
    snapshots = []
    history = []
    for day in dates:
        values = {symbol: m[day] for symbol, m in maps.items() if day in m}
        if len(values) < required:
            continue
        ranked = sorted(values.items(), key=lambda x: x[1], reverse=True)
        arr = list(values.values())
        snapshots.append((day, values))
        history.append({
            'date': day,
            'leader': ranked[0][0],
            'leader_activity': round(ranked[0][1], 4),
            'top3': [{'symbol': s, 'activity': round(v, 4)} for s, v in ranked[:3]],
            'coverage': len(values),
            'mean_activity': round(statistics.fmean(arr), 4),
            'dispersion': round(statistics.pstdev(arr), 4) if len(arr) > 1 else 0.0,
        })
    if not history:
        return {'status': 'insufficient_cross_section', 'history': [], 'rank_persistence': []}
    episodes = []
    cur = history[0]['leader']
    length = 1
    for row in history[1:]:
        if row['leader'] == cur:
            length += 1
        else:
            episodes.append({'leader': cur, 'sessions': length})
            cur, length = row['leader'], 1
    episodes.append({'leader': cur, 'sessions': length})
    switches = sum(a['leader'] != b['leader'] for a, b in zip(history, history[1:]))
    persistence = []
    for lag in ACTIVITY_RANK_LAGS:
        corrs = []
        for i in range(lag, len(snapshots)):
            prev = snapshots[i - lag][1]
            curmap = snapshots[i][1]
            common = sorted(set(prev) & set(curmap))
            if len(common) < required:
                continue
            r0 = average_ranks({k: prev[k] for k in common})
            r1 = average_ranks({k: curmap[k] for k in common})
            corr = pearson([r0[k] for k in common], [r1[k] for k in common])
            if corr is not None:
                corrs.append(corr)
        persistence.append({
            'lag_sessions': lag,
            'mean_spearman': round(statistics.fmean(corrs), 6) if corrs else None,
            'median_spearman': round(statistics.median(corrs), 6) if corrs else None,
            'pairs': len(corrs),
        })
    counts = {}
    for row in history:
        counts[row['leader']] = counts.get(row['leader'], 0) + 1
    return {
        'status': 'descriptive_volume_range_activity_rotation',
        'sector_count': total,
        'required_daily_coverage': required,
        'observations': len(history),
        'switch_count': switches,
        'switch_rate_pct': round(100.0 * switches / max(1, len(history) - 1), 2),
        'median_tenure_sessions': round(statistics.median([e['sessions'] for e in episodes]), 2),
        'latest': history[-1],
        'leader_counts': counts,
        'rank_persistence': persistence,
        'episodes': episodes,
        'history': history,
    }


def percentile_nearest(values, p):
    if not values:
        return None
    arr = sorted(values)
    idx = round((len(arr) - 1) * p)
    return arr[max(0, min(len(arr) - 1, idx))]


def box_duration_stats(instruments):
    out = {}
    for scale in ('small', 'large'):
        vals = []
        for item in instruments.values():
            for box in item.get('boxes') or []:
                if box.get('scale') == scale and box.get('end_at') and finite(box.get('days')):
                    vals.append(int(box['days']))
        out[scale] = {
            'completed_n': len(vals),
            'median_sessions': round(statistics.median(vals), 2) if vals else None,
            'mean_sessions': round(statistics.fmean(vals), 2) if vals else None,
            'p25_sessions': percentile_nearest(vals, 0.25),
            'p75_sessions': percentile_nearest(vals, 0.75),
            'p90_sessions': percentile_nearest(vals, 0.90),
            'min_sessions': min(vals) if vals else None,
            'max_sessions': max(vals) if vals else None,
        }
    return out


def enrich(structure):
    if structure.get('schema') != 'STRUCTURE-LAB-V1':
        raise ValueError('Expected STRUCTURE-LAB-V1')
    instruments = structure.get('instruments') or {}
    spy = instruments.get('SPY', {}).get('bars', [])
    sectors = {}
    if spy:
        for symbol, item in instruments.items():
            if item.get('group') != 'sector':
                continue
            result = sector_cycle(item, spy)
            if result:
                sectors[symbol] = result
    news_n = len(structure.get('news_tension') or [])
    structure['cycle_research'] = {
        'status': 'research_only',
        'method': 'descriptive_weekly_relative_returns_and_activity_rotation_no_forecast',
        'autocorrelation_lags_weeks': [1, MAX_LAG_WEEKS],
        'minimum_pairs_per_correlation': MIN_CORR_PAIRS,
        'sectors': sectors,
        'leadership': leadership_research(instruments, spy) if spy else {'status': 'SPY_missing', 'history': []},
        'activity_rotation': activity_rotation(instruments),
        'boxes': box_duration_stats(instruments),
        'news_status': f'real_archive_{news_n}_days' if news_n else 'unavailable',
        'notes': [
            'Autocorrelation is calculated on weekly sector ETF return minus SPY weekly return.',
            'A correlation peak is descriptive and must not be labelled a confirmed market cycle without separate statistical validation.',
            'Return leadership uses rolling 4-week relative-to-SPY performance and records historical cross-sectional leaders only.',
            'Activity rotation uses the existing turnover/range percentile activity proxy; it is not fund flow, news attention, or social attention.',
            'Activity rank persistence is the average/median cross-sectional Spearman correlation at 1/5/20-session lags.',
            'Box duration uses completed boxes only and is affected by right censoring and detector parameters.',
        ],
    }
    return structure


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--output')
    args = ap.parse_args(argv)
    obj = enrich(load(args.input))
    target = Path(args.output or args.input)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'wrote cycle research to {target}; sectors={len(obj["cycle_research"]["sectors"])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
