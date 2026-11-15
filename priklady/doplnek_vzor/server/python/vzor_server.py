"""Referenční jazykově nezávislý backend adaptér v Pythonu (stdlib: hmac, json, sqlite3)."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import math
import random
import sqlite3
import time
from typing import Any


RATE_LIMIT_MS = 300


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def b64url_decode(text: str) -> bytes:
    pad = '=' * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def create_ticket(payload: dict[str, Any], secret_key: str) -> str:
    """Podepíše JSON payload bezstavovým HMAC-SHA256 podpisem."""
    encoded = b64url_encode(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
    sig = hmac.new(secret_key.encode('utf-8'), encoded.encode('ascii'), hashlib.sha256).hexdigest()
    return f'{encoded}.{sig}'


def verify_ticket(ticket: str, secret_key: str) -> dict[str, Any]:
    """Ověří podpis ticketu a vrátí dekódovaný payload, jinak vyhodí ValueError."""
    if not isinstance(ticket, str) or '.' not in ticket:
        raise ValueError('Neplatný formát ticketu')
    encoded, sig = ticket.split('.', 1)
    expected = hmac.new(secret_key.encode('utf-8'), encoded.encode('ascii'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError('Neplatný HMAC podpis ticketu')
    payload = json.loads(b64url_decode(encoded).decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('Neplatný payload ticketu')
    return payload


def compute_audit_hash(client_ip: str, secret_key: str, when: dt.date | None = None) -> str:
    """GDPR-safe 12znakový otisk IP adresy s týdenní ISO rotací (YYYY-WW)."""
    ref = when or dt.datetime.now(dt.timezone.utc).date()
    iso_year, iso_week, _ = ref.isocalendar()
    msg = f'{client_ip}|{iso_year:04d}-{iso_week:02d}'
    return hmac.new(secret_key.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()[:12]


def _point_in_polygon(x: float, y: float, pts: list[list[float]]) -> bool:
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i][0], pts[i][1]
        xj, yj = pts[j][0], pts[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _polygon_centroid(pts: list[list[float]]) -> dict[str, float]:
    return {
        'x': round(sum(p[0] for p in pts) / len(pts), 1),
        'y': round(sum(p[1] for p in pts) / len(pts), 1),
    }


def match_question_xy(question: dict[str, Any], x: float, y: float) -> dict[str, float] | None:
    """Ověří kliknutí (x, y) vůči bodovému nebo polygonálnímu cíli otázky."""
    r_px = float(question.get('radius_px') or 175.0)
    xy = question.get('xy')
    if isinstance(xy, list) and len(xy) >= 2 and math.hypot(x - xy[0], y - xy[1]) <= r_px:
        return {'x': xy[0], 'y': xy[1]}

    for t in question.get('targets') or []:
        t_type = t.get('type')
        if t_type == 'point' and math.hypot(x - t['xy'][0], y - t['xy'][1]) <= float(t.get('radius_px') or r_px):
            return {'x': t['xy'][0], 'y': t['xy'][1]}
        if t_type == 'polygon' and len(t.get('points') or []) >= 3 and _point_in_polygon(x, y, t['points']):
            return _polygon_centroid(t['points'])
    return None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            nickname TEXT NOT NULL,
            total_time_ms INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            season TEXT NOT NULL,
            certificate_id TEXT NOT NULL,
            audit_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scores_time ON scores(total_time_ms);
        """
    )
    conn.commit()


def _find_level(targets_data: dict[str, Any], level_id: Any) -> dict[str, Any] | None:
    for lvl in targets_data.get('levels') or []:
        if str(lvl.get('lvl')) == str(level_id):
            return lvl
    return None


def handle_action(
    data: dict[str, Any],
    targets_data: dict[str, Any],
    conn: sqlite3.Connection,
    secret_key: str,
    client_ip: str = '127.0.0.1',
    now_ms: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Zpracuje jednu ze 4 akcí (start, verify, finish, leaderboard)."""
    init_db(conn)
    action = str(data.get('action') or '')
    ts = int(time.time() * 1000) if now_ms is None else int(now_ms)

    if action == 'start':
        lvl = _find_level(targets_data, data.get('levelId'))
        if lvl is None:
            return 404, {'error': 'unknown_level', 'message': 'Úroveň neexistuje'}
        qs = lvl.get('questions') or []
        order = list(range(len(qs)))
        random.shuffle(order)
        payload = {
            'lvl': str(lvl.get('lvl')),
            'diff': str(data.get('difficulty') or 'easy')[:32],
            'season': str(data.get('season') or 'summer')[:16],
            'ord': order,
            'step': 0,
            'miss': 0,
            't0': ts,
            'tl': ts,
            'done': False,
            'el': 0,
        }
        return 200, {
            'order': order,
            'questionIds': [qs[i].get('id', '') for i in order],
            'ticket': create_ticket(payload, secret_key),
        }

    if action == 'verify':
        try:
            payload = verify_ticket(str(data.get('ticket') or ''), secret_key)
        except ValueError as exc:
            return 403, {'error': 'invalid_ticket', 'message': str(exc)}

        if payload.get('done'):
            return 400, {'error': 'already_done', 'message': 'Úroveň je již dokončená'}

        if ts - int(payload.get('tl', 0)) < RATE_LIMIT_MS:
            return 429, {'error': 'rate_limit', 'message': 'Příliš rychlé klikání'}

        lvl = _find_level(targets_data, payload.get('lvl'))
        if lvl is None:
            return 404, {'error': 'unknown_level', 'message': 'Úroveň neexistuje'}

        qs = lvl.get('questions') or []
        ord_list = payload.get('ord') or []
        step = int(payload.get('step', 0))
        if step < 0 or step >= len(ord_list):
            return 400, {'error': 'invalid_step', 'message': 'Neplatný krok v ticketu'}

        q = qs[ord_list[step]]
        hit_pt = match_question_xy(q, float(data.get('x', -1e9)), float(data.get('y', -1e9)))
        payload['tl'] = ts

        if hit_pt is None:
            payload['miss'] = int(payload.get('miss', 0)) + 1
            return 200, {'hit': False, 'completed': False, 'ticket': create_ticket(payload, secret_key)}

        step += 1
        payload['step'] = step
        elapsed = max(1, ts - int(payload.get('t0', ts)))
        if step >= len(ord_list):
            payload['done'] = True
            payload['el'] = elapsed

        return 200, {
            'hit': True,
            'completed': bool(payload['done']),
            'elapsedMs': elapsed,
            'targetHint': hit_pt,
            'answer': q.get('answer', ''),
            'ticket': create_ticket(payload, secret_key),
        }

    if action == 'finish':
        raw_tickets = data.get('tickets')
        if not isinstance(raw_tickets, list) or not raw_tickets:
            return 400, {'error': 'missing_tickets', 'message': 'Chybí tickety úrovní'}

        required_lvls = [str(l.get('lvl')) for l in (targets_data.get('levels') or [])]
        verified: dict[str, dict[str, Any]] = {}
        for t in raw_tickets:
            try:
                p = verify_ticket(str(t), secret_key)
            except ValueError as exc:
                return 403, {'error': 'invalid_ticket', 'message': str(exc)}
            if not p.get('done'):
                return 400, {'error': 'incomplete_level', 'message': 'Některá úroveň není dokončená'}
            lvl_id = str(p.get('lvl'))
            if lvl_id in verified:
                return 400, {'error': 'duplicate_level', 'message': 'Duplicitní úroveň v ticketech'}
            verified[lvl_id] = p

        if set(verified.keys()) != set(required_lvls):
            return 400, {'error': 'missing_levels', 'message': 'Nejsou dokončeny všechny povinné úrovně'}

        total_ms = sum(max(1, int(p.get('el', 0))) for p in verified.values())
        last_p = verified[required_lvls[-1]]
        nickname = (str(data.get('nickname') or '').strip() or 'Anonymní hledač')[:50]
        audit_hash = compute_audit_hash(client_ip, secret_key)
        cert_seed = f'{nickname}:{total_ms}:{audit_hash}:{ts}'
        cert_id = hmac.new(secret_key.encode('utf-8'), cert_seed.encode('utf-8'), hashlib.sha256).hexdigest()[:6].upper()

        cur = conn.execute(
            'INSERT INTO scores (nickname, total_time_ms, difficulty, season, certificate_id, audit_hash) VALUES (?, ?, ?, ?, ?, ?)',
            (nickname, total_ms, last_p.get('diff', 'easy'), last_p.get('season', 'summer'), cert_id, audit_hash),
        )
        conn.commit()
        rank = conn.execute('SELECT COUNT(*) FROM scores WHERE total_time_ms < ?', (total_ms,)).fetchone()[0] + 1
        return 200, {
            'saved': True,
            'id': cur.lastrowid,
            'totalTimeMs': total_ms,
            'rank': rank,
            'certificateId': cert_id,
        }

    if action == 'leaderboard':
        rows = conn.execute(
            'SELECT nickname, total_time_ms, difficulty, season, certificate_id, created_at FROM scores ORDER BY total_time_ms ASC, created_at ASC LIMIT 20'
        ).fetchall()
        return 200, {
            'entries': [
                {
                    'nickname': r[0],
                    'totalTimeMs': r[1],
                    'difficulty': r[2],
                    'season': r[3],
                    'certificateId': r[4],
                    'createdAt': r[5],
                }
                for r in rows
            ]
        }

    return 400, {'error': 'unknown_action', 'message': 'Neznámá akce'}
