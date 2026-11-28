# tvar střechy z laseru DMP 1G (body třídy 6 v půdorysu zmenšeném o 0,5 m): plochá, nebo sedlová / valbová složená z dílů
# Díly jsou obdélníky jako v prep.py (roof_parts: hlavní křídlo, příčné křídlo, L, T, kříž) a render.html z nich kreslí
# horní obálku. Pro každý díl se zkouší hřeben podél delší i kratší strany, sedlo i valba a posun půdorysu vůči laseru.
# -> assets/tvary_strech.json: id budovy -> [tvar, sklon °, [[lon, lat, úhel hřebene ° od východu proti směru hodin, délka podél hřebene, šířka], …]]
# jen jisté případy, ostatní chybí. Spouštět po dmp_fetch.py z kořene repa: .venv/bin/python nastroje/tvary_strech.py
import glob, itertools, json, math
import numpy as np

MIN_BODU, MIN_HUSTOTA = 25, 0.4      # na střechách rodinných domů vzorku (Staré Splavy) kolem 1,1 bodu/m²
POSUN = [(dx, dy) for dx in np.arange(-1.5, 1.51, 0.5) for dy in np.arange(-1.5, 1.51, 0.5)]   # půdorys z Overture bývá vůči laseru posunutý


def osy(poly):
    """střed, jednotkové osy (u podél delší strany) a poloviční délky obdélníku opsaného půdorysu"""
    c = np.array(poly.minimum_rotated_rectangle.exterior.coords)[:3]
    e1, e2 = c[1] - c[0], c[2] - c[1]
    if np.linalg.norm(e1) < np.linalg.norm(e2): e1, e2 = e2, e1
    m = (c[0] + c[2]) / 2
    return m, e1 / np.linalg.norm(e1), e2 / np.linalg.norm(e2), np.linalg.norm(e1) / 2, np.linalg.norm(e2) / 2


def max_rect(M):
    """největší obdélník jedniček v binární matici -> (r0, c0, r1, c1) včetně (stejně jako prep.py)"""
    best = (0, None); h = np.zeros(M.shape[1], int)
    for r in range(M.shape[0]):
        h = np.where(M[r], h + 1, 0); st = []
        for c in range(M.shape[1] + 1):
            cur = h[c] if c < M.shape[1] else 0; start = c
            while st and st[-1][1] >= cur:
                s0, hh = st.pop()
                if hh * (c - s0) > best[0]: best = (hh * (c - s0), (r - hh + 1, s0, r, c - 1))
                start = s0
            st.append((start, cur))
    return best[1]


def dily(poly):
    """obdélníky střechy [(střed, úhel delší strany, délka, šířka)]: celý obdélník opsaný, nebo rozklad jako prep.py roof_parts"""
    import shapely
    m, u, v, A, B = osy(poly); ang = math.atan2(u[1], u[0])
    if poly.area / max(poly.minimum_rotated_rectangle.area, 1) > 0.9: return [(m, ang, 2 * A, 2 * B)]
    cs = 0.6; c0 = poly.centroid
    q = shapely.affinity.rotate(poly, -ang, origin=c0, use_radians=True)
    minx, miny, maxx, maxy = q.bounds
    xs = np.arange(minx + cs / 2, maxx, cs); ys = np.arange(miny + cs / 2, maxy, cs)
    if len(xs) < 3 or len(ys) < 3: return []
    XX, YY = np.meshgrid(xs, ys); M = shapely.contains_xy(q, XX, YY); total = M.sum(); out = []
    for _ in range(4):
        r = max_rect(M)
        if r is None: break
        r0, c0_, r1, c1 = r
        if (r1 - r0 + 1) * (c1 - c0_ + 1) < max(0.14 * total, 20 / cs ** 2): break
        w_, h_ = (c1 - c0_ + 1) * cs, (r1 - r0 + 1) * cs
        M[r0:r1 + 1, c0_:c1 + 1] = False
        if min(w_, h_) < 3.0: continue
        pt = shapely.affinity.rotate(shapely.Point((xs[c0_] + xs[c1]) / 2, (ys[r0] + ys[r1]) / 2), ang, origin=c0, use_radians=True)
        out.append((np.array([pt.x, pt.y]), ang if w_ >= h_ else ang + math.pi / 2, max(w_, h_), min(w_, h_)))
    return out


def vyska(xy, D, tvar):
    """výška nad okapem / sklon (tedy vzdálenost k okapu) pro díly [(střed, úhel hřebene, délka, šířka)] jako v render.html:
    horní obálka dílů, mimo díly plochá výplň v úrovni okapu (0). Díl sahá o 1,5 m dál (posun půdorysu vůči laseru)
    a sklon za okapem pokračuje, jinak by posunutý díl udělal z kraje střechy rovinu"""
    x = np.full(len(xy), -np.inf)
    for c, a, L, W in D:
        d = xy - c; s = np.abs(d @ [math.cos(a), math.sin(a)]); t = np.abs(d @ [-math.sin(a), math.cos(a)])
        uvnitr = (s <= L / 2 + 1.5) & (t <= W / 2 + 1.5)
        k = np.maximum(t, s - max(L / 2 - W / 2, 0)) if tvar == 'hipped' else t
        x = np.where(uvnitr, np.maximum(x, W / 2 - k), x)
    return np.where(np.isfinite(x), x, 0)


def _fit(D, z, W):
    """vážené z = h - k*d pro každý řádek D (variantu); vrací rmse, h, k"""
    sw = W.sum(1); dm = (W * D).sum(1) / sw; zm = (W * z).sum(1) / sw
    dd = D - dm[:, None]; vd = (W * dd ** 2).sum(1); cov = (W * dd * (z - zm[:, None])).sum(1)
    b = np.where(vd > 1e-9, cov / np.maximum(vd, 1e-9), 0); a = zm - b * dm
    return np.sqrt((W * (z - a[:, None] - b[:, None] * D) ** 2).sum(1) / sw), a, -b


def _robust(D, z):
    """každá varianta se proloží, zahodí 10 % nejhorších bodů (komíny, vikýře, anténa) a proloží znovu (stejně pro všechny,
    takže jdou porovnat); vrací rmse, k a podíl všech bodů dál než 0,5 m od modelu (křídlo nebo vikýř, které ořez schová)"""
    z = np.broadcast_to(z, D.shape)
    _, a, k = _fit(D, z, np.ones(D.shape))
    r = np.abs(z - a[:, None] + k[:, None] * D)
    W = (r <= np.quantile(r, 0.9, axis=1, keepdims=True)).astype(float)
    e, a, k = _fit(D, z, W)
    return e, k, np.mean(np.abs(z - a[:, None] + k[:, None] * D) > 0.5, axis=1)


def tvar(poly, xyz, zem=None):
    """('flat' | 'gabled' | 'hipped' | None, sklon °, díly [(střed, úhel hřebene, délka podél hřebene, šířka)], chyby modelů)
    None = nejisté, nic neměnit. zem: výška terénu u budovy; body do 2 m nad ním (dvůr, pata zdi) se zahodí"""
    if zem is not None: xyz = xyz[xyz[:, 2] > zem + 2]
    if len(xyz) > 600: xyz = xyz[np.random.default_rng(0).choice(len(xyz), 600, replace=False)]   # stačí na tvar, šetří paměť
    n = len(xyz); D0 = dily(poly)
    if n < MIN_BODU or n / max(poly.area, 1) < MIN_HUSTOTA or not D0: return None, 0, [], {'proc': 'málo bodů'}
    z = xyz[:, 2] - xyz[:, 2].min()
    # rovina: plochá střecha (pultová s velkým sklonem je nejistá)
    G = np.column_stack([np.ones(n), xyz[:, :2] - xyz[:, :2].mean(0)]); cf, *_ = np.linalg.lstsq(G, z, rcond=None)
    res = np.abs(z - G @ cf); keep = res <= np.quantile(res, 0.9); cf, *_ = np.linalg.lstsq(G[keep], z[keep], rcond=None)
    e = {'rovina': math.sqrt(((z[keep] - G[keep] @ cf) ** 2).mean())}
    sklon_r = math.degrees(math.atan(math.hypot(cf[1], cf[2])))
    # varianty: sedlo/valba × hřeben každého dílu podél delší (0) / kratší (1) strany × posun půdorysu vůči laseru
    V = [(t, ot) for t in ('gabled', 'hipped') for ot in itertools.product((0, 1), repeat=len(D0))]
    otoc = lambda ot: [(c, a + o * math.pi / 2, (L, W)[o], (W, L)[o]) for (c, a, L, W), o in zip(D0, ot)]
    E, K, O = _robust(-np.array([vyska(xyz[:, :2] - p, otoc(ot), t) for t, ot in V for p in POSUN]), z)
    E, K, O = (q.reshape(len(V), len(POSUN)) for q in (E, K, O)); j = E.argmin(1); r = np.arange(len(V))
    E, K, O = E[r, j], K[r, j], O[r, j]
    # třídy tvaru: typ a směr hřebene velkých dílů (nad 30 % plochy); směr malého dílu se bere z nejlepší varianty
    velky = [L * W >= 0.3 * sum(q[2] * q[3] for q in D0) for _, _, L, W in D0]
    tridy = {}
    for i, (t, ot) in enumerate(V):
        k = (t, tuple(o for o, v in zip(ot, velky) if v))
        if k not in tridy or E[i] < E[tridy[k]]: tridy[k] = i
    b = int(E.argmin()); t, ot = V[b]
    blizko = sorted(k for k, i in tridy.items() if E[i] <= E[b] * 1.25)   # třídy, které sedí skoro stejně dobře
    if all(k[0] == 'hipped' for k in blizko): blizko = blizko[:1]          # skoro čtvercová valba: na směru hřebene nesejde
    e.update(model=float(E[b]), mimo=float(O[b]), k=float(K[b]))
    if sklon_r < 6 and e['rovina'] < 0.25 and e['rovina'] <= E[b] * 1.2: return 'flat', round(sklon_r), [], e
    if e['rovina'] < 0.3 and sklon_r >= 6: e['proc'] = 'pultová'; return None, round(sklon_r), [], e        # pultová nebo nakloněná: nejisté
    if E[b] < 0.15 and abs(K[b]) < 0.25: return 'flat', round(math.degrees(math.atan(abs(K[b])))), [], e   # do 14° vypadá v mapě jako plochá
    if len(blizko) > 1: e.update(proc='soupeř', soupeř=blizko); return None, 0, [], e     # typ nebo směr hřebene nejde rozlišit
    # členitá střecha, kterou díly nevystihnou (vikýře, přístavby, různé výšky), nebo šum
    if E[b] > 0.25 or E[b] > e['rovina'] * 0.6: e['proc'] = 'chyba modelu'; return None, 0, [], e
    if O[b] > 0.08: e['proc'] = 'body mimo'; return None, 0, [], e
    # sklon pod 25° (render kreslí 40°, na ortofotu tu nejčastěji sporné haly, nízké valby a jejich kusy) nebo nad 63°
    if not 0.47 < K[b] < 2.0: e['proc'] = 'sklon'; return None, 0, [], e
    # díly v poloze půdorysu (posun vůči laseru jen pro proložení), render z něj kreslí zdi
    return t, round(math.degrees(math.atan(K[b]))), otoc(ot), e


def budovy():
    """id a půdorysy budov v EPSG:5514 (načítá se i v podprocesech Pool)"""
    import shapely, pyarrow.parquet as pq
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 5514, always_xy=True); B = {}
    for f in sorted(glob.glob('data*/building.parquet')):
        for r in pq.read_table(f, columns=['id', 'geometry']).to_pylist(): B.setdefault(r['id'], r['geometry'])
    return list(B), shapely.make_valid(shapely.transform(shapely.from_wkb(list(B.values())), lambda c: np.column_stack(T.transform(c[:, 0], c[:, 1]))))


def sheet(f):
    """z jednoho listu -> ({index budovy: body třídy 6 v zmenšeném půdorysu}, {index: výšky terénu v pásu 1–14 m kolem})"""
    import laspy, shapely
    global PS, RING
    if 'PS' not in globals():
        P = budovy()[1]; PS = shapely.buffer(P, -0.5); RING = shapely.difference(shapely.buffer(P, 14), shapely.buffer(P, 1))
    l = laspy.read(f); X, Y, Z, C = np.array(l.x), np.array(l.y), np.array(l.z), np.array(l.classification); out = ({}, {})
    for cls, polys, o in ((6, PS, out[0]), (2, RING, out[1])):
        m = C == cls
        if not m.any(): continue
        pi, ti = shapely.STRtree(shapely.points(X[m], Y[m])).query(polys, predicate='contains')
        q = np.argsort(pi); pi, ti = pi[q], ti[q]; xyz = np.column_stack([X[m], Y[m], Z[m]])
        u, st = np.unique(pi, return_index=True); st = list(st) + [len(pi)]
        for j, k in enumerate(u): o[int(k)] = xyz[ti[st[j]:st[j + 1]]] if cls == 6 else xyz[ti[st[j]:st[j + 1]], 2]
    return out


def zemepisne(D, Ti):
    """díly z EPSG:5514 do [lon, lat, úhel ° (osy východ, sever jako v prep.py), délka, šířka]"""
    out = []
    for c, a, L, W in D:
        (x0, x1), (y0, y1) = Ti.transform([c[0], c[0] + math.cos(a)], [c[1], c[1] + math.sin(a)])
        uhel = round(math.degrees(math.atan2(y1 - y0, (x1 - x0) * math.cos(math.radians(y0))))) % 180
        out.append([round(x0, 7), round(y0, 7), uhel, round(L, 1), round(W, 1)])
    return out


if __name__ == '__main__':
    from multiprocessing import Pool
    from pyproj import Transformer
    ids, P = budovy()
    with Pool(4) as p: listy = p.map(sheet, sorted(glob.glob('build/dmp/*.laz')))
    acc, zem = {}, {}
    for o, g in listy:
        for k, v in o.items(): acc.setdefault(k, []).append(v)
        for k, v in g.items(): zem.setdefault(k, []).append(v)
    res, stat = {}, {}
    Ti = Transformer.from_crs(5514, 4326, always_xy=True)
    for k, v in acc.items():
        # nad 650 m² kreslí prep.py střechu plochou tak jako tak
        if P[k].geom_type != 'Polygon' or not 25 <= P[k].area <= 650 or k not in zem: continue
        r, sklon, D, e = tvar(P[k], np.vstack(v), float(np.median(np.concatenate(zem[k]))))
        q = r or 'nejisté: ' + e.get('proc', '?'); stat[q] = stat.get(q, 0) + 1
        if r: res[ids[k]] = [r, sklon, zemepisne(D, Ti)]
    json.dump(res, open('assets/tvary_strech.json', 'w'), separators=(',', ':'))
    print(json.dumps(stat, ensure_ascii=False, indent=1))
