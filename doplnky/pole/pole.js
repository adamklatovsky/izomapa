// Doplněk „Práce na polích“: ilustrační provoz zemědělských strojů na orné půdě (pole z assets/zabaged.json, hook overlay_hook.py).
// Stroj jede v pruzích tam a zpět po delší ose pole, na souvrati se otočí do dalšího pruhu a za sebou nechává stopu
// (zoraný pás hnědě, sklizený nebo posečený světle; jen uvnitř pole). Co se dělá, určuje roční období: jaro orba, setí
// a válení, léto žně (kombajn a vedle traktor s vlekem) a podmítka, podzim sklizeň kukuřice (řezačka a vlek) a orba, zima nic.
// Které pole a jak daleko je práce, se počítá z data a hodin (od rána), takže všichni návštěvníci vidí totéž. Jen ve dne,
// ne v dešti a ve sněhu. Stroje se kreslí jako lodě v doplňku lode (kvádry stínované sluncem, obrys 1 px); vrstva Doprava.
(() => {
  const ID = 'pole';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;
  let unsub = null;

  const NDIR = 32;
  const SUNV = (() => { const v = [0.38, -0.68, 0.62], n = Math.hypot(...v); return v.map((q) => q / n); })();
  const lit = (rgb, d) => { const f = (0.62 + 0.42 * Math.max(0, d)) / 0.88; return `rgb(${rgb.map((q) => Math.min(255, Math.round(q * f))).join(',')})`; };
  const rnd = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  // posun Europe/Prague proti UTC v sekundách (rozpis prací je podle pražského času, ne podle pásma prohlížeče); jednou za minutu
  const PRG = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Prague', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  let offT = -1e15, off = 0;
  const pragueOff = (t) => {
    if (Math.abs(t - offT) > 60000) {
      const p = Object.fromEntries(PRG.formatToParts(new Date(t)).map((q) => [q.type, +q.value]));
      offT = t; off = Math.round((Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - t) / 1000);
    }
    return off;
  };
  const layerOn = (id) => { const e = document.getElementById(id); return !e || e.checked; };
  const DK = [40, 40, 42], GL = [70, 92, 112], STEEL = [150, 152, 156];
  const TRACTOR = [[54, 132, 56], [196, 42, 32]], COMBINE = [[120, 170, 60], [196, 42, 32]];

  // práce: w šířka záběru (m), v rychlost (m/s), stopa za strojem, komb = vedle jede traktor s vlekem
  const JOBS = {
    orba: { w: 3, v: 2.0, trail: 'rgba(94,64,40,0.55)' },
    seti: { w: 4, v: 2.5, trail: 'rgba(112,84,56,0.45)' },
    valeni: { w: 6, v: 3.0, trail: 'rgba(150,132,96,0.3)' },
    kombajn: { w: 6, v: 1.5, trail: 'rgba(232,214,156,0.55)', komb: true },
    rezacka: { w: 4.5, v: 1.8, trail: 'rgba(204,180,124,0.5)', komb: true },
    seno: { w: 3, v: 3.0, trail: 'rgba(186,206,120,0.5)' },
  };
  const GRAIN = new Set(['wheat', 'rape']);
  function job(season, P, r) {                                // co se dnes na poli dělá (null = nic)
    if (P.p === 'louka') return season === 'summer' ? 'seno' : null;
    if (season === 'spring') return GRAIN.has(P.p) ? null : r < 0.45 ? 'orba' : r < 0.8 ? 'seti' : 'valeni';   // ozimy už rostou, jarní práce jen na holé půdě a pod kukuřici
    if (season === 'summer') return GRAIN.has(P.p) ? 'kombajn' : P.p === 'soil' ? 'orba' : null;   // na holé půdě podmítka
    if (season === 'autumn') return P.p === 'maize' ? 'rezacka' : r < 0.7 ? 'orba' : 'seti';
    return null;
  }

  // modely: kvádry [s0, s1, t0, t1, z0, z1, rgb] (s dopředu, t doleva, z nahoru; metry); sd = strana, kam míří výsypka
  function tractor(box, c) {
    for (const t of [-1, 1]) { box(-1.6, -0.3, t * 0.7, t * 1.15, 0, 1.5, DK); box(1.0, 1.8, t * 0.55, t * 0.9, 0, 0.95, DK); }
    box(-0.4, 2.1, -0.45, 0.45, 0.6, 1.45, c);
    box(-1.5, -0.1, -0.7, 0.7, 0.9, 1.4, c); box(-1.45, -0.15, -0.68, 0.68, 1.4, 2.7, GL); box(-1.6, 0, -0.78, 0.78, 2.7, 2.9, c);
    box(1.2, 1.32, 0.25, 0.37, 1.45, 2.6, DK);
  }
  function model(kind, c, sd) {
    const B = [], box = (...a) => B.push(a);
    if (kind === 'kombajn') {
      for (const t of [-1, 1]) { box(0.2, 1.8, t * 1.45, t * 2.0, 0, 1.75, DK); box(-4.2, -3.2, t * 1.1, t * 1.5, 0, 1.0, DK); }
      box(-4.6, 1.6, -1.45, 1.45, 0.7, 3.3, c); box(-3, 0.6, -1.35, 1.35, 3.3, 4.0, c);
      box(0.9, 2.5, -0.85, 0.85, 2.4, 3.9, GL); box(0.8, 2.6, -0.95, 0.95, 3.9, 4.1, c);
      box(1.6, 3.4, -0.6, 0.6, 0.5, 1.3, c);                  // šikmý dopravník
      box(3.2, 4.6, -3.1, 3.1, 0.15, 1.0, [214, 178, 52]); box(3.6, 4.4, -3.1, 3.1, 1.0, 1.4, [196, 52, 40]);   // žací lišta a přiháněč
      box(-1.0, -0.6, sd * 1.4, sd * 4.6, 3.6, 3.95, c);       // výsypka do vleku vedle
    } else if (kind === 'rezacka') {
      for (const t of [-1, 1]) { box(0.0, 1.6, t * 1.3, t * 1.85, 0, 1.6, DK); box(-3.6, -2.7, t * 1.0, t * 1.4, 0, 1.0, DK); }
      box(-3.9, 1.4, -1.3, 1.3, 0.7, 3.0, c); box(0.6, 2.2, -0.8, 0.8, 2.2, 3.6, GL); box(0.5, 2.3, -0.9, 0.9, 3.6, 3.8, c);
      box(1.5, 3.2, -2.3, 2.3, 0.15, 1.1, [214, 214, 210]);    // adaptér na kukuřici
      box(-1.4, -0.9, -0.25, 0.25, 3.0, 4.4, c); box(-1.4, -0.9, sd * 0.25, sd * 4.0, 4.1, 4.5, c);   // komín metače do vleku
    } else {
      tractor(box, c);
      if (kind === 'orba') for (let k = 0; k < 4; k++) box(-2.4 - k * 0.8, -1.7 - k * 0.8, -0.9 + k * 0.45, -0.4 + k * 0.45, 0, 0.7, [196, 52, 40]);
      else if (kind === 'seti') { box(-2.0, -1.7, -0.2, 0.2, 0.5, 0.7, STEEL); box(-3.8, -2.0, -2.0, 2.0, 0.4, 1.5, [52, 104, 172]); box(-4.0, -3.7, -2.0, 2.0, 0, 0.5, STEEL); }
      else if (kind === 'valeni') { box(-2.2, -1.7, -0.2, 0.2, 0.4, 0.6, STEEL); box(-3.0, -2.2, -3.0, 3.0, 0, 0.75, [92, 92, 98]); }
      else if (kind === 'seno') { box(-2.5, -1.7, -1.6, 1.6, 0, 0.6, [214, 64, 40]); box(-0.8, 0.0, -3.2, -1.2, 0, 0.3, [214, 64, 40]); }
      else if (kind === 'vlek') { box(-2.3, -1.6, -0.1, 0.1, 0.6, 0.8, DK); for (const t of [-1, 1]) box(-6.6, -5.2, t * 0.95, t * 1.25, 0, 1.0, DK); box(-8.2, -2.3, -1.25, 1.25, 1.0, 2.6, [196, 52, 40]); }
    }
    return B;
  }

  Izomapa.registerPlugin(ID, {
    onInit(api) {
      const D = api.getPluginData(ID);
      if (!D || !(D.pole || []).length && !(D.louky || []).length) return;
      api.addTrees?.(D.stromy);                               // stromy na polích a u nich: ořez stopy (drawGround) i strojů
      const toImg = api.toImg, gz = api.gz, W = (q) => api.latLonToWorld(q[0], q[1]);

      // pole ve světových souřadnicích; osa a = delší strana nejmenšího opsaného obdélníku (jako řádky v prep.py)
      const fields = [...(D.pole || []), ...(D.louky || [])].map((P, i) => {
        const R = P.q.map((r) => r.map(W)), o = R[0];
        let best = null;
        for (let k = 0; k < o.length; k++) {
          const a = o[k], b = o[(k + 1) % o.length], an = Math.atan2(b[1] - a[1], b[0] - a[0]), c = Math.cos(an), s = Math.sin(an);
          let u0 = 1e9, u1 = -1e9, v0 = 1e9, v1 = -1e9;
          for (const [x, y] of o) { const u = x * c + y * s, v = -x * s + y * c; u0 = Math.min(u0, u); u1 = Math.max(u1, u); v0 = Math.min(v0, v); v1 = Math.max(v1, v); }
          const A = (u1 - u0) * (v1 - v0);
          if (!best || A < best.A) best = u1 - u0 >= v1 - v0 ? { A, an, u0, u1, v0, v1 } : { A, an: an + Math.PI / 2, u0: v0, u1: v1, v0: -u1, v1: -u0 };
        }
        const c = Math.cos(best.an), s = Math.sin(best.an);
        const toW = (u, v) => [u * c - v * s, u * s + v * c];
        // hrana pole zjemněná po 10 m, aby obrys (ořez stopy) kopíroval terén
        const ring = R.map((r) => { const out = []; for (let k = 0; k < r.length; k++) { const a = r[k], b = r[(k + 1) % r.length], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 10)); for (let j = 0; j < n; j++) out.push([a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n]); } return out; });
        const mid = toW((best.u0 + best.u1) / 2, (best.v0 + best.v1) / 2);
        return { ...P, i, R, c, s, toW, ...best, mid, rad: Math.hypot(best.u1 - best.u0, best.v1 - best.v0) / 2, ring, ringZ: null, plans: {} };
      });

      // jízda po poli: pruhy po w m napříč, tam a zpět, mezi nimi otočka na souvrati (4 m od kraje)
      function plan(F, w) {
        if (F.plans[w]) return F.plans[w];
        const segs = []; let L = 0, prev = null;
        for (let k = 0, dir = 1; ; k++) {
          const v = F.v0 + w * (k + 0.5); if (v > F.v1) break;
          const us = [];
          for (const r of F.R) for (let j = 0; j < r.length; j++) {
            const a = r[j], b = r[(j + 1) % r.length], av = -a[0] * F.s + a[1] * F.c, bv = -b[0] * F.s + b[1] * F.c;
            if ((av > v) !== (bv > v)) { const f = (v - av) / (bv - av); us.push((a[0] + (b[0] - a[0]) * f) * F.c + (a[1] + (b[1] - a[1]) * f) * F.s); }
          }
          us.sort((p, q) => p - q);
          let ua = 0, ub = 0;
          for (let j = 0; j + 1 < us.length; j += 2) if (us[j + 1] - us[j] > ub - ua) { ua = us[j]; ub = us[j + 1]; }
          ua += 4; ub -= 4;                                     // souvrať
          if (ub - ua < 10) continue;
          const a = dir > 0 ? [ua, v] : [ub, v], b = dir > 0 ? [ub, v] : [ua, v];
          if (prev) { const l = Math.hypot(a[0] - prev[0], a[1] - prev[1]); segs.push({ a: prev, b: a, s: L, l, k: -1 }); L += l; }
          segs.push({ a, b, s: L, l: ub - ua, k, dir }); L += ub - ua; prev = b; dir = -dir;
        }
        return (F.plans[w] = { segs, L });
      }
      const at = (F, P, d) => {                                // poloha po d metrech jízdy
        let i = 0; while (i < P.segs.length - 1 && P.segs[i].s + P.segs[i].l < d) i++;
        const g = P.segs[i], f = Math.max(0, Math.min(1, (d - g.s) / (g.l || 1))), u = g.a[0] + (g.b[0] - g.a[0]) * f, v = g.a[1] + (g.b[1] - g.a[1]) * f;
        const [x, y] = F.toW(u, v), du = g.b[0] - g.a[0], dv = g.b[1] - g.a[1];
        return { x, y, u, v, g, h: Math.atan2(du * F.s + dv * F.c, du * F.c - dv * F.s) };
      };

      // denní rozpis: pole vhodná pro dnešní práci zamíchaná podle data, stroj j dostane pole j, j + N, j + 2N …
      // a jede je jedno po druhém od rána (6–8 h) do 20 h; hotová pole zůstanou se stopou celý den
      let sched = null;
      function schedule(season, day) {
        const key = season + day; if (sched && sched.key === key) return sched;
        const ok = fields.map((F) => ({ F, j: job(season, F, rnd(day * 7 + F.i * 13)) })).filter((e) => e.j && plan(e.F, JOBS[e.j].w).L > 0)
          .sort((p, q) => rnd(day * 31 + p.F.i) - rnd(day * 31 + q.F.i));
        const h = ok.findIndex((e) => JOBS[e.j].komb); if (h > 0) ok.unshift(...ok.splice(h, 1));   // sklizeň má přednost: aspoň jeden kombajn nebo řezačka
        const N = Math.max(0, D.stroje ?? 5), slots = [], rest = [];
        let units = 0;
        for (const e of ok) {                                  // kombajn nebo řezačka s vlekem jsou dva stroje
          const cost = JOBS[e.j].komb ? 2 : 1;
          if (units + cost <= N) { const j = slots.length; slots.push({ chain: [e], komb: cost > 1, start: 6 * 3600 + rnd(day * 5 + j) * 7200, c: rnd(day * 3 + j) < 0.5 ? 0 : 1, j }); units += cost; } else rest.push(e);
        }
        for (const komb of [false, true]) {                    // zbylá pole po řadě strojům stejného druhu
          const S = slots.filter((sl) => sl.komb === komb);
          rest.filter((e) => !!JOBS[e.j].komb === komb).forEach((e, m) => S.length && S[m % S.length].chain.push(e));
        }
        return (sched = { key, slots });
      }

      const SPR = new Map();
      function sprite(kind, c, sd, k) {
        const key = kind + c + sd + k; if (SPR.has(key)) return SPR.get(key);
        const a = k / NDIR * Math.PI * 2, fx = Math.cos(a), fy = Math.sin(a), sxv = -fy, syv = fx;
        const O = toImg(0, 0, 0), R = (s, t, h) => { const p = toImg(fx * s + sxv * t, fy * s + syv * t, h); return [p[0] - O[0], p[1] - O[1]]; };
        const vis = (nx, ny) => nx + ny < 0, sun = (nx, ny, nz) => nx * SUNV[0] + ny * SUNV[1] + nz * SUNV[2];
        const boxes = model(kind, c, sd).map((b) => [b, b[4], R((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, 0)[1]]).sort((p, q) => p[1] - q[1] || p[2] - q[2]);
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

      // stopa: hotové pruhy jako jeden pás přes celé pole + rozjetý pruh po stroj, ořez obrysem pole; kreslí se do pomocného
      // plátna (výřez obrazovky s polem) a to se vykreslí přes drawGround, které z ní vyřízne stromy a domy (remízky, stromy na kraji)
      const trC = document.createElement('canvas'), trG = trC.getContext('2d');
      function trail(view, F, J, P, d) {
        const { sx, ox, oy, cw, ch } = view, S = (x, y) => { const p = toImg(x, y, gz(x, y)); return [ox + p[0] * sx, oy + p[1] * sx]; };
        if (!F.ringZ) {
          F.ringZ = F.ring.map((r) => r.map(([x, y]) => [x, y, gz(x, y)]));
          const o = F.R[0]; F.bb = [Math.min(...o.map((p) => p[0])), Math.min(...o.map((p) => p[1])), Math.max(...o.map((p) => p[0])), Math.max(...o.map((p) => p[1]))];
        }
        const scr = F.ringZ.map((r) => r.map(([x, y, z]) => { const p = toImg(x, y, z); return [ox + p[0] * sx, oy + p[1] * sx]; }));
        let x0 = cw, y0 = ch, x1 = 0, y1 = 0;
        for (const r of scr) for (const [X, Y] of r) { x0 = Math.min(x0, X); y0 = Math.min(y0, Y); x1 = Math.max(x1, X); y1 = Math.max(y1, Y); }
        const X0 = Math.max(0, Math.floor(x0) - 1), Y0 = Math.max(0, Math.floor(y0) - 1);
        const w = Math.min(Math.ceil(cw), Math.ceil(x1) + 1) - X0, h = Math.min(Math.ceil(ch), Math.ceil(y1) + 1) - Y0;
        if (w <= 0 || h <= 0) return;
        // rozměr po 128 px, aby se plátno nepřealokovalo každý snímek; přebytek je průhledný a kreslí se s ním
        const PW = Math.ceil(w / 128) * 128, PH = Math.ceil(h / 128) * 128, g = trG;
        if (trC.width !== PW || trC.height !== PH) { trC.width = PW; trC.height = PH; } else g.clearRect(0, 0, PW, PH);
        const band = (ua, ub, va, vb) => {                  // obdélník v osách pole, strany po 10 m
          const pts = [], n = Math.max(1, Math.ceil((ub - ua) / 10)), m = Math.max(1, Math.ceil((vb - va) / 10));
          for (let j = 0; j <= n; j++) pts.push([ua + (ub - ua) * j / n, va]);
          for (let j = 1; j <= m; j++) pts.push([ub, va + (vb - va) * j / m]);
          for (let j = n - 1; j >= 0; j--) pts.push([ua + (ub - ua) * j / n, vb]);
          for (let j = m - 1; j > 0; j--) pts.push([ua, va + (vb - va) * j / m]);
          g.moveTo(...S(...F.toW(...pts[0]))); for (const p of pts.slice(1)) g.lineTo(...S(...F.toW(...p))); g.closePath();
        };
        g.save(); g.setTransform(1, 0, 0, 1, -X0, -Y0); g.beginPath();
        for (const r of scr) r.forEach(([X, Y], k) => (k ? g.lineTo(X, Y) : g.moveTo(X, Y)));
        g.clip('evenodd');
        g.fillStyle = J.trail; g.beginPath();
        const gs = d >= P.L ? null : at(F, P, d).g, done = d >= P.L ? F.v1 : gs.k >= 0 ? gs.a[1] - J.w / 2 : gs.a[1] + J.w / 2;
        if (done > F.v0) band(F.u0 - 5, F.u1 + 5, F.v0 - 5, done);
        if (gs && gs.k >= 0) { const u = at(F, P, d).u; band(Math.min(gs.a[0], u) - (gs.dir > 0 ? 5 : 0), Math.max(gs.a[0], u) + (gs.dir < 0 ? 5 : 0), gs.a[1] - J.w / 2, gs.a[1] + J.w / 2); }
        g.fill(); g.restore();
        api.drawGround(trC, (X0 - ox) / sx, (Y0 - oy) / sx, PW / sx, PH / sx, F.bb, view);
      }

      const draws = [];
      unsub = api.onFrame((ctx, view) => {
        if (view.season === 'winter' || view.night > 0.45 || view.weather === 'rain' || view.weather === 'snow' || view.snowy || !layerOn('l-traffic')) return;
        const { sx, ox, oy } = view, now = Date.now(), loc = now / 1000 + pragueOff(now);
        const day = Math.floor(loc / 86400), sec = Math.min(loc - day * 86400, 20 * 3600);
        const { slots } = schedule(view.season, day);
        draws.length = 0;
        for (const sl of slots) {
          if (view.eco && sl.j % 2) continue;
          let d = Math.max(0, sec - sl.start), cur = null;
          for (const e of sl.chain) {                         // pole v řetězu postupně; mezi nimi 20 min přejezd
            const J = JOBS[e.j], P = plan(e.F, J.w), t = P.L / J.v;
            const vis = view.vis(...toImg(e.F.mid[0], e.F.mid[1], 0), e.F.rad / 0.2 * sx + 50);
            if (d >= t) { if (vis) trail(view, e.F, J, P, P.L); d -= t + 1200; if (d < 0) break; continue; }
            cur = { e, J, P, dist: d * J.v, vis }; break;
          }
          if (!cur) continue;
          const { e, J, P, dist, vis } = cur;
          if (vis) trail(view, e.F, J, P, dist);
          if (sx <= 0.12 || !vis) continue;
          const p = at(e.F, P, dist), off = J.w / 2 + 3.2, side = p.v - off < e.F.v0 ? 1 : -1, sd = side * (p.g.dir ?? 1), kind = e.j;   // vlek po sklizené straně, v prvním pruhu po nesklizené (jinak by jel mimo pole)
          draws.push({ x: p.x, y: p.y, h: p.h, kind, c: (J.komb ? COMBINE : TRACTOR)[sl.c], sd: J.komb ? sd : 1, dust: J.komb, d: dist });
          if (J.komb && p.g.k >= 0) {
            const ox2 = -e.F.s * off * side, oy2 = e.F.c * off * side;
            draws.push({ x: p.x + ox2, y: p.y + oy2, h: p.h, kind: 'vlek', c: TRACTOR[1 - sl.c], sd: 1, d: dist });
          }
        }
        if (!draws.length) return;
        const q = Math.max(1, Math.round(sx)), t = now / 1000;
        draws.sort((a, b) => toImg(a.x, a.y, 0)[1] - toImg(b.x, b.y, 0)[1]);
        for (const b of draws) {
          const z = gz(b.x, b.y), [ix, iy] = toImg(b.x, b.y, z), k = ((Math.round(b.h / (Math.PI * 2) * NDIR) % NDIR) + NDIR) % NDIR, spr = sprite(b.kind, b.c, b.sd, k);
          const fx = Math.cos(b.h), fy = Math.sin(b.h);
          if (b.dust && !api.occluded(b.x, b.y, z + 1)) {     // prach za kombajnem
            ctx.fillStyle = 'rgba(214,196,150,0.35)';
            for (let j = 0; j < 8; j++) { const s = -5 - j * 1.6, w = (rnd(j + Math.floor(t * 4)) - 0.5) * (2 + j), x = b.x + fx * s - fy * w, y = b.y + fy * s + fx * w, pp = toImg(x, y, z + 1 + j * 0.3), r = (2 + j) * q; ctx.fillRect(Math.round(ox + pp[0] * sx - r / 2), Math.round(oy + pp[1] * sx - r / 2), r, r); }
          }
          api.drawOccluded(spr.c, ix + spr.x0, iy + spr.y0, spr.c.width, spr.c.height, b.x, b.y, z + 0.5, view);
          if (b.kind !== 'kombajn' && b.kind !== 'rezacka' && !api.occluded(b.x, b.y, z + 2.5)) {   // kouř z výfuku traktoru
            const ex = b.x + fx * 1.26 + fy * 0.31, ey = b.y + fy * 1.26 - fx * 0.31;
            for (let j = 0; j < 3; j++) {
              const ph = (t * 0.8 + j / 3 + b.d * 0.01) % 1, pp = toImg(ex + ph * 1.5, ey + ph * 1.5, z + 2.7 + ph * 2.5), r = Math.max(1, Math.round((1 + ph * 2) * q));
              ctx.fillStyle = `rgba(90,90,94,${0.45 * (1 - ph)})`; ctx.fillRect(Math.round(ox + pp[0] * sx - r / 2), Math.round(oy + pp[1] * sx - r / 2), r, r);
            }
          }
        }
      }, { layer: 'world' });
    },
    onDestroy() { if (unsub) unsub(); },
  });
})();
