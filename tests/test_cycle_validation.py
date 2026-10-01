import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.validate_cycle_research import bh_qvalues, validate


def synthetic_series(n=180, phase=0.0):
    return [[f'W{i:03d}', math.sin(i * 2 * math.pi / 8 + phase) + 0.15 * math.sin(i * 2 * math.pi / 3)] for i in range(n)]


class CycleValidationTests(unittest.TestCase):
    def test_bh_qvalues_are_bounded_and_monotone(self):
        q = bh_qvalues([('a', 0.001), ('b', 0.02), ('c', 0.04), ('d', 0.5)])
        self.assertTrue(all(0 <= v <= 1 for v in q.values()))
        self.assertLessEqual(q['a'], q['b'])
        self.assertLessEqual(q['b'], q['c'])
        self.assertLessEqual(q['c'], q['d'])

    def test_validation_adds_fdr_bootstrap_and_splits(self):
        structure = {
            'schema': 'STRUCTURE-LAB-V1',
            'cycle_research': {
                'status': 'research_only',
                'sectors': {
                    'XLK': {'relative_weekly_returns': synthetic_series(180, 0.0)},
                    'XLF': {'relative_weekly_returns': synthetic_series(180, 1.2)},
                },
            },
        }
        out = validate(structure, resamples=30)
        v = out['cycle_validation']
        self.assertEqual(v['status'], 'research_validation_only')
        self.assertEqual(v['block_weeks'], 4)
        self.assertEqual(v['time_splits'], 3)
        self.assertEqual(v['summary']['tested_hypotheses'], 52)
        self.assertEqual(set(v['sectors']), {'XLK', 'XLF'})
        row = v['sectors']['XLK']['lags'][0]
        self.assertEqual(len(v['sectors']['XLK']['lags']), 26)
        self.assertEqual(len(row['split_correlations']), 3)
        self.assertEqual(len(row['bootstrap_ci95']), 2)
        self.assertIsNotNone(row['block_permutation_p'])
        self.assertIsNotNone(row['q_sector'])
        self.assertIsNotNone(row['q_global'])
        self.assertIn(row['status'], {'survives_current_checks', 'not_supported_after_correction'})
        for key in ('block_permutation_p', 'q_sector', 'q_global'):
            self.assertTrue(0 <= row[key] <= 1)

    def test_validation_is_deterministic_for_same_input(self):
        base = {
            'schema': 'STRUCTURE-LAB-V1',
            'cycle_research': {'status': 'research_only', 'sectors': {'XLE': {'relative_weekly_returns': synthetic_series(150, 0.4)}}},
        }
        a = validate({'schema': base['schema'], 'cycle_research': base['cycle_research'].copy()}, resamples=25)
        b = validate({'schema': base['schema'], 'cycle_research': base['cycle_research'].copy()}, resamples=25)
        self.assertEqual(a['cycle_validation'], b['cycle_validation'])


if __name__ == '__main__':
    unittest.main()
