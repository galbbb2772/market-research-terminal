import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from tools.fetch_licensed_indices import (MAJOR_INDEX_SYMBOLS, build_history,
                                          canonical_major_indices, fetch_massive,
                                          main, normalize_massive)

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = json.loads((ROOT / 'docs/data/market_universe.json').read_text(encoding='utf-8'))
ROWS = [
    {'t': 1790553600000, 'o': 100, 'h': 105, 'l': 98, 'c': 104},
    {'t': 1790640000000, 'o': 104, 'h': 107, 'l': 103, 'c': 105},
]


class DummyOpener:
    def __init__(self, pages=None):
        self.requests = []
        self.pages = pages or [{'status': 'OK', 'results': ROWS}]

    def __call__(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps(self.pages.pop(0)).encode('utf-8'))


class LicensedIndexTests(unittest.TestCase):
    def test_only_four_major_index_mappings(self):
        ids = canonical_major_indices(UNIVERSE)
        self.assertEqual(ids, set(MAJOR_INDEX_SYMBOLS))
        self.assertEqual(MAJOR_INDEX_SYMBOLS['NASDAQ_COMPOSITE'], 'I:COMP')
        self.assertFalse({'SPY', 'QQQ', 'DIA', 'AAPL', 'DJUSTC'} & ids)

    def test_normalize_no_fabricated_volume_and_validate(self):
        rows = normalize_massive(ROWS, 'I:SPX')
        self.assertEqual(rows[0], ['2026-09-28', 100, 105, 98, 104, None, None])
        self.assertEqual(rows[1][0], '2026-09-29')
        with self.assertRaises(ValueError):
            normalize_massive([ROWS[0], ROWS[0]], 'I:SPX')
        with self.assertRaises(ValueError):
            normalize_massive([{'t': ROWS[0]['t'], 'o': 9, 'h': 8, 'l': 7, 'c': 10}], 'I:SPX')

    def test_real_api_contract_is_mockable_and_key_not_omitted(self):
        opener = DummyOpener()
        rows = fetch_massive('I:NDX', '2026-09-01', '2026-09-30', 'example-secret', opener=opener)
        self.assertEqual(len(rows), 2)
        parsed = urlparse(opener.requests[0].full_url)
        self.assertEqual(parsed.path, '/v2/aggs/ticker/I:NDX/range/1/day/2026-09-01/2026-09-30')
        self.assertEqual(parse_qs(parsed.query)['apiKey'], ['example-secret'])

    def test_canonical_indices_only_no_actual_network(self):
        opener = DummyOpener(pages=[{'status': 'OK', 'results': ROWS}])
        output = build_history(['NDX'], UNIVERSE, '2026-09-01', '2026-09-30',
                               'example-secret', opener=opener)
        self.assertEqual(set(output['instruments']), {'NDX'})
        self.assertEqual(output['rights_status'], 'verified_internal_only')
        self.assertIsNone(output['instruments']['NDX']['bars'][0][5])
        with self.assertRaises(ValueError):
            build_history(['QQQ'], UNIVERSE, '2026-09-01', '2026-09-30', 'key', opener=opener)
        with self.assertRaises(ValueError):
            build_history(['DJUSTC'], UNIVERSE, '2026-09-01', '2026-09-30', 'key', opener=opener)

    def test_public_output_requires_separate_index_licence(self):
        env = {'MASSIVE_API_KEY': 'example-secret',
               'MASSIVE_INDEX_PUBLIC_DISPLAY_APPROVED': '',
               'MASSIVE_INDEX_LICENSE_REFERENCE': ''}
        with patch.dict(os.environ, env):
            with self.assertRaises(SystemExit):
                main(['--publish', '--output', 'docs/data/market_indices_staging.json'])
            with self.assertRaises(SystemExit):
                main(['--output', 'docs/data/market_indices_staging.json'])


if __name__ == '__main__':
    unittest.main()
