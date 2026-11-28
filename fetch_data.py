"""Stáhne data pro výřez: Overture Maps (S3, anonymně) + terén Terrarium (AWS Open Data).

python fetch_data.py --vse         # všechny čtverce z mesto.json + místa + městské části (první spuštění)
python fetch_data.py --chunk -1,0  # čtverec mapy s rezervou 300 m -> data_c-1_0/ (čtverec 0,0 -> data/)
python fetch_data.py --places      # názvy a firmy (Overture places) pro karty budov -> data/places.parquet
python fetch_data.py --deleni      # městské části a osady (Overture divisions) -> data_all/division_area.parquet
"""
import json, math, os, subprocess, sys, time
import pyarrow.dataset as ds, pyarrow.parquet as pq
import geo
from nastroje import overture      # vydání Overture (když vyzkoušené z S3 zmizí, vezme se nejnovější)
from nastroje import orto          # stažení přes dočasný soubor s kontrolou obrázku (useknutá dlaždice se stáhne znovu)
LAYERS = [('buildings', 'building'), ('transportation', 'segment'), ('base', 'land_use'), ('base', 'water'),
          ('base', 'land_cover'), ('base', 'infrastructure'), ('base', 'land'), ('addresses', 'address')]


def tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def dem(D, X0, X1, Y0, Y1, z=14):
    """terén Terrarium (AWS Open Data) pro výřez"""
    os.makedirs(f'{D}/dem', exist_ok=True)
    tx0, ty0 = tile(X0, Y1, z); tx1, ty1 = tile(X1, Y0, z)
    for x in range(tx0, tx1 + 1):
        for y in range(ty0, ty1 + 1):
            url = f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
            if not orto.ortofoto(f'{D}/dem/{z}_{x}_{y}.png', url): sys.exit(f'terén se nestáhl: {url}')


if sys.argv[1:2] == ['--vse']:
    # Overture se prohledává po celém světě (pomalé), proto každou vrstvu jednou pro celou mapu a čtverce se z ní vyříznou lokálně
    os.makedirs('data_all', exist_ok=True)
    X0, X1, Y0, Y1 = geo.bbox_lonlat(400)
    # Stažená data_all/ z menší mapy (novy_mesto.py --max 4) nebo jiného města (--prepsat) by novým čtvercům dala výřez
    # bez budov: bbox.json je obdélník, který stažené vrstvy pokrývají; starší data_all bez něj se posoudí podle prvků
    B = 'data_all/bbox.json'
    hotove = [f'data_all/{typ}.parquet' for _, typ in LAYERS if os.path.exists(f'data_all/{typ}.parquet')]
    try: stazeno = json.load(open(B, encoding='utf-8'))
    except (OSError, ValueError): stazeno = overture.rozsah([pq.read_table(f, columns=['bbox']) for f in hotove])
    if not hotove or not stazeno or not overture.pokryva(stazeno, geo.bbox_lonlat(300)):   # 300 m: výřez čtverce níž
        if hotove: print('data_all/ nepokrývá celou mapu (zvětšená mapa nebo jiné město), vrstvy, místa a části obce se stáhnou znovu', flush=True)
        for f in hotove + ['data/places.parquet', 'data_all/division_area.parquet', B]:
            if os.path.exists(f): os.remove(f)
        stazeno = None
    for theme, typ in LAYERS:
        out = f'data_all/{typ}.parquet'
        if os.path.exists(out): continue
        t = time.time()
        d = overture.dataset(theme, typ)
        f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0) & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
        tb = d.to_table(filter=f); overture.zapis(tb, out)
        stazeno = [X0, X1, Y0, Y1] if stazeno is None else [max(stazeno[0], X0), min(stazeno[1], X1), max(stazeno[2], Y0), min(stazeno[3], Y1)]
        print(typ, tb.num_rows, f'{time.time() - t:.0f}s', flush=True)
    open(B, 'w', encoding='utf-8').write(json.dumps(stazeno))   # po přerušení chybí, pak rozhodnou prvky už stažených vrstev
    # výřezy čtverců se zapisují pokaždé znovu, takže po novém stažení data_all/ jsou i data_c*/ aktuální
    vyrez = {}
    for c in sorted(geo.CHUNKS):
        D = 'data' if c == (0, 0) else f'data_c{c[0]}_{c[1]}'
        os.makedirs(f'{D}/dem', exist_ok=True)
        cx, cy = geo.chunk_center(c); r = geo.HALF + 300
        (x0, x1), (y0, y1) = geo.to_lonlat([cx - r, cx + r], [cy - r, cy + r])
        vyrez[c] = D, float(x0), float(x1), float(y0), float(y1)
    import pyarrow.compute as pc
    for theme, typ in LAYERS:
        tb = pq.read_table(f'data_all/{typ}.parquet')          # každá vrstva jednou pro všechny čtverce
        b = tb.column('bbox').combine_chunks()
        for D, x0, x1, y0, y1 in vyrez.values():
            m = pc.and_(pc.and_(pc.less(b.field('xmin'), x1), pc.greater(b.field('xmax'), x0)),
                        pc.and_(pc.less(b.field('ymin'), y1), pc.greater(b.field('ymax'), y0)))
            overture.zapis(tb.filter(m), f'{D}/{typ}.parquet')
    for c, (D, x0, x1, y0, y1) in vyrez.items():
        dem(D, x0, x1, y0, y1)
        print('čtverec', c, '->', D, flush=True)
    if not os.path.exists('data/places.parquet'): subprocess.run([sys.executable, __file__, '--places'], check=True)
    if not os.path.exists('data_all/division_area.parquet'): subprocess.run([sys.executable, __file__, '--deleni'], check=True)
    sys.exit()
if sys.argv[1:2] == ['--deleni']:
    d = overture.dataset('divisions', 'division_area')
    X0, X1, Y0, Y1 = geo.bbox_lonlat(0)
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    os.makedirs('data_all', exist_ok=True)
    tb = d.to_table(filter=f)
    overture.zapis(tb, 'data_all/division_area.parquet')
    print('částí obcí', tb.num_rows)
    sys.exit()
if sys.argv[1:2] == ['--places']:
    d = overture.dataset('places', 'place')
    X0, X1, Y0, Y1 = geo.bbox_lonlat(0)             # celá mapa
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    os.makedirs('data', exist_ok=True)
    tb = d.to_table(filter=f)
    overture.zapis(tb, 'data/places.parquet')
    print('míst', tb.num_rows)
    sys.exit()
OUT = sys.argv[1] if len(sys.argv) > 1 else 'data'
if OUT != '--chunk':
    X0, X1, Y0, Y1 = tuple(map(float, sys.argv[2].split(",")))   # vlastní výřez lon0,lon1,lat0,lat1
else:
    c = tuple(int(v) for v in sys.argv[2].split(','))
    OUT = 'data' if c == (0, 0) else f'data_c{c[0]}_{c[1]}'
    cx, cy = geo.chunk_center(c); r = geo.HALF + 300
    (X0, X1), (Y0, Y1) = geo.to_lonlat([cx - r, cx + r], [cy - r, cy + r])
os.makedirs(f'{OUT}/dem', exist_ok=True)
for theme, typ in LAYERS:
    t = time.time()
    d = overture.dataset(theme, typ)
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0)
         & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0))
    tb = d.to_table(filter=f)
    overture.zapis(tb, f'{OUT}/{typ}.parquet')
    print(typ, tb.num_rows, f'{time.time() - t:.0f}s')


dem(OUT, X0, X1, Y0, Y1)
print('terén hotov')
