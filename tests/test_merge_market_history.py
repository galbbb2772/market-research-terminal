import copy
import unittest
from tools.merge_market_history import merge


def doc(provider, symbol, status='verified_publishable'):
    return {
        'schema': 'MARKET-HISTORY-V1',
        'provider': provider,
        'rights_status': status,
        'license_reference': f'approved-{provider}' if status == 'verified_publishable' else None,
        'instruments': {
            symbol: {'provider_symbol': symbol, 'bars': [
                ['2026-09-28', 100, 105, 99, 101, None, None],
                ['2026-09-29', 101, 106, 100, 103, None, None],
            ]}
        },
    }


class MergerTests(unittest.TestCase):
    def test_merge_preserves_instrument_provider_and_no_volume(self):
        etfs = doc('ETF Provider', 'SPY')
        indices = doc('Index Provider', 'SP500')
        original_etfs = copy.deepcopy(etfs)
        result = merge(etfs, [indices], publish=True)
        self.assertEqual(result['rights_status'], 'verified_publishable')
        self.assertEqual(set(result['instruments']), {'SPY', 'SP500'})
        self.assertEqual(result['instruments']['SPY']['provider'], 'ETF Provider')
        self.assertEqual(result['instruments']['SP500']['provider'], 'Index Provider')
        self.assertIsNone(result['instruments']['SP500']['bars'][0][5])
        self.assertEqual(etfs, original_etfs, 'must not mutate inputs')

    def test_overlay_replaces_updated_symbol_only(self):
        base = doc('ETF Provider', 'SPY')
        base['instruments']['QQQ'] = {'bars': [['2026-09-29', 100, 101, 99, 101, 100, None]]}
        new = doc('Refreshed Provider', 'SPY')
        new['instruments']['SPY']['bars'][-1][4] = 104
        output = merge(base, [new], publish=True)
        self.assertEqual(output['instruments']['SPY']['bars'][-1][4], 104)
        self.assertIn('QQQ', output['instruments'])

    def test_reject_nonpublishable_source_even_if_other_is_approved(self):
        etfs = doc('ETF Provider', 'SPY')
        indices = doc('Index Provider', 'SP500', 'verified_internal_only')
        with self.assertRaises(ValueError):
            merge(etfs, [indices], publish=True)
        safe = merge(etfs, [indices])
        self.assertNotEqual(safe['rights_status'], 'verified_publishable')

    def test_reject_missing_or_empty_source(self):
        with self.assertRaises(ValueError):
            merge(None, [])
        with self.assertRaises(ValueError):
            merge(None, [{'schema': 'MARKET-HISTORY-V1', 'instruments': {}}])


if __name__ == '__main__': unittest.main()
