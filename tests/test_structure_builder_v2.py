import datetime as dt
import math
import unittest

from tools.build_structure_lab_v2 import CFG, build, detect_boxes


def range_bars(n=180, volume=1_000_000):
    out=[]
    day=dt.date(2025, 1, 2)
    while len(out)<n:
        if day.weekday()<5:
            i=len(out)
            close=100+2.2*math.sin(i/4.2)+0.35*math.sin(i/1.7)
            out.append([day.isoformat(), close-0.25, close+0.95, close-0.95, close, volume])
        day+=dt.timedelta(days=1)
    return out


class StructureBuilderV2Tests(unittest.TestCase):
    def test_v2_requires_real_formation_window(self):
        self.assertEqual(detect_boxes(range_bars(44)), [])
        boxes=detect_boxes(range_bars(180))
        self.assertTrue(boxes)
        self.assertTrue(any(b['scale']=='small' for b in boxes))
        self.assertTrue(any(b['scale']=='large' for b in boxes))

    def test_v2_exposes_independent_touch_and_trend_metadata(self):
        boxes=detect_boxes(range_bars(180))
        self.assertTrue(boxes)
        for box in boxes:
            self.assertIn('switches', box['touches'])
            self.assertIn('span', box['touches'])
            self.assertGreaterEqual(box['touches']['upper'], 2)
            self.assertGreaterEqual(box['touches']['lower'], 2)
            self.assertIn('efficiency', box['trend'])
            self.assertIn('slope_ratio', box['trend'])
            self.assertTrue(all(0 <= v <= 10 for v in box['scores'].values()))

    def test_v2_detection_date_is_not_moved_backward_by_future_breakout(self):
        first=range_bars(145)
        a=detect_boxes(first)
        self.assertTrue(a)
        earliest=min(x['detected_at'] for x in a)
        day=dt.date.fromisoformat(first[-1][0])
        future=list(first)
        price=128.0
        for i in range(8):
            day+=dt.timedelta(days=1)
            while day.weekday()>=5:
                day+=dt.timedelta(days=1)
            future.append([day.isoformat(), price-0.2, price+0.8, price-0.8, price, 1_000_000])
        b=detect_boxes(future)
        self.assertTrue(b)
        self.assertEqual(earliest, min(x['detected_at'] for x in b))

    def test_public_build_declares_v2_parameters(self):
        bars=range_bars(180)
        history={
            'schema':'MARKET-HISTORY-V1',
            'rights_status':'verified_publishable',
            'provider':'unit-test',
            'instruments':{'SP500':{'bars':bars}},
        }
        universe={
            'benchmarks':[],
            'major_indices':[{'id':'SP500','type':'index','name':'S&P 500 Index'}],
            'sector_systems':{},
        }
        result=build(history, universe)
        params=result['parameters']
        self.assertEqual(params['template'], 'RANGE-TEMPLATE-V2')
        self.assertEqual(params['small']['window'], 45)
        self.assertEqual(params['small']['min_days'], 30)
        self.assertEqual(params['small']['break_confirm'], 3)
        self.assertEqual(params['large']['window'], 120)
        self.assertEqual(params['large']['min_days'], 80)
        self.assertEqual(params['large']['break_confirm'], 4)
        self.assertTrue(result['instruments']['SP500']['boxes'])

    def test_cfg_matches_personal_terminal_contract(self):
        self.assertEqual(CFG['small']['max_width_pct'], 18.0)
        self.assertEqual(CFG['large']['max_width_pct'], 45.0)
        self.assertEqual(CFG['small']['merge_gap'], 20)
        self.assertEqual(CFG['large']['merge_gap'], 45)


if __name__ == '__main__':
    unittest.main()
