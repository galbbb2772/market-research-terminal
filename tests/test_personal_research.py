import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PersonalResearchTests(unittest.TestCase):
    def test_page_mounts_full_private_research_pipeline(self):
        page = (ROOT / 'docs/personal-data.html').read_text(encoding='utf-8')
        self.assertIn('./personal-research.js', page)
        self.assertIn('./personal-tiingo.js', page)
        self.assertIn('./personal-import.js', page)
        self.assertIn('./personal-tiingo-fetch.py', page)
        self.assertIn('id="bundleFile"', page)
        self.assertIn('id="rememberBundle"', page)
        self.assertIn('id="useSavedBundle"', page)
        self.assertIn('id="forgetSavedBundle"', page)
        self.assertIn('id="savedBundleStatus"', page)
        self.assertIn('id="personalBoxes"', page)
        self.assertIn('id="activityValidationTable"', page)
        self.assertIn('id="cycleValidationTable"', page)
        self.assertIn('完整真实市场研究链', page)
        self.assertIn('本地 Tiingo Bundle', page)
        self.assertIn('常用 Bundle', page)

    def test_token_never_enters_worker_payload(self):
        js = (ROOT / 'docs/personal-tiingo.js').read_text(encoding='utf-8')
        research = (ROOT / 'docs/personal-research.js').read_text(encoding='utf-8')
        strict_worker = (ROOT / 'docs/personal-research-worker-v2.js').read_text(encoding='utf-8')
        self.assertIn("detail:{cache}", js)
        self.assertNotIn('detail:{cache,token}', js)
        self.assertIn("new Worker('./personal-research-worker-v2.js')", research)
        self.assertIn('worker.postMessage({cache})', research)
        self.assertNotIn("$('token')", research)
        self.assertNotIn("getElementById('token')", research)
        self.assertNotIn('Authorization', research)
        self.assertNotIn('localStorage', research)
        self.assertNotIn('sessionStorage', research)
        self.assertNotIn('Authorization', strict_worker)
        self.assertNotIn('localStorage', strict_worker)
        self.assertNotIn('sessionStorage', strict_worker)

    def test_local_bundle_import_has_no_token_dependency(self):
        importer = (ROOT / 'docs/personal-import.js').read_text(encoding='utf-8')
        tiingo = (ROOT / 'docs/personal-tiingo.js').read_text(encoding='utf-8')
        helper = (ROOT / 'docs/personal-tiingo-fetch.py').read_text(encoding='utf-8')
        self.assertIn('MRT-TIINGO-PERSONAL-BUNDLE-V1', importer)
        self.assertIn("new CustomEvent('mrt-personal-import'", importer)
        self.assertIn('indexedDB', importer)
        self.assertIn('DEFAULT_KEY', importer)
        self.assertIn('useSaved(true)', importer)
        self.assertIn('navigator.storage?.persist', importer)
        self.assertNotIn("$('token')", importer)
        self.assertNotIn('Authorization', importer)
        self.assertNotIn('localStorage', importer)
        self.assertNotIn('sessionStorage', importer)
        self.assertIn("addEventListener('mrt-personal-import'", tiingo)
        self.assertIn('getpass.getpass', helper)
        self.assertIn('Authorization', helper)
        self.assertIn('MRT-TIINGO-PERSONAL-BUNDLE-V1', helper)
        self.assertNotIn('"token":', helper)
        self.assertNotIn("'token':", helper)

    def test_worker_matches_registered_research_parameters(self):
        worker = (ROOT / 'docs/personal-research-worker.js').read_text(encoding='utf-8')
        strict_worker = (ROOT / 'docs/personal-research-worker-v2.js').read_text(encoding='utf-8')
        self.assertIn("ACT_LAGS=[1,5,20]", worker)
        self.assertIn('MAX_LAG=26', worker)
        self.assertIn('RESAMPLES=5000', worker)
        self.assertIn('RETURN_BOOT_BLOCK=52', worker)
        self.assertIn("detectScale(bars,'small',20,14)", worker)
        self.assertIn("detectScale(bars,'large',60,28)", worker)
        self.assertIn('shuffleBlocks', worker)
        self.assertIn('movingBootstrap', worker)
        self.assertIn('q_research_global', worker)
        self.assertIn('block_permutation_p', worker)
        self.assertIn('bootstrap_ci95', worker)
        self.assertIn('RESAMPLES=5000', strict_worker)
        self.assertIn('movingClusterBootstrap', strict_worker)
        self.assertIn('q_condition_family', strict_worker)
        self.assertIn('split_excesses', strict_worker)
        self.assertIn('cycle_survivors', strict_worker)
        self.assertIn('applyResearchGlobal', strict_worker)

    def test_renderer_uses_research_wide_fdr_gate(self):
        js = (ROOT / 'docs/personal-research.js').read_text(encoding='utf-8')
        self.assertIn('q_research_global', js)
        self.assertIn('q<=.10', js)
        self.assertIn('spl.length>=2', js)
        self.assertIn('survives_research_wide_checks', js)
        self.assertIn('q_condition_family', js)
        self.assertIn('split_excesses', js)
        self.assertIn('cycle_survivors', js)


if __name__ == '__main__':
    unittest.main()
