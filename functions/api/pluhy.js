// Cloudflare Pages Function: sypače a pluhy zimní údržby ŘSD (dálnice a silnice I. třídy) z veřejné mapy https://udrzba.rsd.cz.
// Prohlížeč na API ŘSD přímo nedosáhne (bez CORS), proto se ptá tohoto endpointu. Dotaz: lamin, lamax, lomin, lomax.
// Odpověď: { pts: [{ id, lon, lat, t, v, z, s }], trasy: [{ a, z, s, l: [[lon, lat], …] }] }, kde
//   z = 0 zásah (posyp / pluhování), 1 = pojezd bez zásahu; s = 1 dálnice, 0 silnice I. třídy;
//   a = stáří trasy (0 do 30 min, 1 do 1 h, 2 do 3 h, 3 do 6 h, 4 do 12 h).
// Polohy se cachují 5 s, trasy 60 s (pro všechny návštěvníky společně).
const API = 'https://udrzba.rsd.cz/data/api/v1.0/GPSMapsAPI/';
const AGE = { toThirty: 0, fromThirtyToSixty: 1, fromSixtyToThreeHours: 2, fromThreeHoursToSixHours: 3, fromSixHoursToTwelveHours: 4 };

async function cached(path, ttl) {
  const cache = caches.default, key = new Request(API + path);
  let r = await cache.match(key);
  if (!r) {
    let body = 'null';                                   // výpadek ŘSD se cachuje taky (30 s), ať každý dotaz nečeká 6 s na timeout
    try {
      const up = await fetch(API + path, { headers: { 'user-agent': 'izomapa-pluhy/1.0' }, signal: AbortSignal.timeout(6000) });
      if (up.ok) body = await up.text();
    } catch {}
    r = new Response(body, { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': `public, max-age=${body === 'null' ? 30 : ttl}` } });
    await cache.put(key, r.clone());
  }
  try { return await r.json(); } catch { return null; }
}

export async function onRequest({ request }) {
  const q = new URL(request.url).searchParams;
  const [la0, la1, lo0, lo1] = ['lamin', 'lamax', 'lomin', 'lomax'].map((k) => Number.parseFloat(q.get(k)));
  const J = (o, st = 200) => new Response(JSON.stringify(o), { status: st, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=5' } });
  if (![la0, la1, lo0, lo1].every(Number.isFinite) || la1 - la0 > 2 || lo1 - lo0 > 3) return J({ pts: [], trasy: [] }, 400);
  const inBox = ([lon, lat]) => lat >= la0 && lat <= la1 && lon >= lo0 && lon <= lo1;
  const [P, L, O] = await Promise.all([cached('GetGEOJSONWholeLivePoints', 5), cached('GetGEOJSONWholeLive/2/0/0/0/0', 60), cached('GetGEOJSONWholeOld/2/0/0/0/0', 60)]);
  const ok = (f) => f && f.properties && f.geometry && Array.isArray(f.geometry.coordinates);   // neúplný záznam přeskočit, ať neshodí celou odpověď
  const pts = ((P && P.features) || []).filter((f) => ok(f) && inBox(f.geometry.coordinates)).map((f) => ({
    id: f.properties.name, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], t: f.properties.time,
    v: f.properties.speed, z: f.properties.control, s: f.properties.roadType }));
  const trasy = [];
  for (const f of [...((L && L.features) || []), ...((O && O.features) || [])]) {
    if (!ok(f)) continue;
    const a = AGE[f.properties.name]; if (a === undefined) continue;
    const lines = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const l of lines) {
      let run = [];                                     // jen části uvnitř výřezu (s jedním bodem přesahu kvůli okraji)
      for (let i = 0; i < l.length; i++) {
        if (inBox(l[i]) || (i + 1 < l.length && inBox(l[i + 1])) || (i > 0 && inBox(l[i - 1]))) run.push(l[i].map((v) => Math.round(v * 1e6) / 1e6));
        else if (run.length) { if (run.length > 1) trasy.push({ a, z: f.properties.control, s: f.properties.roadType, l: run }); run = []; }
      }
      if (run.length > 1) trasy.push({ a, z: f.properties.control, s: f.properties.roadType, l: run });
    }
  }
  return J({ pts, trasy });
}
