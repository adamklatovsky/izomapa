"""Doplněk pole: build hook (doplnky/pole/overlay_hook.py) a ukázková konfigurace priklady/pole.sample.json."""
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pole_hook', ROOT / 'doplnky/pole/overlay_hook.py')
hook = importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
SAMPLE = json.loads((ROOT / 'priklady/pole.sample.json').read_text(encoding='utf-8'))
KX = 111320 * math.cos(math.radians(50.58))
LOC = lambda la, lo: ((lo - 14.6) * KX, (la - 50.58) * 111320)
LL = lambda x, y: (50.58 + y / 111320, 14.6 + x / KX)


def obdelnik(x0, y0, w, h, n=1):                # [lat, lon] obdélník w × h m, na každé straně n bodů navíc (k zjednodušení)
    kx, ky = 111320 * math.cos(math.radians(50.58)), 111320
    xy = [(x0 + w * k / n, y0) for k in range(n)] + [(x0 + w, y0 + h * k / n) for k in range(n)] + \
         [(x0 + w - w * k / n, y0 + h) for k in range(n)] + [(x0, y0 + h - h * k / n) for k in range(n)]
    return [[50.58 + y / ky, 14.6 + x / kx] for x, y in xy]


class HookTest(unittest.TestCase):
    def test_stromy_u_poli(self):
        from shapely.geometry import box
        # čtverec se středem (0, 0), half 100; pole -40..60 × -20..20
        trees = [[10, 0, 1, 8, 0, 0],      # na poli (remízek)
                 [-45, -8, 1, 8, 0, 0],    # 5 m západně od pole (před ním)
                 [-5, -32, 1, 8, 0, 0],    # 12 m jižně (před polem)
                 [70, 0, 1, 8, 0, 0],      # 10 m východně, korunu přes pole nemá, ne
                 [30, 32, 1, 8, 0, 0],     # 12 m severně (za polem), ne
                 [15, 5, 1, 8, 0, 2],      # druh 2, ne
                 [-110, 0, 1, 8, 0, 0]]    # mimo vlastní čtverec (pás souseda), ne
        out = hook.stromy_u_poli([box(-40, -20, 60, 20)], [(0, 0, 100, trees)])
        self.assertEqual([t[:2] for t in out], [[10, 0], [-45, -8], [-5, -32]])

    def test_bez_konfigurace_nebo_dat_se_vypne(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = {'data_file': Path(d) / 'doplnky' / 'pole.json', 'assets_dir': Path(d)}
            self.assertFalse(hook.build_overlay(ctx))           # bez assets/doplnky/pole.json
            ctx['data_file'].parent.mkdir(); ctx['data_file'].write_text(json.dumps(SAMPLE), encoding='utf-8')
            self.assertFalse(hook.build_overlay(ctx))           # bez assets/zabaged.json

    def test_vybere_velka_pole_a_zjednodusi_je(self):
        zab = {'orna_dil': [[obdelnik(0, 0, 250, 120, 20)], [obdelnik(400, 0, 60, 60)]], 'orna_plodina': ['maize', 'wheat'],
               'ttp': [[obdelnik(0, 300, 200, 100)]], 'pole': []}
        out = hook.postav(SAMPLE, zab, LOC, LL)
        self.assertEqual(len(out['pole']), 1)                   # pole 0,36 ha je pod min_ha
        P = out['pole'][0]
        self.assertEqual(P['p'], 'maize')
        self.assertEqual(len(P['q'][0]), 4)                     # rovné strany zjednodušené na rohy
        rohy = [zab['orna_dil'][0][0][k * 20] for k in range(4)]
        self.assertTrue(all(min(math.dist(LOC(*q), LOC(*r)) for r in rohy) < 0.2 for q in P['q'][0]))
        self.assertEqual(out['louky'], [])
        self.assertEqual(len(hook.postav({**SAMPLE, 'louky': True}, zab, LOC, LL)['louky']), 1)
        self.assertEqual(out['stroje'], SAMPLE['stroje'])

    def test_orez_na_mapu(self):
        from shapely.geometry import box
        zab = {'orna_dil': [[obdelnik(0, 0, 400, 100)]], 'orna_plodina': ['wheat']}
        P = hook.postav(SAMPLE, zab, LOC, LL, box(-10, -10, 200, 200))['pole'][0]
        self.assertLess(max(LOC(*q)[0] for q in P['q'][0]), 200.2)   # půlka pole za okrajem mapy odpadne
        self.assertEqual(hook.postav(SAMPLE, zab, LOC, LL, box(390, -10, 600, 200))['pole'], [])   # zbytek pod min_ha

    def test_plodina_bez_ortofota_jako_prep(self):
        zab = {'orna_dil': [[obdelnik(0, 0, 200, 100)]], 'orna_plodina': [None]}
        p = hook.postav(SAMPLE, zab, LOC, LL)['pole'][0]['p']
        self.assertIn(p, hook.CROPS)
        self.assertEqual(p, hook.postav(SAMPLE, zab, LOC, LL)['pole'][0]['p'])

    def test_ukazka(self):
        self.assertEqual(set(SAMPLE) - {'pozn'}, {'stroje', 'min_ha', 'louky'})
        self.assertTrue(3 <= SAMPLE['stroje'] <= 6)


if __name__ == '__main__':
    unittest.main()
