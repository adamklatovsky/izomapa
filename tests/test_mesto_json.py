import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VZOR = json.loads((ROOT / 'priklady/mesto.json').read_text(encoding='utf-8'))
ENV = {**{k: v for k, v in os.environ.items() if k != 'IZO_MESTO'}, 'PYTHONPATH': str(ROOT), 'PYTHONUTF8': '1'}


def spust(d, m, args):
    (d / 'mesto.json').write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
    return subprocess.run([sys.executable, *args], cwd=d, env=ENV, capture_output=True, text=True, encoding='utf-8')


class GeoTest(unittest.TestCase):
    """geo.py při načtení mesto.json: srozumitelná chyba místo KeyError nebo pádu až v dzi.py"""
    def chyba(self, m, *hledej):
        with tempfile.TemporaryDirectory() as td:
            r = spust(Path(td), m, ['-c', 'import geo'])
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('Traceback', r.stderr)
        for h in hledej: self.assertIn(h, r.stderr)

    def test_platny(self):
        with tempfile.TemporaryDirectory() as td:
            r = spust(Path(td), VZOR, ['-c', 'import geo; print(len(geo.CHUNKS))'])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(len(VZOR['ctverce'])))

    def test_chybi_klice(self):
        self.chyba({k: v for k, v in VZOR.items() if k not in ('href', 'dno')}, 'href', 'dno')
        self.chyba({**VZOR, 'stred': None}, 'stred')

    def test_chybi_stred_mapy(self):
        self.chyba({**VZOR, 'ctverce': [c for c in VZOR['ctverce'] if c != [0, 0]]}, '[0, 0]')

    def test_duplicitni_ctverec(self):
        self.chyba({**VZOR, 'ctverce': VZOR['ctverce'] + [[1, 0]]}, '(1, 0)')


class BuildHtmlTest(unittest.TestCase):
    def postav(self, m):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); d = Path(td.name)
        shutil.copytree(ROOT / 'web', d / 'web', ignore=shutil.ignore_patterns('__pycache__'))
        r = spust(d, m, [str(ROOT / 'build_html.py')])
        return r, (d / 'site/index.html').read_text(encoding='utf-8') if r.returncode == 0 else ''

    def test_chybi_texty(self):
        r, _ = self.postav({**{k: v for k, v in VZOR.items() if k != 'podtitul'}, 'h1': 'Chrastava'})
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('podtitul', r.stderr); self.assertIn('h1', r.stderr)

    def test_dalsi_zdroje(self):
        r, page = self.postav({**VZOR, 'dalsi_zdroje': ['Kronika obce', None, {'text': 'Zlý', 'url': 'javascript:alert(1)'},
                                                         {'url': 'https://example.cz/pasport'}, {'text': 'Technická mapa', 'url': 'https://example.cz/tm'}]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(', Kronika obce', page)
        self.assertNotIn('javascript:alert', page); self.assertIn(', Zlý', page)
        self.assertIn('<a href="https://example.cz/pasport" target="_blank" rel="noopener">https://example.cz/pasport</a>', page)
        self.assertIn('<a href="https://example.cz/tm" target="_blank" rel="noopener">Technická mapa</a>', page)

    def test_zdroj_mhd(self):
        mhd = {'gtfs': 'https://example.cz/gtfs.zip', 'zdroj': 'DPMX'}
        r, page = self.postav({**VZOR, 'mhd': {**mhd, 'zdroj_url': 'https://example.cz/'}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('jízdní řády MHD © <a href="https://example.cz/" target="_blank" rel="noopener">DPMX</a>', page)
        r, page = self.postav({**VZOR, 'mhd': mhd})        # bez zdroj_url: dřív KeyError
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('jízdní řády MHD © DPMX', page)


if __name__ == '__main__': unittest.main()
