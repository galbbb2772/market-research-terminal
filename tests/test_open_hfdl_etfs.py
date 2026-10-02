import datetime as dt
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fetch_open_etfs_hfdl import (
    HF_LICENSE,
    IEX_ATTRIBUTION,
    build_history,
    canonical_etfs,
    parse_daily_csv,
)

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = json.loads((ROOT / 'docs/data/market_universe.json').read_text(encoding='utf-8'))


def sample_csv(days=35):
    rows = ['datetime,open,high,low,close,volume,source']
    start = dt.date(2022, 2, 15)
    for i in range(days):
        day = start + dt.timedelta(days=i)
        px = 100 + i * 0.1
        source = 'pitrading' if day < dt.date(2022, 3, 7) else 'iex'
        rows.append(f'{day.isoformat()},{px:.2f},{px+1:.2f},{px-1:.2f},{px+0.3:.2f},{10000+i},{source}')
    return ('\n'.join(rows) + '\n').encode('utf-8')


class HFDLOpenETFTests(unittest.TestCase):
    def test_canonical_scope_and_essential_family(self):
        all_etfs, essential = canonical_etfs(UNIVERSE)
        self.assertTrue({'SPY', 'QQQ', 'DIA', 'XLB', 'XLK', 'XLV', 'QTEC'} <= set(all_etfs))
        self.assertTrue({'SPY', 'QQQ', 'DIA', 'XLB', 'XLK', 'XLV'} <= essential)
        self.assertNotIn('QTEC', essential)
        self.assertFalse({'AAPL', 'NDX', 'DJIA', 'DJUSTC'} & set(all_etfs))

    def test_daily_csv_normalizes_and_preserves_source_break(self):
        bars, provenance = parse_daily_csv(sample_csv(), 'SPY', '2022-02-15', '2022-03-21')
        self.assertGreaterEqual(len(bars), 30)
        self.assertEqual(len(bars[0]), 7)
        self.assertEqual(bars[0][6], bars[0][4])
        self.assertIn('pitrading', provenance['source_counts'])
        self.assertIn('iex', provenance['source_counts'])
        self.assertLess(provenance['source_ranges']['pitrading']['end'],
                        provenance['source_ranges']['iex']['start'])

    def test_history_is_explicitly_publishable_with_attribution(self):
        all_etfs, essential = canonical_etfs(UNIVERSE)

        def fake_fetch(symbol, start, end, api_key):
            bars, prov = parse_daily_csv(sample_csv(), symbol, start, end)
            return {
                'provider_symbol': symbol,
                'source_status': 'actual_open_licensed_provider_response',
                'start': bars[0][0], 'end': bars[-1][0], 'bars': bars,
                'provenance': prov,
            }

        with patch('tools.fetch_open_etfs_hfdl.fetch_symbol', side_effect=fake_fetch):
            history = build_history(all_etfs, UNIVERSE, '2022-02-15', '2022-03-21', 'not-persisted', pause=0)
        self.assertEqual(history['rights_status'], 'verified_publishable')
        self.assertEqual(history['license_reference'], HF_LICENSE)
        self.assertIn(IEX_ATTRIBUTION, history['notes'])
        self.assertTrue(essential <= set(history['instruments']))
        self.assertNotIn('NDX', history['instruments'])

    def test_missing_essential_symbol_refuses_partial_publication(self):
        all_etfs, essential = canonical_etfs(UNIVERSE)
        victim = sorted(essential)[0]

        def fake_fetch(symbol, start, end, api_key):
            if symbol == victim:
                raise RuntimeError('synthetic upstream miss')
            bars, prov = parse_daily_csv(sample_csv(), symbol, start, end)
            return {'provider_symbol': symbol, 'start': bars[0][0], 'end': bars[-1][0],
                    'bars': bars, 'provenance': prov}

        with patch('tools.fetch_open_etfs_hfdl.fetch_symbol', side_effect=fake_fetch):
            with self.assertRaises(RuntimeError):
                build_history(all_etfs, UNIVERSE, '2022-02-15', '2022-03-21', 'x', pause=0)


if __name__ == '__main__':
    unittest.main()
