"""python -m unittest tests/test_mhd.py: mhd.py na malém GTFS bez volitelných sloupců a při výpadku stahování."""
import json, os, pathlib, subprocess, sys, tempfile, unittest, zipfile

MHD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mhd.py')
GTFS = {   # bez volitelných shape_dist_traveled a trip_headsign
    'routes.txt': 'route_id,route_short_name,route_type\nR1,1,3\n',
    'trips.txt': 'route_id,service_id,trip_id,shape_id\nR1,S1,T1,SH1\n',
    'calendar.txt': 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nS1,1,1,1,1,1,1,1,20260101,20271231\n',
    'calendar_dates.txt': 'service_id,date,exception_type\n',
    'stops.txt': 'stop_id,stop_name,stop_lat,stop_lon\nZ1,První,50.0,15.0\nZ2,Druhá,50.002,15.003\n',
    'stop_times.txt': 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,08:00:00,08:00:00,Z1,1\nT1,08:05:00,08:05:00,Z2,2\n',
    'shapes.txt': 'shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nSH1,50.0,15.0,1\nSH1,50.002,15.003,2\n',
}


class Mhd(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.d = t.name
        os.makedirs(os.path.join(self.d, 'build')); os.makedirs(os.path.join(self.d, 'site'))
        self.zip = os.path.join(self.d, 'zdroj.zip')
        with zipfile.ZipFile(self.zip, 'w') as z:
            for n, t in GTFS.items(): z.writestr(n, t)

    def run_mhd(self, url):
        m = {'stred': [15.0, 50.0], 'href': 0, 'dno': -30, 'ctverce': [[0, 0]]}
        if url: m['mhd'] = {'gtfs': url}
        with open(os.path.join(self.d, 'mesto.json'), 'w', encoding='utf-8') as f: json.dump(m, f)
        env = dict(os.environ, IZO_MESTO=os.path.join(self.d, 'mesto.json'), PYTHONUTF8='1')
        return subprocess.run([sys.executable, MHD, '--stahnout'], cwd=self.d, env=env, capture_output=True, text=True, encoding='utf-8')

    def test_bez_volitelnych_sloupcu(self):
        r = self.run_mhd(pathlib.Path(self.zip).as_uri())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('VAROVÁNÍ: shapes.txt bez shape_dist_traveled', r.stdout)
        with open(os.path.join(self.d, 'site/mhd.json'), encoding='utf-8') as f: d = json.load(f)
        self.assertEqual(len(d['trips']), 1)
        self.assertEqual(d['names'][d['trips'][0][5]], 'Druhá')       # bez trip_headsign je cíl poslední zastávka

    def test_bez_gtfs_konci_normalne(self):
        r = self.run_mhd(None)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, 'site/mhd.json')))

    def test_vypadek_stahovani(self):
        spatna = pathlib.Path(self.d, 'neni.zip').as_uri()
        self.assertNotEqual(self.run_mhd(spatna).returncode, 0)       # bez starého zipu není z čeho stavět
        os.replace(self.zip, os.path.join(self.d, 'build/gtfs.zip'))
        r = self.run_mhd(spatna)                                     # starý zip zůstal: použije se s varováním
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('VAROVÁNÍ: GTFS se nepodařilo stáhnout', r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.d, 'site/mhd.json')))


if __name__ == '__main__':
    unittest.main()
