import json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.stage_data import validate

class StaticSiteTests(unittest.TestCase):
    def test_sites_present_and_have_honest_status(self):
        for file in ('index.html','research-hub.html','structure-lab.html','cycle-lab.html'):
            s=(ROOT/'docs'/file).read_text(encoding='utf-8')
            self.assertIn('<html',s)
            self.assertIn('</body>',s)
        self.assertIn('news_history.json',(ROOT/'docs/index.html').read_text(encoding='utf-8'))
        self.assertIn('structure_lab.json',(ROOT/'docs/structure-lab.html').read_text(encoding='utf-8'))
        self.assertFalse((ROOT/'docs/data/structure_lab.json').exists(), 'New repo MUST NOT ship vendor history without source rights.')
    def test_static_links_and_assets(self):
        for file in ('research-hub.html','structure-lab.html','cycle-lab.html'):
            s=(ROOT/'docs'/file).read_text(encoding='utf-8')
            for target in re.findall(r'(?:(?:href|src)=)["\']([^"\']+)["\']',s):
                if target.startswith(('http:','https:','#','data:')):continue
                target=target.split('#',1)[0].split('?',1)[0]
                if target.startswith('./') and target:
                    self.assertTrue((ROOT/'docs'/target[2:]).exists(),f'{file}: {target}')
    def test_news_archive_is_original_real_short_archive(self):
        x=json.loads((ROOT/'docs/data/news_history.json').read_text(encoding='utf-8'))
        rows=x.get('history',[])
        self.assertTrue(rows)
        self.assertEqual(len({r['date'] for r in rows}),len(rows))
        self.assertTrue(all('reaction_adjusted' in r for r in rows))
    def test_no_synthetic_history_accepted_for_empty_inputs(self):
        with self.assertRaises(ValueError):validate({'schema':'STRUCTURE-LAB-V1','instruments':{}})

if __name__=='__main__':unittest.main()
