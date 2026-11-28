// Doplněk „Výletní vláček“: silniční turistický vláček (lokomotiva a vagónky) jezdí po okruhu přes zastávky podle jízdního
// řádu (assets/doplnky/vlacek.json, trasu po silnicích a časy dopočítá overlay_hook.py). Ilustrační provoz, ne živá poloha:
// jedna otočka jízdního řádu (perioda P) se opakuje celý den podle hodin v Praze, takže všichni návštěvníci vidí totéž
// a v provozní době to sedí s jízdním řádem. Jezdí jen ve zvoleném období (výchozí léto), ve dne a ne v dešti ani ve sněhu.
// Každý díl soupravy jede po trase s odstupem, takže se v zatáčkách lomí. Kreslí se jako vozidla mapy: kvádry stínované
// sluncem od jihovýchodu, obrys 1 px, cache podle dílu a směru (48 směrů). Kliknutím se ukáže název a odkaz na provozovatele.
(() => {
  const ID = 'vlacek';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;
  let unsubFrame = null, unsubClick = null, pop = null;

  const NDIR = 48;
  const SUNV = (() => { const v = [0.38, -0.68, 0.62], n = Math.hypot(...v); return v.map((q) => q / n); })();
  const lit = (rgb, d) => { const f = (0.62 + 0.42 * Math.max(0, d)) / 0.88; return `rgb(${rgb.map((q) => Math.min(255, Math.round(q * f))).join(',')})`; };
  const rgbOf = (h, d) => (typeof h === 'string' && /^#[0-9a-f]{6}$/i.test(h) ? [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) : d);
  const LOCO = 4.6, WAG = 4.0, GAP = 1.1, WID = 2.1, RIGHT = 1.2;   // m; mezera = oj mezi vozy, v ostré zatáčce se vnitřní rohy jinak překrývají; souprava jede kousek vpravo od osy

  Izomapa.registerPlugin(ID, {
    onInit(api) {
      const D = api.getPluginData(ID);
      if (!D || !D.trasa || D.trasa.length < 2 || !D.kf || !D.kf.length) return;
      const toImg = api.toImg, gz = api.gz;
      const B = D.barvy || {};
      const C = { loco: rgbOf(B.lokomotiva, [232, 115, 30]), cab: rgbOf(B.kabina, [43, 43, 47]), wag: rgbOf(B.vagony, [232, 115, 30]),
                  roof: rgbOf(B.strecha, [241, 237, 226]), frame: rgbOf(B.ramy, [43, 43, 47]) };
      // okruh ve světových souřadnicích a kumulativní délky (měřítko na délku z hooku, ať časy sedí)
      const P = D.trasa.map((q) => api.latLonToWorld(q[0], q[1]));
      const cum = [0]; for (let i = 1; i < P.length; i++) cum.push(cum[i - 1] + Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]));
      const L = cum[cum.length - 1], k = L / (D.L || L);
      const at = (s) => {                                   // bod na okruhu ve vzdálenosti s (m, libovolné, bere se modulo délka)
        s = ((s % L) + L) % L;
        let lo = 0, hi = cum.length - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (cum[m] <= s) lo = m; else hi = m; }
        const f = (s - cum[lo]) / ((cum[hi] - cum[lo]) || 1);
        return [P[lo][0] + (P[hi][0] - P[lo][0]) * f, P[lo][1] + (P[hi][1] - P[lo][1]) * f];
      };
      // čas v Praze (s od půlnoci) -> vzdálenost lokomotivy po okruhu, nebo null mimo jízdy
      const tzFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Prague', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
      const pragueSec = () => { const [h, m, s] = tzFmt.format(new Date()).split(':').map(Number); return h * 3600 + m * 60 + s + (Date.now() % 1000) / 1000; };
      let tzOff = pragueSec() - (Date.now() / 1000) % 86400;   // jednou: posun Prahy proti UTC, pak už jen Date.now()
      const sNow = () => {
        const u = ((((Date.now() / 1000 + tzOff) % 86400) - D.t0) % D.P + D.P) % D.P, kf = D.kf;
        if (u <= kf[0][0]) return kf[kf.length - 1][1] * k;       // před první jízdou otočky stojí na konečné (= začátek okruhu)
        for (let i = 1; i < kf.length; i++) if (u <= kf[i][0]) {
          const a = kf[i - 1], b = kf[i], f = (u - a[0]) / ((b[0] - a[0]) || 1);
          return (a[1] + (b[1] - a[1]) * f) * k;
        }
        return kf[kf.length - 1][1] * k;
      };
      const SPR = new Map();
      function sprite(kind, dir) {
        const key = kind + dir; if (SPR.has(key)) return SPR.get(key);
        const a = dir / NDIR * Math.PI * 2, fx = Math.cos(a), fy = Math.sin(a), sxv = -fy, syv = fx;
        const O = toImg(0, 0, 0), R = (s, t, h) => { const p = toImg(fx * s + sxv * t, fy * s + syv * t, h); return [p[0] - O[0], p[1] - O[1]]; };
        const faces = [], vis = (nx, ny) => nx + ny < 0, sun = (nx, ny, nz) => nx * SUNV[0] + ny * SUNV[1] + nz * SUNV[2];
        let order = 0;
        const box = (s0, s1, t0, t1, z0, z1, rgb, top) => {
          for (const [nx, ny, P0, P1] of [[fx, fy, [s1, t0], [s1, t1]], [-fx, -fy, [s0, t1], [s0, t0]], [sxv, syv, [s1, t1], [s0, t1]], [-sxv, -syv, [s0, t0], [s1, t0]]])
            if (vis(nx, ny)) faces.push([[R(P0[0], P0[1], z0), R(P1[0], P1[1], z0), R(P1[0], P1[1], z1), R(P0[0], P0[1], z1)], lit(rgb, sun(nx, ny, 0)), z0, order]);
          faces.push([[R(s0, t0, z1), R(s1, t0, z1), R(s1, t1, z1), R(s0, t1, z1)], lit(top || rgb, sun(0, 0, 1)), z1, order++]);
        };
        const w = WID / 2, DK = [32, 32, 35], GL = [70, 86, 106], TY = [26, 26, 28], CH = [200, 200, 196];
        if (kind === 'L') {
          // mašinka: podvozek, „kotel“ vpředu, komín, kabina s okny a střechou vzadu, kola
          const l = LOCO / 2;
          for (const s of [l - 1.0, -l + 0.9]) for (const e of [-1, 1]) box(s - 0.38, s + 0.38, e * w - 0.02, e * w * 0.72, 0, 0.72, TY);
          box(-l, l, -w * 0.8, w * 0.8, 0.3, 0.6, DK);
          box(-l + 1.7, l - 0.15, -w * 0.62, w * 0.62, 0.6, 1.55, C.loco);                                    // kotel
          box(-l + 1.7, l - 0.15, -w * 0.64, w * 0.64, 1.0, 1.1, CH);                                       // lišta
          box(l - 0.15, l, -w * 0.5, w * 0.5, 0.65, 1.45, DK);                                              // čelo
          box(l - 1.0, l - 0.6, -0.17, 0.17, 1.55, 2.3, C.cab); box(l - 1.06, l - 0.54, -0.23, 0.23, 2.3, 2.45, C.loco);   // komín
          box(-l, -l + 1.7, -w, w, 0.6, 1.4, C.loco);                                                        // kabina dole
          for (const e of [-1, 1]) box(-l + 0.15, -l + 1.55, e * w - 0.02 * e, e * w * 0.9, 1.4, 2.25, GL);   // boční okna
          box(-l + 1.55, -l + 1.7, -w * 0.85, w * 0.85, 1.4, 2.25, GL);                                     // přední okno kabiny
          box(-l - 0.1, -l + 1.85, -w - 0.05, w + 0.05, 2.25, 2.45, C.cab);                                // střecha kabiny
        } else {
          // vagónek: podvozek, nízké bočnice, sloupky, střecha
          const l = WAG / 2;
          for (const s of [l - 0.8, -l + 0.8]) for (const e of [-1, 1]) box(s - 0.3, s + 0.3, e * w - 0.02, e * w * 0.75, 0, 0.6, TY);
          box(-l + 0.1, l - 0.1, -w * 0.85, w * 0.85, 0.3, 0.55, DK);
          box(-l, l, -w, w, 0.55, 1.15, C.wag, [120, 92, 70]);                                              // bočnice, uvnitř lavice
          box(-l, l, -w, w, 1.15, 1.22, C.frame);
          for (const s of [-l, -l / 3, l / 3, l - 0.12]) for (const e of [-1, 1]) box(s, s + 0.12, e * w - 0.12 * e, e * w, 1.22, 2.15, C.frame);
          box(-l - 0.05, l + 0.05, -w - 0.08, w + 0.08, 2.15, 2.3, C.frame, C.roof);                         // střecha
          box(-l + 0.1, l - 0.1, -w + 0.05, w - 0.05, 2.3, 2.36, C.roof);
        }
        faces.sort((p, q) => p[2] - q[2] || p[3] - q[3]);
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const [pts] of faces) for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
        x0 = Math.floor(x0) - 1; y0 = Math.floor(y0) - 1;
        const cw = Math.ceil(x1) - x0 + 2, chh = Math.ceil(y1) - y0 + 2, cv = document.createElement('canvas'); cv.width = cw; cv.height = chh;
        const g = cv.getContext('2d');
        for (const [pts, fill] of faces) { g.fillStyle = fill; g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x - x0, y - y0) : g.moveTo(x - x0, y - y0))); g.closePath(); g.fill(); }
        const im = g.getImageData(0, 0, cw, chh), d = im.data, solid = new Uint8Array(cw * chh);   // ostré okraje a tmavý obrys jako vozidla
        for (let i = 0; i < cw * chh; i++) { solid[i] = d[i * 4 + 3] >= 110 ? 1 : 0; d[i * 4 + 3] = solid[i] ? 255 : 0; }
        for (let y = 0; y < chh; y++) for (let x = 0; x < cw; x++) {
          const i = y * cw + x; if (solid[i]) continue;
          if ((x > 0 && solid[i - 1]) || (x < cw - 1 && solid[i + 1]) || (y > 0 && solid[i - cw]) || (y < chh - 1 && solid[i + cw])) d.set([27, 28, 34, 255], i * 4);
        }
        g.putImageData(im, 0, 0);
        const spr = { c: cv, x0, y0 }; SPR.set(key, spr); return spr;
      }
      // díly soupravy: [druh, vzdálenost středu za čelem, délka]
      const parts = [['L', LOCO / 2, LOCO]];
      for (let i = 0; i < Math.max(0, Math.min(6, D.vagony ?? 3)); i++) parts.push(['W', LOCO + GAP + WAG / 2 + i * (WAG + GAP), WAG]);
      let drawn = [];
      unsubFrame = api.onFrame((ctx, view) => {
        drawn = [];
        if (view.sx <= 0.12 || view.night > 0.45 || view.weather === 'rain' || view.weather === 'snow') return;
        if (!(D.obdobi || ['summer']).includes(view.season)) return;
        const s = sNow(), { sx, ox, oy } = view;
        const [hx, hy] = at(s);
        if (!view.vis(...toImg(hx, hy, gz(hx, hy)), 120)) return;
        const items = parts.map(([kind, off, len]) => {
          const f = at(s - off + len / 2), b = at(s - off - len / 2), dx = f[0] - b[0], dy = f[1] - b[1], n = Math.hypot(dx, dy) || 1;
          const x = (f[0] + b[0]) / 2 + dy / n * RIGHT, y = (f[1] + b[1]) / 2 - dx / n * RIGHT;
          const [ix, iy] = toImg(x, y, gz(x, y));
          return { kind, ix, iy, x, y, dir: ((Math.round(Math.atan2(dy, dx) / (Math.PI * 2) * NDIR) % NDIR) + NDIR) % NDIR };
        }).sort((p, q) => p.iy - q.iy);                  // vzdálenější díl (výš na obrazovce) dřív
        for (const it of items) {
          const spr = sprite(it.kind, it.dir);
          if (api.drawOccluded) api.drawOccluded(spr.c, it.ix + spr.x0, it.iy + spr.y0, spr.c.width, spr.c.height, it.x, it.y, gz(it.x, it.y), view);   // každý vůz zvlášť: dům nebo strom před ním ho zakryje
          else ctx.drawImage(spr.c, Math.round(ox + (it.ix + spr.x0) * sx), Math.round(oy + (it.iy + spr.y0) * sx), Math.round(spr.c.width * sx), Math.round(spr.c.height * sx));
          drawn.push([ox + it.ix * sx, oy + (it.iy - 6) * sx]);
        }
      }, { layer: 'world' });

      const closePop = () => { if (pop) { pop.remove(); pop = null; } };
      unsubClick = api.onMapClick((e) => {
        closePop();
        const r = document.getElementById('osd')?.getBoundingClientRect();
        if (!r || !drawn.some(([x, y]) => Math.hypot(x - e.screenX, y - e.screenY) < 22)) return false;
        pop = document.createElement('div');
        pop.style.cssText = 'position:fixed;z-index:50;max-width:260px;padding:8px 10px;border-radius:6px;background:rgba(24,26,32,.92);color:#f2f2ee;'
          + 'font:13px/1.35 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.4)';
        if (matchMedia('(max-width: 640px)').matches) {   // telefon: dole nad lištou jako karta místa (40-mobil.css), ne přes panel
          Object.assign(pop.style, { left: '8px', right: '8px', maxWidth: 'none', bottom: 'calc(72px + env(safe-area-inset-bottom, 0px))' });
        } else { pop.style.left = `${Math.min(r.left + e.screenX + 12, innerWidth - 272)}px`; pop.style.top = `${Math.max(8, r.top + e.screenY - 70)}px`; }
        const b = document.createElement('b'); b.textContent = D.nazev || 'Výletní vláček'; pop.appendChild(b);
        if (D.popis) { const p = document.createElement('div'); p.textContent = D.popis; pop.appendChild(p); }
        if (/^https?:\/\//.test(D.url || '')) {
          const a = document.createElement('a'); a.href = D.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = D.url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
          a.style.color = '#ffc078'; pop.appendChild(a);
        }
        document.body.appendChild(pop);
        return true;
      }, { priority: 5 });
    },
    onDestroy() { if (unsubFrame) unsubFrame(); if (unsubClick) unsubClick(); if (pop) pop.remove(); },
  });
})();
