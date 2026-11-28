"""Tvar střechy z laseru (nastroje/tvary_strech.py) na syntetických bodech: rovina, sedlo, valba, dům do L, málo bodů."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import shapely
from shapely import affinity

spec = importlib.util.spec_from_file_location('tvary_strech', Path(__file__).resolve().parents[1] / 'nastroje/tvary_strech.py')
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

UHEL = 30                                     # dům natočený, ať se testují i osy
DUM = affinity.rotate(shapely.box(-6, -4, 6, 4), UHEL, origin=(0, 0))   # 12 × 8 m


def body(vyska, krok=0.9, sum=0.05):
    """body v půdorysu zmenšeném o 0,5 m (~1,2 bodu/m² jako DMP 1G); vyska(s, t) v souřadnicích domu"""
    s, t = [g.ravel() for g in np.meshgrid(np.arange(-5.5, 5.6, krok), np.arange(-3.5, 3.6, krok))]
    z = 300 + vyska(s, t) + np.random.default_rng(1).normal(0, sum, len(s))
    a = np.radians(UHEL)
    return np.column_stack([s * np.cos(a) - t * np.sin(a), s * np.sin(a) + t * np.cos(a), z])


def smer(dil):
    """úhel hřebene dílu ve ° od osy x, 0–179"""
    return round(np.degrees(dil[1])) % 180


def body_l(krok=0.9):
    """dům do L: hlavní křídlo 12 × 8 m s hřebenem podél x, k němu na sever křídlo 4 × 6 m s hřebenem podél y (horní obálka)"""
    p = shapely.union(shapely.box(-6, -4, 6, 4), shapely.box(2, 4, 6, 10))
    x, y = [g.ravel() for g in np.meshgrid(np.arange(-6, 6, krok), np.arange(-4, 10, krok))]
    m = shapely.contains_xy(p.buffer(-0.5), x, y); x, y = x[m], y[m]
    hl = np.where(np.abs(y) <= 4, 4 - np.abs(y), 0)
    kr = np.where((np.abs(x - 4) <= 2) & (y >= -4), 2 - np.abs(x - 4), 0)
    return p, np.column_stack([x, y, 300 + 5 + 0.8 * np.maximum(hl, kr) + np.random.default_rng(1).normal(0, 0.05, len(x))])


class TvarStrechyTest(unittest.TestCase):
    def test_rovina(self):
        self.assertEqual(ts.tvar(DUM, body(lambda s, t: 6 + 0 * s), zem=294)[0], 'flat')

    def test_sedlo_podel_delsi(self):
        r, sklon, D, _ = ts.tvar(DUM, body(lambda s, t: 9 - 0.8 * np.abs(t)), zem=294)
        self.assertEqual((r, len(D), smer(D[0])), ('gabled', 1, UHEL))
        self.assertAlmostEqual(sklon, 39, delta=3)
        self.assertAlmostEqual(D[0][2], 12, delta=0.5)        # délka podél hřebene

    def test_sedlo_podel_kratsi(self):
        r, _, D, _ = ts.tvar(DUM, body(lambda s, t: 9 - 0.8 * np.abs(s)), zem=294)
        self.assertEqual((r, smer(D[0])), ('gabled', UHEL + 90))

    def test_valba(self):
        self.assertEqual(ts.tvar(DUM, body(lambda s, t: 9 - 0.8 * np.maximum(np.abs(t), np.abs(s) - 2)), zem=294)[0], 'hipped')

    def test_dum_do_l(self):
        p, b = body_l()
        r, _, D, _ = ts.tvar(p, b, zem=294)
        self.assertEqual(r, 'gabled')
        self.assertEqual(sorted(smer(d) for d in D), [0, 90])  # hlavní křídlo podél x, boční podél y

    def test_malo_bodu_je_nejiste(self):
        self.assertIsNone(ts.tvar(DUM, body(lambda s, t: 9 - 0.8 * np.abs(t), krok=3), zem=294)[0])

    def test_body_u_zeme_se_zahodi(self):
        b = body(lambda s, t: 9 - 0.8 * np.abs(t)); b[::8, 2] = 294.3     # dvůr pod posunutým půdorysem
        self.assertEqual(ts.tvar(DUM, b, zem=294)[0], 'gabled')

    def test_posunuty_pudorys(self):
        b = body(lambda s, t: 9 - 0.8 * np.abs(t)); b[:, :2] += [0.7, -0.6]   # půdorys z Overture vedle laseru
        r, _, D, _ = ts.tvar(DUM, b, zem=294)
        self.assertEqual((r, smer(D[0])), ('gabled', UHEL))

    def test_velky_sum_je_nejisty(self):
        self.assertIsNone(ts.tvar(DUM, body(lambda s, t: 6 + 0 * s, sum=1.0), zem=294)[0])


if __name__ == '__main__':
    unittest.main()
