"""Doplněk „Rychlostní zkouška“ (doplnky/rz): build hook a kódování trati v odkazu."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import plugins  # noqa: E402


def _hook():
    spec = importlib.util.spec_from_file_location('rz_hook', ROOT / 'doplnky' / 'rz' / 'overlay_hook.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDoplnekRz(unittest.TestCase):
    def _ctx(self, tmp: Path, data=None, mesto=None):
        f = tmp / 'rz.json'
        if data is not None:
            f.write_text(json.dumps(data), encoding='utf-8')
        return {'data_file': f, 'mesto': mesto or {'ctverce': [[0, 0], [1, 0]], 'polovina': 1000}}

    def test_bez_dat_jen_stavba_trati(self):
        with tempfile.TemporaryDirectory() as td:
            out = _hook().build_overlay(self._ctx(Path(td)))
            self.assertEqual(out['ctverce'], [[0, 0], [1, 0]])
            self.assertEqual(out['polovina'], 1000.0)
            self.assertNotIn('trat', out)

    def test_pripravena_trat_a_vypnuti(self):
        with tempfile.TemporaryDirectory() as td:
            data = json.loads((ROOT / 'doplnky' / 'rz' / 'priklady' / 'rz.json').read_text(encoding='utf-8'))
            out = _hook().build_overlay(self._ctx(Path(td), data))
            t = out['trat']
            self.assertEqual(t['kola'], 2)
            self.assertTrue(3500 < t['delka'] < 4500, t['delka'])          # městská RZ Bohemia Rally: 2 × ~1,9 km
            self.assertRegex(t['tabulka'], r'^[a-z0-9-]{1,40}$')
            self.assertFalse(_hook().build_overlay(self._ctx(Path(td), {**data, 'enabled': False})))

    def test_nesmyslna_trat_se_vynecha(self):
        with tempfile.TemporaryDirectory() as td:
            out = _hook().build_overlay(self._ctx(Path(td), {'trasa': [[50.0, 14.0], [50.0001, 14.0]]}))
            self.assertNotIn('trat', out)

    def test_zavadec_zkopiruje_skripty_a_knihovny(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / 'assets').mkdir()
            (tmp / 'assets' / 'doplnky.json').write_text('{"rz": true}', encoding='utf-8')
            res = plugins.load_and_run_plugins({'nazev': 'Test', 'ctverce': [[0, 0]]}, {'mpp': 0.2, 'w': 100, 'h': 100}, lambda la, lo, *a: [lo, la],
                                               assets_dir=tmp / 'assets', site_dir=tmp / 'site', build_dir=tmp / 'build',
                                               plugins_dir=ROOT / 'doplnky', libs_dir=ROOT / 'knihovny')
            self.assertIn('rz', res)
            self.assertTrue((tmp / 'site' / 'doplnky' / 'rz' / 'rz.js').is_file())
            self.assertTrue(any('server_client' in s for s in res['rz']['lib_scripts']))

    @unittest.skipUnless(shutil.which('node'), 'chybí node')
    def test_kodovani_trati_v_odkazu(self):
        js = (ROOT / 'doplnky' / 'rz' / 'rz.js').read_text(encoding='utf-8')
        a, b = js.index('const kodTrat'), js.index('const hashStr')
        prog = js[a:b] + '''
          const body = [[50.41203, 14.90428], [50.41488, 14.91012], [50.40999, 14.9001]];
          const k = kodTrat(body, 2, true), d = dekodTrat(k);
          console.log(JSON.stringify({ k, d, spatne: dekodTrat('x') }));'''
        out = json.loads(subprocess.run(['node', '-e', prog], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out['d']['kola'], 2)
        self.assertTrue(out['d']['okruh'])
        self.assertEqual(out['d']['body'], [[50.41203, 14.90428], [50.41488, 14.91012], [50.40999, 14.9001]])
        self.assertIsNone(out['spatne'])


if __name__ == '__main__':
    unittest.main()
