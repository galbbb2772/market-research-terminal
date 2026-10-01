import datetime as dt
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.enrich_cycle_research import enrich, relative_weekly_returns, autocorrelation_rows


def bars(mult=1.0, phase=0.0, n=520, volume=1_000_000):
    out=[]
    day=dt.date(2024,1,2)
    while len(out)<n:
        if day.weekday()<5:
            i=len(out)
            trend=100*(1+0.0006*i)
            cyc=1+0.015*math.sin(i/13+phase)
            c=trend*cyc*mult
            out.append([day.isoformat(),c*.998,c*1.006,c*.994,c,volume])
        day+=dt.timedelta(days=1)
    return out


class CycleResearchTests(unittest.TestCase):
    def test_weekly_relative_returns_and_lags(self):
        s=bars(1.0,.8)
        p=bars(1.0,0)
        series=relative_weekly_returns(s,p)
        self.assertGreater(len(series),80)
        lags=autocorrelation_rows(series)
        self.assertEqual(len(lags),26)
        self.assertEqual(lags[0]['lag_weeks'],1)
        self.assertGreaterEqual(lags[0]['pairs'],20)
        self.assertTrue(lags[0]['correlation'] is None or -1<=lags[0]['correlation']<=1)

    def test_enrich_adds_sector_rotation_and_box_stats(self):
        structure={'schema':'STRUCTURE-LAB-V1','news_tension':[{'date':'2026-01-01'}],'instruments':{
            'SPY':{'group':'benchmark','bars':bars(1.0,0),'boxes':[]},
            'XLK':{'group':'sector','bars':bars(1.0,.6),'boxes':[{'scale':'small','days':25,'end_at':'2025-01-01'}]},
            'XLF':{'group':'sector','bars':bars(1.0,1.7),'boxes':[{'scale':'small','days':40,'end_at':'2025-02-01'},{'scale':'large','days':75,'end_at':'2025-03-01'}]},
            'XLE':{'group':'sector','bars':bars(1.0,2.6),'boxes':[{'scale':'large','days':95,'end_at':'2025-04-01'}]},
        }}
        out=enrich(structure)
        c=out['cycle_research']
        self.assertEqual(c['status'],'research_only')
        self.assertEqual(set(c['sectors']),{'XLK','XLF','XLE'})
        self.assertEqual(c['boxes']['small']['completed_n'],2)
        self.assertEqual(c['boxes']['large']['completed_n'],2)
        self.assertIn(c['leadership']['status'],{'descriptive_4w_relative_to_spy','insufficient_cross_section'})
        if c['leadership']['history']:
            self.assertIn(c['leadership']['latest']['leader'],{'XLK','XLF','XLE'})
            self.assertGreaterEqual(c['leadership']['switch_count'],0)

if __name__=='__main__':unittest.main()
