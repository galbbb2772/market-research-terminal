import json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.stage_data import validate as validate_structure
from tools.build_market_snapshot import validate_history, canonical_ids

class StaticSiteTests(unittest.TestCase):
    def test_sites_present_and_have_honest_status(self):
        pages=('index.html','research-hub.html','structure-lab.html','cycle-lab.html','theme-rotation.html','personal-data.html','api-status.html','sector-map.html','instrument.html','news-archive.html')
        for file in pages:
            s=(ROOT/'docs'/file).read_text(encoding='utf-8')
            self.assertIn('<html',s)
            self.assertIn('</body>',s)
        self.assertIn('news_history.json',(ROOT/'docs/index.html').read_text(encoding='utf-8'))
        self.assertIn('personal-data.html',(ROOT/'docs/index.html').read_text(encoding='utf-8'))
        self.assertIn('theme-rotation.html',(ROOT/'docs/index.html').read_text(encoding='utf-8'))
        structure=(ROOT/'docs/structure-lab.html').read_text(encoding='utf-8')
        self.assertIn('structure_lab.json',structure)
        self.assertIn('id="currentBox"',structure)
        self.assertIn('底部区',structure)
        self.assertIn('顶部区',structure)
        self.assertIn('x[5]==null&&b[5]==null?null',structure)
        cycle=(ROOT/'docs/cycle-lab.html').read_text(encoding='utf-8')
        self.assertIn('id="selectedValidation"',cycle)
        self.assertIn('id="validationGlobal"',cycle)
        self.assertIn('Benjamini-Hochberg',cycle)
        self.assertIn('保留候选',cycle)
        self.assertIn('未获支持',cycle)

    def test_personal_tiingo_mode_is_browser_private(self):
        page=(ROOT/'docs/personal-data.html').read_text(encoding='utf-8')
        js=(ROOT/'docs/personal-tiingo.js').read_text(encoding='utf-8')
        importer=(ROOT/'docs/personal-import.js').read_text(encoding='utf-8')
        self.assertIn('PRIVATE TIINGO DATA',page)
        self.assertIn('本地 Tiingo Bundle',page)
        self.assertIn('Token 不会保存',js)
        self.assertIn("Authorization:'Token '+token",js)
        self.assertNotIn('localStorage',js)
        self.assertNotIn('sessionStorage',js)
        self.assertNotIn('localStorage',importer)
        self.assertNotIn('sessionStorage',importer)
        self.assertNotIn('TIINGO_API_TOKEN=',page)
        self.assertNotIn('TIINGO_API_TOKEN=',js)
        self.assertNotIn('TIINGO_API_TOKEN=',importer)
        all_tickers=('SPY','QQQ','DIA','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY','SMH','BOTZ','SKYY','CIBR','FINX','DRIV','LIT','ICLN','TAN','URA','ITA','XBI','ARKG','ESPO','PAVE')
        for ticker in all_tickers:
            self.assertIn("'"+ticker+"'",js)
            self.assertIn("'"+ticker+"'",importer)

    def test_theme_rotation_page_and_worker(self):
        page=(ROOT/'docs/theme-rotation.html').read_text(encoding='utf-8')
        worker=(ROOT/'docs/personal-theme-worker.js').read_text(encoding='utf-8')
        renderer=(ROOT/'docs/personal-theme-research.js').read_text(encoding='utf-8')
        loader=(ROOT/'docs/theme-rotation-loader.js').read_text(encoding='utf-8')
        self.assertIn('美股题材轮动研究',page)
        self.assertIn('./personal-theme-research.js',page)
        self.assertIn('./theme-rotation-loader.js',page)
        self.assertIn('ACT_LAGS=[1,5,20]',worker)
        self.assertIn('MAX_LAG=26',worker)
        self.assertIn("SMH:'半导体'",worker)
        self.assertIn("BOTZ:'机器人/AI'",worker)
        self.assertIn('top_transitions',worker)
        self.assertIn('singleWeekRelativeRows',worker)
        self.assertIn("cycle_basis:'single_week_relative_to_spy'",worker)
        self.assertIn('不重叠的单周相对SPY收益',worker)
        self.assertIn("new Worker('./personal-theme-worker.js?v=20261001-singleweek')",renderer)
        self.assertIn('三段历史',renderer)
        self.assertIn('不重叠的单周相对SPY收益',page)
        self.assertIn("DB_NAME='mrt-personal-local-data'",loader)
        self.assertNotIn('localStorage',loader)
        self.assertNotIn('sessionStorage',loader)

    def test_static_links_and_assets(self):
        for file in ('index.html','research-hub.html','structure-lab.html','cycle-lab.html','theme-rotation.html','personal-data.html','api-status.html','sector-map.html','instrument.html','news-archive.html'):
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

    def test_absent_or_authorized_real_history_only(self):
        universe=json.loads((ROOT/'docs/data/market_universe.json').read_text(encoding='utf-8'))
        history_path=ROOT/'docs/data/market_history.json'
        structure_path=ROOT/'docs/data/structure_lab.json'
        snapshot_path=ROOT/'docs/data/market_snapshot.json'
        if history_path.exists():
            history=json.loads(history_path.read_text(encoding='utf-8'))
            self.assertEqual(history.get('rights_status'),'verified_publishable')
            validate_history(history,canonical_ids(universe))
            self.assertTrue(all(src.get('rights_status')=='verified_publishable' for src in history.get('sources',[])))
        if structure_path.exists():
            self.assertTrue(history_path.exists(),'Structure requires approved market history')
            structure=json.loads(structure_path.read_text(encoding='utf-8'))
            self.assertEqual(structure.get('rights_status'),'verified_publishable')
            self.assertTrue(validate_structure(structure))
            self.assertEqual(set(structure['instruments']),set(history['instruments']))
        if snapshot_path.exists():
            self.assertTrue(history_path.exists(),'Snapshot requires approved market history')
            snap=json.loads(snapshot_path.read_text(encoding='utf-8'))
            self.assertEqual(snap.get('rights_status'),'verified_publishable')
            self.assertEqual({r['id'] for r in snap.get('rows',[])},set(history['instruments']))

    def test_new_pages_do_not_embed_fake_market_history(self):
        for file in ('index.html','sector-map.html','instrument.html','personal-data.html','theme-rotation.html'):
            text=(ROOT/'docs'/file).read_text(encoding='utf-8').lower()
            self.assertNotIn('demo data',text)
            self.assertNotIn('mock data',text)

    def test_news_archive_is_original_real_short_archive(self):
        x=json.loads((ROOT/'docs/data/news_history.json').read_text(encoding='utf-8'))
        rows=x.get('history',[])
        self.assertTrue(rows)
        self.assertEqual(len({r['date'] for r in rows}),len(rows))
        self.assertTrue(all('reaction_adjusted' in r for r in rows))

    def test_no_synthetic_history_accepted_for_empty_inputs(self):
        with self.assertRaises(ValueError):validate_structure({'schema':'STRUCTURE-LAB-V1','instruments':{}})

if __name__=='__main__':unittest.main()
