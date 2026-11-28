import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from nastroje.tenis import tenis_mrizka


class TenisMrizkaTest(unittest.TestCase):
    def test_jeden_kurt(self):
        self.assertEqual(tenis_mrizka(36, 18), (1, 1))

    def test_kurty_vedle_sebe_podel_delsi_strany(self):
        # tři kurty bokem k sobě: plocha 51 × 34, délka kurtu podél kratší strany plochy
        self.assertEqual(tenis_mrizka(51, 34), (-1, 3))

    def test_kurty_za_sebou(self):
        # dva kurty za sebou (konec na konec): 68 × 17
        self.assertEqual(tenis_mrizka(68, 17), (2, 1))

    def test_ctyri_kurty_dva_krat_dva(self):
        self.assertEqual(tenis_mrizka(68, 34), (2, 2))

    def test_mala_plocha_je_jeden_kurt(self):
        # v datech jen hrací plocha bez výběhu
        self.assertEqual(tenis_mrizka(24, 11), (1, 1))


if __name__ == '__main__':
    unittest.main()
