"""python -m unittest tests/test_podklady_pamatek.py: přerušené stažení listu DMP ani výpadek Commons nerozbijí podklady památek (bez sítě)."""
import io, json, os, shutil, sys, tempfile, types, unittest, urllib.request, zipfile
from unittest import mock
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pamatky'))
CWD = os.getcwd()
# bez mesto.json města: podvržené geo a ukázkové město jen pro import (podklady_laser navíc přepne do kořene repa)
GEO = types.SimpleNamespace(LON0=15.0, LAT0=50.0, KX=71000.0, KY=111000.0, MESTO={})
with mock.patch.dict(sys.modules, {'geo': GEO}), mock.patch.dict(os.environ, {'IZO_MESTO': os.path.join(ROOT, 'priklady', 'mesto.json')}):
    import podklady_laser as L, podklady_fotky as F
os.chdir(CWD)

ATOM = (b'<feed><entry><georss:polygon>50 15 51 15 51 16 50 16</georss:polygon>'
        b'<id>DMP1G-SJTSK_AB12.xml</id></entry></feed>')


def odpoved(b):
    return mock.Mock(read=lambda: b)


def zip_laz():
    z = io.BytesIO()
    with zipfile.ZipFile(z, 'w') as f: f.writestr('AB12.laz', b'x' * 1000)
    return z.getvalue()


class LaserTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.chdir(self.d); self.addCleanup(shutil.rmtree, self.d, True)

    def tearDown(self):
        os.chdir(CWD)

    def stahni(self):
        # patch.object na modul, který podklady_laser opravdu používá (síť se nesmí dotknout)
        with mock.patch.object(L.urllib.request, 'urlopen', lambda req, timeout: odpoved(ATOM if 'atom' in req.full_url else zip_laz())):
            L.listy(15.2, 50.2, 15.3, 50.3)

    def test_prerusene_rozbaleni_nenecha_laz(self):
        def prerus(self_, path):
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, 'AB12.laz'), 'wb') as f: f.write(b'x' * 10)
            raise KeyboardInterrupt
        with mock.patch.object(zipfile.ZipFile, 'extractall', prerus), self.assertRaises(KeyboardInterrupt): self.stahni()
        self.assertFalse(os.path.exists('build/dmp/AB12.laz'))
        self.stahni()
        self.assertEqual(os.path.getsize('build/dmp/AB12.laz'), 1000, 'další běh list stáhne celý')
        self.assertEqual(os.listdir('build/dmp/rozbaleno'), [])

    def test_useknuty_seznam_se_smaze(self):
        os.makedirs('build/dmp')
        with open('build/dmp/atom.xml', 'wb') as f: f.write(ATOM[:-20])
        with self.assertRaises(SystemExit): L.listy(15.2, 50.2, 15.3, 50.3)
        self.assertFalse(os.path.exists('build/dmp/atom.xml'))


class FotkyTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, t, True)
        os.makedirs(os.path.join(t, 'pamatky'))
        with open(os.path.join(t, 'pamatky', 'kostel.json'), 'w', encoding='utf-8') as f: json.dump({'nazev': 'Kostel'}, f)
        self.fd = os.path.join(t, 'out', 'kostel', 'fotky'); os.makedirs(self.fd)
        for n in ('01', '02'): Image.new('RGB', (4, 4)).save(os.path.join(self.fd, n + '.jpg'))
        self.zdroje = [{'soubor': '01.jpg'}, {'soubor': '02.jpg'}]
        with open(os.path.join(self.fd, 'zdroje.json'), 'w', encoding='utf-8') as f: json.dump(self.zdroje, f)
        self.p = [mock.patch.object(F, 'ROOT', t), mock.patch.object(F, 'OUT', os.path.join(t, 'out')),
                  mock.patch.object(F, 'info', lambda ts: {x: {'url': 'u', 'descriptionurl': 'c'} for x in ts})]
        for p in self.p: p.start()

    def tearDown(self):
        for p in self.p: p.stop()

    def stare_zustaly(self):
        self.assertEqual(sorted(os.listdir(self.fd)), ['01.jpg', '02.jpg', 'zdroje.json'])
        with open(os.path.join(self.fd, 'zdroje.json'), encoding='utf-8') as f: self.assertEqual(json.load(f), self.zdroje)

    def test_vypadek_stahovani_necha_stare(self):
        with mock.patch.object(F, 'get', mock.Mock(side_effect=RuntimeError('opakovaně 429/5xx'))):
            F.run('kostel', vyber=['a.jpg'])
        self.stare_zustaly()

    def test_vypadek_api_necha_stare(self):
        with mock.patch.object(F, 'info', mock.Mock(side_effect=RuntimeError('opakovaně 429/5xx'))), self.assertRaises(RuntimeError):
            F.run('kostel', znovu=True, vyber=['a.jpg'])
        self.stare_zustaly()

    def test_uspech_nahradi(self):
        b = io.BytesIO(); Image.new('RGB', (8, 8)).save(b, 'JPEG')
        with mock.patch.object(F, 'get', lambda u: b.getvalue()):
            F.run('kostel', vyber=['a.jpg'])
        self.assertEqual(sorted(f for f in os.listdir(self.fd) if f.endswith('.jpg')), ['01.jpg', '_arch.jpg'])
        with open(os.path.join(self.fd, 'zdroje.json'), encoding='utf-8') as f: self.assertEqual([z['soubor'] for z in json.load(f)], ['01.jpg'])


if __name__ == '__main__':
    unittest.main()
