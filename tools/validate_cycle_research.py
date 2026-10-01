#!/usr/bin/env python3
"""Add a conservative validation layer to cycle_research in STRUCTURE-LAB-V1.

The validator uses only already-derived weekly sector-relative returns. It does not
forecast prices and does not call any data provider.

For each sector ETF and lag 1..26 weeks it records:
- chronological three-way split correlations (stability check)
- a 4-week block-permutation two-sided p-value (alignment null)
- a 4-week circular moving-block bootstrap 95% interval
- Benjamini-Hochberg FDR q-values within each sector and globally across sectors/lags

Passing these checks means only that a historical dependence candidate survived the
current procedure; it is not evidence of future tradability or a confirmed cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

MAX_LAG_WEEKS = 26
BLOCK_WEEKS = 4
RESAMPLES = 200
FDR_ALPHA = 0.10
TIME_SPLITS = 3
MIN_PAIRS = 20
MIN_SPLIT_PAIRS = 12


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


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


def all_corr(values, min_pairs=MIN_PAIRS):
    return [corr_at(values, lag, min_pairs) for lag in range(1, MAX_LAG_WEEKS + 1)]


def block_shuffle(values, rng, block=BLOCK_WEEKS):
    blocks = [values[i:i + block] for i in range(0, len(values), block)]
    rng.shuffle(blocks)
    return [v for part in blocks for v in part]


def moving_block_bootstrap(values, rng, block=BLOCK_WEEKS):
    n = len(values)
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


def validate_sector(symbol, sector, resamples=RESAMPLES):
    series = sector.get('relative_weekly_returns') or []
    values = [float(row[1]) for row in series if isinstance(row, list) and len(row) >= 2]
    observed = all_corr(values)
    rng = random.Random(stable_seed(symbol))
    nulls = [[] for _ in range(MAX_LAG_WEEKS)]
    boots = [[] for _ in range(MAX_LAG_WEEKS)]
    if len(values) >= MIN_PAIRS + 1:
        for _ in range(resamples):
            shuffled = all_corr(block_shuffle(values, rng))
            booted = all_corr(moving_block_bootstrap(values, rng))
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
        valid_splits = [v for v in splits if v is not None]
        same_sign = 0
        if obs is not None:
            same_sign = sum((v > 0) == (obs > 0) for v in valid_splits if v != 0)
        consistency = same_sign / len(valid_splits) if valid_splits else None
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
    return {
        'weeks': len(values),
        'resamples': resamples,
        'lags': rows,
    }


def add_global_fdr(sectors):
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


def summarize(sectors):
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


def validate(structure, resamples=RESAMPLES):
    if structure.get('schema') != 'STRUCTURE-LAB-V1':
        raise ValueError('Expected STRUCTURE-LAB-V1')
    cycle = structure.get('cycle_research') or {}
    source_sectors = cycle.get('sectors') or {}
    sectors = {symbol: validate_sector(symbol, sector, resamples) for symbol, sector in source_sectors.items()}
    add_global_fdr(sectors)
    structure['cycle_validation'] = {
        'status': 'research_validation_only',
        'method': 'three_time_splits_plus_4w_block_permutation_and_moving_block_bootstrap_with_bh_fdr',
        'block_weeks': BLOCK_WEEKS,
        'resamples': resamples,
        'time_splits': TIME_SPLITS,
        'fdr_alpha': FDR_ALPHA,
        'multiple_testing': 'BH within sector and globally across all sector-lag hypotheses',
        'summary': summarize(sectors),
        'sectors': sectors,
        'notes': [
            'Block permutation p-values are approximate and preserve short within-block dependence while breaking most long-run alignment.',
            'Moving-block bootstrap intervals describe sampling uncertainty and do not prove a causal or forecastable market cycle.',
            'A lag survives_current_checks only when global FDR q<=0.10 and at least two chronological splits have the same correlation sign as the full sample.',
            'Passing this layer is a research candidate designation, not a trading signal or evidence of future profitability.',
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
    print(f'wrote cycle validation to {target}; tested={summary["tested_hypotheses"]}; stable_global={summary["stable_global_survivors"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
