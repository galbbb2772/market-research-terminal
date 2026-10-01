import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PersonalResearchTests(unittest.TestCase):
    def test_page_mounts_full_private_research_pipeline(self):
        page = (ROOT / 'docs/personal-data.html').read_text(encoding='utf-8')
        self.assertIn('./personal-research.js', page)
        self.assertIn('id="personalBoxes"', page)
        self.assertIn('id="activityValidationTable"', page)
        self.assertIn('id="cycleValidationTable"', page)
        self.assertIn('完整真实市场研究链', page)

    def test_token_never_enters_worker_payload(self):
        js = (ROOT / 'docs/personal-tiingo.js').read_text(encoding='utf-8')
        research = (ROOT / 'docs/personal-research.js').read_text(encoding='utf-8')
        self.assertIn("detail:{cache}", js)
        self.assertNotIn('detail:{cache,token}', js)
        self.assertIn("new Worker('./personal-research-worker.js')", research)
        self.assertIn('worker.postMessage({cache})', research)
        self.assertNotIn('token', research.lower())

    def test_worker_matches_registered_research_parameters(self):
        worker = (ROOT / 'docs/personal-research-worker.js').read_text(encoding='utf-8')
        self.assertIn("ACT_LAGS=[1,5,20]", worker)
        self.assertIn('MAX_LAG=26', worker)
        self.assertIn('RESAMPLES=200', worker)
        self.assertIn("detectScale(bars,'small',20,14)", worker)
        self.assertIn("detectScale(bars,'large',60,28)", worker)
        self.assertIn('shuffleBlocks', worker)
        self.assertIn('movingBootstrap', worker)
        self.assertIn('q_research_global', worker)
        self.assertIn('block_permutation_p', worker)
        self.assertIn('bootstrap_ci95', worker)

    def test_renderer_uses_research_wide_fdr_gate(self):
        js = (ROOT / 'docs/personal-research.js').read_text(encoding='utf-8')
        self.assertIn('q_research_global', js)
        self.assertIn('q<=.10', js)
        self.assertIn('spl.length>=2', js)
        self.assertIn('survives_research_wide_checks', js)


if __name__ == '__main__':
    unittest.main()
