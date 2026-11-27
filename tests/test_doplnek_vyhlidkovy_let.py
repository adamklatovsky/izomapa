"""Doplněk „Vyhlídkový let“ (doplnky/vyhlidkovy_let): build hook – dráha (vlastní / z doplňku letiste), místa, vypnutí."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _hook():
    spec = importlib.util.spec_from_file_location('let_hook', ROOT / 'doplnky' / 'vyhlidkovy_let' / 'overlay_hook.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVyhlidkovyLet(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = Path(self.td.name)
        (self.tmp / 'assets' / 'doplnky').mkdir(parents=True)
        (self.tmp / 'mista.json').write_text(json.dumps([
            {'nazev': 'Hrad', 'lat': 50.41, 'lon': 14.90, 'text': ''},
            {'nazev': 'Letiště Mladá Boleslav', 'lat': 50.39, 'lon': 14.89, 'text': ''},
        ]), encoding='utf-8')
        self.cwd = os.getcwd(); os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd); self.td.cleanup()

    def _ctx(self):
        return {'data_file': self.tmp / 'assets' / 'doplnky' / 'vyhlidkovy_let.json', 'assets_dir': self.tmp / 'assets',
                'mesto': {'ctverce': [[0, 0]]}, 'plugin_config': {'nazev': 'Vyhlídkový let'}}

    def test_bez_letiste_start_ve_vzduchu(self):
        out = _hook().build_overlay(self._ctx())
        self.assertNotIn('draha', out)
        self.assertEqual([m['n'] for m in out['mista']], ['Hrad'])      # letiště samo není cíl

    def test_draha_z_doplnku_letiste(self):
        (self.tmp / 'assets' / 'doplnky' / 'letiste.json').write_text(json.dumps({
            'drahy': [{'ref': '05/23', 'a': [50.3952702, 14.8931922], 'b': [50.4000228, 14.9002772], 'sirka': 24}],
            'aktivni': {'draha': '05/23', 'od': 'b'}}), encoding='utf-8')
        out = _hook().build_overlay(self._ctx())
        self.assertEqual(out['draha']['a'], [50.4000228, 14.9002772])   # rozjezd od konce „b“ aktivní dráhy

    def test_vlastni_draha_a_vypnuti(self):
        f = self._ctx()['data_file']
        f.write_text(json.dumps({'nazev': 'Andula', 'draha': {'a': [50.0, 14.0], 'b': [50.01, 14.01]}}), encoding='utf-8')
        out = _hook().build_overlay(self._ctx())
        self.assertEqual(out['nazev'], 'Andula')
        self.assertEqual(out['draha']['b'], [50.01, 14.01])
        f.write_text(json.dumps({'enabled': False}), encoding='utf-8')
        self.assertFalse(_hook().build_overlay(self._ctx()))

    def test_bez_mist_se_nezapne(self):
        (self.tmp / 'mista.json').write_text('[]', encoding='utf-8')
        self.assertFalse(_hook().build_overlay(self._ctx()))


if __name__ == '__main__':
    unittest.main()
