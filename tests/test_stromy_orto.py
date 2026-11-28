import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from nastroje.stromy_orto import jehlicnan, M, koruny_stromu, vyska


def koruna(img, ci, cj, r_m, rng):
    """listnatá koruna: tmavě zelená kopule osvětlená shora, zrnitá (listí), okraj ve stínu"""
    ii, jj = np.mgrid[:img.shape[0], :img.shape[1]]
    d = np.hypot(ii - ci, jj - cj) * M / r_m
    k = d < 1
    shade = np.sqrt(np.clip(1 - d ** 2, 0, 1))
    base = np.array([50, 78, 62], float)                     # jako koruna na snímku ČÚZK: L ~70, do modrozelena
    img[k] = np.clip(base * (0.6 + 0.6 * shade[k, None]) + rng.normal(0, 9, (k.sum(), 1)), 0, 255)


class StromyOrtoTest(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(1)
        n = int(60 / M)                                            # 60 × 60 m
        self.img = np.zeros((n, n, 3), float)
        self.img[:, : n // 2] = [150, 170, 95]                     # trávník: světlý, žlutozelený, hladký
        self.img[:, n // 2:] = [120, 120, 122]                     # asfalt
        self.img += self.rng.normal(0, 1.5, self.img.shape)

    def test_travnik_a_asfalt_nic(self):
        self.assertEqual(koruny_stromu(np.clip(self.img, 0, 255).astype(np.uint8)), [])

    def test_dve_koruny_vedle_sebe_se_oddeli(self):
        # dvě koruny o poloměru 4 m, středy 7 m od sebe (koruny se překrývají), na trávníku
        c = int(30 / M); a, b = c - int(3.5 / M), c + int(3.5 / M)
        koruna(self.img, c, a, 4, self.rng); koruna(self.img, c, b, 4, self.rng)
        t = koruny_stromu(np.clip(self.img, 0, 255).astype(np.uint8))
        self.assertEqual(len(t), 2, t)
        for (i, j, r, con), sj in zip(sorted(t, key=lambda q: q[1]), (a, b)):
            self.assertLess(np.hypot(i - c, j - sj) * M, 1.5)       # střed do 1,5 m
            self.assertTrue(2.5 < r < 5, r)
            self.assertFalse(con)

    def test_vyska(self):
        self.assertAlmostEqual(vyska(3.1, False, None), 10.0)      # z koruny: renderer kreslí poloměr 0,31 h
        self.assertEqual(vyska(3.1, False, 12.0), 12.0)           # z laseru
        self.assertEqual(vyska(3.1, False, 40.0), 15.0)           # laser jen v mezích podle koruny

    def test_jehlicnan_na_snimku_bez_listi(self):
        g = np.random.default_rng(2)
        sum_ = lambda c: np.clip(np.array(c, float) + g.normal(0, 8, (200, 3)), 0, 255)
        self.assertTrue(jehlicnan(sum_([50, 72, 55])))              # borovice: tmavě zelená i v dubnu
        self.assertFalse(jehlicnan(sum_([95, 88, 80])))             # holé větve listnáče nad zemí
        self.assertFalse(jehlicnan(sum_([105, 125, 70])))           # trávník pod holým stromem: zelený, ale světlý
        self.assertFalse(jehlicnan(np.zeros((0, 3))))


if __name__ == '__main__':
    unittest.main()
