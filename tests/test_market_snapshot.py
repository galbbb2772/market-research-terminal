import datetime,unittest
from tools.build_market_snapshot import build

def bars(base,growth=1.0,n=40):
    out=[]
    d=datetime.date(2026,1,2)
    for i in range(n):
        c=base+i*growth
        out.append([(d+datetime.timedelta(days=i)).isoformat(),c-.2,c+.5,c-.5,c,1000+i,c])
    return out

class MarketSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.universe={'benchmarks':[{'id':'SPY'},{'id':'QQQ'}],'major_indices':[],'sector_systems':{}}

    def test_builds_returns_volatility_and_relative_spy(self):
        history={'schema':'MARKET-HISTORY-V1','provider':'test-fixture','rights_status':'verified_internal_only','instruments':{'SPY':{'bars':bars(100,1)},'QQQ':{'bars':bars(100,2)}}}
        out=build(history,self.universe)
        self.assertEqual(out['schema'],'MARKET-SNAPSHOT-V1')
        rows={x['id']:x for x in out['rows']}
        self.assertEqual(set(rows),{'SPY','QQQ'})
        self.assertAlmostEqual(rows['SPY']['relative_to_spy_20d'],0.0,places=9)
        self.assertGreater(rows['QQQ']['relative_to_spy_20d'],0)
        self.assertIsNotNone(rows['QQQ']['volatility_20d'])
        self.assertGreaterEqual(rows['QQQ']['activity_score'],0)
        self.assertLessEqual(rows['QQQ']['activity_score'],100)

    def test_rejects_noncanonical_symbol(self):
        history={'schema':'MARKET-HISTORY-V1','instruments':{'AAPL':{'bars':bars(100)}}}
        with self.assertRaises(ValueError):build(history,self.universe)

if __name__=='__main__':unittest.main()
