import datetime as dt
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_structure_lab import build, detect_boxes
from tools.stage_data import validate


def flat_bars(n=80, volume=None):
    out=[]
    day=dt.date(2026,1,2)
    while len(out)<n:
        if day.weekday()<5:
            i=len(out)
            c=100+1.8*math.sin(i/2.3)
            out.append([day.isoformat(),c-.2,c+1.1,c-1.1,c,volume])
        day+=dt.timedelta(days=1)
    return out


class StructureBuilderTests(unittest.TestCase):
    def test_detection_is_not_moved_backward_by_future_rows(self):
        first=flat_bars(45,None)
        a=detect_boxes(first)
        self.assertTrue(a)
        earliest=min(x['detected_at'] for x in a)
        future=first+[[
            (dt.date.fromisoformat(first[-1][0])+dt.timedelta(days=i+1)).isoformat(),
            125,126,124,125,None
        ] for i in range(5)]
        b=detect_boxes(future)
        self.assertEqual(earliest,min(x['detected_at'] for x in b))

    def test_index_null_volume_is_valid_structure_data(self):
        bars=flat_bars(70,None)
        history={'schema':'MARKET-HISTORY-V1','rights_status':'verified_internal_only','provider':'unit-test','instruments':{'SP500':{'bars':bars}}}
        universe={'benchmarks':[],'major_indices':[{'id':'SP500','type':'index','name':'S&P 500 Index'}],'sector_systems':{}}
        result=build(history,universe)
        self.assertIsNone(result['instruments']['SP500']['bars'][0][5])
        self.assertTrue(validate(result))

    def test_scores_are_bounded_and_detection_follows_start(self):
        for box in detect_boxes(flat_bars(80,1_000_000)):
            self.assertLessEqual(box['start_at'],box['detected_at'])
            self.assertTrue(all(0<=v<=10 for v in box['scores'].values()))

if __name__=='__main__':unittest.main()
