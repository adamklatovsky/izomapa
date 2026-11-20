// Vzorový server společné tabulky doplňku „Rychlostní zkouška“ pro Cloudflare Pages Functions.
// Instalace: zkopírujte do functions/api/rz.js, v Cloudflare vytvořte KV namespace, navažte ho jako RZ (wrangler.toml:
// [[kv_namespaces]] binding = "RZ", id = "…") a v assets/doplnky.json nastavte "rz": { "server_url": "/api/rz" }.
// Protokol (JSON POST, knihovna server_client): viz ../SPEC.md.
const MAX = 30;
const J = (o, st = 200) => new Response(JSON.stringify(o), { status: st, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

export async function onRequest({ request, env }) {
  if (!env.RZ) return J({ ok: false, error: 'not_configured', message: 'Tabulka není na serveru zapnutá.' }, 501);
  if (request.method !== 'POST') return J({ ok: false, error: 'method' }, 405);
  let b; try { b = await request.json(); } catch { return J({ ok: false, error: 'bad_json' }, 400); }
  const tab = String(b.tabulka || '');
  if (!/^[a-z0-9-]{1,40}$/.test(tab)) return J({ ok: false, error: 'bad_table', message: 'Neplatná trať.' }, 400);
  const key = `rz:${tab}`, L = (await env.RZ.get(key, 'json')) || [];
  if (b.action === 'leaderboard') return J({ ok: true, entries: L });
  if (b.action !== 'submit') return J({ ok: false, error: 'bad_action' }, 400);
  const n = String(b.nickname || '').replace(/[<>\u0000-\u001f]/g, '').trim().slice(0, 20), t = Number(b.time), delka = Number(b.delka);
  const s = Array.isArray(b.splits) ? b.splits.slice(0, 3).map(Number) : [];
  // věrohodnost: rostoucí mezičasy, průměr nejvýš 200 km/h (Rally2 v ulicích), nejvýš hodina
  const ok = n && Number.isFinite(t) && Number.isFinite(delka) && delka >= 300 && delka <= 300000 && t >= delka / 55 && t <= 3600
    && s.length === 3 && s.every((v, i) => Number.isFinite(v) && v > (i ? s[i - 1] : 0) && v < t);
  if (!ok) return J({ ok: false, error: 'invalid_record', message: 'Neplatný záznam.' }, 400);
  L.push({ n, t: Math.round(t * 100) / 100, s: s.map((v) => Math.round(v * 100) / 100), d: new Date().toISOString().slice(0, 10) });
  L.sort((a, c) => a.t - c.t);
  const top = L.slice(0, MAX);
  await env.RZ.put(key, JSON.stringify(top));
  return J({ ok: true, entries: top, rank: top.findIndex((r) => r.n === n && r.t === Math.round(t * 100) / 100) + 1 || null });
}
