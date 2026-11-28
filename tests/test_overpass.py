"""Dotaz na Overpass bez sítě: přetížený hlavní server -> záložní, chybná odpověď -> srozumitelná chyba."""
import subprocess, sys, unittest
from unittest import mock
sys.path.insert(0, '.')
from nastroje import overpass as op


def curl(*odpovedi):
    """podvržený subprocess.run: postupně vrací odpovědi; int = návratový kód curl (chyba)"""
    volani = []
    def run(args, **kw):
        volani.append(args[-1]); o = odpovedi[len(volani) - 1]
        if isinstance(o, int): raise subprocess.CalledProcessError(o, args)
        return subprocess.CompletedProcess(args, 0, stdout=o)
    return run, volani


class TestOverpass(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(op.time, 'sleep'); p.start(); self.addCleanup(p.stop)

    def test_zalozni_server(self):
        run, volani = curl(22, '{"elements": [{"id": 1}]}')
        with mock.patch.object(op.subprocess, 'run', run):
            self.assertEqual(op.overpass('q')['elements'], [{'id': 1}])
        self.assertEqual(volani, op.URL)

    def test_chybna_odpoved(self):
        run, volani = curl(*['<html>rate limited</html>', '{"remark": "bez elements"}'] * 3)
        with mock.patch.object(op.subprocess, 'run', run), self.assertRaises(SystemExit) as ex:
            op.overpass('q')
        self.assertIn('Overpass nedostupný', str(ex.exception.code))
        self.assertEqual(len(volani), 6)


if __name__ == '__main__':
    unittest.main()
