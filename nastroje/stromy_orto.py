# jednotlivé stromy mimo les z ortofota ČÚZK (CC BY 4.0) po 0,2 m/px a z laseru (build/dmp/*.laz, třída 5 nad terénem)
# -> assets/stromy_orto.json: [[lat, lon, výška m, jehličnan 0/1, poloměr koruny m], …]; prep.py je přidá mimo les
# stahuje jen dlaždice 300 × 300 m se zástavbou do build/orto_stromy/ (cache, po přerušení pokračuje)
# jehličnan / listnáč: z archivního ortofota snímaného bez listí (build/orto_bezlisti/), jinak odhadem z barvy
# spouštět z kořene repa: python nastroje/stromy_orto.py   (stažení ~5 min, výpočet ~10 min)
import glob, json, os, subprocess, sys
import numpy as np
from scipy import ndimage as nd

M = 0.2                                   # m/px ortofota (snímek ČÚZK má ~0,2 m, větší rozlišení už nic nepřidá)
UA = 'izomapa-stromy/1.0'


def _avg(x, k):
    return nd.uniform_filter(x.astype(np.float32), 2 * k + 1, mode='nearest')


def maska_korun(rgb, mpx=M):
    """koruny stromů na ortofotu: tmavší modrozelená a zrnitá plocha. Trávník je světlý, žlutozelený a hladký,
    asfalt a střechy nejsou zelené, voda je modrá. Vlastní stín koruny (tmavý, do zelena) patří ke koruně."""
    px = lambda m_: max(1, int(round(m_ / mpx)))                  # metry -> pixely
    a = rgb.astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]; L = a.mean(2)
    q = (g - r) / (L + 10); y = (g - b) / (L + 10)               # zelenost a žlutost
    hf = _avg(np.abs(L - _avg(L, 1)), px(0.8))                    # zrnitost (listí a mezery mezi ním)
    lit = (q > Q0) & (L < L0) & (y < 0.22 + 0.004 * (95 - L)) & (hf > HF0)
    dark = (L < 55) & (g >= r - 2) & (g >= b - 6)                 # stinná strana koruny
    m = _avg(lit | (dark & (_avg(lit, px(1.2)) > 0.25)), px(0.4)) > 0.5
    m = nd.binary_opening(m, np.ones((2 * px(0.4) + 1,) * 2))
    return nd.binary_fill_holes(m), L


Q0, L0, HF0 = 0.06, 105, 2.2


def koruny_stromu(rgb, mpx=M, rmin=1.5, rmax=6.0, rfill=4.0):
    """jednotlivé koruny: středy jsou nejsvětlejší místa (slunce svítí na vrchol koruny) a zároveň dál od okraje masky,
    sousední koruny dělí hranice mezi vrcholy. -> [(řádek, sloupec, poloměr m, jehličnan)]"""
    m, L = maska_korun(rgb, mpx)
    if not m.any(): return []
    dist = nd.distance_transform_edt(m) * mpx                    # m od okraje koruny
    sg = 1.5 / mpx; sL = nd.gaussian_filter(L * m, sg) / np.maximum(nd.gaussian_filter(m.astype(np.float32), sg), 1e-3)   # jas jen z koruny (okolní trávník je světlejší)
    f = np.where(m, sL / 255 * 4 + np.minimum(dist, 1.5), 0).astype(np.float32)   # vrchol: světlo + vzdálenost od okraje
    k = max(3, int(round(3.4 / mpx)) | 1)                         # dva středy nejblíž ~3,4 m od sebe
    pk = (f == nd.maximum_filter(f, k)) & m & (dist >= 0.8)
    lab, n = nd.label(pk)
    if n == 0: return []
    cen = np.array(nd.center_of_mass(pk, lab, range(1, n + 1))).round().astype(int)
    # každý pixel koruny k nejbližšímu vrcholu ve stejné souvislé ploše (watershed_ift ze scipy na plochých vrcholech selhává)
    mk = np.zeros(m.shape, np.int32); mk[cen[:, 0], cen[:, 1]] = np.arange(1, n + 1)
    ii, jj = nd.distance_transform_edt(mk == 0, return_indices=True, return_distances=False)
    ws = mk[ii, jj]; comp = nd.label(m)[0]
    ws[(~m) | (comp != comp[cen[ws - 1, 0], cen[ws - 1, 1]])] = 0
    area = nd.sum(np.ones_like(ws), ws, range(1, n + 1)) * mpx * mpx
    cen = np.array(nd.center_of_mass(np.ones_like(ws), ws, range(1, n + 1)))   # střed koruny = těžiště povodí
    a = rgb.astype(np.float32); idx = np.arange(1, n + 1)
    med = np.r_[0, nd.median(L, ws, idx)]                          # barva osvětlené poloviny koruny (bez stínů uvnitř)
    lit = np.where(L > med[ws], ws, 0)
    mean = np.stack([nd.mean(a[..., c], lit, idx) for c in range(3)], 1)
    out, big = [], []
    for lab_, (i, j), ar, c in zip(range(1, n + 1), cen, area, mean):
        if not np.isfinite(i): continue
        rr = float(np.sqrt(ar / np.pi))
        if rr < rmin: continue                                     # keř, šum
        Lc = c.mean()
        if (c[1] - c[0]) / Lc < 0.06: continue                     # osvětlená část není zelená: stín na střeše, štěrk trati
                                                                   # jehličnan (borovice): tmavší a méně zelený; v borovém lese tak vyjde
        con = bool(Lc < 74 and (c[1] - c[0]) / Lc < 0.22)          # asi pětina korun, v zahradách 3–10 %, jinak listnatý
        if rr > rmax: big.append((lab_, con)); continue
        out.append((int(round(i)), int(round(j)), rr, con))
    # souvislý porost bez zřetelných vrcholů (hustá zahrada, remíz): stromy po ~8 m na mřížce svázané s pixely snímku
    s = max(2, int(round(2 * rfill / mpx)))
    for lab_, con in big:
        ii, jj = np.nonzero((ws == lab_) & (dist >= 1.5))
        k = (ii % s == s // 2) & (jj % s == s // 2)
        out += [(int(i), int(j), rfill, con) for i, j in zip(ii[k], jj[k])]
    return out


# ---------------- celá mapa ----------------
T = 1500                                  # dlaždice 300 × 300 m
WMS = 'https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=0&STYLES=&CRS=EPSG:4326'


def _soubor(geo, X0, Y1, W, H, tx, ty, wms=WMS, slozka='build/orto_stromy'):
    """dlaždice ortofota z cache (slozka), jinak ji stáhne; None, když se nepovede"""
    from PIL import Image
    w, h = min(T, W - tx), min(T, H - ty)
    f = f'{slozka}/{round(X0 + tx * M)}_{round(Y1 - ty * M)}_{w}x{h}.jpg'   # podle polohy jako nastroje/strechy.py
    for _ in range(3):
        try:
            with Image.open(f) as im: return np.asarray(im.convert('RGB'))
        except Exception: pass
        os.makedirs(slozka, exist_ok=True)
        lo0, la1 = geo.to_lonlat(X0 + tx * M, Y1 - ty * M); lo1, la0 = geo.to_lonlat(X0 + (tx + w) * M, Y1 - (ty + h) * M)
        url = f'{wms}&BBOX={la0},{lo0},{la1},{lo1}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg'
        if subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA, '-o', f + '.part', url]).returncode == 0: os.replace(f + '.part', f)
    print('CHYBA: ortofoto se nestáhlo', f, file=sys.stderr, flush=True)
    return None


WMS_ARCHIV = 'https://geoportal.cuzk.cz/WMS_ORTOFOTO_ARCHIV/WMService.aspx?SERVICE=WMS&VERSION=1.3.0&STYLES=&CRS=EPSG:4326&REQUEST=GetMap'


def rok_bez_listi(lon, lat):
    """poslední rok archivního ortofota ČÚZK snímaného do konce dubna (listnáče bez listí), podle metadat
    mapového listu SM5 v bodě; None, když takový není. Ověřuje datum snímkování, ne jen rok."""
    import re
    url = ('https://ags.cuzk.gov.cz/arcgis/rest/services/Metadata/MapServer/13/query?geometryType=esriGeometryPoint'
           f'&geometry={lon},{lat}&inSR=4326&outFields=datum_aktualizace&returnGeometry=false&f=json')
    try:
        d = json.loads(subprocess.run(['curl', '-s', '-f', '-m', '60', '-A', UA, url], capture_output=True, text=True).stdout)
        txt = d['features'][0]['attributes']['datum_aktualizace']
    except Exception:
        return None
    roky = [int(r) for r, mes in re.findall(r'(\d{4}): \d{1,2}\. (\d{2})\. \d{4}', txt) if int(mes) <= 4 and int(r) >= 2015]
    return max(roky) if roky else None


def jehlicnan(rgb):
    """koruna na snímku bez listí (pixely uvnitř koruny, N × 3): jehličnan zůstane tmavě zelený, listnáč je
    holý (šedé a hnědé větve, pod nimi světlý trávník nebo zem). Prahy z ručně určených korun v Doksech a Splavech"""
    p = np.asarray(rgb, float).reshape(-1, 3)
    if len(p) == 0: return False
    L = p.mean(1)
    return bool(L.mean() < 85 and ((p[:, 1] - p[:, 0]) / (L + 10)).mean() > 0.07)


def _polygony(geo):
    """místní polygony: kde stromy nehledat (les a křoviny z dat, tam sází prep.py; budovy; voda) a budovy zvlášť (výběr dlaždic)"""
    import pyarrow.parquet as pq, shapely
    loc = lambda g: shapely.transform(g, lambda c: np.c_[geo.to_local(c[:, 0], c[:, 1])])
    ex, bld = [], []
    for f, cls in [('land', {'forest', 'wood', 'scrub', 'shrub'}), ('water', None), ('building', None)]:
        for r in pq.read_table(f'data_all/{f}.parquet', columns=['class', 'geometry'] if cls else ['geometry']).to_pylist():
            if cls and r['class'] not in cls: continue
            g = shapely.from_wkb(r['geometry'])
            if g.geom_type not in ('Polygon', 'MultiPolygon'): continue
            g = loc(g); ex.append(g)
            if f == 'building': bld.append(g)
    if os.path.exists('assets/zabaged.json'):                      # orná půda: řádky a pruhy plodin vypadají jako koruny
        for r in json.load(open('assets/zabaged.json', encoding='utf-8')).get('orna', []):
            ring = lambda q: [geo.to_local(lo, la) for la, lo in q]
            g = shapely.Polygon(ring(r[0]), [ring(q) for q in r[1:]]).buffer(0).buffer(-3)   # remízky na okraji zůstanou
            if not g.is_empty: ex.append(g)
    return ex, bld


def _vyjimky(ex, tree, x0, y1, w, h):
    """maska dlaždice (levý horní roh x0, y1), kde stromy nehledat; okraj 0,4 m (okap budovy)"""
    import shapely
    from PIL import Image, ImageDraw
    im = Image.new('1', (w, h)); d = ImageDraw.Draw(im)
    P = lambda c: [((x - x0) / M, (y1 - y) / M) for x, y in c]
    for k in tree.query(shapely.box(x0, y1 - h * M, x0 + w * M, y1)):
        g = ex[k]
        for p in getattr(g, 'geoms', [g]):
            d.polygon(P(p.exterior.coords), fill=1)
            for q in p.interiors: d.polygon(P(q.coords), fill=0)
    return nd.binary_dilation(np.asarray(im), np.ones((5, 5)))


def _laser(geo):
    """body vegetace (třída 5) s výškou nad terénem; terén = lineární prolnutí bodů třídy 2.
    -> ((x, y, výška) vegetace, (x, y) země) v místních m. Laser je zřejmě bez listí (v Doksech pod polovinou korun
    z ortofota jen body země), takže strom nevyřazuje; jen jehličnan bez bodů vegetace vrátí na listnáč (jehlicnan_laser)"""
    import laspy
    from pyproj import Transformer
    from scipy.interpolate import LinearNDInterpolator
    fs = sorted(glob.glob('build/dmp/*.laz'))
    if not fs: return None
    Tr = Transformer.from_crs(5514, 4326, always_xy=True)
    G, V = [], []
    for f in fs:
        l = laspy.read(f); c = np.asarray(l.classification)
        x, y = geo.to_local(*Tr.transform(np.asarray(l.x), np.asarray(l.y))); z = np.asarray(l.z)
        G.append(np.c_[x[c == 2], y[c == 2], z[c == 2]])
        V.append(np.c_[x[c == 5], y[c == 5], z[c == 5]])
    G = np.concatenate(G); V = np.concatenate(V)
    zg = LinearNDInterpolator(G[:, :2], G[:, 2])(V[:, :2])
    ok = np.isfinite(zg)
    return np.c_[V[ok, :2], np.maximum(V[ok, 2] - zg[ok], 0)], G[:, :2]


def jehlicnan_laser(con, veg, zem):
    """jehličnan podle snímku bez listí potvrdí laser (taky bez listí): jehličnan vrátí body vegetace, holý listnáč
    často jen zem. Jen zem (veg 0, zem > 0) -> listnáč; snímek tu plete holou korunu nad zeleným dubnovým trávníkem
    a stín sousedních stromů s jehličnanem. Bez bodů vůbec (mimo laser) zůstane, jak řekl snímek"""
    return con and (veg > 0 or zem == 0)


def vyska(r, con, hl):
    """výška stromu pro scénu: z laseru (hl, None = bez bodů), jinak z koruny. Renderer kreslí korunu o poloměru 0,31 h
    (jehličnan 0,21 h), proto výška z laseru jen v mezích, aby koruna na mapě nebyla o moc širší nebo užší než na snímku"""
    hr = r / (0.21 if con else 0.31)
    h = hr if hl is None else min(max(hl, 0.7 * hr), 1.5 * hr)
    return round(float(np.clip(h, 3, 30)), 1)


def main():
    sys.path.insert(0, '.')
    import geo, shapely
    from scipy.spatial import cKDTree
    X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 20)                  # stejný rozsah jako nastroje/strechy.py
    W, H = int((X1 - X0) / M), int((Y1 - Y0) / M); P = 60          # překryv 12 m: koruna na hraně dlaždice se najde celá
    ex, bld = _polygony(geo); tree = shapely.STRtree(ex)
    bc = shapely.get_coordinates(shapely.centroid(bld))            # jen dlaždice s budovami: zástavba a zahrady, ne les a pole
    jen = set(zip(((bc[:, 0] - X0) / M // T * T).astype(int), ((Y1 - bc[:, 1]) / M // T * T).astype(int)))
    tiles = [(tx, ty) for ty in range(0, H, T) for tx in range(0, W, T) if (tx, ty) in jen]
    print('dlaždic se zástavbou', len(tiles), 'z', len(range(0, H, T)) * len(range(0, W, T)), flush=True)
    for n, (tx, ty) in enumerate(tiles):
        _soubor(geo, X0, Y1, W, H, tx, ty)
        if n % 20 == 0: print('ortofoto', n, len(tiles), flush=True)
    rok = rok_bez_listi(*geo.to_lonlat((X0 + X1) / 2, (Y0 + Y1) / 2))
    wms_bl = f'{WMS_ARCHIV}&LAYERS={rok}' if rok else None
    print('ortofoto bez listí', rok or 'není, jehličnany jen odhadem z barvy', flush=True)
    if rok:
        for tx, ty in tiles: _soubor(geo, X0, Y1, W, H, tx, ty, wms_bl, f'build/orto_bezlisti/{rok}')
    las, zem = _laser(geo) or (None, None)
    kd = cKDTree(las[:, :2]) if las is not None else None; kz = cKDTree(zem) if zem is not None else None
    print('laser', 0 if las is None else len(las), 'bodů vegetace', flush=True)
    have = set(tiles); out = []
    for tx, ty in tiles:
        a = _soubor(geo, X0, Y1, W, H, tx, ty)
        if a is None: continue
        h, w = a.shape[:2]
        big = np.zeros((h + 2 * P, w + 2 * P, 3), np.uint8)       # dlaždice s okrajem ze sousedních
        for sx in (tx - T, tx, tx + T):
            for sy in (ty - T, ty, ty + T):
                b = a if (sx, sy) == (tx, ty) else _soubor(geo, X0, Y1, W, H, sx, sy) if (sx, sy) in have else None
                if b is None: continue
                ox, oy = sx - tx + P, sy - ty + P
                x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(big.shape[1], ox + b.shape[1]), min(big.shape[0], oy + b.shape[0])
                if x1 > x0 and y1 > y0: big[y0:y1, x0:x1] = b[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        exm = _vyjimky(ex, tree, X0 + tx * M, Y1 - ty * M, w, h)
        bl = _soubor(geo, X0, Y1, W, H, tx, ty, wms_bl, f'build/orto_bezlisti/{rok}') if rok else None
        if bl is not None and bl.shape[:2] != (h, w): bl = None
        for i, j, r, con in koruny_stromu(big):
            i, j = i - P, j - P
            if not (0 <= i < h and 0 <= j < w) or exm[i, j]: continue
            if bl is not None:                                     # vnitřek koruny (0,7 r) na snímku bez listí
                q = max(0.7 * r, 1.0) / M; i0, i1, j0, j1 = int(max(0, i - q)), int(min(h, i + q + 1)), int(max(0, j - q)), int(min(w, j + q + 1))
                ii, jj = np.mgrid[i0:i1, j0:j1]
                con = jehlicnan(bl[i0:i1, j0:j1][np.hypot(ii - i, jj - j) <= q])
            x, y = X0 + (tx + j + 0.5) * M, Y1 - (ty + i + 0.5) * M
            hl = None
            if kd is not None:
                k = kd.query_ball_point((x, y), max(r, 2.5))
                if k: hl = float(las[k, 2].max())
                if hl is not None and hl < 2.5: hl = None
                con = jehlicnan_laser(con, len(k), len(kz.query_ball_point((x, y), max(r, 2.5))))
            lo, la = geo.to_lonlat(x, y)
            out.append([round(float(la), 6), round(float(lo), 6), vyska(r, con, hl), int(con), round(r, 1)])
        print('dlaždice', tx, ty, 'stromů', len(out), flush=True)
    json.dump(out, open('assets/stromy_orto.json', 'w'), separators=(',', ':'))
    print('stromů', len(out), 'jehličnanů', sum(t[3] for t in out))


if __name__ == '__main__':
    main()
