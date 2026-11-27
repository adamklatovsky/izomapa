"""Vyhlídkový let (doplněk): předá prohlížeči dráhu letiště, místa z mista.json (cíle letu) a čtverce mapy (budovy pro náraz).

Dráha: assets/doplnky/vyhlidkovy_let.json → "draha": {"a": [lat, lon], "b": [lat, lon], "sirka": 24}, "letiste": "název",
jinak aktivní dráha z doplňku letiste (assets/doplnky/letiste.json). Bez dráhy se startuje ve vzduchu nad městem."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _bod(p: Any) -> list[float] | None:
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        try:
            return [round(float(p[0]), 7), round(float(p[1]), 7)]
        except (TypeError, ValueError):
            return None
    return None


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    f: Path = ctx['data_file']
    raw: dict[str, Any] = json.loads(f.read_text(encoding='utf-8')) if f.is_file() else {}
    if raw.get('enabled', True) is False:
        return False
    mesto = ctx.get('mesto') or {}
    out: dict[str, Any] = {
        'ctverce': [list(c) for c in mesto.get('ctverce', [[0, 0]])],
        'polovina': float(mesto.get('polovina', 1150.0)),
        'nazev': str(raw.get('nazev') or ctx['plugin_config'].get('nazev') or 'Vyhlídkový let')[:60],
    }
    # dráha: vlastní, jinak aktivní dráha doplňku letiste
    d = raw.get('draha')
    if not d:
        lf = Path(ctx['assets_dir']) / 'doplnky' / 'letiste.json'
        if lf.is_file():
            le = json.loads(lf.read_text(encoding='utf-8'))
            akt = le.get('aktivni') or {}
            dr = next((r for r in le.get('drahy') or [] if r.get('ref') == akt.get('draha')), (le.get('drahy') or [None])[0])
            if dr:
                d = {'a': dr['b'], 'b': dr['a'], 'sirka': dr.get('sirka', 24)} if akt.get('od') == 'b' else dr
                out['letiste'] = str(raw.get('letiste') or le.get('nazev') or 'letiště')[:60]
    if d and _bod(d.get('a')) and _bod(d.get('b')):
        out['draha'] = {'a': _bod(d['a']), 'b': _bod(d['b']), 'sirka': float(d.get('sirka', 24))}
        out.setdefault('letiste', str(raw.get('letiste') or 'letiště')[:60])
    # cíle: místa z mista.json (nejvýš 60), bez samotného letiště
    mf = Path(raw.get('mista_soubor') or 'mista.json')
    mista = []
    if mf.is_file():
        for m in json.loads(mf.read_text(encoding='utf-8')):
            try:
                n, la, lo = str(m['nazev'])[:60], float(m['lat']), float(m['lon'])
            except (KeyError, TypeError, ValueError):
                continue
            if not n.lower().startswith('letiště'):
                mista.append({'n': n, 'lat': round(la, 6), 'lon': round(lo, 6)})
    out['mista'] = mista[:60]
    if not mista:
        print('Doplněk vyhlidkovy_let: mista.json je prázdný nebo chybí – hra nemá cíle, přeskakuje se.')
        return False
    return out
