"""Doplněk vlacek: jízdní řád -> klíčové body jízdy po okruhu (overlay_hook.postav s falešným grafem silnic)."""
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('vlacek_hook', ROOT / 'doplnky/vlacek/overlay_hook.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


class RovnyGraf:
    """path(): přímka přes body; jako road_route.Graph začíná čára v zadaném bodě první zastávky (tady 5 m mimo silnici)
    a pak vede po silnici; vrací i vzdálenosti zastávek po čáře"""
    fails = 0

    def path(self, pts):
        line = [(pts[0][0], pts[0][1] - 5)] + list(pts)
        d = [5.0]
        for a, b in zip(pts, pts[1:]): d.append(d[-1] + math.dist(a, b))
        return line, d


to_xy = lambda la, lo: (lo * 1000.0, la * 1000.0)      # 1 stupeň = 1 km, ať se dobře počítá
to_ll = lambda x, y: (y / 1000.0, x / 1000.0)


def data(**kw):
    raw = {'rychlost': 15, 'rychlost_max': 25, 'stani_s': 30,
           'zastavky': [{'nazev': 'A', 'lat': 0, 'lon': 0}, {'nazev': 'B', 'lat': 0, 'lon': 1}, {'nazev': 'C', 'lat': 0, 'lon': 2}],
           'smery': [{'zastavky': [0, 1, 2], 'jizdy': [['10:00', '10:04', '10:08'], ['12:00', '12:04', '12:08']]},
                     {'zastavky': [2, 0], 'jizdy': [['10:30', '10:40'], ['12:30', '12:40']]}]}
    raw.update(kw)
    return raw


class TestVlacek(unittest.TestCase):
    def test_cas(self):
        self.assertEqual(H.cas('10:05'), 36300)

    def test_jizda_stoji_a_drzi_rychlost(self):
        v, vmax = 15 / 3.6, 25 / 3.6
        kf = H.jizda([0, 1000, 2000], [0, 240, 480], v, vmax, 30)
        self.assertEqual(kf[0], [0.0, 0])
        for (t0, s0), (t1, s1) in zip(kf, kf[1:]):
            self.assertGreaterEqual(t1, t0)
            if s1 > s0: self.assertLessEqual((s1 - s0) / (t1 - t0), vmax + 1e-9)
        # na mezilehlé zastávce stojí (dva body se stejnou s) a z ní neodjede před časem jízdního řádu
        stani = [(a, b) for a, b in zip(kf, kf[1:]) if a[1] == b[1] == 1000]
        self.assertTrue(stani and stani[0][1][0] >= 240)
        # pomalá jízda: rychlost nejméně 0,7·v, i když jízdní řád dává víc času
        kf = H.jizda([0, 100], [0, 3600], v, vmax, 30)
        self.assertGreaterEqual(100 / (kf[-1][0] - kf[0][0]), 0.7 * v - 1e-9)

    def test_postav_okruh(self):
        out = H.postav(data(), RovnyGraf(), to_xy, to_ll)
        # okruh A-B-C-A po silnici; kus od bodu zastávky k silnici (5 m) se zahodí
        self.assertAlmostEqual(out['L'], 4000.0, delta=0.01)
        self.assertEqual(out['t0'], 36000)
        self.assertEqual(out['P'], 7200)
        kf = out['kf']
        self.assertTrue(all(0 <= t < out['P'] for t, _ in kf))
        self.assertEqual([t for t, _ in kf], sorted(t for t, _ in kf))
        self.assertAlmostEqual(kf[-1][1], out['L'], delta=1)          # zpáteční jízda končí na konci okruhu
        self.assertEqual(len(out['trasa']), 4)                         # A, B, C, A bez bodu mimo silnici

    def test_spatny_pocet_casu(self):
        raw = data()
        raw['smery'][0]['jizdy'][0] = ['10:00', '10:04']
        with self.assertRaises(ValueError):
            H.postav(raw, RovnyGraf(), to_xy, to_ll)

    def test_neuplna_data(self):
        self.assertIsNone(H.postav({'zastavky': [], 'smery': []}, RovnyGraf(), to_xy, to_ll))

    def test_ukazka(self):
        raw = json.loads((ROOT / 'priklady/vlacek.sample.json').read_text(encoding='utf-8'))
        self.assertTrue(raw['url'].startswith('https://'))
        for s in raw['smery']:
            for j in s['jizdy']: self.assertEqual(len(j), len(s['zastavky']))
        out = H.postav(raw, RovnyGraf(), lambda la, lo: (lo * 71000, la * 111320), lambda x, y: (y / 111320, x / 71000))
        self.assertEqual(out['P'], 153 * 60)

    def test_pres_budovy(self):
        import shapely
        dum = shapely.box(10, -5, 20, 5)
        self.assertEqual(H.pres_budovy([(0, 0), (30, 0)], [dum]), [(0, 8.0)])     # dům zmenšený o 1 m: 8 m
        self.assertEqual(H.pres_budovy([(0, 5.5), (30, 5.5)], [dum]), [])          # ulice podél zdi
        self.assertEqual(H.pres_budovy([(0, 4.5), (30, 4.5)], [dum]), [])          # do 1 m od zdi se toleruje

    @unittest.skipUnless(all((ROOT / f).is_file() for f in ('mesto.json', 'data_all/segment.parquet', 'data_all/building.parquet')),
                         'bez dat města (mesto.json, data_all)')
    def test_ukazka_neprojizdi_budovy(self):
        import sys
        def nacti(jmeno):                       # ze souboru: jiné testy dávají do sys.modules prázdný 'geo'
            sp = importlib.util.spec_from_file_location(jmeno, ROOT / f'{jmeno}.py'); m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m); return m
        puvodni = sys.modules.get('geo')
        sys.modules['geo'] = geo = nacti('geo')
        try: road_route = nacti('road_route')
        finally:
            if puvodni is None: sys.modules.pop('geo', None)
            else: sys.modules['geo'] = puvodni
        raw = json.loads((ROOT / 'priklady/vlacek.sample.json').read_text(encoding='utf-8'))
        z = raw['zastavky'][0]
        if math.dist((z['lat'], z['lon']), (geo.LAT0, geo.LON0)) > 0.2: self.skipTest('ukázka je z jiného města')
        out = H.postav(raw, road_route.Graph(str(ROOT / 'data_all/segment.parquet')),
                       lambda la, lo: tuple(float(q) for q in geo.to_local(lo, la)),
                       lambda x, y: tuple(float(q) for q in geo.to_lonlat(x, y))[::-1])
        B = H.budovy_xy(ROOT, lambda la, lo: geo.to_local(lo, la))
        self.assertTrue(B)
        self.assertEqual(H.pres_budovy([geo.to_local(lo, la) for la, lo in out['trasa']], B), [])


if __name__ == '__main__':
    unittest.main()
