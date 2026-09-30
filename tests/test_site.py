import json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.stage_data import validate

class StaticSiteTests(unittest.TestCase):
    def test_sites_present_and_have_honest_status(self):
        pages=('index.html','research-hub.html','structure-lab.html','cycle-lab.html','api-status.html','sector-map.html','instrument.html','news-archive.html')
        for file in pages:
            s=(ROOT/'docs'/file).read_text(encoding='utf-8')
            self.assertIn('<html',s)
            self.assertIn('</body>',s)
        self.assertIn('news_history.json',(ROOT/'docs/index.html').read_text(encoding='utf-8'))
        structure=(ROOT/'docs/structure-lab.html').read_text(encoding='utf-8')
        self.assertIn('structure_lab.json',structure)
        self.assertIn('id="currentBox"',structure)
        self.assertIn('底部区',structure)
        self.assertIn('顶部区',structure)
        self.assertIn('x[5]==null&&b[5]==null?null',structure)
        self.assertFalse((ROOT/'docs/data/structure_lab.json').exists(),'Repo must not ship unapproved structure history.')

    def test_static_links_and_assets(self):
        for file in ('index.html','research-hub.html','structure-lab.html','cycle-lab.html','api-status.html','sector-map.html','instrument.html','news-archive.html'):
            s=(ROOT/'docs'/file).read_text(encoding='utf-8')
            for target in re.findall(r'(?:(?:href|src)=)["\']([^"\']+)["\']',s):
                if target.startswith(('http:','https:','#','data:')):continue
                target=target.split('#',1)[0].split('?',1)[0]
                if target.startswith('./') and target:
                    self.assertTrue((ROOT/'docs'/target[2:]).exists(),f'{file}: {target}')

    def test_market_universe_is_etf_and_index_only(self):
        x=json.loads((ROOT/'docs/data/market_universe.json').read_text(encoding='utf-8'))
        self.assertEqual(x['scope'],'ETF_AND_MAJOR_INDEX_ONLY')
        self.assertTrue(x['exclude']['individual_stocks'])
        self.assertTrue(x['exclude']['delisted_stocks'])
        self.assertEqual({r['id'] for r in x['benchmarks']},{'SPY','QQQ','DIA'})
        self.assertEqual({r['id'] for r in x['major_indices']},{'SP500','NDX','NASDAQ_COMPOSITE','DJIA'})
        sp=x['sector_systems']['sp500']['items']
        self.assertEqual(len(sp),11)
        self.assertEqual({r['id'] for r in sp},{'XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'})
        self.assertTrue(all(r.get('id') or r.get('status')=='taxonomy_only' for r in x['sector_systems']['nasdaq100']['items']))

    def test_market_contract_schemas_are_valid_json(self):
        for file in ('market_snapshot.schema.json','market_history.schema.json'):
            x=json.loads((ROOT/'docs/data'/file).read_text(encoding='utf-8'))
            self.assertIn('$schema',x)
            self.assertIn('properties',x)

    def test_new_pages_do_not_embed_fake_market_history(self):
        for file in ('index.html','sector-map.html','instrument.html'):
            text=(ROOT/'docs'/file).read_text(encoding='utf-8').lower()
            self.assertNotIn('demo data',text)
            self.assertNotIn('mock data',text)
        self.assertFalse((ROOT/'docs/data/market_history.json').exists(),'Do not commit market history before display rights are approved.')

    def test_news_archive_is_original_real_short_archive(self):
        x=json.loads((ROOT/'docs/data/news_history.json').read_text(encoding='utf-8'))
        rows=x.get('history',[])
        self.assertTrue(rows)
        self.assertEqual(len({r['date'] for r in rows),len(rows)))
        self.assertTrue(all('reaction_adjusted' in r for r in rows))

    def test_no_synthetic_history_accepted_for_empty_inputs(self):
        with self.assertRaises(ValueError):validate({'schema':'STRUCTURE-LAB-V1','instruments':{}})

if __name__=='__main__':unittest.main()
