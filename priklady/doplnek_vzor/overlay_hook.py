"""Referenční build-time hook pro obecný doplněk (client i server režim)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _project_target(item: Any, default_radius_m: float, mpp: float, project_xy) -> dict[str, Any] | None:
    """Převede bodový nebo polygonální cíl ze zeměpisných souřadnic na pixely mapy."""
    if isinstance(item, dict) and isinstance(item.get('polygon'), list):
        pts = [list(project_xy(float(p[0]), float(p[1]))) for p in item['polygon'] if len(p) >= 2]
        return {'type': 'polygon', 'points': pts} if len(pts) >= 3 else None

    if isinstance(item, list) and len(item) >= 3 and isinstance(item[0], (list, tuple)):
        pts = [list(project_xy(float(p[0]), float(p[1]))) for p in item if len(p) >= 2]
        return {'type': 'polygon', 'points': pts} if len(pts) >= 3 else None

    if isinstance(item, (list, tuple)) and len(item) >= 2:
        r_m = float(item[2]) if len(item) >= 3 else default_radius_m
        return {'type': 'point', 'xy': list(project_xy(float(item[0]), float(item[1]))), 'radius_px': round(r_m / mpp, 1)}

    if isinstance(item, dict) and 'lat' in item and 'lon' in item:
        r_m = float(item.get('radius', default_radius_m))
        return {'type': 'point', 'xy': list(project_xy(float(item['lat']), float(item['lon']))), 'radius_px': round(r_m / mpp, 1)}

    return None


def _project_camera(cam_raw: Any, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Promítne volitelnou výchozí kameru [lat, lon, km] na {x, y, km, zoom}."""
    if not isinstance(cam_raw, (list, tuple)) or len(cam_raw) < 2:
        return None
    cx, cy = ctx['project_xy'](float(cam_raw[0]), float(cam_raw[1]))
    km = float(cam_raw[2]) if len(cam_raw) >= 3 else 1.2
    out: dict[str, Any] = {'x': cx, 'y': cy, 'km': km}
    w = ctx['cam'].get('w')
    mpp = float(ctx['cam'].get('mpp') or 0.2)
    if w:
        clamped_km = min(max(km if km > 0 else 1.0, 0.05), w * mpp / 1000.0)
        out['zoom'] = round((w * mpp) / (clamped_km * 1000.0), 6)
    return out


def build_overlay(ctx: dict[str, Any]) -> dict[str, Any] | bool:
    """Zpracuje datový JSON doplňku pro client nebo server režim."""
    plugin_id = ctx['plugin_id']
    cfg = ctx['plugin_config']
    data_file = ctx['assets_dir'] / f'{plugin_id}.json'
    if not data_file.is_file():
        return False

    raw = json.loads(data_file.read_text(encoding='utf-8'))
    if raw.get('enabled', True) is False:
        return False

    mpp = float(ctx['cam'].get('mpp') or 0.2)
    mode = cfg.get('mode', 'client')
    project_xy = ctx['project_xy']

    public_levels: list[dict[str, Any]] = []
    secret_levels: list[dict[str, Any]] = []

    for lvl in raw.get('levels', []):
        cam_proj = _project_camera(lvl.get('camera'), ctx)
        pub_qs: list[dict[str, Any]] = []
        sec_qs: list[dict[str, Any]] = []

        for q in lvl.get('questions', []):
            radius_m = float(q.get('radius', 35))
            radius_px = round(radius_m / mpp, 1)
            q_pub: dict[str, Any] = {'id': q.get('id', ''), 'text': q.get('text', '')}
            q_sec: dict[str, Any] = {'id': q.get('id', ''), 'text': q.get('text', ''), 'radius_px': radius_px, 'answer': q.get('answer', '')}

            if 'lat' in q and 'lon' in q:
                q_sec['xy'] = list(project_xy(float(q['lat']), float(q['lon'])))

            targets_proj = []
            for t in q.get('targets') or []:
                pt = _project_target(t, radius_m, mpp, project_xy)
                if pt:
                    targets_proj.append(pt)
            if targets_proj:
                q_sec['targets'] = targets_proj

            if mode != 'server':
                pub_qs.append(q_sec)
            else:
                pub_qs.append(q_pub)
            sec_qs.append(q_sec)

        pub_lvl = {'lvl': lvl.get('lvl', '1'), 'text': lvl.get('text', ''), 'questions': pub_qs}
        if cam_proj:
            pub_lvl['camera'] = cam_proj
        public_levels.append(pub_lvl)
        secret_levels.append({'lvl': lvl.get('lvl', '1'), 'text': lvl.get('text', ''), 'questions': sec_qs})

    if mode == 'server':
        out_path = Path(cfg.get('server_data_out') or (ctx['server_data_dir'] / f'{plugin_id}.targets.json'))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    'plugin_id': plugin_id,
                    'title': raw.get('title', plugin_id),
                    'profanity_filter': bool(cfg.get('profanity_filter', True)),
                    'levels': secret_levels,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )

    return {
        'title': raw.get('title', plugin_id),
        'difficulties': raw.get('difficulties', {}),
        'levels': public_levels,
    }
