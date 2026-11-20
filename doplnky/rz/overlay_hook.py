"""Rychlostní zkouška (doplněk): hra s rallyovým autem na trati, kterou si hráč postaví kdekoli na mapě (po silnicích),
volitelně i s předem připravenou tratí z assets/doplnky/rz.json ("trasa" [[lat, lon], …], počet kol a texty).
Bez souboru se doplněk zapne jen tehdy, když je povolený v assets/doplnky.json (pak je k dispozici jen stavba vlastní trati)."""
from __future__ import annotations

import json
import math
from typing import Any


def _delka(trasa: list[list[float]]) -> float:
    """Délka lomené čáry [[lat, lon], …] v metrech (rovinná aproximace, na pár kilometrů stačí)."""
    d = 0.0
    for (a, b), (c, e) in zip(trasa, trasa[1:]):
        kx = 111320.0 * math.cos(math.radians((a + c) / 2))
        d += math.hypot((e - b) * kx, (c - a) * 110574.0)
    return d


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    f = ctx['data_file']
    raw: dict[str, Any] = json.loads(f.read_text(encoding='utf-8')) if f.is_file() else {}
    if raw.get('enabled', True) is False:
        return False
    mesto = ctx.get('mesto') or {}
    out: dict[str, Any] = {
        'ctverce': [list(c) for c in mesto.get('ctverce', [[0, 0]])],    # dílky overlay/c<i>_<j>.json se silnicemi pro stavbu trati
        'polovina': float(mesto.get('polovina', 1150.0)),
        'auto': str(raw.get('auto') or 'Rally2')[:40],
    }
    trasa = [[float(p[0]), float(p[1])] for p in raw.get('trasa') or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    if trasa:
        delka = _delka(trasa)
        if len(trasa) < 2 or not 200 <= delka <= 30000:
            print(f'Doplněk rz: připravená trať (assets/doplnky/rz.json) má {len(trasa)} bodů a {delka:.0f} m, vynechává se.')
        else:
            kola = max(1, min(10, int(raw.get('kola', 1))))
            out['trat'] = {
                'nazev': str(raw.get('nazev') or 'Rychlostní zkouška')[:60],
                'popis': str(raw.get('popis') or '')[:1200],
                'zdroj': str(raw.get('zdroj') or '')[:400],
                'kola': kola,
                'delka': round(delka * kola),
                'tabulka': ''.join(ch for ch in str(raw.get('tabulka') or 'rz').lower() if ch.isalnum() or ch == '-')[:40] or 'rz',
                'trasa': [[round(a, 6), round(b, 6)] for a, b in trasa],
            }
    return out
