"""Práce na polích (doplněk): z assets/zabaged.json (orná půda, nastroje/zabaged.py a pole_cesty.py) vybere pole
větší než `min_ha` a pošle prohlížeči zjednodušené obrysy s plodinou. assets/doplnky/pole.json má jen počty a volby."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

CROPS = ['wheat'] * 4 + ['rape'] * 2 + ['maize'] * 2 + ['soil'] * 2   # stejně jako prep.py pro pole bez plodiny z ortofota


def _plodina(c0) -> str:
    # prep.py: CROPS[int(h01(wkey(centroid) + 'pole') * len(CROPS))], ať stroj jede po poli, které tak i vypadá
    h = int(hashlib.md5(f'{round(c0.x, 1)},{round(c0.y, 1)}pole'.encode()).hexdigest()[:8], 16) / 0xffffffff
    return CROPS[int(h * len(CROPS))]


def postav(raw: dict[str, Any], zab: dict[str, Any], to_local: Callable[[float, float], tuple[float, float]],
           to_ll: Callable[[float, float], tuple[float, float]], mapa: Any = None) -> dict[str, Any]:
    """to_local(lat, lon) -> (x, y) m, to_ll(x, y) -> (lat, lon); mapa = plocha čtverců (pole se na ni ořízne)"""
    import shapely
    from shapely.geometry import Polygon

    def poly(rings):                                      # jako _zpoly v prep.py (celé pole, i když make_valid vrátí víc kusů)
        xy = [[to_local(q[0], q[1]) for q in r] for r in rings]
        return shapely.make_valid(Polygon(xy[0], xy[1:]))

    def ven(g, plod):
        # největší kus uvnitř mapy, zjednodušený na 3 m, zpátky do [lat, lon]
        if mapa is not None:
            g = g.intersection(mapa)
        polys = [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon']
        if not polys:
            return None
        s = max(polys, key=lambda p: p.area).simplify(3.0)
        if s.geom_type != 'Polygon' or s.is_empty or s.area < min_m2:
            return None
        q = [[[round(float(v), 6) for v in to_ll(x, y)] for x, y in list(r.coords)[:-1]] for r in [s.exterior, *s.interiors] if len(r.coords) >= 4]
        return {'q': q, 'p': plod}

    min_m2 = float(raw.get('min_ha', 1)) * 10000
    dil = 'orna_dil' in zab
    orna = zab['orna_dil'] if dil else zab.get('orna', []) + [zab['ttp'][i] for i in sorted(set(zab.get('pole', [])))]
    plod = zab.get('orna_plodina') if dil else None
    pole = []
    for i, rings in enumerate(orna):
        g = poly(rings)
        if g.area < min_m2:
            continue
        o = ven(g, (plod[i] if plod else None) or _plodina(g.centroid))
        if o:
            pole.append(o)
    louky = []
    if raw.get('louky'):                                  # senoseč na trvalých travních porostech (bez těch, co jsou na ortofotu pole)
        jsou_pole = set(zab.get('pole', []))
        for i, rings in enumerate(zab.get('ttp', [])):
            g = None if i in jsou_pole else poly(rings)
            if g is not None and g.area >= min_m2 and (o := ven(g, 'louka')):
                louky.append(o)
    return {'pole': pole, 'louky': louky, 'stroje': int(raw.get('stroje', 5))}


def stromy_u_poli(polygony: list, scene_trees, okraj: float = 15.0) -> list[list]:
    """Stromy ze scén čtverců na polích a do `okraj` m od nich k jihozápadu (remízky, stromy na kraji), aby jimi prohlížeč ořízl
    stopu. Pohled je od jihozápadu: korunu přes pole má jen strom na něm nebo před ním, stromy za polem by jen zvětšily data
    (v Doksech 22 500 stromů v pásu kolem polí, z toho 13 700 na poli a před ním).
    polygony = shapely polygony polí v m, scene_trees = [(ox, oy, half, stromy čtverce v jeho souřadnicích)]."""
    import shapely
    from shapely.affinity import translate
    d = okraj / 2 ** 0.5                                   # posun po úhlopříčce k jihozápadu po krocích 5 m, kolem 3 m rezerva
    n = max(1, int(okraj // 5))
    oblast = shapely.union_all([translate(P, -d * k / n, -d * k / n) for P in polygony for k in range(n + 1)]).buffer(3)
    if oblast.is_empty:
        return []
    shapely.prepare(oblast)
    out = []
    for ox, oy, half, trees in scene_trees:
        for t in trees:
            if (len(t) > 5 and t[5] == 2) or abs(t[0]) > half or abs(t[1]) > half:   # druh 2 se nekreslí, pás sousedů má soused sám
                continue
            if oblast.contains(shapely.Point(t[0] + ox, t[1] + oy)):
                out.append([round(t[0] + ox, 2), round(t[1] + oy, 2), round(t[2], 1), t[3], t[4], t[5] if len(t) > 5 else 0])
    return out


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    f, z = ctx['data_file'], ctx['assets_dir'] / 'zabaged.json'
    if not f.is_file() or not z.is_file():
        return False
    raw = json.loads(f.read_text(encoding='utf-8'))
    if raw.get('enabled', True) is False:
        return False
    import geo
    from shapely.geometry import box
    from shapely.ops import unary_union
    H = geo.HALF
    mapa = unary_union([box(i * 2 * H - H, j * 2 * H - H, i * 2 * H + H, j * 2 * H + H) for i, j in geo.CHUNKS])
    out = postav(raw, json.loads(z.read_text(encoding='utf-8')), lambda la, lo: tuple(float(v) for v in geo.to_local(lo, la)),
                 lambda x, y: tuple(float(v) for v in geo.to_lonlat(x, y))[::-1], mapa)
    if not out['pole'] and not out['louky']:
        return False
    if ctx.get('build_dir'):
        from pathlib import Path
        from shapely.geometry import Polygon
        to_xy = lambda q: [geo.to_local(lo, la) for la, lo in q]
        polys = [Polygon(to_xy(P['q'][0]), [to_xy(r) for r in P['q'][1:]]) for P in out['pole'] + out['louky']]
        sc = []
        for c in geo.CHUNKS:
            f = Path(geo.chunk_dir(c), 'scene.json')
            if f.is_file():
                sc.append((*geo.chunk_center(c), H, json.loads(f.read_text(encoding='utf-8'))['trees']))
        out['stromy'] = stromy_u_poli(polys, sc)
    return out
