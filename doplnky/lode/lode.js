// Doplněk „Lodě a koupání“: ilustrační provoz na jezeře (assets/doplnky/lode.json).
// Parníky jezdí po trase lodní linky (čára [lat, lon], uzavřená smyčka nebo tam a zpět) a na zastávkách stojí; poloha
// se počítá z hodin, takže všichni návštěvníci vidí loď na stejném místě. Šlapadla bloumají kolem půjčoven, plachetnice
// křižují po jezeře (nebo po "plachetnice.oblast"); každý úsek cesty se předem ověří, že vede po vodě dál od břehu.
// Kajaky a kánoe jezdí tam a zpět podél břehu (5–30 m od něj, mimo trasu parníku) a jejich poloha se počítá z hodin.
// V létě za jasného počasí se u pláží koupou lidé a na plážích leží, sedí a chodí k vodě (slunečníky, deky). Jen ve dne a v sezóně (v létě nejvíc, na jaře a na podzim málo,
// v zimě nic), za deště a mlhy méně. Lodě se kreslí jako vozidla mapy (kvádry stínované sluncem, obrys 1 px, cache
// podle druhu a směru), plavci jako chodci (bod 10 cm). Lodě patří k vrstvě Doprava, plavci k vrstvě Lidé.
// V zimě (zimní dlaždice kreslí jezero jako led) jezdí po ledu ve dne za jasna lední jachty a snowkiteři (podle větru,
// v bezvětří skoro nikdo) a u břehu bruslí lidé ("zima" v datech). Ilustrační provoz, na led se smí jen v mrazivé zimě.
(() => {
  const ID = 'lode';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;
  let unsub = null;

  const NDIR = 32;
  const SUNV = (() => { const v = [0.38, -0.68, 0.62], n = Math.hypot(...v); return v.map((q) => q / n); })();
  const lit = (rgb, d) => { const f = (0.62 + 0.42 * Math.max(0, d)) / 0.88; return `rgb(${rgb.map((q) => Math.min(255, Math.round(q * f))).join(',')})`; };
  const rnd = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const SEASON = { summer: 1, spring: 0.3, autumn: 0.3, winter: 0 };     // sezóna zhruba květen až září
  const WEATHER = { clear: 1, rain: 0.35, fog: 0.5, snow: 0 };
  const SL_COL = [[242, 196, 48], [214, 64, 40], [47, 111, 209], [236, 238, 236], [42, 163, 107]];
  const SAIL_COL = [[246, 246, 240], [246, 246, 240], [246, 246, 240], [214, 64, 40], [240, 200, 90]];
  const SKIN = ['#e8b894', '#d9a27c', '#f0c8a8', '#b97f5a'], CAPS = ['#d8352a', '#2f6fd1', '#f2c230', '#f2f0ea', '#2aa36b', '#e0629a'];
  const HAIR = ['#3a2a22', '#6b4a2e', '#c9a05a', '#1d1f24'];
  const layerOn = (id) => { const e = document.getElementById(id); return !e || e.checked; };

  // modely lodí: kvádry [s0, s1, t0, t1, z0, z1, rgb] (s podél lodi dopředu, t napříč, z nahoru; metry)
  const WHITE = [238, 240, 238], GL = [64, 84, 108], DK = [44, 46, 50], WOOD = [150, 108, 66], BLUE = [40, 86, 160], SKN = [222, 172, 136];
  function model(kind, c) {
    const B = [];
    const box = (...a) => B.push(a);
    if (kind === 'sl') {                                      // šlapadlo 3 × 1,6 m: dva plováky, sedadlo, dva lidé
      box(-1.5, 1.5, -0.8, -0.42, 0, 0.35, c); box(-1.5, 1.5, 0.42, 0.8, 0, 0.35, c);
      box(-1.0, 1.0, -0.6, 0.6, 0.28, 0.4, WHITE);
      box(0.2, 0.7, -0.22, 0.22, 0.4, 0.7, c);                // kryt šlapacího kola
      box(-0.75, -0.5, -0.6, 0.6, 0.4, 0.95, c);             // opěradlo
      for (const t of [-0.3, 0.3]) { box(-0.5, -0.2, t - 0.17, t + 0.17, 0.4, 0.95, t < 0 ? [47, 111, 209] : [214, 64, 40]); box(-0.45, -0.25, t - 0.1, t + 0.1, 0.95, 1.2, SKN); }
    } else if (kind === 'pl') {                              // plachetnice 5 m: trup, kokpit, stěžeň, hlavní plachta a kosatka (stupňovitě)
      box(-2.5, 1.9, -0.9, 0.9, 0, 0.5, WHITE); box(1.9, 2.5, -0.45, 0.45, 0, 0.5, WHITE);
      box(-2.5, 1.9, -0.92, 0.92, 0.12, 0.22, BLUE);
      box(-2.1, -0.5, -0.6, 0.6, 0.5, 0.6, WOOD);
      box(-1.7, -1.4, -0.4, -0.1, 0.6, 1.2, SKN);            // kormidelník
      box(0.55, 0.7, -0.06, 0.06, 0.5, 7.5, [190, 192, 196]);
      for (let k = 0; k < 6; k++) { const L = 3.0 * (1 - k / 6.5); box(0.55 - L, 0.55, -0.03, 0.03, 0.9 + k * 1.05, 1.95 + k * 1.05, c); }
      for (let k = 0; k < 5; k++) { const L = 1.7 * (1 - k / 5.5); box(0.7, 0.7 + L, -0.03, 0.03, 0.6 + k * 1.2, 1.8 + k * 1.2, c); }
    } else if (kind === 'kj' || kind === 'kn') {             // kajak 4,6 m s jedním, kánoe 5,2 m se dvěma (vesty); pádla kreslí lode.js zvlášť, aby se hýbala
      const kn = kind === 'kn', hw = kn ? 0.42 : 0.3, L = kn ? 2.3 : 2.05;
      box(-L, L, -hw, hw, 0, kn ? 0.38 : 0.28, c); box(L, L + 0.4, -hw * 0.4, hw * 0.4, 0, kn ? 0.42 : 0.22, c); box(-L - 0.4, -L, -hw * 0.4, hw * 0.4, 0, kn ? 0.42 : 0.22, c);
      for (const s of kn ? [-1.3, 1.3] : [-0.1]) {
        box(s - 0.17, s + 0.13, -0.2, 0.2, 0.3, 0.82, s > 0 ? [214, 64, 40] : [242, 196, 48]);
        box(s - 0.11, s + 0.09, -0.1, 0.1, 0.82, 1.06, SKN);
      }
    } else if (kind[0] === 'j') {                            // lední jachta ~6 m: trup, příčník se dvěma bruslemi, řiditelná brusle vpředu, jezdec vleže
      const sd = kind === 'jL' ? -1 : 1;                     // plachta vyfouknutá na závětrnou stranu
      box(-2.6, 3.4, -0.16, 0.16, 0.35, 0.5, c);
      box(-1.25, -0.95, -2.3, 2.3, 0.35, 0.45, WOOD);
      for (const tt of [-2.2, 2.2]) box(-1.7, -0.5, tt - 0.05, tt + 0.05, 0, 0.35, DK);
      box(2.9, 3.8, -0.05, 0.05, 0, 0.35, DK);
      box(-2.4, -0.7, -0.28, 0.28, 0.5, 0.78, [214, 64, 40]); box(-0.7, -0.4, -0.22, 0.22, 0.5, 0.85, [240, 240, 236]);   // jezdec vleže a přilba
      box(0.85, 1.0, -0.06, 0.06, 0.5, 7.0, [190, 192, 196]);
      for (let k = 0; k < 6; k++) { const L = 3.2 * (1 - k / 6.5), tt = sd * 0.12 * (6 - k); box(0.85 - L, 0.85, tt - 0.03, tt + 0.03, 0.8 + k * 1.0, 1.85 + k * 1.0, [246, 246, 240]); }
    } else if (kind === 'pm') {                              // malá výletní loď ~16 m: trup s pruhem, kajuta s okny, kormidelna
      box(-8, 6.5, -2, 2, 0, 1.2, WHITE); box(6.5, 8, -1.2, 1.2, 0, 1.2, WHITE);
      box(-8, 6.5, -2.03, 2.03, 0.55, 0.8, c);
      box(-6, 4, -1.7, 1.7, 1.2, 3.0, WHITE); box(-5.8, 3.8, -1.72, 1.72, 2.0, 2.6, GL);
      box(-6.3, 4.3, -1.9, 1.9, 3.0, 3.2, c);
      box(2.6, 4.0, -1.0, 1.0, 3.2, 4.1, WHITE); box(3.5, 4.02, -0.9, 0.9, 3.5, 3.9, GL);
    } else {                                                  // velká loď ~30 m: dvě paluby, horní paluba se stříškou a lidmi
      box(-15, 13, -3.2, 3.2, 0, 1.6, WHITE); box(13, 15, -2, 2, 0, 1.6, WHITE);
      box(-15, 13, -3.23, 3.23, 0.7, 1.0, c);
      box(-12, 10, -2.9, 2.9, 1.6, 3.6, WHITE); box(-11.8, 9.8, -2.92, 2.92, 2.4, 3.1, GL);
      box(-13, 11, -3.05, 3.05, 3.6, 3.8, [226, 220, 204]);
      for (const s of [-12.5, -6, 0, 5.5]) for (const t of [-2.8, 2.6]) box(s, s + 0.2, t, t + 0.2, 3.8, 5.6, DK);
      for (let k = 0; k < 9; k++) { const s = -11 + k * 1.8 + rnd(k) * 0.6, t = (rnd(k + 9) - 0.5) * 4; box(s, s + 0.4, t, t + 0.4, 3.8, 4.9, [[214, 64, 40], [47, 111, 209], [240, 240, 236], [42, 163, 107]][k % 4]); box(s + 0.05, s + 0.35, t + 0.05, t + 0.35, 4.9, 5.25, SKN); }
      box(-13, 6, -3.0, 3.0, 5.6, 5.75, c);
      box(6.5, 9.8, -1.8, 1.8, 3.8, 5.8, WHITE); box(9.0, 9.82, -1.6, 1.6, 4.6, 5.4, GL); box(6.3, 10, -2.0, 2.0, 5.8, 6.0, c);
    }
    return B;
  }

  Izomapa.registerPlugin(ID, {
    onInit(api) {
      const D = api.getPluginData(ID);
      if (!D || !D.voda) return;
      const W = (q) => api.latLonToWorld(q[0], q[1]);
      const toImg = api.toImg, gz = api.gz;
      // plocha z prstenců: sudo-liché pravidlo, takže ostrovy (další prstence uvnitř) jsou díry
      const area = (rings) => {
        const E = []; let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const r0 of rings) { const r = r0.map(W); for (let i = 0, j = r.length - 1; i < r.length; j = i++) E.push([r[j], r[i]]); for (const [x, y] of r) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); } }
        const inside = (x, y) => { let c = false; for (const [[xj, yj], [xi, yi]] of E) if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; return c; };
        const dist = (x, y) => { let m = 1e9; for (const [a, b] of E) { const dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy || 1))); m = Math.min(m, Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)); } return m; };
        const near = (x, y) => { let m = 1e9, q = null; for (const [a, b] of E) { const dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy || 1))), d = Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy); if (d < m) { m = d; q = [a[0] + t * dx, a[1] + t * dy]; } } return q; };
        return { inside, dist, near, box: [x0, y0, x1, y1] };
      };
      const voda = area(D.voda), sailA = D.plachetnice?.oblast ? area(D.plachetnice.oblast) : null;
      const ok = (x, y, mg, A) => voda.inside(x, y) && voda.dist(x, y) > mg && (!A || A.inside(x, y));
      const legOk = (a, b, mg, A) => {                       // celý úsek po vodě (jezero je členité, rovná čára může přejít poloostrov)
        const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 10));
        for (let k = 1; k <= n; k++) if (!ok(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, mg, A)) return false;
        return true;
      };
      const pick = (cx, cy, R, mg, A, from) => {
        for (let k = 0; k < 40; k++) {
          const a = Math.random() * Math.PI * 2, r = R * Math.sqrt(Math.random()), x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
          if (ok(x, y, mg, A) && (!from || legOk(from, [x, y], mg, A))) return [x, y];
        }
        return null;
      };

      // bloudící lodě: šlapadla u půjčoven, plachetnice po jezeře
      const boats = [];
      let n = 0;
      for (const P of D.pujcovny || []) {
        const h = W(P.q);
        for (let k = 0; k < (P.pocet ?? 5); k++, n++) {
          const p = pick(h[0], h[1], P.radius ?? 110, 6); if (!p) continue;
          boats.push({ kind: 'sl', c: SL_COL[n % SL_COL.length], x: p[0], y: p[1], home: h, R: P.radius ?? 110, mg: 6, v: 0.9 + rnd(n) * 0.4, q: rnd(n + 50), h: rnd(n + 7) * 6.28, wait: rnd(n + 3) * 20, len: 3 });
        }
      }
      const [bx0, by0, bx1, by1] = (sailA || voda).box, bc = [(bx0 + bx1) / 2, (by0 + by1) / 2], bR = Math.hypot(bx1 - bx0, by1 - by0) / 2;
      for (let k = 0; k < (D.plachetnice?.pocet ?? 0); k++, n++) {
        const p = pick(bc[0], bc[1], bR, 20, sailA); if (!p) continue;
        boats.push({ kind: 'pl', c: SAIL_COL[k % SAIL_COL.length], x: p[0], y: p[1], home: null, mg: 20, v: 2.2 + rnd(n) * 1.2, q: rnd(n + 50), h: rnd(n + 7) * 6.28, wait: rnd(n + 3) * 10, len: 5 });
      }
      function stepBoat(b, dt) {
        if (!b.t) {
          b.wait -= dt; if (b.wait > 0) return;
          const t = b.next ? b.next(b) : b.kind === 'pl' ? pick(b.x, b.y, 600, b.mg, sailA, [b.x, b.y]) : pick(b.home[0], b.home[1], b.R, b.mg, null, [b.x, b.y]);
          if (!t || Math.hypot(t[0] - b.x, t[1] - b.y) < 15) { b.wait = 3; return; }
          b.t = t;
        }
        const dx = b.t[0] - b.x, dy = b.t[1] - b.y, d = Math.hypot(dx, dy);
        let dh = Math.atan2(dy, dx) - b.h; dh = Math.atan2(Math.sin(dh), Math.cos(dh));
        const tr = b.tr ?? 0.5; b.h += Math.max(-tr * dt, Math.min(tr * dt, dh));   // nejdřív se natočí, pak jede rovně po ověřeném úseku
        if (Math.abs(dh) > 0.35) { b.moving = false; return; }
        const s = Math.min(d, b.v * dt); b.x += dx / d * s; b.y += dy / d * s; b.moving = true;
        if (d - s < 0.5) { b.t = null; b.moving = false; b.wait = b.pause ? b.pause() : b.kind === 'pl' ? 2 + Math.random() * 8 : 5 + Math.random() * 25; }
      }

      // parníky: poloha z hodin podle jízdního řádu na smyčce (stání na zastávkách, mezi nimi stálá rychlost)
      const ships = (D.parniky || []).map((S, i) => {
        const pts = S.trasa.map(W), closed = Math.hypot(pts[0][0] - pts[pts.length - 1][0], pts[0][1] - pts[pts.length - 1][1]) < 30;
        if (!closed) for (let k = pts.length - 2; k > 0; k--) pts.push(pts[k]);   // otevřená trasa: tam a zpět
        pts.push(pts[0]);
        const len = [0]; for (let k = 1; k < pts.length; k++) len.push(len[k - 1] + Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]));
        const L = len[len.length - 1], V = S.rychlost ?? 2.0, DW = S.stani ?? (S.zastavky?.length > 1 ? 60 : 600);
        const stops = (S.zastavky || []).map((q) => { const w = W(q); let b = 0; pts.forEach((p, k) => { if (Math.hypot(p[0] - w[0], p[1] - w[1]) < Math.hypot(pts[b][0] - w[0], pts[b][1] - w[1])) b = k; }); return len[b] % L; }).sort((a, b) => a - b);
        const plan = []; let T = 0;                          // [začátek, s0, s1, stání?]
        if (!stops.length) { plan.push([0, 0, L, 0]); T = L / V; }
        stops.forEach((s, k) => { plan.push([T, s, s, 1]); T += DW; const s1 = k + 1 < stops.length ? stops[k + 1] : stops[0] + L; plan.push([T, s, s1, 0]); T += (s1 - s) / V; });
        const at = (s) => { s = ((s % L) + L) % L; let k = 1; while (k < len.length - 1 && len[k] < s) k++; const a = pts[k - 1], b = pts[k], f = (s - len[k - 1]) / ((len[k] - len[k - 1]) || 1); return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, b[0] - a[0], b[1] - a[1]]; };
        return { kind: S.typ === 'velky' ? 'pv' : 'pm', c: S.typ === 'velky' ? [36, 70, 140] : [40, 110, 170], plan, T, at, V, off: (S.posun ?? 0) * T, q: rnd(i + 200) * 0.6, len: S.typ === 'velky' ? 30 : 16 };
      });
      const shipPose = (S, now) => {
        const tau = ((now / 1000 + S.off) % S.T + S.T) % S.T;
        let k = S.plan.length - 1; while (k > 0 && S.plan[k][0] > tau) k--;
        const [t0, s0, s1, dwell] = S.plan[k], s = dwell ? s0 : s0 + (tau - t0) * S.V, p = S.at(dwell ? s0 + 1 : s);
        return { x: p[0], y: p[1], h: Math.atan2(p[3], p[2]), moving: !dwell };
      };

      // koupající: body ve vodě do 22 m od pláže
      const swimmers = [];
      (D.plaze || []).forEach((P, bi) => {
        const A = area([P.q]), [x0, y0, x1, y1] = A.box, N = P.pocet ?? 30;
        for (let k = 0, tries = 0; k < N && tries < N * 80; tries++) {
          const x = x0 - 30 + rnd(bi * 9973 + tries * 2) * (x1 - x0 + 60), y = y0 - 30 + rnd(bi * 7919 + tries * 2 + 1) * (y1 - y0 + 60);
          if (!voda.inside(x, y) || A.inside(x, y) || A.dist(x, y) > 22 || voda.dist(x, y) < 1.5) continue;
          const z = bi * 1000 + k++;
          swimmers.push({ x, y, ph: rnd(z) * 6.28, kind: rnd(z + 1) < 0.25 ? 1 : rnd(z + 2) < 0.15 ? 2 : 0, skin: SKIN[z % SKIN.length], cap: rnd(z + 3) < 0.4 ? CAPS[z % CAPS.length] : HAIR[z % HAIR.length],
            suit: CAPS[(z + 2) % CAPS.length], ring: CAPS[(z + 4) % CAPS.length], q: rnd(z + 4) });
        }
      });

      // kajaky a kánoe: smyčka tam a zpět podél břehu (5–30 m od něj, 25 m od trasy parníku), poloha z hodin a z čísla lodi,
      // takže všichni návštěvníci je vidí na stejném místě; domov je u půjčoven a pláží
      const route = (x, y) => { let m = 1e9; for (const S of D.parniky || []) { const r = S.trasa.map(W); for (let i = 1; i < r.length; i++) { const [a, b] = [r[i - 1], r[i]], dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy || 1))); m = Math.min(m, Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)); } } return m; };
      const band = (x, y) => { if (!voda.inside(x, y)) return false; const d = voda.dist(x, y); return d >= 5 && d <= 30 && route(x, y) > 25; };
      const bandLeg = (a, b) => { const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 5)); for (let k = 1; k <= n; k++) if (!band(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)) return false; return true; };
      const homes = [...(D.pujcovny || []).map((P) => W(P.q)), ...(D.plaze || []).map((P) => { const r = P.q.map(W); return [r.reduce((a, q) => a + q[0], 0) / r.length, r.reduce((a, q) => a + q[1], 0) / r.length]; })];
      const kayaks = [];
      for (let k = 0; k < (homes.length ? D.kajaky?.pocet ?? 0 : 0); k++) {
        const h = homes[k % homes.length], z = 900 + k * 61; let p = null;
        for (let t = 0; t < 200 && !p; t++) { const a = rnd(z + t * 2) * 6.283, r = 150 * Math.sqrt(rnd(z + t * 2 + 1)), q = [h[0] + Math.cos(a) * r, h[1] + Math.sin(a) * r]; if (band(...q)) p = q; }
        if (!p) continue;
        const pts = [p];
        for (let leg = 0, t = 0; leg < 10 && t < 400; t++) {
          const a = rnd(z + 500 + t * 2) * 6.283, L = 20 + rnd(z + 501 + t * 2) * 40, c = pts[pts.length - 1], q = [c[0] + Math.cos(a) * L, c[1] + Math.sin(a) * L];
          if (Math.hypot(q[0] - h[0], q[1] - h[1]) < 260 && bandLeg(c, q)) { pts.push(q); leg++; }
        }
        if (pts.length < 2) continue;
        for (let i = pts.length - 2; i >= 0; i--) pts.push(pts[i]);   // tam a zpět
        const len = [0]; for (let i = 1; i < pts.length; i++) len.push(len[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
        kayaks.push({ kind: rnd(z + 3) < 0.35 ? 'kn' : 'kj', c: [[214, 64, 40], [236, 128, 32], [42, 163, 107], [47, 111, 209], [236, 238, 236]][k % 5], pts, len, v: 1.0 + rnd(z + 4) * 0.5, off: rnd(z + 5) * 1e4, q: rnd(z + 6) });
      }
      const kayakPose = (K, now) => {
        const L = K.len[K.len.length - 1], s = ((now / 1000 * K.v + K.off) % L + L) % L; let i = 1; while (i < K.len.length - 1 && K.len[i] < s) i++;
        const a = K.pts[i - 1], b = K.pts[i], f = (s - K.len[i - 1]) / ((K.len[i] - K.len[i - 1]) || 1);
        return { x: a[0] + (b[0] - a[0]) * f, y: a[1] + (b[1] - a[1]) * f, h: Math.atan2(b[1] - a[1], b[0] - a[0]), moving: true, kind: K.kind, c: K.c, len: K.kind === 'kn' ? 5.2 : 4.6, paddle: now / 1000 * 2.4 + K.off };
      };

      // lidé na plážích (plaze[].lezaci): leží na dekách, sedí, chodí k vodě a zpět, děti; slunečníky. Místa pevně podle čísla pláže
      // a postavy, chůze k vodě podle hodin: všichni návštěvníci vidí totéž
      const TOWEL = ['#e8402a', '#2f6fd1', '#f2c230', '#f2f0ea', '#2aa36b', '#e0629a', '#7a3fa8'], beach = [];
      (D.plaze || []).forEach((P, bi) => {
        const A = area([P.q]), [x0, y0, x1, y1] = A.box, N = P.lezaci ?? 0;
        for (let k = 0, t = 0; k < N && t < N * 80; t++) {
          const z = 3000 + bi * 7001 + t * 3, x = x0 + rnd(z) * (x1 - x0), y = y0 + rnd(z + 1) * (y1 - y0);
          if (!A.inside(x, y) || A.dist(x, y) < 1.5 || voda.inside(x, y)) continue;
          const w = bi * 1000 + k++, r = rnd(w + 7), o = { x, y, q: rnd(w + 8), d: rnd(w + 9) < 0.5 ? 1 : -1, skin: SKIN[w % SKIN.length], hair: HAIR[w % HAIR.length], suit: CAPS[(w + 1) % CAPS.length], towel: TOWEL[w % TOWEL.length] };
          o.m = r < 0.45 ? 'lie' : r < 0.7 ? 'sit' : r < 0.85 ? 'walk' : 'kid';
          if (o.m === 'walk') { const wq = voda.near(x, y), d = Math.hypot(wq[0] - x, wq[1] - y); o.wq = [x + (wq[0] - x) * (d + 1.5) / d, y + (wq[1] - y) * (d + 1.5) / d]; o.T = 2 * (d + 1.5) / 1.1 + 40 + rnd(w + 10) * 60; o.off = rnd(w + 11) * o.T; }
          beach.push(o);
          if (o.m === 'lie' && rnd(w + 12) < 0.35) beach.push({ m: 'umb', x: x + 0.6, y: y - 0.6, q: o.q, c: [CAPS[w % CAPS.length], CAPS[(w + 3) % CAPS.length]] });   // slunečník trochu před dekou, aby ji kryl
        }
      });
      const beachPos = (o, now) => {
        if (o.m !== 'walk') return [o.x, o.y, 0];
        const ph = ((now / 1000 + o.off) % o.T + o.T) % o.T, d = Math.hypot(o.wq[0] - o.x, o.wq[1] - o.y), tw = d / 1.1, rest = (o.T - 2 * tw) / 2;
        const f = ph < tw ? ph / tw : ph < tw + rest ? 1 : ph < 2 * tw + rest ? 1 - (ph - tw - rest) / tw : 0, mv = (ph < tw || (ph >= tw + rest && ph < 2 * tw + rest)) ? 1 : 0;
        return [o.x + (o.wq[0] - o.x) * f, o.y + (o.wq[1] - o.y) * f, mv];
      };

      // zima na ledu: vítr ve světových souřadnicích (kam fouká); prohlížeč zná jen směr na obrazovce, převod zpět z 00-zaklad.js
      let WD = [0.7071, -0.7071];                            // bez skutečného větru jako kouř z komínů: vítr na obrazovce doprava
      const setWind = (w) => { if (!w) return; const a = w.dx / 0.7071, c = -w.dy / 0.3536, e = (a + c) / 2, nn = (c - a) / 2, l = Math.hypot(e, nn); if (l > 1e-6) WD = [e / l, nn / l]; };
      const Z = D.zima || {}, ice = [];
      const legTo = (b, ang, L0, L1) => {                    // dlouhý rovný úsek přes led pod úhlem k větru, ověřený po celé délce
        for (let k = 0; k < 24; k++) {
          const a = Math.atan2(WD[1], WD[0]) + (Math.random() < 0.5 ? -1 : 1) * (ang[0] + Math.random() * (ang[1] - ang[0])), L = L0 + Math.random() * (L1 - L0);
          const p = [b.x + Math.cos(a) * L, b.y + Math.sin(a) * L];
          if (ok(p[0], p[1], b.mg) && legOk([b.x, b.y], p, b.mg)) return p;
        }
        return pick(b.x, b.y, 300, b.mg, null, [b.x, b.y]);
      };
      const SUITS = ['#d8352a', '#2f6fd1', '#2aa36b', '#e0a020', '#7a3fa8', '#1d1f24'];
      (Z.bruslari || []).forEach((P, bi) => {
        const h = W(P.q);
        for (let k = 0; k < (P.pocet ?? 12); k++) {
          const z = 500 + bi * 100 + k, p = pick(h[0], h[1], P.radius ?? 140, 8); if (!p) continue;
          ice.push({ kind: 'br', x: p[0], y: p[1], home: h, R: P.radius ?? 140, mg: 8, v: 2 + rnd(z) * 2.5, tr: 3, q: rnd(z + 1), h: rnd(z + 2) * 6.28, wait: rnd(z + 3) * 8,
            col: SUITS[z % SUITS.length], hat: CAPS[(z + 3) % CAPS.length], skin: SKIN[z % SKIN.length], ph: rnd(z + 4) * 6.28, next: (b) => pick(b.home[0], b.home[1], b.R, b.mg, null, [b.x, b.y]), pause: () => 1 + Math.random() * 6 });
        }
      });
      for (let k = 0; k < (Z.jachty ?? 0); k++) {            // lední jachty: napříč větrem (nejrychlejší kurz), dlouhé dráhy
        const z = 700 + k, p = pick(bc[0], bc[1], bR, 30); if (!p) continue;
        ice.push({ kind: 'lj', c: [[214, 64, 40], [47, 111, 209], [242, 196, 48], [238, 240, 238]][k % 4], x: p[0], y: p[1], mg: 30, v: 9 + rnd(z) * 5, tr: 1.2, q: rnd(z + 1), h: rnd(z + 2) * 6.28, wait: rnd(z + 3) * 10, len: 6,
          next: (b) => legTo(b, [1.2, 1.95], 250, 700), pause: () => 2 + Math.random() * 6 });
      }
      for (let k = 0; k < (Z.kitari ?? 0); k++) {            // snowkiting: jízdy napříč větrem tam a zpět (jen po větru by se za hodinu všichni sjeli u závětrného břehu)
        const z = 800 + k, p = pick(bc[0], bc[1], bR, 30); if (!p) continue;
        ice.push({ kind: 'kt', x: p[0], y: p[1], mg: 30, v: 6 + rnd(z) * 4, tr: 1.5, q: rnd(z + 1), h: rnd(z + 2) * 6.28, wait: rnd(z + 3) * 10, len: 2,
          col: SUITS[(z + 1) % SUITS.length], kite: [['#e8402a', '#f2c230'], ['#2f6fd1', '#f2f0ea'], ['#2aa36b', '#f2c230'], ['#e0629a', '#1d1f24']][k % 4], ph: rnd(z + 4) * 6.28,
          next: (b) => legTo(b, [1.2, 1.95], 150, 450), pause: () => 3 + Math.random() * 10 });
      }

      // obrázek lodi (cache podle druhu, barvy a směru): kvádry od nejnižších a nejvzdálenějších, obrys 1 px
      const SPR = new Map();
      function sprite(kind, c, k) {
        const key = kind + c + k; if (SPR.has(key)) return SPR.get(key);
        const a = k / NDIR * Math.PI * 2, fx = Math.cos(a), fy = Math.sin(a), sxv = -fy, syv = fx;
        const O = toImg(0, 0, 0), R = (s, t, h) => { const p = toImg(fx * s + sxv * t, fy * s + syv * t, h); return [p[0] - O[0], p[1] - O[1]]; };
        const vis = (nx, ny) => nx + ny < 0, sun = (nx, ny, nz) => nx * SUNV[0] + ny * SUNV[1] + nz * SUNV[2];
        const boxes = model(kind, c).map((b) => [b, b[4], R((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, 0)[1]]).sort((p, q) => p[1] - q[1] || p[2] - q[2]);
        const faces = [];
        for (const [[s0, s1, t0, t1, z0, z1, rgb]] of boxes) {
          for (const [nx, ny, P0, P1] of [[fx, fy, [s1, t0], [s1, t1]], [-fx, -fy, [s0, t1], [s0, t0]], [sxv, syv, [s1, t1], [s0, t1]], [-sxv, -syv, [s0, t0], [s1, t0]]])
            if (vis(nx, ny)) faces.push([[R(P0[0], P0[1], z0), R(P1[0], P1[1], z0), R(P1[0], P1[1], z1), R(P0[0], P0[1], z1)], lit(rgb, sun(nx, ny, 0))]);
          faces.push([[R(s0, t0, z1), R(s1, t0, z1), R(s1, t1, z1), R(s0, t1, z1)], lit(rgb, sun(0, 0, 1))]);
        }
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const [pts] of faces) for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
        x0 = Math.floor(x0) - 1; y0 = Math.floor(y0) - 1;
        const cw = Math.ceil(x1) - x0 + 2, chh = Math.ceil(y1) - y0 + 2, cv = document.createElement('canvas'); cv.width = cw; cv.height = chh;
        const g = cv.getContext('2d');
        for (const [pts, fill] of faces) { g.fillStyle = fill; g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x - x0, y - y0) : g.moveTo(x - x0, y - y0))); g.closePath(); g.fill(); }
        const im = g.getImageData(0, 0, cw, chh), d = im.data, solid = new Uint8Array(cw * chh);
        for (let i = 0; i < cw * chh; i++) { solid[i] = d[i * 4 + 3] >= 110 ? 1 : 0; d[i * 4 + 3] = solid[i] ? 255 : 0; }
        for (let y = 0; y < chh; y++) for (let x = 0; x < cw; x++) {
          const i = y * cw + x; if (solid[i]) continue;
          if ((x > 0 && solid[i - 1]) || (x < cw - 1 && solid[i + 1]) || (y > 0 && solid[i - cw]) || (y < chh - 1 && solid[i + cw])) d.set([27, 28, 34, 255], i * 4);
        }
        g.putImageData(im, 0, 0);
        const spr = { c: cv, x0, y0 }; SPR.set(key, spr); return spr;
      }

      unsub = api.onFrame((ctx, view, t) => {
        const dt = Math.min(0.1, view.dt || 0), { sx, ox, oy } = view;
        if (view.season === 'winter') { drawIce(ctx, view, dt); return; }   // v zimě je jezero zamrzlé: žádné lodě ani koupání
        const day = view.night > 0.45 ? 0 : 1, share = (SEASON[view.season] ?? 0) * (WEATHER[view.weather] ?? 1) * day;
        if (share <= 0) return;
        const smallShare = share * (view.eco ? 0.5 : 1);
        if (layerOn('l-traffic')) {
          const list = [];
          for (const b of boats) if (b.q < smallShare) { stepBoat(b, dt); list.push(b); }
          for (const S of ships) if (S.q < share) list.push({ ...shipPose(S, Date.now()), kind: S.kind, c: S.c, len: S.len });
          const windF = view.wind && view.wind.strength > 1.5 ? 0.4 : 1;   // od ~4,5 m/s na kajaku jezdí málokdo
          for (const K of kayaks) if (K.q < smallShare * windF) list.push(kayakPose(K, Date.now()));
          if (sx > 0.12) {
            const q = Math.max(1, Math.round(sx));
            const drawn = list.map((b) => { const [ix, iy] = toImg(b.x, b.y, gz(b.x, b.y)); return [b, ix, iy]; }).filter((e) => view.vis(e[1], e[2], 200)).sort((p, r) => p[2] - r[2]);
            for (const [b, ix, iy] of drawn) {
              const z = gz(b.x, b.y) + 0.5;
              if (b.moving && !api.occluded(b.x - Math.cos(b.h) * b.len / 2, b.y - Math.sin(b.h) * b.len / 2, z)) {                                   // brázda za zádí
                const fx = Math.cos(b.h), fy = Math.sin(b.h);
                ctx.fillStyle = 'rgba(236,246,255,0.55)';
                for (let k = 1; k <= 7; k++) for (const sd of [-1, 1]) {
                  const s = -b.len / 2 - k * b.len * 0.18, w = sd * (b.len * 0.08 + k * b.len * 0.05), x = b.x + fx * s - fy * w, y = b.y + fy * s + fx * w, p = toImg(x, y, gz(x, y));
                  ctx.globalAlpha = 1 - k / 8; ctx.fillRect(Math.round(ox + p[0] * sx), Math.round(oy + p[1] * sx), q * 2, q);
                }
                ctx.globalAlpha = 1;
              }
              const k = ((Math.round(b.h / (Math.PI * 2) * NDIR) % NDIR) + NDIR) % NDIR, spr = sprite(b.kind, b.c, k);
              api.drawOccluded(spr.c, ix + spr.x0, iy + spr.y0, spr.c.width, spr.c.height, b.x, b.y, z, view);   // stromy a domy na břehu loď zakryjí
              if (b.paddle !== undefined && !api.occluded(b.x, b.y, z + 0.5)) {   // pádla: kajak dvojpádlo kolébavě, kánoe každý na své straně
                const fx = Math.cos(b.h), fy = Math.sin(b.h), z0 = gz(b.x, b.y), sn = Math.sin(b.paddle), cs = Math.cos(b.paddle), qq = Math.max(1, Math.round(sx * 1.2));
                const P = (s, t, hh) => { const p = toImg(b.x + fx * s - fy * t, b.y + fy * s + fx * t, z0 + hh); return [Math.round(ox + p[0] * sx), Math.round(oy + p[1] * sx)]; };
                ctx.strokeStyle = '#3a2f26'; ctx.fillStyle = '#2a2c31'; ctx.lineWidth = Math.max(1, sx * 0.8);
                for (const s of b.kind === 'kn' ? [1.3, -1.3] : [-0.1]) {
                  const sd = s > 0 ? 1 : -1, ends = b.kind === 'kn' ? [P(s + 0.1, sd * 0.35, 1.05), P(s - 0.5 * cs, sd * 0.75, 0.05 + 0.3 * Math.max(0, sn))] : [P(s + 0.3 * cs, 1.1, 0.75 + 0.45 * sn), P(s - 0.3 * cs, -1.1, 0.75 - 0.45 * sn)];
                  ctx.beginPath(); ctx.moveTo(ends[0][0], ends[0][1]); ctx.lineTo(ends[1][0], ends[1][1]); ctx.stroke();
                  for (const e of b.kind === 'kn' ? [ends[1]] : ends) ctx.fillRect(e[0] - qq, e[1] - qq / 2, 2 * qq, qq);
                }
              }
            }
          }
        }
        // koupající: jen v létě za jasna ve dne
        if (view.season !== 'summer' || view.weather !== 'clear' || view.night > 0.3 || (!swimmers.length && !beach.length) || !layerOn('l-people')) return;
        const hpx = Math.abs(toImg(0, 0, 1)[1] - toImg(0, 0, 0)[1]), u = hpx * 0.1 * sx;   // bod 10 cm jako u chodců
        if (u < 0.3) return;
        const tt = view.now / 1000, list = [];
        for (const s of swimmers) {
          if (s.q > (view.eco ? 0.5 : 1) * (1 - 0.8 * view.night)) continue;
          const x = s.x + Math.sin(tt * 0.05 + s.ph) * 2, y = s.y + Math.cos(tt * 0.04 + s.ph * 1.3) * 2, ip = toImg(x, y, gz(x, y));
          if (view.vis(ip[0], ip[1], 30) && !api.occluded(x, y, gz(x, y) + 0.3)) list.push([s, ip]);
        }
        const nowMs = Date.now();
        for (const o of beach) {
          if (o.q > (view.eco ? 0.5 : 1) * (1 - 0.8 * view.night)) continue;
          const [x, y, mv] = beachPos(o, nowMs), z = gz(x, y), ip = toImg(x, y, z);
          if (view.vis(ip[0], ip[1], 40) && !api.occluded(x, y, z + (o.m === 'umb' ? 1.5 : 0.4))) list.push([o, ip, mv]);
        }
        list.sort((a, b) => a[1][1] - b[1][1]);
        const R = (X, Y, x0, y0, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(X + x0 * u, Y + y0 * u, w * u, h * u); };
        const OUT = 'rgba(24,26,32,0.85)';
        for (const [s, ip, mv] of list) {
          if (s.m) {                                          // pláž: postavy po 10 cm jako plavci; d zrcadlí ležící a sedící
            const X = Math.round(ox + ip[0] * sx), Y = Math.round(oy + ip[1] * sx), M = (x0, y0, w, h, c) => R(X, Y, s.d > 0 ? x0 : -x0 - w, y0, w, h, c);
            if (s.m === 'umb') {
              R(X, Y, -9, -1, 18, 3, 'rgba(60,44,20,0.18)'); R(X, Y, -0.5, -23, 1, 23, '#e8e4da');
              R(X, Y, -12.5, -26.5, 25, 5, OUT); R(X, Y, -4, -28, 8, 2, OUT);
              for (let i = 0; i < 6; i++) R(X, Y, -12 + i * 4, -26, 4, 4, s.c[i % 2]);
              R(X, Y, -3.5, -27.5, 7, 1.5, s.c[0]);
            } else if (s.m === 'lie' || s.m === 'sit') {
              M(-7.5, -2.5, 15, 5, OUT); M(-7, -2, 14, 4, s.towel);
              if (s.m === 'lie') { M(-4.5, -3, 10, 3, OUT); M(-4, -2.5, 9, 2, s.skin); M(-0.5, -2.5, 3, 2, s.suit); M(-6.5, -3.5, 3, 3, OUT); M(-6, -3, 2, 2, s.skin); M(-6, -3, 2, 1, s.hair); }
              else { M(-1, -3, 5, 2.5, OUT); M(-0.5, -2.5, 4, 1.5, s.skin); M(-3, -9, 4, 7, OUT); M(-2.5, -8.5, 3, 5, s.skin); M(-2.5, -4.5, 3, 2, s.suit); M(-3, -12, 4, 4, OUT); M(-2.5, -11.5, 3, 3, s.skin); M(-2.5, -11.5, 3, 1, s.hair); }
            } else {                                          // stojí nebo jde k vodě; dítě menší
              const k = s.m === 'kid' ? 0.65 : 1, Q = (x0, y0, w, h, c) => R(X, Y, x0 * k, y0 * k, w * k, h * k, c), st = mv && Math.sin(nowMs / 160 + s.x) > 0 ? 1 : 0;
              Q(-2.5, -16.5, 5, 16.5, OUT); Q(-1.5, -6, 1, 6 - st, s.skin); Q(0.5, -6, 1, 5 + st, s.skin); Q(-2, -9, 4, 3, s.suit); Q(-2, -13, 4, 4, s.skin); Q(-1.5, -16, 3, 3, s.skin); Q(-1.5, -16, 3, 1, s.hair);
            }
            continue;
          }
          const X = Math.round(ox + ip[0] * sx), Y = Math.round(oy + ip[1] * sx), bob = Math.sin(tt * 2 + s.ph * 5) > 0.6 ? 1 : 0, Yb = Y + bob * u;
          R(X, Y, -4, 0, 2, 1, 'rgba(236,246,255,0.7)'); R(X, Y, 2, 0, 2, 1, 'rgba(236,246,255,0.7)'); R(X, Y, -2, 1, 4, 1, 'rgba(236,246,255,0.45)');
          if (s.kind === 1) {                                 // stojí po pás ve vodě: trup v plavkách a ruce
            R(X, Yb, -3, -6, 6, 6, 'rgba(24,26,32,0.85)'); R(X, Yb, -2, -5, 4, 5, s.skin); R(X, Yb, -2, -3, 4, 3, s.suit); R(X, Yb, -3, -5, 1, 3, s.skin); R(X, Yb, 2, -5, 1, 3, s.skin);
            R(X, Yb, -2, -9, 4, 4, 'rgba(24,26,32,0.85)'); R(X, Yb, -1.5, -8.5, 3, 3, s.skin); R(X, Yb, -1.5, -8.5, 3, 1, s.cap);
          } else {                                            // plave: hlava nad hladinou, ramena, někdo v kruhu
            if (s.kind === 2) { R(X, Yb, -4, -1, 8, 2, s.ring); R(X, Yb, -2, -1, 1, 2, '#f2f0ea'); R(X, Yb, 1, -1, 1, 2, '#f2f0ea'); }
            R(X, Yb, -2, -4, 4, 4, 'rgba(24,26,32,0.85)'); R(X, Yb, -1.5, -3.5, 3, 3, s.skin); R(X, Yb, -1.5, -3.5, 3, 1.2, s.cap);
            R(X, Yb, -3, -0.5, 6, 1, s.kind === 2 ? s.ring : s.skin);
          }
        }
      }, { layer: 'world' });

      // zimní provoz: jen ve dne za jasna; jachty a kiteři potřebují vítr (síla 1 ≈ 3 m/s), silný vítr (≥ 6,6 m/s, víc prohlížeč nerozliší) nikoho nepustí
      function drawIce(ctx, view, dt) {
        const { sx, ox, oy } = view, w = view.wind, st = w ? w.strength : 1;
        if (!ice.length || view.night > 0.3 || view.weather !== 'clear' || st >= 2.2) return;
        setWind(w);
        const eco = view.eco ? 0.5 : 1, windShare = Math.max(0, Math.min(1, (st - 0.3) / 0.7)) * eco;
        const traffic = layerOn('l-traffic') && sx > 0.12, people = layerOn('l-people');
        const hpx = Math.abs(toImg(0, 0, 1)[1] - toImg(0, 0, 0)[1]), u = hpx * 0.2125 * sx;   // postava 1,7 m = 8 bodů jako bruslaři na kluzišti
        const list = [];
        for (const b of ice) {
          const on = b.kind === 'br' ? people && b.q < eco : traffic && b.q < windShare;
          if (!on) continue;
          stepBoat(b, dt);
          const [ix, iy] = toImg(b.x, b.y, gz(b.x, b.y));
          if (view.vis(ix, iy, 300)) list.push([b, ix, iy]);
        }
        list.sort((p, r) => p[2] - r[2]);
        const tt = view.now / 1000;
        for (const [b, ix, iy] of list) {
          const X = Math.round(ox + ix * sx), Y = Math.round(oy + iy * sx);
          if (b.kind === 'lj') {
            const sideW = Math.cos(b.h) * -WD[1] + Math.sin(b.h) * WD[0] < 0 ? 'jR' : 'jL';   // na kterou stranu trupu vítr tlačí plachtu
            const k = ((Math.round(b.h / (Math.PI * 2) * NDIR) % NDIR) + NDIR) % NDIR, spr = sprite(sideW, b.c, k);
            api.drawOccluded(spr.c, ix + spr.x0, iy + spr.y0, spr.c.width, spr.c.height, b.x, b.y, gz(b.x, b.y) + 0.5, view);
            continue;
          }
          const hid = api.occluded(b.x, b.y, gz(b.x, b.y) + 1);   // postava za stromem na břehu
          const uu = Math.max(u, 0.5), B = (bx, by, ww, hh, c) => { ctx.fillStyle = c; ctx.fillRect(X + bx * uu, Y - by * uu, ww * uu, hh * uu); };
          if (b.kind === 'br') {                             // bruslař: zimní bunda, čepice, ruce se při jízdě kývají
            if (u < 0.5 || hid) continue;
            const sw = b.moving && Math.sin(tt * 3 + b.ph) > 0 ? 1 : 0;
            B(-1, 1, 3, 1, '#9aa0a8'); B(-1, 4, 2, 3, '#2a2c31'); B(-1, 7, 2, 3, b.col); B(-2 + sw * 3, 6, 1, 2, b.col); B(-1, 8, 2, 1, b.skin); B(-1, 9, 2, 1, b.hat);
            continue;
          }
          // snowkiter: postava na prkně, drak výš po větru na dvou šňůrách, oblouk napříč větrem
          const pw = [-WD[1], WD[0]], sd = Math.sin(tt * 0.3 + b.ph) * 0.35, kx = b.x + WD[0] * 16 + pw[0] * sd * 8, ky = b.y + WD[1] * 16 + pw[1] * sd * 8, kh = gz(b.x, b.y) + 15;
          // oblouk kreslený napříč šňůrami na obrazovce: skutečný oblouk napříč větrem by se při větru od JZ/SV jevil jako svislá čárka
          const hand = toImg(b.x, b.y, gz(b.x, b.y) + 1.1), kc = toImg(kx, ky, kh), lx = kc[0] - hand[0], ly = kc[1] - hand[1], ll = Math.hypot(lx, ly) || 1, nx = -ly / ll, ny = lx / ll, half = 25;   // půl rozpětí 5 m v pixelech mapy
          const arc = []; for (let i = -3; i <= 3; i++) { const f = i / 3; arc.push([kc[0] + nx * f * half - lx / ll * f * f * half * 0.45, kc[1] + ny * f * half - ly / ll * f * f * half * 0.45]); }
          if (!api.occluded(kx, ky, kh)) {
          ctx.strokeStyle = 'rgba(30,32,38,0.55)'; ctx.lineWidth = 1; ctx.beginPath();
          for (const a of [arc[0], arc[6]]) { ctx.moveTo(Math.round(ox + hand[0] * sx) + 0.5, Math.round(oy + hand[1] * sx) + 0.5); ctx.lineTo(Math.round(ox + a[0] * sx) + 0.5, Math.round(oy + a[1] * sx) + 0.5); }
          ctx.stroke();
          const kq = Math.max(2, Math.round(sx * 9));   // článek oblouku ~1,8 m, drak ~10 m napříč
          arc.forEach((a, i) => { ctx.fillStyle = '#1b1c22'; ctx.fillRect(Math.round(ox + a[0] * sx) - kq / 2 - 1, Math.round(oy + a[1] * sx) - kq / 2 - 1, kq + 2, kq + 2); });
          arc.forEach((a, i) => { ctx.fillStyle = b.kite[i % 2]; ctx.fillRect(Math.round(ox + a[0] * sx) - kq / 2, Math.round(oy + a[1] * sx) - kq / 2, kq, kq); });
          }
          if (hid) continue;
          if (b.moving) { ctx.fillStyle = 'rgba(255,255,255,0.8)'; for (let k = 1; k <= 4; k++) { const p = toImg(b.x - Math.cos(b.h) * k * 1.5, b.y - Math.sin(b.h) * k * 1.5, gz(b.x, b.y)); ctx.globalAlpha = 1 - k / 5; ctx.fillRect(Math.round(ox + p[0] * sx), Math.round(oy + p[1] * sx), Math.max(1, uu * 2), Math.max(1, uu)); } ctx.globalAlpha = 1; }
          B(-3, 1, 6, 1, '#f2f0ea'); B(-1, 4, 2, 3, '#2a2c31'); B(-1, 7, 2, 3, b.col); B(-1, 8, 2, 1, '#e8b894'); B(-1, 9, 2, 1, '#1d1f24');
        }
      }
    },
    onDestroy() { if (unsub) unsub(); },
  });
})();
