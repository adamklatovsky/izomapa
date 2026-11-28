"""python tests/test_stahovani.py: data_all/ musí pokrývat mapu a přerušené stahování nenechá rozbitý soubor (bez sítě)."""
import os, pathlib, subprocess, sys, tempfile, unittest
from unittest import mock
import pyarrow as pa
from nastroje import overture

ROOT = pathlib.Path(__file__).resolve().parent.parent


def tabulka(boxy):
    return pa.table({'bbox': [dict(zip(('xmin', 'xmax', 'ymin', 'ymax'), b)) for b in boxy]})


class PokrytiTest(unittest.TestCase):
    def test_pokryva(self):
        self.assertTrue(overture.pokryva([14, 15, 50, 51], [14.2, 14.8, 50.2, 50.8]))
        self.assertTrue(overture.pokryva([14, 15, 50, 51], [14, 15, 50, 51]))
        self.assertFalse(overture.pokryva([14, 15, 50, 51], [14.2, 15.1, 50.2, 50.8]))   # mapa zvětšená na východ
        self.assertFalse(overture.pokryva([14, 15, 50, 51], [16, 17, 49, 50]))           # jiné město

    def test_rozsah_je_uvnitr_dotazu(self):
        dotaz = [14, 15, 50, 51]
        prvky = [(13.9, 14.05, 50.5, 50.6), (14.95, 15.2, 50.1, 50.2), (14.5, 14.5, 49.98, 50.02), (14.4, 14.6, 50.97, 51.3)]
        r = overture.rozsah([tabulka(prvky[:2]), tabulka(prvky[2:]), tabulka([])])
        self.assertEqual(r, [14.05, 14.95, 50.02, 50.97])
        self.assertTrue(overture.pokryva(dotaz, r))
        self.assertIsNone(overture.rozsah([tabulka([])]))


class PrerusenyZapisTest(unittest.TestCase):
    def test_parquet_po_preruseni_nezustane(self):
        d = tempfile.mkdtemp(); f = os.path.join(d, 'building.parquet')

        def preruseny(tb, cil):
            with open(cil, 'wb') as fh: fh.write(b'PAR1useknut')
            raise KeyboardInterrupt
        with mock.patch('pyarrow.parquet.write_table', preruseny), self.assertRaises(KeyboardInterrupt):
            overture.zapis(tabulka([]), f)
        self.assertFalse(os.path.exists(f))
        overture.zapis(tabulka([(1, 2, 3, 4)]), f)
        self.assertEqual(sorted(os.listdir(d)), ['building.parquet'])   # zbytek po přerušení přepsal další zápis
        import pyarrow.parquet as pq
        self.assertEqual(pq.read_table(f).num_rows, 1)


@unittest.skipIf(os.name == 'nt', 'podvržený curl je shellový skript')
class DmpFetchTest(unittest.TestCase):
    def spust(self, curl, atom=None):
        d = tempfile.mkdtemp(); b = os.path.join(d, 'bin'); os.makedirs(b); os.makedirs(os.path.join(d, 'build/dmp'))
        open(os.path.join(b, 'curl'), 'w').write('#!/bin/sh\n' + curl); os.chmod(os.path.join(b, 'curl'), 0o755)
        if atom: open(os.path.join(d, 'build/dmp/atom.xml'), 'w').write(atom)
        env = dict(os.environ, PATH=b + os.pathsep + os.environ['PATH'])
        p = subprocess.run([sys.executable, str(ROOT / 'dmp_fetch.py')], cwd=d, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(d, 'build/dmp/atom.xml')))
        return p

    def test_useknuty_seznam_listu_nezustane(self):
        # curl zapíše půlku a skončí chybou (vypršel čas, -m)
        self.spust('while [ "$1" != -o ]; do shift; done; printf "<feed><entry>" > "$2"; exit 28\n')

    def test_list_se_rozbali_az_cely(self):
        d = tempfile.mkdtemp(); b = os.path.join(d, 'bin'); os.makedirs(b); os.makedirs(os.path.join(d, 'data'))
        import pyarrow.parquet as pq, zipfile
        pq.write_table(pa.table({'id': ['b1'], 'bbox': [{'xmin': 14.1, 'xmax': 14.2, 'ymin': 50.1, 'ymax': 50.2}]}), os.path.join(d, 'data/building.parquet'))
        open(os.path.join(d, 'feed.xml'), 'w').write('<feed><entry><georss:polygon>50 14 50 15 51 15 51 14</georss:polygon>'
                                                    '<id>DMP1G-SJTSK_AB12.xml</id></entry>\n</feed>\n')
        with zipfile.ZipFile(os.path.join(d, 'list.zip'), 'w') as z: z.writestr('AB12.laz', b'laz')
        open(os.path.join(b, 'curl'), 'w').write(f'#!/bin/sh\nwhile [ "$1" != -o ]; do shift; done\n'
                                                 f'case "$3" in *.xml) cp {d}/feed.xml "$2";; *) cp {d}/list.zip "$2";; esac\n')
        os.chmod(os.path.join(b, 'curl'), 0o755)
        os.makedirs(os.path.join(d, 'build/dmp/rozbaleno'))
        open(os.path.join(d, 'build/dmp/rozbaleno/STARY.laz'), 'w').write('useknutý zbytek')
        p = subprocess.run([sys.executable, str(ROOT / 'dmp_fetch.py')], cwd=d, capture_output=True, text=True,
                           env=dict(os.environ, PATH=b + os.pathsep + os.environ['PATH']))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(d, 'build/dmp'))), ['AB12.laz', 'atom.xml', 'rozbaleno'])
        self.assertEqual(os.listdir(os.path.join(d, 'build/dmp/rozbaleno')), [])

    def test_useknuty_seznam_z_drivejska_se_smaze(self):
        self.assertIn('useknutý', self.spust('exit 1\n', atom='<feed><entry>useknuto').stderr)


if __name__ == '__main__': unittest.main()
