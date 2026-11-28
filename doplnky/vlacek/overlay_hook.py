"""Výletní vláček (doplněk): trasa po silnicích přes zastávky a časy jízdy podle jízdního řádu (assets/doplnky/vlacek.json).

Všechny směry se spojí do jednoho okruhu (tam a zpět), trasa mezi zastávkami se dopočítá po silnicích
z Overture (road_route.Graph, stejně jako trasy autobusů bez shapes.txt). Prohlížeč dostane okruh [lat, lon], jeho délku
a „klíčové body“ jedné otočky [čas s od půlnoci, vzdálenost po okruhu m]; mezi nimi jen interpoluje.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

KMH = 1 / 3.6


def cas(t: str) -> int:
    """'10:05' -> sekundy od půlnoci"""
    h, m = str(t).split(':')
    return int(h) * 3600 + int(m) * 60


def jizda(d: list[float], T: list[int], v: float, vmax: float, stani: float) -> list[list[float]]:
    """klíčové body jedné jízdy [[t, s]]: d vzdálenosti zastávek po okruhu, T časy odjezdu podle jízdního řádu.
    Ze zastávky odjede nejdřív v čase jízdního řádu a po `stani` s stání; rychlost vyplní čas do další zastávky,
    ale drží se mezi 0,7·v a vmax (pozdě nebo brzy přijede a na zastávce počká)."""
    kf, t = [[float(T[0]), d[0]]], float(T[0])
    for i in range(1, len(d)):
        dep = max(t, float(T[i - 1]))
        if dep > kf[-1][0]: kf.append([dep, d[i - 1]])
        dist = d[i] - d[i - 1]
        rychl = min(vmax, max(0.7 * v, dist / max(1.0, T[i] - dep - stani)))
        t = dep + dist / rychl
        kf.append([t, d[i]])
        if i < len(d) - 1: t += stani
    return kf


def postav(raw: dict[str, Any], graf: Any, to_xy: Callable, to_ll: Callable) -> dict[str, Any] | None:
    """raw: data z vlacek.json; graf: objekt s path([(x, y)]) -> (čára, vzdálenosti zastávek) jako road_route.Graph;
    to_xy(lat, lon) -> (x, y) m, to_ll(x, y) -> (lat, lon)."""
    zast, smery = raw.get('zastavky') or [], raw.get('smery') or []
    if len(zast) < 2 or not smery or any(len(s.get('zastavky') or []) < 2 or not s.get('jizdy') for s in smery):
        return None
    # okruh zastávek: směry za sebou, společná konečná jen jednou, nakonec zpět na začátek
    okruh, kde = [], []                        # kde[k] = indexy zastávek směru k v okruhu
    for s in smery:
        idx = s['zastavky']
        if okruh and okruh[-1] == idx[0]: kde.append(list(range(len(okruh) - 1, len(okruh) - 1 + len(idx)))); okruh += idx[1:]
        else: kde.append(list(range(len(okruh), len(okruh) + len(idx)))); okruh += idx
    if okruh[-1] != okruh[0]: okruh.append(okruh[0])
    line, dists = graf.path([to_xy(zast[i]['lat'], zast[i]['lon']) for i in okruh])
    if len(line) > 2:                          # path() začíná přesně v bodě zastávky (může být kousek mimo silnici): začni na silnici
        d0 = math.dist(line[0], line[1]); line = line[1:]; dists = [max(0.0, x - d0) for x in dists]
    L = float(dists[-1])
    v, vmax, stani = float(raw.get('rychlost', 15)) * KMH, float(raw.get('rychlost_max', 25)) * KMH, float(raw.get('stani_s', 30))
    # jedna otočka: od prvního odjezdu prvního směru po další odjezd prvního směru (jízdní řád se opakuje s touto periodou)
    j0 = sorted(cas(j[0]) for j in smery[0]['jizdy'])
    t0 = j0[0]
    P = int(raw.get('perioda_min', 0)) * 60 or (j0[1] - j0[0] if len(j0) > 1 else 0)
    kf = []
    for k, s in enumerate(smery):
        for j in s['jizdy']:
            T = [cas(x) for x in j]
            if len(T) != len(s['zastavky']): raise ValueError(f'vláček: jízda {j[0]} má {len(T)} časů na {len(s["zastavky"])} zastávek')
            if P and not t0 <= T[0] < t0 + P: continue          # další otočky jsou stejné posunuté o P
            kf += jizda([dists[i] for i in kde[k]], T, v, vmax, stani)
    kf.sort(key=lambda q: q[0])
    if not P: P = int(kf[-1][0] - t0) + 600
    return {
        'nazev': raw.get('nazev', 'Výletní vláček'), 'url': raw.get('url', ''), 'popis': raw.get('popis', ''),
        'obdobi': raw.get('obdobi', ['summer']), 'vagony': int(raw.get('vagony', 3)), 'barvy': raw.get('barvy', {}),
        'zastavky': [{'nazev': z['nazev'], 'lat': z['lat'], 'lon': z['lon']} for z in zast],
        'trasa': [[round(float(a), 6), round(float(b), 6)] for a, b in (to_ll(x, y) for x, y in line)],
        'L': round(L, 1), 't0': t0, 'P': P,
        'kf': [[round(t - t0, 1), round(s, 1)] for t, s in kf],
    }


def pres_budovy(trasa_xy: list, budovy: list, tol: float = 1.0) -> list[tuple[int, float]]:
    """úseky trasy přes půdorysy budov: [(index budovy, délka m)]; budova zmenšená o tol (silnice těsně u zdi nevadí)"""
    import shapely
    line, P = shapely.LineString(trasa_xy), shapely.buffer(shapely.make_valid(budovy), -tol)
    out = [(int(i), round(float(shapely.length(shapely.intersection(line, P[i]))), 1))
           for i in shapely.STRtree(P).query(line, predicate='intersects')]
    return [q for q in out if q[1] > 0]


def budovy_xy(root: Path, to_xy: Callable) -> list:
    """půdorysy budov z data*/building.parquet v metrech (pro kontrolu trasy)"""
    import numpy as np, pyarrow.parquet as pq, shapely
    f = next((p for p in (root / 'data_all/building.parquet', root / 'data/building.parquet') if p.is_file()), None)
    if f is None: return []
    G = shapely.from_wkb(pq.read_table(f, columns=['geometry']).column('geometry').to_pylist())
    return list(shapely.transform(G, lambda c: np.column_stack(to_xy(c[:, 1], c[:, 0]))))


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    f = ctx['data_file']
    if not f.is_file():
        return False
    raw = json.loads(f.read_text(encoding='utf-8'))
    if raw.get('enabled', True) is False:
        return False
    root = Path(ctx['assets_dir']).resolve().parent
    seg = next((p for p in (root / 'data_all/segment.parquet', root / 'data/segment.parquet') if p.is_file()), None)
    if seg is None:                            # shortcut: bez dat silnic se vláček vypne; ruční trasa by šla doplnit, kdyby bylo potřeba
        print('vláček: chybí data_all/segment.parquet (silnice), doplněk se vypíná')
        return False
    import geo, road_route
    graf = road_route.Graph(str(seg))
    out = postav(raw, graf, lambda la, lo: tuple(float(q) for q in geo.to_local(lo, la)),
                 lambda x, y: tuple(float(q) for q in geo.to_lonlat(x, y))[::-1])
    if not out:
        return False
    if graf.fails: print(f'vláček: {graf.fails} úseků bez cesty po silnici vede rovně, zkontroluj zastávky')
    tr = out['trasa']                          # kontrola: dlouhý rovný kus = zastávka mimo silnici nebo chybějící silnice
    for a, b in zip(tr, tr[1:]):
        m = math.hypot((b[0] - a[0]) * 111320, (b[1] - a[1]) * 111320 * math.cos(math.radians(a[0])))
        if m > 30: print(f'vláček: rovný úsek {m:.0f} m u {a} (mimo silnici?)')
    B = budovy_xy(root, lambda la, lo: geo.to_local(lo, la))
    for i, m in pres_budovy([geo.to_local(lo, la) for la, lo in tr], B) if B else []:
        print(f'vláček: trasa vede {m} m přes budovu č. {i} (zastávka nebo silnice v datech?)')
    print(f'vláček: okruh {out["L"] / 1000:.1f} km, {len(out["zastavky"])} zastávek, otočka {out["P"] // 60} min')
    return out
