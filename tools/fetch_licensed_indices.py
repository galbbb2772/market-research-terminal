#!/usr/bin/env python3
"""Fetch only the four canonical headline indices from Massive.

This is an integration adapter, not a redistribution licence. By default it writes
private/local output. Public output is blocked unless separate Massive/index-display
approval and a written licence reference are explicitly configured.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse, parse_qsl, urlunparse
from urllib.request import Request, urlopen

UNIVERSE = Path('docs/data/market_universe.json')
BASE = 'https://api.massive.com'

# Verified against Massive's index reference endpoint on 2026-09-30.
MAJOR_INDEX_SYMBOLS = {
    'SP500': 'I:SPX',
    'NDX': 'I:NDX',
    'NASDAQ_COMPOSITE': 'I:COMP',
    'DJIA': 'I:DJI',
}


def canonical_major_indices(universe):
    return {x['id'] for x in universe.get('major_indices', []) if x.get('id')}


def normalize_massive(results, symbol):
    if not isinstance(results, list) or not results:
        raise ValueError(f'{symbol}: Massive returned no daily bars')
    bars = []
    for item in results:
        stamp = int(item['t'])
        day = dt.datetime.fromtimestamp(stamp / 1000, tz=dt.timezone.utc).date().isoformat()
        o, h, l, c = [float(item[k]) for k in ('o', 'h', 'l', 'c')]
        if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
            raise ValueError(f'{symbol}: non-positive or nonfinite OHLC on {day}')
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f'{symbol}: inconsistent OHLC on {day}')
        # Headline indices have no economically meaningful exchange volume here.
        bars.append([day, o, h, l, c, None, None])
    bars.sort(key=lambda x: x[0])
    if len({b[0] for b in bars}) != len(bars):
        raise ValueError(f'{symbol}: duplicate Massive trading dates')
    return bars


def _with_key(url, api_key):
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q['apiKey'] = api_key
    return urlunparse(parsed._replace(query=urlencode(q)))


def fetch_massive(provider_symbol, start, end, api_key, opener=urlopen):
    symbol = quote(provider_symbol, safe=':')
    url = (f'{BASE}/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}'
           f'?{urlencode({"sort": "asc", "limit": 50000, "adjusted": "true", "apiKey": api_key})}')
    all_rows = []
    pages = 0
    while url:
        pages += 1
        if pages > 20:
            raise RuntimeError(f'{provider_symbol}: excessive pagination')
        req = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'MarketResearchTerminal/1.0'})
        try:
            with opener(req, timeout=45) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f'{provider_symbol}: index-data fetch failed ({type(exc).__name__}); key omitted') from None
        if not isinstance(payload, dict):
            raise ValueError(f'{provider_symbol}: unexpected Massive response')
        status = str(payload.get('status', '')).upper()
        if status in {'ERROR', 'NOT_AUTHORIZED'} or payload.get('error'):
            raise RuntimeError(f'{provider_symbol}: provider rejected request: {payload.get("error") or payload.get("message") or status}')
        rows = payload.get('results') or []
        if not isinstance(rows, list):
            raise ValueError(f'{provider_symbol}: malformed results')
        all_rows.extend(rows)
        next_url = payload.get('next_url')
        url = _with_key(next_url, api_key) if next_url else None
    return normalize_massive(all_rows, provider_symbol)


def build_history(selected, universe, start, end, api_key, opener=urlopen,
                  rights_status='verified_internal_only'):
    allowed = canonical_major_indices(universe)
    invalid = set(selected) - allowed
    if invalid:
        raise ValueError(f'non-major-index or non-canonical ids not allowed: {sorted(invalid)}')
    unmapped = set(selected) - set(MAJOR_INDEX_SYMBOLS)
    if unmapped:
        raise ValueError(f'canonical indices missing verified Massive mapping: {sorted(unmapped)}')
    if not selected:
        raise ValueError('select at least one canonical major index')
    out = {
        'schema': 'MARKET-HISTORY-V1',
        'provider': 'Massive Indices',
        'rights_status': rights_status,
        'adjustment': 'provider index OHLC; no synthetic volume or adjusted close',
        'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'license_reference': os.getenv('MASSIVE_INDEX_LICENSE_REFERENCE', '') if rights_status == 'verified_publishable' else None,
        'instruments': {},
        'notes': [
            'Major-index-only Massive adapter; ETFs use a separate licensed source adapter.',
            'SP500=I:SPX, NDX=I:NDX, NASDAQ_COMPOSITE=I:COMP, DJIA=I:DJI.',
            'Public display/redistribution requires separately confirmed rights for each applicable index feed.',
        ],
    }
    for canonical in selected:
        provider_symbol = MAJOR_INDEX_SYMBOLS[canonical]
        bars = fetch_massive(provider_symbol, start, end, api_key, opener=opener)
        out['instruments'][canonical] = {
            'provider': 'Massive Indices',
            'provider_symbol': provider_symbol,
            'source_status': 'actual_provider_response',
            'start': bars[0][0],
            'end': bars[-1][0],
            'bars': bars,
        }
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--universe', default=str(UNIVERSE))
    p.add_argument('--symbols', default='SP500,NDX,NASDAQ_COMPOSITE,DJIA')
    p.add_argument('--start', default='2019-01-01')
    p.add_argument('--end', default=dt.date.today().isoformat())
    p.add_argument('--output', default='/tmp/market_indices_private.json')
    p.add_argument('--publish', action='store_true')
    a = p.parse_args(argv)
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    if start > end:
        p.error('--start must precede --end')
    target = Path(a.output)
    public_tree = target.resolve().is_relative_to(Path('docs/data').resolve())
    if public_tree and not a.publish:
        p.error('output inside docs/data requires --publish and licensed public-display rights')
    if a.publish and not public_tree:
        p.error('--publish must target docs/data')
    rights = 'verified_internal_only'
    if a.publish:
        approved = os.getenv('MASSIVE_INDEX_PUBLIC_DISPLAY_APPROVED', '').lower() == 'true'
        ref = os.getenv('MASSIVE_INDEX_LICENSE_REFERENCE', '').strip()
        if not approved or not ref:
            p.error('public index display requires explicit approval AND nonempty written licence reference')
        rights = 'verified_publishable'
    api_key = os.getenv('MASSIVE_API_KEY', '').strip()
    if not api_key:
        p.error('MASSIVE_API_KEY missing; put it in GitHub Actions Secrets, NEVER commit it')
    universe = json.loads(Path(a.universe).read_text(encoding='utf-8'))
    selected = [x.strip().upper() for x in a.symbols.split(',') if x.strip()]
    history = build_history(selected, universe, a.start, a.end, api_key, rights_status=rights)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Fetched {len(history["instruments"])} canonical indices; saved to {target}; rights={rights}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
