#!/usr/bin/env python3
"""Fetch only canonical ETFs from Tiingo; default output is private/local.

IMPORTANT: An API token is not a redistribution licence. Public publication requires
independently confirmed written public-display AND static-JSON distribution rights.
This adapter intentionally does not claim to cover proprietary index histories.
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, os, sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

UNIVERSE = Path('docs/data/market_universe.json')


def canonical_etfs(universe):
    out = {item['id'] for item in universe.get('benchmarks', []) if item.get('type') == 'etf'}
    for system in universe.get('sector_systems', {}).values():
        for item in system.get('items', []):
            if item.get('kind', '').upper() == 'ETF':
                out.add(item['id'])
    return out


def normalize_tiingo(rows, symbol):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'{symbol}: Tiingo returned no daily bars')
    bars = []
    for item in rows:
        day = str(item['date'])[:10]
        dt.date.fromisoformat(day)
        o, h, l, c = [float(item[k]) for k in ('open', 'high', 'low', 'close')]
        if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
            raise ValueError(f'{symbol}: non-positive or nonfinite OHLC on {day}')
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f'{symbol}: inconsistent OHLC on {day}')
        vol = item.get('volume')
        vol = None if vol is None else float(vol)
        if vol is not None and (not math.isfinite(vol) or vol < 0):
            raise ValueError(f'{symbol}: invalid volume on {day}')
        adj = item.get('adjClose')
        adj = None if adj is None else float(adj)
        if adj is not None and (not math.isfinite(adj) or adj <= 0):
            raise ValueError(f'{symbol}: invalid adjusted close on {day}')
        bars.append([day, o, h, l, c, vol, adj])
    bars.sort(key=lambda x: x[0])
    if len({b[0] for b in bars}) != len(bars):
        raise ValueError(f'{symbol}: duplicate Tiingo trading dates')
    return bars


def fetch_tiingo(symbol, start, end, token, opener=urlopen):
    query = urlencode({'startDate': start, 'endDate': end, 'format': 'json'})
    url = f'https://api.tiingo.com/tiingo/daily/{quote(symbol, safe="")}/prices?{query}'
    req = Request(url, headers={'Authorization': f'Token {token}', 'Accept': 'application/json',
                                'User-Agent': 'MarketResearchTerminal/1.0'})
    try:
        with opener(req, timeout=40) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f'{symbol}: market-data fetch failed ({type(exc).__name__}); token omitted') from None
    if not isinstance(data, list):
        raise ValueError(f'{symbol}: unexpected Tiingo response (verify entitlement and symbol)')
    return normalize_tiingo(data, symbol)


def build_history(selected, universe, start, end, token, opener=urlopen, rights_status='verified_internal_only'):
    allowed = canonical_etfs(universe)
    invalid = set(selected) - allowed
    if invalid:
        raise ValueError(f'non-ETF or non-canonical symbols not allowed: {sorted(invalid)}')
    if not selected:
        raise ValueError('select at least one canonical ETF')
    result = {'schema': 'MARKET-HISTORY-V1', 'provider': 'Tiingo EOD',
              'rights_status': rights_status, 'adjustment': 'raw OHLCV; adjClose for adjusted returns',
              'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'license_reference': os.getenv('MARKET_DATA_LICENSE_REFERENCE', '') if rights_status == 'verified_publishable' else None,
              'instruments': {}, 'notes': ['ETF-only Tiingo adapter; major indices require their own licensed source.',
                                             'Public JSON redistribution requires separately confirmed written permission.']}
    for symbol in selected:
        bars = fetch_tiingo(symbol, start, end, token, opener)
        result['instruments'][symbol] = {'provider_symbol': symbol, 'source_status': 'actual_provider_response',
                                         'start': bars[0][0], 'end': bars[-1][0], 'bars': bars}
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--universe', default=str(UNIVERSE))
    p.add_argument('--symbols', default='SPY,QQQ,DIA,XLB,XLC,XLE,XLF,XLI,XLK,XLP,XLRE,XLU,XLV,XLY')
    p.add_argument('--start', default='2019-01-01')
    p.add_argument('--end', default=dt.date.today().isoformat())
    p.add_argument('--output', default='/tmp/market_history_private.json')
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
        approved = os.getenv('MARKET_DATA_PUBLIC_DISPLAY_APPROVED', '').lower() == 'true'
        ref = os.getenv('MARKET_DATA_LICENSE_REFERENCE', '').strip()
        if not approved or not ref:
            p.error('public display requires explicit approval AND nonempty written licence reference')
        rights = 'verified_publishable'
    token = os.getenv('TIINGO_API_TOKEN', '').strip()
    if not token:
        p.error('TIINGO_API_TOKEN missing; put token in GitHub Actions Secrets, NEVER commit it')
    universe = json.loads(Path(a.universe).read_text(encoding='utf-8'))
    selected = [x.strip().upper() for x in a.symbols.split(',') if x.strip()]
    history = build_history(selected, universe, a.start, a.end, token, rights_status=rights)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(f'Fetched {len(history["instruments"])} licensed-scope ETFs; saved to {target}; rights={rights}')
    return 0


if __name__ == '__main__':
    sys.exit(main())