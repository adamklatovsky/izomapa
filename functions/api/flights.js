// Cloudflare Pages Function: aircraft near the map from adsb.lol (ODbL, no key).
// Browsers cannot call adsb.lol or OpenSky directly (no CORS for other origins), so the map asks this endpoint.
// Query: lamin, lamax, lomin, lomax (the box the map sends); answer is cached for 15 s for all visitors.
// Only a map-sized box (the map asks for ~0.7° × 1.05°) centred in Czechia and around it (izomapa works only there),
// so the endpoint is not an open proxy to adsb.lol for the whole world. An outage is cached too (empty list),
// so visitors do not each wait for the timeout (4 s, shorter than the map's 4.5 s, so the empty answer gets cached).
export async function onRequest({ request }) {
  const q = new URL(request.url).searchParams;
  const n = (k) => Number.parseFloat(q.get(k));
  const [la0, la1, lo0, lo1] = ['lamin', 'lamax', 'lomin', 'lomax'].map(n);
  const la = (la0 + la1) / 2, lo = (lo0 + lo1) / 2;
  if (![la0, la1, lo0, lo1].every(Number.isFinite) || la1 - la0 > 2 || lo1 - lo0 > 3 || la < 47.5 || la > 52 || lo < 11 || lo > 20)
    return new Response('{"ac":[]}', { status: 400, headers: { 'content-type': 'application/json' } });
  const src = `https://api.adsb.lol/v2/point/${la.toFixed(2)}/${lo.toFixed(2)}/35`;
  const cache = caches.default, key = new Request(src);
  let r = await cache.match(key);
  if (!r) {
    let body = '{"ac":[]}';
    try {
      const up = await fetch(src, { headers: { 'user-agent': 'izomapa-letadla/1.0' }, signal: AbortSignal.timeout(4000) });
      if (up.ok) body = await up.text();
    } catch {}
    r = new Response(body, { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=15' } });
    await cache.put(key, r.clone());
  }
  return r;
}
