import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.validate_cycle_research import bh_qvalues, validate


def synthetic_series(n=180, phase=0.0):
    return [[f'W{i:03d}', math.sin(i * 2 * math.pi / 8 + phase) + 0.15 * math.sin(i * 2 * math.pi / 3)] for i in range(n)]


def activity_history(phase=0.0, n=220):
    rows = []
    for i in range(n):
        value = 50 + 24 * math.sin(i * 2 * math.pi / 37 + phase) + 8 * math.sin(i * 2 * math.pi / 9 + phase / 2)
        rows.append([f'D{i:03d}', max(0.0, min(100.0, value)), 50.0, 50.0, 0.0])
    return rows


def validation_structure():
    return {
        'schema': 'STRUCTURE-LAB-V1',
        'cycle_research': {
            'status': 'research_only',
            'sectors': {
                'XLK': {'relative_weekly_returns': synthetic_series(180, 0.0)},
                'XLF': {'relative_weekly_returns': synthetic_series(180, 1.2)},
            },
            'activity_rotation': {'required_daily_coverage': 3},
        },
        'instruments': {
            'XLK': {'group': 'sector', 'sector_history': activity_history(0.0)},
            'XLF': {'group': 'sector', 'sector_history': activity_history(0.7)},
            'XLE': {'group': 'sector', 'sector_history': activity_history(1.4)},
            'XLV': {'group': 'sector', 'sector_history': activity_history(2.1)},
        },
    }


class CycleValidationTests(unittest.TestCase):
    def test_bh_qvalues_are_bounded_and_monotone(self):
        q = bh_qvalues([('a', 0.001), ('b', 0.02), ('c', 0.04), ('d', 0.5)])
        self.assertTrue(all(0 <= v <= 1 for v in q.values()))
        self.assertLessEqual(q['a'], q['b'])
        self.assertLessEqual(q['b'], q['c'])
        self.assertLessEqual(q['c'], q['d'])

    def test_validation_adds_fdr_bootstrap_and_splits(self):
        out = validate(validation_structure(), resamples=30)
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
        self.assertIsNotNone(row['q_research_global'])
        self.assertIn(row['status'], {'survives_current_checks', 'not_supported_after_correction'})
        for key in ('block_permutation_p', 'q_sector', 'q_global', 'q_research_global'):
            self.assertTrue(0 <= row[key] <= 1)

    def test_activity_rank_persistence_gets_same_validation_class(self):
        out = validate(validation_structure(), resamples=30)
        a = out['cycle_validation']['activity_rank_persistence']
        self.assertEqual(a['status'], 'research_validation_only')
        self.assertEqual(a['block_sessions'], 5)
        self.assertEqual(a['lags_sessions'], [1, 5, 20])
        self.assertEqual(a['summary']['tested_hypotheses'], 3)
        self.assertGreaterEqual(a['observations'], 200)
        self.assertEqual([r['lag_sessions'] for r in a['lags']], [1, 5, 20])
        for row in a['lags']:
            self.assertGreaterEqual(row['pairs'], 30)
            self.assertEqual(len(row['split_mean_spearman']), 3)
            self.assertEqual(len(row['bootstrap_ci95']), 2)
            self.assertIsNotNone(row['observed_mean_spearman'])
            self.assertIsNotNone(row['block_permutation_p'])
            self.assertIsNotNone(row['q_activity_family'])
            self.assertIsNotNone(row['q_research_global'])
            self.assertIn(row['status'], {'survives_current_checks', 'not_supported_after_correction'})
            for key in ('block_permutation_p', 'q_activity_family', 'q_research_global'):
                self.assertTrue(0 <= row[key] <= 1)

    def test_validation_is_deterministic_for_same_input(self):
        a = validate(validation_structure(), resamples=25)
        b = validate(validation_structure(), resamples=25)
        self.assertEqual(a['cycle_validation'], b['cycle_validation'])


if __name__ == '__main__':
    unittest.main()
