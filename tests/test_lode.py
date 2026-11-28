"""Doplněk lode: build hook (doplnky/lode/overlay_hook.py) a ukázková data priklady/lode.sample.json."""
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lode_hook', ROOT / 'doplnky/lode/overlay_hook.py')
hook = importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
SAMPLE = json.loads((ROOT / 'priklady/lode.sample.json').read_text(encoding='utf-8'))


def m(a, b):                                   # vzdálenost dvou [lat, lon] v metrech (stačí na pár km)
    return math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])))


def in_water(p, rings):                        # sudo-liché pravidlo přes všechny prstence (ostrovy jsou díry), stejně jako lode.js
    c = False
    for r in rings:
        for i in range(len(r)):
            (yi, xi), (yj, xj) = r[i], r[i - 1]
            if (yi > p[0]) != (yj > p[0]) and p[1] < (xj - xi) * (p[0] - yi) / (yj - yi) + xi:
                c = not c
    return c


def run(data):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / 'lode.json'
        if data is not None:
            f.write_text(json.dumps(data), encoding='utf-8')
        return hook.build_overlay({'data_file': f})


class HookTest(unittest.TestCase):
    def test_stromy_plazi_ze_scen_ctvercu(self):
        # pláž 10 × 10 m kolem počátku (lat = y, lon = x), dva čtverce po 200 m; strom na pláži, u ní, daleko, v pásu souseda a druhu 2
        with tempfile.TemporaryDirectory() as d:
            sc = {(0, 0): [[2, 3, 1.0, 12, 0, 0], [20, 0, 1.0, 8, 1], [90, 90, 1.0, 10, 0, 0], [3, 3, 1.0, 5, 0, 2]],
                  (1, 0): [[-102, 0, 1.0, 9, 0, 0], [-90, 0, 1.0, 9, 0, 0]]}   # -102: pás souseda (x 98), -90: x 110 u druhé pláže
            for c, T in sc.items():
                Path(d, f'c{c[0]}').mkdir()
                Path(d, f'c{c[0]}', 'scene.json').write_text(json.dumps({'trees': T}), encoding='utf-8')
            out = hook.stromy_plazi([{'q': [[-5, -5], [-5, 5], [5, 5], [5, -5]]}, {'q': [[-5, 85], [5, 85], [5, 95], [-5, 95]]}], lambda lon, lat: (lon, lat), sc,
                                    lambda c: f'{d}/c{c[0]}', lambda c: (c[0] * 200.0, 0.0), 100.0)
        self.assertEqual(sorted(t[:2] for t in out), [[2, 3], [20, 0], [110, 0]])   # strom x 98 je v čtverci (1, 0) jen v pásu souseda
        self.assertEqual(next(t for t in out if t[0] == 2), [2, 3, 1.0, 12, 0, 0])

    def test_bez_souboru_nebo_vody_se_vypne(self):
        self.assertFalse(run(None))
        self.assertFalse(run({'parniky': []}))
        self.assertFalse(run({'voda': [[[50, 14], [50, 14.1]]]}))
        self.assertFalse(run({**SAMPLE, 'enabled': False}))

    def test_preda_jen_znama_data(self):
        out = run({**SAMPLE, 'pozn': 'x', 'parniky': SAMPLE['parniky'] + [{'trasa': [[50, 14]]}]})
        self.assertEqual(set(out), {'voda', 'parniky', 'pujcovny', 'plachetnice', 'kajaky', 'plaze', 'zima'})
        self.assertEqual(len(out['parniky']), len(SAMPLE['parniky']))   # trasa s jedním bodem vypadne


class UkazkaTest(unittest.TestCase):
    def test_trasa_parniku_vede_po_vode(self):
        voda, mola = SAMPLE['voda'], [z for p in SAMPLE['parniky'] for z in p['zastavky']]
        for p in SAMPLE['parniky']:
            tr = p['trasa'] + [p['trasa'][0]]
            for a, b in zip(tr, tr[1:]):
                n = max(1, int(m(a, b) // 10))
                for k in range(n + 1):
                    q = [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]
                    if min(m(q, z) for z in mola) > 40:   # u mola (i cizí zastávky) smí být na břehu
                        self.assertTrue(in_water(q, voda), (p['nazev'], q))

    def test_zastavky_pujcovny_a_plaze_jsou_u_vody(self):
        voda = SAMPLE['voda']
        bod_u_vody = lambda c, r: any(in_water([c[0] + dy / 111320, c[1] + dx / 70700], voda) for dx in range(-r, r + 1, 5) for dy in range(-r, r + 1, 5))
        for p in SAMPLE['parniky']:
            for z in p['zastavky']:
                self.assertTrue(min(m(z, q) for q in p['trasa']) < 30, z)
        for P in SAMPLE['pujcovny']:
            self.assertTrue(bod_u_vody(P['q'], 30), P)
        for P in SAMPLE['plaze']:
            self.assertTrue(any(bod_u_vody(q, 10) for q in P['q']), P['nazev'])
        for P in SAMPLE['zima']['bruslari']:
            self.assertTrue(bod_u_vody(P['q'], 30), P['nazev'])

    def test_kajaky_maji_kde_jezdit(self):
        # lode.js: domov kajaku u půjčovny nebo pláže, pás 5–30 m od břehu a víc než 25 m od trasy parníku, do 150 m od domova
        k = SAMPLE['kajaky']['pocet']
        self.assertIsInstance(k, int); self.assertGreater(k, 0)
        voda = SAMPLE['voda']
        def seg(p, a, b):
            bx, by = (b[1] - a[1]) * 70700, (b[0] - a[0]) * 111320
            px, py = (p[1] - a[1]) * 70700, (p[0] - a[0]) * 111320
            t = max(0, min(1, (px * bx + py * by) / (bx * bx + by * by or 1)))
            return math.hypot(px - t * bx, py - t * by)
        breh = [(r[i - 1], r[i]) for r in voda for i in range(len(r))]
        trasy = [(t[i - 1], t[i]) for p in SAMPLE['parniky'] for t in [p['trasa']] for i in range(1, len(t))]
        doma = [P['q'] for P in SAMPLE['pujcovny']] + [[sum(q[0] for q in P['q']) / len(P['q']), sum(q[1] for q in P['q']) / len(P['q'])] for P in SAMPLE['plaze']]
        for h in doma:
            ok = sum(1 for dx in range(-150, 151, 15) for dy in range(-150, 151, 15)
                     for q in [[h[0] + dy / 111320, h[1] + dx / 70700]]
                     if math.hypot(dx, dy) <= 150 and in_water(q, voda) and 5 <= min(seg(q, a, b) for a, b in breh) <= 30
                     and min(seg(q, a, b) for a, b in trasy) > 25)
            self.assertGreater(ok, 3, h)

    def test_lide_na_plazi_maji_misto(self):
        for P in SAMPLE['plaze']:
            n = P.get('lezaci', 0)
            self.assertIsInstance(n, int); self.assertGreaterEqual(n, 0)
            lat, lon = [q[0] for q in P['q']], [q[1] for q in P['q']]
            body = [[a, b] for a in [min(lat) + (max(lat) - min(lat)) * i / 20 for i in range(21)] for b in [min(lon) + (max(lon) - min(lon)) * j / 20 for j in range(21)]]
            souso = sum(1 for q in body if in_water(q, [P['q']]) and not in_water(q, SAMPLE['voda']))   # v polygonu pláže a na suchu
            self.assertGreater(souso, 20, P['nazev'])


if __name__ == '__main__':
    unittest.main()
