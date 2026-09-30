import io, json, os, unittest
from pathlib import Path
from unittest.mock import patch
from tools.fetch_licensed_etfs import canonical_etfs, normalize_tiingo, fetch_tiingo, build_history, main

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = json.loads((ROOT / 'docs/data/market_universe.json').read_text(encoding='utf-8'))
SAMPLE = [
    {'date': '2026-09-28T00:00:00.000Z', 'open': 100, 'high': 105, 'low': 99, 'close': 104,
     'volume': 12000, 'adjClose': 103.6},
    {'date': '2026-09-29T00:00:00.000Z', 'open': 104, 'high': 107, 'low': 102, 'close': 105,
     'volume': 14000, 'adjClose': 104.5},
]


class DummyOpener:
    def __init__(self): self.requests = []
    def __call__(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps(SAMPLE).encode('utf-8'))


class LicensedETFTests(unittest.TestCase):
    def test_only_etfs_in_allowlist(self):
        ids = canonical_etfs(UNIVERSE)
        self.assertTrue({'SPY', 'QQQ', 'DIA', 'XLK', 'QTEC'} <= ids)
        self.assertFalse({'AAPL', 'NDX', 'DJIA', 'DJUSTC'} & ids)

    def test_normalization_and_auth_header(self):
        adapter = DummyOpener()
        bars = fetch_tiingo('SPY', '2026-09-01', '2026-09-29', 'sample-secret', opener=adapter)
        self.assertEqual(bars[0], ['2026-09-28', 100, 105, 99, 104, 12000, 103.6])
        self.assertEqual(adapter.requests[0].get_header('Authorization'), 'Token sample-secret')
        self.assertNotIn('sample-secret', adapter.requests[0].full_url)
        with self.assertRaises(ValueError):
            normalize_tiingo([SAMPLE[0], SAMPLE[0]], 'SPY')

    def test_integration_requires_canonical_etfs(self):
        adapter = DummyOpener()
        output = build_history(['SPY', 'XLK'], UNIVERSE, '2026-09-01', '2026-09-29',
                               'sample-secret', opener=adapter)
        self.assertEqual(set(output['instruments']), {'SPY', 'XLK'})
        self.assertEqual(output['rights_status'], 'verified_internal_only')
        with self.assertRaises(ValueError):
            build_history(['AAPL'], UNIVERSE, '2026-09-01', '2026-09-29', 'x', opener=adapter)
        with self.assertRaises(ValueError):
            build_history(['SP500'], UNIVERSE, '2026-09-01', '2026-09-29', 'x', opener=adapter)

    def test_public_output_blocked_without_licence(self):
        with patch.dict(os.environ, {'TIINGO_API_TOKEN': 'sample-secret',
                                    'MARKET_DATA_PUBLIC_DISPLAY_APPROVED': '',
                                    'MARKET_DATA_LICENSE_REFERENCE': ''}):
            with self.assertRaises(SystemExit):
                main(['--publish', '--output', 'docs/data/market_history.json'])
            with self.assertRaises(SystemExit):
                main(['--output', 'docs/data/market_history.json'])


if __name__ == '__main__': unittest.main()
