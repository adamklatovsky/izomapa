import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import plugins  # noqa: E402


def _load_vzor_server():
    spec = importlib.util.spec_from_file_location(
        'vzor_server', ROOT / 'priklady/doplnek_vzor/server/python/vzor_server.py'
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dummy_project_xy(lat: float, lon: float, is_world: bool = False):
    return [round(lon * 100.0, 1), round(lat * 100.0, 1)]


class TestPluginsCore(unittest.TestCase):
    def test_empty_plugins_zero_bloat_and_host_api(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            site = tmp / 'site'
            build = tmp / 'build'
            server_root = tmp / 'site_server'
            plugins_dir = tmp / 'doplnky'
            assets.mkdir()
            plugins_dir.mkdir()

            res = plugins.load_and_run_plugins(
                {'nazev': 'TestCity'},
                {'mpp': 0.2, 'w': 2000, 'h': 1000},
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )
            self.assertEqual(res, {})
            self.assertFalse(server_root.exists())
            self.assertFalse((site / 'doplnky').exists())

        overlay_py = (ROOT / 'overlay.py').read_text(encoding='utf-8')
        self.assertIn('load_and_run_plugins', overlay_py)
        self.assertIn("**({'doplnky': _doplnky} if _doplnky else {})", overlay_py)

        app_html = (ROOT / 'web/app.html').read_text(encoding='utf-8')
        for method in (
            'getPluginData',
            'getPluginConfig',
            'registerPlugin',
            'onMapClick',
            'setClickCapture',
            'setCursor',
            'setPinsVisible',
            'getPluginLayer',
            'getView',
            'panTo',
            'getEnvironment',
            'setEnvironment',
            'getUiSlot',
        ):
            self.assertIn(method, app_html)
        self.assertIn('window.Izomapa', app_html)

    def test_config_precedence_and_autodiscovery(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            plugins_dir = tmp / 'doplnky'
            vzor_dir = plugins_dir / 'vzor_doplnku'
            vzor_dir.mkdir(parents=True)
            assets.mkdir()
            shutil.copytree(ROOT / 'priklady/doplnek_vzor', vzor_dir, dirs_exist_ok=True)
            shutil.copy2(vzor_dir / 'vzor_doplnku.sample.json', assets / 'vzor_doplnku.json')

            # 1) Auto-discovery: bez assets/doplnky.json se aktivuje vzor_doplnku v client režimu
            active = plugins.discover_plugin_configs({'nazev': 'Test'}, assets, plugins_dir)
            self.assertIn('vzor_doplnku', active)

            # 2) Vypnutí v mesto.json zabrání auto-discovery
            active_off = plugins.discover_plugin_configs(
                {'nazev': 'Test', 'doplnky': {'vzor_doplnku': {'enabled': False}}},
                assets,
                plugins_dir,
            )
            self.assertNotIn('vzor_doplnku', active_off)

            # 3) assets/doplnky.json přepisuje mesto.json
            (assets / 'doplnky.json').write_text(
                json.dumps({'vzor_doplnku': {'enabled': True, 'mode': 'server', 'server_url': '/api/vzor.php'}}),
                encoding='utf-8',
            )
            active_override = plugins.discover_plugin_configs(
                {'nazev': 'Test', 'doplnky': {'vzor_doplnku': {'enabled': False}}},
                assets,
                plugins_dir,
            )
            self.assertEqual(active_override['vzor_doplnku']['mode'], 'server')

    def test_vzor_client_and_server_modes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            site = tmp / 'site'
            build = tmp / 'build'
            server_root = tmp / 'site_server'
            plugins_dir = tmp / 'doplnky'
            vzor_dir = plugins_dir / 'vzor_doplnku'
            assets.mkdir()
            vzor_dir.mkdir(parents=True)
            shutil.copytree(ROOT / 'priklady/doplnek_vzor', vzor_dir, dirs_exist_ok=True)
            shutil.copy2(vzor_dir / 'vzor_doplnku.sample.json', assets / 'vzor_doplnku.json')

            cam = {'mpp': 0.2, 'w': 4000, 'h': 2000}

            # Client režim (auto-discovery)
            res_client = plugins.load_and_run_plugins(
                {'nazev': 'Test'},
                cam,
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )
            self.assertIn('vzor_doplnku', res_client)
            q0 = res_client['vzor_doplnku']['data']['levels'][0]['questions'][0]
            self.assertEqual(q0['radius_px'], 175.0)
            self.assertIn('xy', q0)
            self.assertTrue((site / 'doplnky/vzor_doplnku/vzor.js').is_file())
            self.assertTrue((site / 'doplnky/vzor_doplnku/vzor.css').is_file())
            self.assertFalse(server_root.exists())

            # Server režim: žádné souřadnice ani answer v overlay.json, targets.json v site_server/server_data/
            (assets / 'doplnky.json').write_text(
                json.dumps({'vzor_doplnku': {'enabled': True, 'mode': 'server', 'server_url': '/api/vzor_server.php'}}),
                encoding='utf-8',
            )
            res_server = plugins.load_and_run_plugins(
                {'nazev': 'Test'},
                cam,
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )
            pub_json = json.dumps(res_server['vzor_doplnku']['data'], ensure_ascii=False)
            for forbidden in ('"xy"', '"lat"', '"lon"', '"targets"', '"radius"', '"radius_px"', '"answer"'):
                self.assertNotIn(forbidden, pub_json)
            self.assertNotIn('server_data_out', res_server['vzor_doplnku']['config'])

            targets_file = server_root / 'server_data/vzor_doplnku.targets.json'
            self.assertTrue(targets_file.is_file())
            self.assertTrue((server_root / 'README.md').is_file())
            htaccess = (server_root / 'server_data/.htaccess').read_text(encoding='utf-8')
            self.assertIn('Require all denied', htaccess)

            targets_data = json.loads(targets_file.read_text(encoding='utf-8'))
            self.assertIn('xy', targets_data['levels'][0]['questions'][0])
            self.assertEqual(targets_data['levels'][0]['questions'][1]['targets'][0]['type'], 'polygon')

    def test_python_reference_server_hmac_and_audit_hash(self):
        vzor = _load_vzor_server()
        secret = 'super_tajny_test_klic_123456'
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            site = tmp / 'site'
            build = tmp / 'build'
            server_root = tmp / 'site_server'
            plugins_dir = tmp / 'doplnky'
            vzor_dir = plugins_dir / 'vzor_doplnku'
            assets.mkdir()
            vzor_dir.mkdir(parents=True)
            shutil.copytree(ROOT / 'priklady/doplnek_vzor', vzor_dir, dirs_exist_ok=True)
            shutil.copy2(vzor_dir / 'vzor_doplnku.sample.json', assets / 'vzor_doplnku.json')
            (assets / 'doplnky.json').write_text(
                json.dumps({'vzor_doplnku': {'enabled': True, 'mode': 'server', 'server_url': '/api/vzor_server.php'}}),
                encoding='utf-8',
            )
            plugins.load_and_run_plugins(
                {'nazev': 'Test'},
                {'mpp': 0.2, 'w': 4000, 'h': 2000},
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )
            targets = json.loads((server_root / 'server_data/vzor_doplnku.targets.json').read_text(encoding='utf-8'))

            conn = sqlite3.connect(tmp / 'test.sqlite')
            # 1) Start
            code, st = vzor.handle_action(
                {'action': 'start', 'levelId': '1', 'difficulty': 'hard', 'season': 'winter'},
                targets, conn, secret, client_ip='192.0.2.42', now_ms=1000000,
            )
            self.assertEqual(code, 200)
            ticket = st['ticket']
            order = st['order']

            # 2) Zfalšovaný ticket musí být odmítnut
            p = vzor.verify_ticket(ticket, secret)
            p['t0'] = 999999999
            forged = vzor.b64url_encode(json.dumps(p).encode('utf-8')) + '.' + ticket.split('.')[1]
            c_forged, _ = vzor.handle_action({'action': 'verify', 'x': 0, 'y': 0, 'ticket': forged}, targets, conn, secret, now_ms=1001000)
            self.assertEqual(c_forged, 403)

            # 3) Rate-limit (< 300 ms)
            c_rl, _ = vzor.handle_action({'action': 'verify', 'x': 0, 'y': 0, 'ticket': ticket}, targets, conn, secret, now_ms=1000100)
            self.assertEqual(c_rl, 429)

            # 4) Minutí nesmí prozradit targetHint ani answer
            c_miss, r_miss = vzor.handle_action({'action': 'verify', 'x': 0, 'y': 0, 'ticket': ticket}, targets, conn, secret, now_ms=1000500)
            self.assertEqual(c_miss, 200)
            self.assertFalse(r_miss['hit'])
            self.assertNotIn('targetHint', r_miss)
            self.assertNotIn('answer', r_miss)
            ticket = r_miss['ticket']

            # 5) Zásahy podle vylosovaného pořadí (bod i polygon)
            qs = targets['levels'][0]['questions']
            t_ms = 1001500
            for q_idx in order:
                q = qs[q_idx]
                if 'xy' in q:
                    hx, hy = q['xy']
                else:
                    pts = q['targets'][0]['points']
                    hx = sum(pt[0] for pt in pts) / len(pts)
                    hy = sum(pt[1] for pt in pts) / len(pts)
                c_hit, r_hit = vzor.handle_action({'action': 'verify', 'x': hx, 'y': hy, 'ticket': ticket}, targets, conn, secret, now_ms=t_ms)
                self.assertEqual(c_hit, 200)
                self.assertTrue(r_hit['hit'])
                self.assertIn('targetHint', r_hit)
                self.assertIn('answer', r_hit)
                ticket = r_hit['ticket']
                t_ms += 1000

            self.assertTrue(r_hit['completed'])

            # 6) Finish a ověření 12znakového audit_hash + absence surové IP
            c_fin, r_fin = vzor.handle_action(
                {'action': 'finish', 'nickname': 'Tester', 'tickets': [ticket]},
                targets, conn, secret, client_ip='192.0.2.42', now_ms=t_ms + 500,
            )
            self.assertEqual(c_fin, 200)
            self.assertTrue(r_fin['saved'])
            self.assertEqual(r_fin['rank'], 1)
            self.assertTrue(len(r_fin['certificateId']) >= 4)

            row = conn.execute('SELECT nickname, difficulty, season, audit_hash FROM scores').fetchone()
            self.assertEqual(row[0], 'Tester')
            self.assertEqual(row[1], 'hard')
            self.assertEqual(row[2], 'winter')
            self.assertEqual(len(row[3]), 12)
            self.assertEqual(row[3], vzor.compute_audit_hash('192.0.2.42', secret))

            c_lb, r_lb = vzor.handle_action({'action': 'leaderboard'}, targets, conn, secret)
            self.assertEqual(c_lb, 200)
            self.assertEqual(len(r_lb['entries']), 1)

    def test_php_reference_server_via_cli_subprocess(self):
        php_bin = shutil.which('php')
        if not php_bin:
            self.skipTest('PHP CLI není nainstalováno')

        php_script = ROOT / 'priklady/doplnek_vzor/server/php/vzor_server.php'
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            site = tmp / 'site'
            build = tmp / 'build'
            server_root = tmp / 'site_server'
            plugins_dir = tmp / 'doplnky'
            vzor_dir = plugins_dir / 'vzor_doplnku'
            assets.mkdir()
            vzor_dir.mkdir(parents=True)
            shutil.copytree(ROOT / 'priklady/doplnek_vzor', vzor_dir, dirs_exist_ok=True)
            shutil.copy2(vzor_dir / 'vzor_doplnku.sample.json', assets / 'vzor_doplnku.json')
            (assets / 'doplnky.json').write_text(
                json.dumps({'vzor_doplnku': {'enabled': True, 'mode': 'server', 'server_url': '/api/vzor_server.php'}}),
                encoding='utf-8',
            )
            plugins.load_and_run_plugins(
                {'nazev': 'Test'},
                {'mpp': 0.2, 'w': 4000, 'h': 2000},
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )

            env = {
                **os.environ,
                'IZOMAPA_PLUGIN_SECRET': 'php_test_secret_key_987',
                'IZOMAPA_TARGETS_FILE': str(server_root / 'server_data/vzor_doplnku.targets.json'),
                'IZOMAPA_DB_PATH': str(tmp / 'php_vzor.sqlite'),
            }

            def call_php(payload: dict) -> dict:
                proc = subprocess.run(
                    [php_bin, str(php_script)],
                    input=json.dumps(payload),
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                return json.loads(proc.stdout)

            # Start přes PHP CLI
            st = call_php({'action': 'start', 'levelId': '1', 'difficulty': 'easy', 'season': 'summer'})
            self.assertIn('ticket', st)
            ticket = st['ticket']

            # Minutí nesmí vrátit targetHint ani answer
            miss = call_php({'action': 'verify', 'x': -999, 'y': -999, 'ticket': ticket})
            # Pozn.: pokud proběhne do 300ms od startu, PHP vrátí rate_limit, jinak hit:false
            if miss.get('error') == 'rate_limit':
                import time
                time.sleep(0.35)
                miss = call_php({'action': 'verify', 'x': -999, 'y': -999, 'ticket': ticket})
            self.assertFalse(miss['hit'])
            self.assertNotIn('targetHint', miss)
            self.assertNotIn('answer', miss)
            ticket = miss['ticket']

            # Padělaný ticket přes PHP CLI
            bad = call_php({'action': 'verify', 'x': 0, 'y': 0, 'ticket': ticket + 'tamper'})
            self.assertEqual(bad.get('error'), 'invalid_ticket')

            # Dokončení obou otázek přes PHP CLI
            import time
            targets = json.loads((server_root / 'server_data/vzor_doplnku.targets.json').read_text(encoding='utf-8'))
            qs = targets['levels'][0]['questions']
            for q_idx in st['order']:
                time.sleep(0.35)
                q = qs[q_idx]
                if 'xy' in q:
                    hx, hy = q['xy']
                else:
                    pts = q['targets'][0]['points']
                    hx = sum(pt[0] for pt in pts) / len(pts)
                    hy = sum(pt[1] for pt in pts) / len(pts)
                hit_res = call_php({'action': 'verify', 'x': hx, 'y': hy, 'ticket': ticket})
                self.assertTrue(hit_res['hit'])
                self.assertIn('targetHint', hit_res)
                self.assertIn('answer', hit_res)
                ticket = hit_res['ticket']

            self.assertTrue(hit_res['completed'])
            fin = call_php({'action': 'finish', 'nickname': 'PhpTester', 'tickets': [ticket]})
            self.assertTrue(fin['saved'])
            self.assertIn('certificateId', fin)

            lb = call_php({'action': 'leaderboard'})
            self.assertEqual(len(lb['entries']), 1)
            self.assertEqual(lb['entries'][0]['nickname'], 'PhpTester')

            sqlite_file = tmp / 'php_vzor.sqlite'
            if sqlite_file.is_file():
                conn = sqlite3.connect(sqlite_file)
                audit_hash = conn.execute('SELECT audit_hash FROM scores').fetchone()[0]
            else:
                stored = json.loads((tmp / 'php_vzor.sqlite.json').read_text(encoding='utf-8'))
                audit_hash = stored[0]['auditHash']
            self.assertEqual(len(audit_hash), 12)

            # Sprostá přezdívka přes PHP CLI musí být odmítnuta
            bad_nick_php = call_php({'action': 'finish', 'nickname': 'Píča_123', 'tickets': [ticket]})
            self.assertEqual(bad_nick_php.get('error'), 'profanity_nickname')

    def test_profanity_filter_default_enabled_and_configurable(self):
        self.assertTrue(plugins.contains_profanity('Kurva123'))
        self.assertTrue(plugins.contains_profanity('p.i.č.a'))
        self.assertTrue(plugins.contains_profanity('p1c4'))
        self.assertTrue(plugins.contains_profanity('kokotina'))
        self.assertFalse(plugins.contains_profanity('Sekunda'))
        self.assertFalse(plugins.contains_profanity('Srnka z Teplic'))
        self.assertFalse(plugins.contains_profanity('Anonymní hledač'))
        self.assertFalse(plugins.contains_profanity('Kurva123', {'profanity_filter': False}))

        vzor = _load_vzor_server()
        secret = 'profanity_secret_key'
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / 'assets'
            site = tmp / 'site'
            build = tmp / 'build'
            server_root = tmp / 'site_server'
            plugins_dir = tmp / 'doplnky'
            vzor_dir = plugins_dir / 'vzor_doplnku'
            assets.mkdir()
            vzor_dir.mkdir(parents=True)
            shutil.copytree(ROOT / 'priklady/doplnek_vzor', vzor_dir, dirs_exist_ok=True)
            shutil.copy2(vzor_dir / 'vzor_doplnku.sample.json', assets / 'vzor_doplnku.json')
            (assets / 'doplnky.json').write_text(
                json.dumps({'vzor_doplnku': {'enabled': True, 'mode': 'server', 'server_url': '/api/vzor_server.php'}}),
                encoding='utf-8',
            )
            res = plugins.load_and_run_plugins(
                {'nazev': 'Test'},
                {'mpp': 0.2, 'w': 4000, 'h': 2000},
                _dummy_project_xy,
                assets_dir=assets,
                site_dir=site,
                build_dir=build,
                server_root=server_root,
                plugins_dir=plugins_dir,
            )
            self.assertTrue(res['vzor_doplnku']['config']['profanity_filter'])
            self.assertTrue((server_root / 'server_data/profanity.json').is_file())
            targets = json.loads((server_root / 'server_data/vzor_doplnku.targets.json').read_text(encoding='utf-8'))
            self.assertTrue(targets['profanity_filter'])

            conn = sqlite3.connect(tmp / 'prof.sqlite')
            _, st = vzor.handle_action({'action': 'start', 'levelId': '1'}, targets, conn, secret, now_ms=1000)
            ticket = st['ticket']
            t_ms = 1500
            for q_idx in st['order']:
                q = targets['levels'][0]['questions'][q_idx]
                hx, hy = q['xy'] if 'xy' in q else (sum(p[0] for p in q['targets'][0]['points']) / len(q['targets'][0]['points']), sum(p[1] for p in q['targets'][0]['points']) / len(q['targets'][0]['points']))
                _, r = vzor.handle_action({'action': 'verify', 'x': hx, 'y': hy, 'ticket': ticket}, targets, conn, secret, now_ms=t_ms)
                ticket = r['ticket']
                t_ms += 500

            c_bad, r_bad = vzor.handle_action({'action': 'finish', 'nickname': 'k.u.r.v.a', 'tickets': [ticket]}, targets, conn, secret, now_ms=t_ms + 500)
            self.assertEqual(c_bad, 400)
            self.assertEqual(r_bad['error'], 'profanity_nickname')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM scores').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
