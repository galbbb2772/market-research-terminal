#!/usr/bin/env python3
"""Add conservative validation layers to cycle_research in STRUCTURE-LAB-V1.

The validator uses only already-derived market/sector observations. It never downloads
or invents data and does not forecast prices.

Return-cycle validation, for each sector ETF and lag 1..26 weeks:
- chronological three-way split correlations
- 4-week block-permutation two-sided p-values
- 4-week circular moving-block bootstrap 95% intervals
- Benjamini-Hochberg FDR within sector and globally across sector/lag hypotheses

Activity-rank validation, for 1/5/20-session rank persistence:
- reconstruct daily full sector-activity cross sections from sector_history
- compute daily cross-sectional Spearman correlations at each lag
- chronological three-way split mean Spearman stability
- 5-session block-permutation two-sided p-values that break date alignment while
  preserving short-run blocks and the marginal sector activity/rank structure
- 5-session moving-block bootstrap 95% intervals for the mean Spearman
- BH FDR across the 1/5/20-session activity family
- a combined research-wide BH FDR across return-cycle and activity hypotheses

Passing these checks means only that a historical dependence candidate survived the
current procedure; it is not a trading signal or evidence of future profitability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

MAX_LAG_WEEKS = 26
BLOCK_WEEKS = 4
ACTIVITY_LAGS = (1, 5, 20)
ACTIVITY_BLOCK_SESSIONS = 5
RESAMPLES = 200
FDR_ALPHA = 0.10
TIME_SPLITS = 3
MIN_PAIRS = 20
MIN_SPLIT_PAIRS = 12
MIN_ACTIVITY_PAIRS = 30
MIN_ACTIVITY_SPLIT_PAIRS = 10


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def corr_at(values, lag, min_pairs=MIN_PAIRS):
    n = len(values) - lag
    if n < min_pairs:
        return None
    x = values[:n]
    y = values[lag:]
    sx, sy = sum(x), sum(y)
    sxx = sum(v * v for v in x)
    syy = sum(v * v for v in y)
    sxy = sum(a * b for a, b in zip(x, y))
    num = sxy - sx * sy / n
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n
    if vx <= 0 or vy <= 0:
        return None
    return num / math.sqrt(vx * vy)


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


def all_corr(values, min_pairs=MIN_PAIRS):
    return [corr_at(values, lag, min_pairs) for lag in range(1, MAX_LAG_WEEKS + 1)]


def block_shuffle(values, rng, block):
    blocks = [values[i:i + block] for i in range(0, len(values), block)]
    rng.shuffle(blocks)
    return [v for part in blocks for v in part]


def moving_block_bootstrap(values, rng, block):
    n = len(values)
    if not n:
        return []
    out = []
    while len(out) < n:
        start = rng.randrange(n)
        out.extend(values[(start + j) % n] for j in range(block))
    return out[:n]


def quantile(values, p):
    if not values:
        return None
    arr = sorted(values)
    pos = (len(arr) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return arr[lo]
    w = pos - lo
    return arr[lo] * (1.0 - w) + arr[hi] * w


def stable_seed(symbol):
    return int.from_bytes(hashlib.sha256(symbol.encode('utf-8')).digest()[:8], 'big')


def time_split_corr(values, lag):
    n = len(values)
    cuts = [round(n * i / TIME_SPLITS) for i in range(TIME_SPLITS + 1)]
    out = []
    for i in range(TIME_SPLITS):
        part = values[cuts[i]:cuts[i + 1]]
        out.append(corr_at(part, lag, MIN_SPLIT_PAIRS))
    return out


def bh_qvalues(pairs):
    """Return {key:q} using Benjamini-Hochberg with monotone adjusted q-values."""
    valid = [(key, float(p)) for key, p in pairs if p is not None]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    out = {}
    running = 1.0
    for rank in range(m, 0, -1):
        key, p = valid[rank - 1]
        running = min(running, p * m / rank)
        out[key] = min(1.0, running)
    return out


def sign_consistency(observed, split_values):
    valid = [v for v in split_values if v is not None and v != 0]
    if observed is None or not valid:
        return None
    same = sum((v > 0) == (observed > 0) for v in valid)
    return same / len(valid)


def validate_sector(symbol, sector, resamples=RESAMPLES):
    series = sector.get('relative_weekly_returns') or []
    values = [float(row[1]) for row in series if isinstance(row, list) and len(row) >= 2]
    observed = all_corr(values)
    rng = random.Random(stable_seed('return:' + symbol))
    nulls = [[] for _ in range(MAX_LAG_WEEKS)]
    boots = [[] for _ in range(MAX_LAG_WEEKS)]
    if len(values) >= MIN_PAIRS + 1:
        for _ in range(resamples):
            shuffled = all_corr(block_shuffle(values, rng, BLOCK_WEEKS))
            booted = all_corr(moving_block_bootstrap(values, rng, BLOCK_WEEKS))
            for i, value in enumerate(shuffled):
                if value is not None:
                    nulls[i].append(value)
            for i, value in enumerate(booted):
                if value is not None:
                    boots[i].append(value)
    rows = []
    p_pairs = []
    for i, obs in enumerate(observed):
        lag = i + 1
        splits = time_split_corr(values, lag) if obs is not None else [None] * TIME_SPLITS
        consistency = sign_consistency(obs, splits)
        null = nulls[i]
        if obs is not None and null:
            extreme = sum(abs(v) >= abs(obs) for v in null)
            p = (extreme + 1.0) / (len(null) + 1.0)
        else:
            p = None
        boot = boots[i]
        lo = quantile(boot, 0.025)
        hi = quantile(boot, 0.975)
        row = {
            'lag_weeks': lag,
            'observed_correlation': round(obs, 6) if obs is not None else None,
            'pairs': max(0, len(values) - lag),
            'split_correlations': [round(v, 6) if v is not None else None for v in splits],
            'split_sign_consistency': round(consistency, 4) if consistency is not None else None,
            'block_permutation_p': round(p, 6) if p is not None else None,
            'bootstrap_ci95': [round(lo, 6), round(hi, 6)] if lo is not None and hi is not None else [None, None],
        }
        rows.append(row)
        p_pairs.append((lag, p))
    q_sector = bh_qvalues(p_pairs)
    for row in rows:
        row['q_sector'] = round(q_sector[row['lag_weeks']], 6) if row['lag_weeks'] in q_sector else None
    return {'weeks': len(values), 'resamples': resamples, 'lags': rows}


def add_cycle_global_fdr(sectors):
    pairs = []
    for symbol, result in sectors.items():
        for row in result['lags']:
            pairs.append(((symbol, row['lag_weeks']), row.get('block_permutation_p')))
    q_global = bh_qvalues(pairs)
    for symbol, result in sectors.items():
        for row in result['lags']:
            key = (symbol, row['lag_weeks'])
            qg = q_global.get(key)
            row['q_global'] = round(qg, 6) if qg is not None else None
            valid_splits = sum(v is not None for v in row['split_correlations'])
            stable = row.get('split_sign_consistency') is not None and row['split_sign_consistency'] >= 2 / 3 and valid_splits >= 2
            row['status'] = (
                'survives_current_checks'
                if qg is not None and qg <= FDR_ALPHA and stable
                else 'not_supported_after_correction'
                if qg is not None
                else 'insufficient_history'
            )


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


def spearman_maps(a, b, required):
    common = sorted(set(a) & set(b))
    if len(common) < required:
        return None
    r0 = average_ranks({k: a[k] for k in common})
    r1 = average_ranks({k: b[k] for k in common})
    return pearson([r0[k] for k in common], [r1[k] for k in common])


def activity_snapshots(structure):
    instruments = structure.get('instruments') or {}
    maps = {}
    for symbol, item in instruments.items():
        if item.get('group') != 'sector':
            continue
        day_map = {}
        for row in item.get('sector_history') or []:
            if isinstance(row, list) and len(row) >= 2 and finite(row[1]):
                day_map[str(row[0])] = float(row[1])
        if day_map:
            maps[symbol] = day_map
    total = len(maps)
    if not total:
        return [], 0, 0
    cycle_activity = ((structure.get('cycle_research') or {}).get('activity_rotation') or {})
    required = int(cycle_activity.get('required_daily_coverage') or max(3, math.ceil(total * 0.7)))
    dates = sorted(set().union(*(set(m) for m in maps.values())))
    snapshots = []
    for day in dates:
        values = {symbol: m[day] for symbol, m in maps.items() if day in m}
        if len(values) >= required:
            snapshots.append((day, values))
    return snapshots, required, total


def activity_pair_corrs(snapshots, lag, required, current_sequence=None):
    later = current_sequence if current_sequence is not None else [x[1] for x in snapshots]
    base = [x[1] for x in snapshots]
    out = []
    for i in range(lag, min(len(base), len(later))):
        value = spearman_maps(base[i - lag], later[i], required)
        if value is not None:
            out.append(value)
    return out


def activity_split_means(snapshots, lag, required):
    n = len(snapshots)
    cuts = [round(n * i / TIME_SPLITS) for i in range(TIME_SPLITS + 1)]
    out = []
    for i in range(TIME_SPLITS):
        part = snapshots[cuts[i]:cuts[i + 1]]
        corrs = activity_pair_corrs(part, lag, required)
        out.append(statistics.fmean(corrs) if len(corrs) >= MIN_ACTIVITY_SPLIT_PAIRS else None)
    return out


def validate_activity(structure, resamples=RESAMPLES):
    snapshots, required, total = activity_snapshots(structure)
    rows = []
    rng = random.Random(stable_seed('activity-rank-persistence'))
    p_pairs = []
    for lag in ACTIVITY_LAGS:
        observed_corrs = activity_pair_corrs(snapshots, lag, required) if snapshots else []
        observed = statistics.fmean(observed_corrs) if len(observed_corrs) >= MIN_ACTIVITY_PAIRS else None
        splits = activity_split_means(snapshots, lag, required) if observed is not None else [None] * TIME_SPLITS
        consistency = sign_consistency(observed, splits)
        null_means = []
        boot_means = []
        if observed is not None:
            base_sequence = [x[1] for x in snapshots]
            for _ in range(resamples):
                shuffled = block_shuffle(base_sequence, rng, ACTIVITY_BLOCK_SESSIONS)
                null_corrs = activity_pair_corrs(snapshots, lag, required, current_sequence=shuffled)
                if len(null_corrs) >= MIN_ACTIVITY_PAIRS:
                    null_means.append(statistics.fmean(null_corrs))
                boot = moving_block_bootstrap(observed_corrs, rng, ACTIVITY_BLOCK_SESSIONS)
                if boot:
                    boot_means.append(statistics.fmean(boot))
        if observed is not None and null_means:
            extreme = sum(abs(v) >= abs(observed) for v in null_means)
            p = (extreme + 1.0) / (len(null_means) + 1.0)
        else:
            p = None
        lo = quantile(boot_means, 0.025)
        hi = quantile(boot_means, 0.975)
        row = {
            'lag_sessions': lag,
            'observed_mean_spearman': round(observed, 6) if observed is not None else None,
            'pairs': len(observed_corrs),
            'split_mean_spearman': [round(v, 6) if v is not None else None for v in splits],
            'split_sign_consistency': round(consistency, 4) if consistency is not None else None,
            'block_permutation_p': round(p, 6) if p is not None else None,
            'bootstrap_ci95': [round(lo, 6), round(hi, 6)] if lo is not None and hi is not None else [None, None],
        }
        rows.append(row)
        p_pairs.append((lag, p))
    q_family = bh_qvalues(p_pairs)
    for row in rows:
        q = q_family.get(row['lag_sessions'])
        row['q_activity_family'] = round(q, 6) if q is not None else None
    return {
        'status': 'research_validation_only',
        'method': 'daily_cross_sectional_spearman_three_splits_plus_5_session_block_permutation_and_moving_block_bootstrap_with_bh_fdr',
        'sector_count': total,
        'required_daily_coverage': required,
        'observations': len(snapshots),
        'lags_sessions': list(ACTIVITY_LAGS),
        'block_sessions': ACTIVITY_BLOCK_SESSIONS,
        'resamples': resamples,
        'lags': rows,
    }


def add_research_global_fdr(sectors, activity):
    pairs = []
    for symbol, result in sectors.items():
        for row in result['lags']:
            pairs.append((('return', symbol, row['lag_weeks']), row.get('block_permutation_p')))
    for row in activity.get('lags', []):
        pairs.append((('activity', row['lag_sessions']), row.get('block_permutation_p')))
    q_all = bh_qvalues(pairs)
    for symbol, result in sectors.items():
        for row in result['lags']:
            q = q_all.get(('return', symbol, row['lag_weeks']))
            row['q_research_global'] = round(q, 6) if q is not None else None
    for row in activity.get('lags', []):
        q = q_all.get(('activity', row['lag_sessions']))
        row['q_research_global'] = round(q, 6) if q is not None else None
        valid_splits = sum(v is not None for v in row['split_mean_spearman'])
        stable = row.get('split_sign_consistency') is not None and row['split_sign_consistency'] >= 2 / 3 and valid_splits >= 2
        row['status'] = (
            'survives_current_checks'
            if q is not None and q <= FDR_ALPHA and stable
            else 'not_supported_after_correction'
            if q is not None
            else 'insufficient_history'
        )


def summarize_cycle(sectors):
    rows = [row for result in sectors.values() for row in result['lags'] if row.get('block_permutation_p') is not None]
    sector_survivors = sum(row.get('q_sector') is not None and row['q_sector'] <= FDR_ALPHA for row in rows)
    global_survivors = sum(row.get('q_global') is not None and row['q_global'] <= FDR_ALPHA for row in rows)
    robust = sum(row.get('status') == 'survives_current_checks' for row in rows)
    return {
        'tested_hypotheses': len(rows),
        'sector_fdr_survivors': sector_survivors,
        'global_fdr_survivors': global_survivors,
        'stable_global_survivors': robust,
    }


def summarize_activity(activity):
    rows = [r for r in activity.get('lags', []) if r.get('block_permutation_p') is not None]
    return {
        'tested_hypotheses': len(rows),
        'activity_family_fdr_survivors': sum(r.get('q_activity_family') is not None and r['q_activity_family'] <= FDR_ALPHA for r in rows),
        'research_global_fdr_survivors': sum(r.get('q_research_global') is not None and r['q_research_global'] <= FDR_ALPHA for r in rows),
        'stable_research_global_survivors': sum(r.get('status') == 'survives_current_checks' for r in rows),
    }


def validate(structure, resamples=RESAMPLES):
    if structure.get('schema') != 'STRUCTURE-LAB-V1':
        raise ValueError('Expected STRUCTURE-LAB-V1')
    cycle = structure.get('cycle_research') or {}
    source_sectors = cycle.get('sectors') or {}
    sectors = {symbol: validate_sector(symbol, sector, resamples) for symbol, sector in source_sectors.items()}
    add_cycle_global_fdr(sectors)
    activity = validate_activity(structure, resamples)
    add_research_global_fdr(sectors, activity)
    activity['summary'] = summarize_activity(activity)
    structure['cycle_validation'] = {
        'status': 'research_validation_only',
        'method': 'time_splits_plus_block_permutation_moving_block_bootstrap_and_bh_fdr',
        'block_weeks': BLOCK_WEEKS,
        'resamples': resamples,
        'time_splits': TIME_SPLITS,
        'fdr_alpha': FDR_ALPHA,
        'multiple_testing': 'BH within return sector, across all return sector-lags, within activity 1/5/20 lags, and combined across return plus activity hypotheses',
        'summary': summarize_cycle(sectors),
        'sectors': sectors,
        'activity_rank_persistence': activity,
        'notes': [
            'Return-cycle block permutation preserves short within-block dependence while breaking most long-run alignment.',
            'Activity validation reconstructs daily full sector-activity rankings before testing; it does not test only the three precomputed summary means.',
            'Activity block permutation shuffles 5-session blocks of the later-day cross sections, preserving marginal sector rank structure while breaking date alignment.',
            'Moving-block bootstrap intervals describe sampling uncertainty and do not prove a causal or forecastable market cycle.',
            'Activity lag survives_current_checks only when combined research-wide FDR q<=0.10 and at least two chronological splits share the full-sample sign.',
            'Passing any validation layer is a research-candidate designation, not a trading signal or evidence of future profitability.',
        ],
    }
    return structure


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True)
    ap.add_argument('--output')
    ap.add_argument('--resamples', type=int, default=RESAMPLES)
    args = ap.parse_args(argv)
    if args.resamples < 20:
        raise ValueError('resamples must be at least 20')
    obj = validate(load(args.input), args.resamples)
    target = Path(args.output or args.input)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    summary = obj['cycle_validation']['summary']
    activity = obj['cycle_validation']['activity_rank_persistence']['summary']
    print(
        f'wrote cycle validation to {target}; return_tested={summary["tested_hypotheses"]}; '
        f'activity_tested={activity["tested_hypotheses"]}; '
        f'activity_stable_global={activity["stable_research_global_survivors"]}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
