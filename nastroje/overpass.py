# dotaz na Overpass API (OpenStreetMap, ODbL, bez registrace): nastroje/hriste.py, kominy.py, prejezdy.py, cyklotrasy_osm.py
import json, subprocess, sys, time

URL = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter']


def overpass(dotaz, pokusu=6, pauza=20):
    """odpověď Overpassu jako dict s 'elements'; Overpass bývá přetížený, proto střídá hlavní a záložní server.
    Když neuspěje ani jeden pokus, skončí přes sys.exit se srozumitelnou hláškou (SystemExit jde odchytit)."""
    for pokus in range(pokusu):
        url = URL[pokus % 2]
        try:
            t = subprocess.run(['curl', '-s', '-f', '-m', '150', '-A', 'izomapa-tools/1.0', '--data-urlencode', f'data={dotaz}', url],
                               check=True, capture_output=True, text=True, encoding='utf-8').stdout
            d = json.loads(t); d['elements']
            return d
        except subprocess.CalledProcessError as ex:     # curl -f: HTTP chyba nebo timeout = server přetížený
            print(url, 'nedostupný, curl', ex.returncode, flush=True)
        except (ValueError, KeyError, TypeError) as ex:  # odpověď přišla, ale není to JSON s elements
            print(url, 'vrátil chybnou odpověď:', str(ex)[:120], t[:200], flush=True)
        if pokus + 1 < pokusu: time.sleep(pauza)
    sys.exit('Overpass nedostupný, zkus to později')
