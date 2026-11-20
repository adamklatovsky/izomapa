// Doplněk „Vyhlídkový let“: hráč pilotuje dvouplošník An-2 „Andula“ – vzlétne z dráhy místního letiště, obletí co nejvíc
// míst z mista.json (žlutý kroužek nad dalším nejbližším místem, šipka ukazuje směr), ve výšce aspoň 300 m vysadí tři skupiny
// parašutistů a přistane zpátky na dráze. Náraz do domu (budova vyšší než letadlo, obrysy a výšky z dílků overlay) nebo
// přistání mimo dráhu body půlí. Bez dráhy (doplněk letiste ani vlastní "draha") začíná let ve 200 m nad městem a přistávat
// se nedá. Výsledky v „Hangáru slávy“ (localStorage). Ovládání: ← → zatáčení, ↑ ↓ stoupání/klesání, W / S plyn, mezerník
// výsadek, Esc konec; na dotykovém displeji tlačítka.
(() => {
  const ID = 'vyhlidkovy_let';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;

  const SUNV = (() => { const v = [0.38, -0.68, 0.62], n = Math.hypot(...v); return v.map((q) => q / n); })();
  const lit = (rgb, d) => { const f = (0.62 + 0.42 * Math.max(0, d)) / 0.88; return `rgb(${rgb.map((q) => Math.min(255, Math.round(q * f))).join(',')})`; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const NDIR = 48, RING = 40, SKIC = ['#d8352a', '#2f6fd1', '#f2c230', '#2aa36b', '#e0629a', '#f07a24'];
  let cleanup = [];

  Izomapa.registerPlugin(ID, {
    onInit(api) {
      const D = api.getPluginData(ID);
      if (!D || !D.mista || !D.mista.length) return;
      const cfg = api.getPluginConfig(ID) || {};
      const profanity = cfg.profanity_filter !== false ? api.getLib('profanity') : null;
      const toImg = api.toImg, gz = api.gz, cam = api.getCam(), MPP = cam.mpp || 0.2;
      const HALF = D.polovina || 1150, CTV = new Set((D.ctverce || [[0, 0]]).map(([i, j]) => `${i}_${j}`));
      const W_ = (q) => api.latLonToWorld(q[0], q[1]);
      const rw = D.draha ? (() => { const A = W_(D.draha.a), B = W_(D.draha.b), L = Math.hypot(B[0] - A[0], B[1] - A[1]); return { A, L, u: [(B[0] - A[0]) / L, (B[1] - A[1]) / L], hw: (D.draha.sirka || 24) / 2 + 6 }; })() : null;
      const MISTA = D.mista.map((m) => { const [x, y] = W_([m.lat, m.lon]); return { n: m.n, x, y }; });
      const G = { on: false, keys: new Set() };
      const HOF = `izomapa-let-${(cfg.tabulka || 'hangar').replace(/[^a-z0-9-]/gi, '')}`;

      // ---------- budovy pro náraz: obrysy (obrazové souřadnice) a výšky z dílků overlay, načítají se kolem letadla ----------
      const B = { nacteno: new Set(), ceka: new Set(), list: [] };
      function nactiDilek(key) {
        if (B.nacteno.has(key) || B.ceka.has(key) || !CTV.has(key)) return;
        B.ceka.add(key);
        fetch(`overlay/c${key}.json`).then((r) => (r.ok ? r.json() : null)).then((d) => {
          for (const b of (d && d.buildings) || []) {
            if (!b.hull || b.hull.length < 3) continue;
            let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [x, y] of b.hull) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
            B.list.push({ p: b.hull, bb: [x0, y0, x1, y1], h: +b.h || 10 });
          }
        }).catch(() => {}).finally(() => { B.nacteno.add(key); B.ceka.delete(key); });
      }
      const nactiOkoli = (x, y) => { const i = Math.floor((x + HALF) / (2 * HALF)), j = Math.floor((y + HALF) / (2 * HALF)); for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) nactiDilek(`${i + a}_${j + b}`); };
      const inPoly = (x, y, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
      const budova = (ix, iy) => B.list.find((b) => ix >= b.bb[0] && ix <= b.bb[2] && iy >= b.bb[1] && iy <= b.bb[3] && inPoly(ix, iy, b.p));

      // ---------- sprite An-2 (stejný jako v doplňku letiste): 48 směrů, kvádry stínované sluncem, tmavý obrys ----------
      const SPR = new Map();
      function sprite(k) {
        if (SPR.has(k)) return SPR.get(k);
        const a = k / NDIR * Math.PI * 2, fx = Math.cos(a), fy = Math.sin(a), sxv = -fy, syv = fx;
        const O = toImg(0, 0, 0), R = (s, t, h) => { const p = toImg(fx * s + sxv * t, fy * s + syv * t, h); return [p[0] - O[0], p[1] - O[1]]; };
        const faces = [], vis = (nx, ny) => nx + ny < 0, sun = (nx, ny, nz) => nx * SUNV[0] + ny * SUNV[1] + nz * SUNV[2];
        const box = (s0, s1, t0, t1, z0, z1, rgb) => {
          for (const [nx, ny, P0, P1] of [[fx, fy, [s1, t0], [s1, t1]], [-fx, -fy, [s0, t1], [s0, t0]], [sxv, syv, [s1, t1], [s0, t1]], [-sxv, -syv, [s0, t0], [s1, t0]]])
            if (vis(nx, ny)) faces.push([[R(P0[0], P0[1], z0), R(P1[0], P1[1], z0), R(P1[0], P1[1], z1), R(P0[0], P0[1], z1)], lit(rgb, sun(nx, ny, 0)), (z0 + z1) / 2]);
          faces.push([[R(s0, t0, z1), R(s1, t0, z1), R(s1, t1, z1), R(s0, t1, z1)], lit(rgb, sun(0, 0, 1)), z1]);
        };
        const l = 6.35, w = 9.1, C = [178, 184, 180], S = [214, 64, 40], GL = [64, 84, 108], DK = [44, 46, 50], PR = [70, 72, 76];
        box(l - 2.3, l - 1.9, -1.55, -1.25, 0, 0.75, DK); box(l - 2.3, l - 1.9, 1.25, 1.55, 0, 0.75, DK);
        box(-l + 0.3, -l + 0.6, -0.1, 0.1, 0, 0.5, DK);
        box(-l + 0.6, -l + 4.5, -0.45, 0.45, 0.9, 2.1, C);
        box(-l + 4.5, l - 1.2, -0.85, 0.85, 0.75, 2.75, C);
        box(-l + 4.5, l - 1.2, -0.87, 0.87, 1.55, 1.75, S);
        for (const s of [-1.5, -0.4, 0.7, 1.8]) for (const e of [-1, 1]) box(s, s + 0.55, e * 0.87 - 0.02, e * 0.87 + 0.02, 1.95, 2.35, GL);
        box(l - 3.2, l - 1.6, -0.75, 0.75, 2.75, 3.15, GL);
        box(l - 1.2, l - 0.25, -0.95, 0.95, 0.85, 2.65, PR); box(l - 0.25, l, -0.7, 0.7, 1.05, 2.45, DK);
        box(l, l + 0.05, -1.7, 1.7, 1.7, 1.9, DK); box(l, l + 0.05, -0.1, 0.1, 0.9, 2.7, DK);
        box(l - 3.4, l - 1.0, -w, w, 3.75, 3.95, C);
        box(l - 3.4, l - 2.9, -w, -w + 1.8, 3.77, 3.97, S); box(l - 3.4, l - 2.9, w - 1.8, w, 3.77, 3.97, S);
        box(l - 3.2, l - 1.2, -w * 0.78, w * 0.78, 0.8, 0.98, C);
        for (const t of [-w * 0.55, w * 0.55]) { box(l - 2.9, l - 2.75, t - 0.05, t + 0.05, 0.98, 3.75, DK); box(l - 1.75, l - 1.6, t - 0.05, t + 0.05, 0.98, 3.75, DK); }
        box(-l + 0.3, -l + 2.2, -3.6, 3.6, 2.0, 2.15, C);
        box(-l + 0.2, -l + 2.0, -0.08, 0.08, 2.1, 4.6, C); box(-l + 0.2, -l + 1.0, -0.09, 0.09, 3.6, 4.6, S);
        faces.sort((p, q) => p[2] - q[2]);
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
        const s = { c: cv, x0, y0 }; SPR.set(k, s); return s;
      }

      // ---------- rozhraní ----------
      const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
      const btn = el('button', 'px-btn let-btn', '✈'); btn.type = 'button'; btn.title = `${D.nazev} – proleť se nad městem`; btn.setAttribute('aria-label', `Hra ${D.nazev}`);
      (api.getUiSlot('sidebar-tabs') || document.body).appendChild(btn);
      const dlg = el('dialog', 'help let-dlg');
      dlg.innerHTML = `<button type="button" class="let-x" data-r="zavrit" aria-label="Zavřít">×</button>
        <h3>✈ ${esc(D.nazev)}</h3>
        <p>${rw ? `Vzlétni s dvouplošníkem An-2 „Andula“ z ${esc(D.letiste || 'letiště')}, obleť co nejvíc míst ze seznamu Místa a přistaň zpátky na dráze.` : 'Leť s dvouplošníkem An-2 „Andula“ nad městem a obleť co nejvíc míst ze seznamu Místa.'}</p>
        <p><b>Ovládání:</b> ← → zatáčení, ↑ ↓ stoupání a klesání, W / S plyn, mezerník výsadek parašutistů, Esc konec. Na telefonu tlačítka dole.</p>
        <p><b>Body:</b> průlet žlutým kroužkem nad místem +100 (pod 60 m ještě +50), všechna místa +500.${rw ? ' Přistání na dráze +300, k tomu zbylé palivo a jemné dosednutí.' : ''} Tři skupiny parašutistů vysaď mezerníkem aspoň ve 300 m – za skupinu polovina výšky seskoku. Náraz do domu${rw ? ' nebo přistání mimo dráhu' : ''} body půlí.</p>
        <div data-r="konec" hidden><p class="let-vysl" data-r="vysl"></p><p><input data-r="jmeno" maxlength="20" placeholder="Jméno pilota" autocomplete="nickname"> <button class="px-btn" type="button" data-r="uloz">Zapsat do hangáru</button></p></div>
        <h4>🏆 Hangár slávy</h4><ol data-r="tab"></ol>
        <p><button class="px-btn" type="button" data-r="start">${rw ? 'Vzlétnout' : 'Letět'}</button></p>
        <p class="let-muted">Výsledky se ukládají jen v tomto prohlížeči.</p>`;
      document.body.appendChild(dlg);
      const $ = (k) => dlg.querySelector(`[data-r="${k}"]`);
      const hud = el('div', 'let-hud', `<div class="let-panel"><b>${esc(D.nazev)}</b> <span data-h="body">0</span> b. · <span data-h="vys">0</span> m · <span data-h="rych">0</span> km/h
        · palivo <span class="let-pal"><i data-h="pal"></i></span><br><span data-h="cil"></span></div>
        <div class="let-sipka" data-h="sipka">➤</div><div class="let-msg" data-h="msg" hidden></div>`);
      hud.hidden = true; document.body.appendChild(hud);
      const H = (k) => hud.querySelector(`[data-h="${k}"]`);
      const pad = el('div', 'let-pad');
      for (const [k, t] of [['ArrowLeft', '◀'], ['ArrowUp', '▲'], ['ArrowDown', '▼'], ['ArrowRight', '▶'], [' ', 'výsadek'], ['w', 'plyn+'], ['s', 'plyn−'], ['Escape', 'konec']]) {
        const b = el('button', '', t); b.type = 'button'; pad.appendChild(b);
        b.addEventListener('pointerdown', (e) => { e.preventDefault(); if (k === 'Escape') return konec('konec'); if (k === ' ') return vysadek(); G.keys.add(k); });
        for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) b.addEventListener(ev, () => G.keys.delete(k));
      }
      hud.appendChild(pad);

      const hofLoad = () => { try { return JSON.parse(localStorage.getItem(HOF) || '[]'); } catch { return []; } };
      function hof() {
        const ol = $('tab'); ol.replaceChildren(); const L = hofLoad();
        if (!L.length) ol.append(el('li', '', 'Hangár je zatím prázdný. Buď první!'));
        for (const r of L) { const li = el('li'); li.textContent = `${r.n} – ${r.b} b. (${r.m} míst${r.p ? ', přistál' : ''}) ${r.d}`; ol.append(li); }
      }
      const hodnost = (b, vse) => (b >= 1800 && vse ? 'Kroužitel nad městem' : b >= 1200 ? 'Eso aeroklubu' : b >= 600 ? 'Pilot Anduly' : b >= 200 ? 'Žák pilota' : 'Pasažér');
      const zprava = (t, s = 2.5) => { H('msg').textContent = t; H('msg').hidden = false; G.msgT = s; };

      // ---------- let ----------
      function start() {
        let x, y, z = 0, hd = 0, v = 0, vzduch = false;
        if (rw) { x = rw.A[0] + rw.u[0] * 30; y = rw.A[1] + rw.u[1] * 30; hd = Math.atan2(rw.u[1], rw.u[0]); }
        else { const c = api.getView(); [x, y] = api.imgToWorld(c.x, c.y); z = 200; v = 40; vzduch = true; }
        Object.assign(G, { on: true, x, y, z, hd, v, thr: rw ? 0 : 0.6, vs: 0, fuel: 1, body: 0, done: new Set(), cil: null, msgT: 0, air: vzduch, landed: 0, skupiny: 3, chutes: [] });
        G.mista = MISTA.filter((p) => Math.hypot(p.x - x, p.y - y) < 9000);
        dlg.close(); hud.hidden = false; if (document.activeElement) document.activeElement.blur();
        nactiOkoli(x, y);
        const [ix, iy] = toImg(x, y, gz(x, y) + z); api.panTo(ix, iy, cam.w * MPP / 450, false);
        zprava(rw ? 'Plyn (W), rozjezd po dráze a nad 100 km/h šipkou ↑ vzlet!' : 'Leť ke žlutému kroužku – šipka ukazuje směr.', 4);
      }
      function konec(proc) {
        if (!G.on) return;
        G.on = false; hud.hidden = true; G.keys.clear();
        let b = G.body, txt;
        if (proc === 'pristal') { const bonus = 300 + Math.round(G.fuel * 300) + Math.round(Math.max(0, 13 - Math.abs(G.vsLand)) * 12); b += bonus; txt = `Přistání! +${bonus} b.`; }
        else if (proc === 'havarie') { b = Math.round(b / 2); txt = 'Havárie… body se půlí.'; }
        else txt = 'Let ukončen.';
        const vse = G.mista.length && G.done.size >= G.mista.length; if (vse) b += 500;
        G.vysl = { b, m: G.done.size, p: proc === 'pristal' };
        $('vysl').textContent = `${txt} Celkem ${b} bodů, ${G.done.size} z ${G.mista.length} míst. Hodnost: ${hodnost(b, vse)}.`;
        $('konec').hidden = false; hof(); dlg.showModal();
      }
      function vysadek() {                                              // dva parašutisté, padák se otevře po krátkém volném pádu
        if (!G.on) return;
        if (G.skupiny <= 0) return zprava('Už nikdo nechce skákat.');
        if (G.z < 300) return zprava(`Příliš nízko na výsadek! Vystoupej aspoň na 300 m (teď ${Math.round(G.z)} m).`);
        G.skupiny--; const pts = Math.round(G.z / 2); G.body += pts;
        for (let j = 0; j < 2; j++) { const x = G.x - Math.cos(G.hd) * j * 20, y = G.y - Math.sin(G.hd) * j * 20; G.chutes.push({ x, y, z: G.z, ff: 0.25 + j * 0.15, tx: x + (j - 0.5) * 40, ty: y + 30, col: SKIC[(j + G.skupiny * 2) % SKIC.length], land: 0 }); }
        zprava(`Výsadek z ${Math.round(G.z)} m! +${pts} b. Zbývá skupin: ${G.skupiny}`);
      }
      function krok(dt) {
        const K = G.keys;
        if (K.has('w') && !G.landed) G.thr = Math.min(1, G.thr + dt * 0.7); if (K.has('s')) G.thr = Math.max(0, G.thr - dt * 0.7);
        if (G.fuel <= 0) G.thr = 0;
        G.fuel = Math.max(0, G.fuel - dt * G.thr / 240);
        G.v += (8 + G.thr * 52 - G.v) * Math.min(1, dt * (G.z > 1 ? 0.25 : 0.45));     // do ~215 km/h
        const g0 = gz(G.x, G.y), fly = G.v > 28;                               // An-2 vzlétá kolem 100 km/h
        if (K.has('ArrowLeft')) G.hd += dt * (G.z > 1 ? 0.55 : 0.25); if (K.has('ArrowRight')) G.hd -= dt * (G.z > 1 ? 0.55 : 0.25);
        let vs = 0;
        if (K.has('ArrowUp') && fly) vs = 14; else if (K.has('ArrowDown')) vs = -12;
        if (!fly && G.z > 0.5) vs = Math.min(vs, -3.5);                        // pomalu = padá
        G.vs = vs; G.z = Math.max(0, Math.min(700, G.z + vs * dt));
        G.x += Math.cos(G.hd) * G.v * dt; G.y += Math.sin(G.hd) * G.v * dt;
        if (G.z > 3) G.air = true;
        let naDraze = false;
        if (rw) { const rx = G.x - rw.A[0], ry = G.y - rw.A[1], s = rx * rw.u[0] + ry * rw.u[1], t = Math.abs(-rx * rw.u[1] + ry * rw.u[0]); naDraze = s > -20 && s < rw.L + 20 && t < rw.hw; }
        if (G.air && G.z <= 0.01) {                                            // dosedl
          G.vsLand = vs;
          if (naDraze && vs > -13) { zprava('Dosednutí!', 2); G.air = false; G.landed = performance.now(); G.thr = 0; }
          else return konec('havarie');
        }
        if (G.landed) { G.thr = 0; G.v = Math.max(0, G.v - dt * 12); if (G.v < 6 || performance.now() - G.landed > 4000) return konec('pristal'); }
        if (!G.air && !G.landed && G.z <= 0.01 && !naDraze && G.v > 3) return konec('havarie');
        nactiOkoli(G.x, G.y);
        const [gi, gj] = toImg(G.x, G.y, g0), b = budova(gi, gj);
        if (b && G.z > 0.5 && G.z < b.h + 1) return konec('havarie');
        const vKruhu = (c) => {                                                // letadlo na obrázku uvnitř kroužku (jak ho hráč vidí)
          const [pi, pj] = toImg(G.x, G.y, g0 + G.z), [ci, cj] = toImg(c.x, c.y, gz(c.x, c.y)), r = RING / MPP;
          return ((pi - ci) / (r * 0.9)) ** 2 + ((pj - cj) / (r * 0.45)) ** 2 < 1;
        };
        if (G.cil && G.air && vKruhu(G.cil)) { const low = G.z < 60; G.done.add(G.cil.n); G.body += low ? 150 : 100; zprava(`${G.cil.n} +${low ? 150 : 100}${low ? ' (nízko!)' : ''}`); G.cil = null; }
        if (!G.cil) { let best = null, bd = 1e9; for (const p of G.mista) { if (G.done.has(p.n)) continue; const d = Math.hypot(p.x - G.x, p.y - G.y); if (d < bd) { bd = d; best = p; } } G.cil = best; }
        if (G.cil) G.cil.d = Math.hypot(G.cil.x - G.x, G.cil.y - G.y);
        for (const c of G.chutes) {
          if (c.land) { c.land += dt; continue; }
          c.ff -= dt; const vz = c.ff > 0 ? 45 : 4.5; c.z -= vz * dt;
          const d = Math.hypot(c.tx - c.x, c.ty - c.y) || 1, hv = c.ff > 0 ? 0 : Math.min(6, d / Math.max(1, c.z / vz));
          c.x += (c.tx - c.x) / d * hv * dt; c.y += (c.ty - c.y) / d * hv * dt;
          if (c.z <= 0) { c.z = 0; c.land = 0.01; }
        }
        G.chutes = G.chutes.filter((c) => c.land < 25);
        if (G.msgT > 0 && (G.msgT -= dt) <= 0) H('msg').hidden = true;
        H('body').textContent = G.body; H('vys').textContent = Math.round(G.z); H('rych').textContent = Math.round(G.v * 3.6);
        H('pal').style.width = `${Math.round(G.fuel * 100)}%`;
        H('cil').textContent = (G.cil ? `Cíl: ${G.cil.n} (${(G.cil.d / 1000).toFixed(1).replace('.', ',')} km)` : rw ? 'Všechna místa obletěna! Hurá zpátky na letiště.' : 'Všechna místa obletěna!')
          + (G.skupiny ? ` · parašutisté: ${G.skupiny}× ${G.z >= 300 ? '– mezerník!' : '(seskok od 300 m)'}` : '');
        const [ix, iy] = toImg(G.x, G.y, g0 + G.z); api.panTo(ix, iy, undefined, false);
      }
      function kresli(ctx, view) {
        const { sx, ox, oy } = view, g0 = gz(G.x, G.y), [ix, iy] = toImg(G.x, G.y, g0 + G.z);
        if (G.cil) {                                                          // kroužek nad dalším místem a šipka k němu
          const [ci, cj] = toImg(G.cil.x, G.cil.y, gz(G.cil.x, G.cil.y)), an = Math.atan2(cj - iy, ci - ix);
          H('sipka').style.transform = `translate(-50%, -50%) rotate(${an}rad) translateX(70px)`;
          ctx.strokeStyle = 'rgba(255,200,60,0.9)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(ox + ci * sx, oy + cj * sx, RING / MPP * sx * 0.9, RING / MPP * sx * 0.45, 0, 0, 7); ctx.stroke();
        }
        for (const c of G.chutes) {                                          // parašutisté
          const [px, py] = toImg(c.x, c.y, gz(c.x, c.y) + c.z), q = Math.max(1, Math.round(sx * 1.6)), X = Math.round(ox + px * sx), Y = Math.round(oy + py * sx);
          ctx.fillStyle = '#2a2c31'; ctx.fillRect(X - q / 2, Y - 2 * q, q, 2 * q);
          if (c.ff <= 0 && !c.land) { ctx.fillStyle = c.col; ctx.fillRect(X - 4 * q, Y - 7 * q, 8 * q, 2 * q); ctx.fillStyle = 'rgba(40,40,44,.6)'; ctx.fillRect(X - 3 * q, Y - 5 * q, q / 2, 3 * q); ctx.fillRect(X + 3 * q, Y - 5 * q, q / 2, 3 * q); }
          else if (c.land) { ctx.fillStyle = c.col; ctx.fillRect(X + q, Y - q, 5 * q, q); }
        }
        const sh = [-SUNV[0] / SUNV[2] * G.z, -SUNV[1] / SUNV[2] * G.z], [si, sj] = toImg(G.x + sh[0], G.y + sh[1], gz(G.x + sh[0], G.y + sh[1]));
        ctx.fillStyle = `rgba(20,26,30,${Math.max(0.08, 0.35 * (1 - G.z / 300)).toFixed(2)})`;
        ctx.beginPath(); ctx.ellipse(ox + si * sx, oy + sj * sx, 9 * sx * 2.2, 4 * sx * 2.2, 0, 0, 7); ctx.fill();
        const k = ((Math.round(G.hd / (Math.PI * 2) * NDIR) % NDIR) + NDIR) % NDIR, spr = sprite(k);
        ctx.drawImage(spr.c, Math.round(ox + (ix + spr.x0) * sx), Math.round(oy + (iy + spr.y0) * sx), Math.round(spr.c.width * sx), Math.round(spr.c.height * sx));
      }

      // ---------- události ----------
      btn.addEventListener('click', () => { $('konec').hidden = true; hof(); dlg.showModal(); });
      $('zavrit').addEventListener('click', () => dlg.close());
      $('start').addEventListener('click', start);
      $('uloz').addEventListener('click', () => {
        const r = G.vysl; if (!r) return;
        const n = ($('jmeno').value || 'Neznámý pilot').trim().slice(0, 20);
        if (profanity && !profanity.isValid(n)) { $('vysl').textContent = 'Zvol prosím jiné jméno.'; return; }
        const L = hofLoad(); L.push({ n, b: r.b, m: r.m, p: r.p, d: new Date().toLocaleDateString('cs-CZ') }); L.sort((a, b) => b.b - a.b);
        try { localStorage.setItem(HOF, JSON.stringify(L.slice(0, 10))); } catch {}
        G.vysl = null; $('konec').hidden = true; hof();
      });
      const KEYS = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'w', 's']);
      const kd = (e) => {
        if (!G.on) return;
        if (e.key === 'Escape') { e.preventDefault(); return konec('konec'); }
        if (e.key === ' ') { e.preventDefault(); e.stopPropagation(); return vysadek(); }
        const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
        if (KEYS.has(k)) { G.keys.add(k); e.preventDefault(); e.stopPropagation(); }   // šipky nesmí posouvat mapu
      };
      const ku = (e) => { if (G.on && e.key === ' ') { e.preventDefault(); e.stopPropagation(); } G.keys.delete(e.key.length === 1 ? e.key.toLowerCase() : e.key); };
      addEventListener('keydown', kd, true); addEventListener('keyup', ku, true);
      const unFrame = api.onFrame((ctx, view) => {
        if (!G.on) return;
        krok(Math.min(view.dt || 0.016, 0.1));
        if (G.on) kresli(ctx, view);
      }, { layer: 'sky', priority: 5 });
      cleanup = [() => removeEventListener('keydown', kd, true), () => removeEventListener('keyup', ku, true), unFrame, () => { btn.remove(); dlg.remove(); hud.remove(); }];
    },
    onDestroy() { for (const f of cleanup) try { f(); } catch {} cleanup = []; },
  });
})();
