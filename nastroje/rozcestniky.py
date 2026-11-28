# turistické rozcestníky z OpenStreetMap (Overpass, ODbL, bez registrace) -> assets/rozcestniky.json: [[lat, lon, název, výška m n. m. nebo null]]
# OSM tourism=information + information=guidepost (rozcestníky KČT); prohlížeč je kreslí jako sloupek se žlutou tabulkou, klik ukáže název
# spouštět z kořene repa: python nastroje/rozcestniky.py
import json, re, subprocess, sys; sys.path.insert(0, '.')
import geo

if __name__ == '__main__':
    x0, y0, x1, y1 = geo.extent(geo.MARGIN + 20)
    lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1); b = f'{la0},{lo0},{la1},{lo1}'
    q = f'[out:json][timeout:60];node["tourism"="information"]["information"="guidepost"]({b});out;'
    t = None
    for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter'):   # záložní server
        try:
            t = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', 'izomapa-tools/1.0', '--data-urlencode', f'data={q}', url],
                               check=True, capture_output=True, text=True).stdout; break
        except subprocess.CalledProcessError: continue
    if t is None: sys.exit('Overpass nedostupný, zkus to později')
    out = []
    for e in json.loads(t)['elements']:
        if 'lat' not in e: continue
        tg = e.get('tags', {})
        m = re.match(r'\s*(\d+(?:[.,]\d+)?)', tg.get('ele', '') or '')
        out.append([round(e['lat'], 6), round(e['lon'], 6), tg.get('name') or tg.get('ref') or 'Turistický rozcestník', round(float(m.group(1).replace(',', '.'))) if m else None])
    out.sort()
    json.dump(out, open('assets/rozcestniky.json', 'w'), ensure_ascii=False)
    print('rozcestníků', len(out), 's názvem', sum(1 for v in out if v[2] != 'Turistický rozcestník'), 's výškou', sum(1 for v in out if v[3]))
