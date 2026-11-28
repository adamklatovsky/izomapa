"""Lodě (doplněk): z assets/doplnky/lode.json předá prohlížeči vodní plochu, trasy parníků, půjčovny šlapadel, plachetnice, kajaky, pláže a zimní provoz na ledu (lat/lon)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KLICE = ('voda', 'parniky', 'pujcovny', 'plachetnice', 'kajaky', 'plaze', 'zima')


def stromy_plazi(plaze: list[dict], to_local, chunks, chunk_dir, chunk_center, half: float, okraj: float = 30.0) -> list[list]:
    """Stromy ze scén čtverců na plážích a do `okraj` m od nich: [x, y, z, výška, jehličnan, druh] ve světě jako stromy
    v overlay/*.json (prohlížeč za nimi schová lidi na pláži a podle nich je rozmístí mimo kmeny)."""
    import shapely
    oblast = shapely.union_all([shapely.Polygon([to_local(lon, lat) for lat, lon in P['q']]).buffer(okraj) for P in plaze if len(P.get('q') or []) >= 3])
    if oblast.is_empty:
        return []
    shapely.prepare(oblast)
    out = []
    for c in chunks:
        f = Path(chunk_dir(c), 'scene.json')
        if not f.is_file():
            continue
        ox, oy = chunk_center(c)
        for t in json.loads(Path(f).read_text(encoding='utf-8'))['trees']:
            if (len(t) > 5 and t[5] == 2) or abs(t[0]) > half or abs(t[1]) > half:   # jako v overlay.py: bez druhu 2 a bez pásu sousedů
                continue
            if oblast.contains(shapely.Point(t[0] + ox, t[1] + oy)):
                out.append([round(t[0] + ox, 2), round(t[1] + oy, 2), round(t[2], 1), t[3], t[4], t[5] if len(t) > 5 else 0])
    return out


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    f = ctx['data_file']
    if not f.is_file():
        return False
    raw = json.loads(f.read_text(encoding='utf-8'))
    voda = [r for r in raw.get('voda') or [] if len(r) >= 3]
    if raw.get('enabled', True) is False or not voda:
        return False                                   # bez vodní plochy nemají lodě kde jezdit
    out = {k: raw[k] for k in KLICE if k in raw}
    out['voda'] = voda
    out['parniky'] = [p for p in raw.get('parniky') or [] if len(p.get('trasa') or []) >= 2]
    if out.get('plaze') and ctx.get('build_dir'):      # jen ze stavby mapy (overlay.py), ne v testech bez města
        import geo
        out['stromy'] = stromy_plazi(out['plaze'], geo.to_local, geo.CHUNKS, geo.chunk_dir, geo.chunk_center, geo.HALF)
    return out
