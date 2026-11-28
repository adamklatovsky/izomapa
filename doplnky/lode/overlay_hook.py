"""Lodě (doplněk): z assets/doplnky/lode.json předá prohlížeči vodní plochu, trasy parníků, půjčovny šlapadel, plachetnice, kajaky, pláže a zimní provoz na ledu (lat/lon)."""
from __future__ import annotations

import json
from typing import Any

KLICE = ('voda', 'parniky', 'pujcovny', 'plachetnice', 'kajaky', 'plaze', 'zima')


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
    return out
