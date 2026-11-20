// Doplněk „Rychlostní zkouška“: hráč si kdekoli na mapě postaví trať (klikáním bodů; mezi nimi se trať sama vede po silnicích
// z dílků overlay/c<i>_<j>.json) a projede ji v rallyovém autě (Rally2) – fyzika se smykem a ruční brzdou, mimo trať auto
// zpomalí, domy a svodidla podél trati zastaví, odpočet startu, mezičasy ve ¼, ½ a ¾ zkoušky se ztrátou na vedoucího.
// Trať jde sdílet odkazem (?rz=…, body v adrese) a každá má vlastní tabulku výsledků: v prohlížeči (localStorage), nebo
// společnou na serveru (config "server_url", knihovna server_client; vzor serveru je v server/). Volitelně je k dispozici
// i připravená trať z assets/doplnky/rz.json (např. městská RZ Bohemia Rally). Po dobu jízdy se vypne doprava (uzavřená trať).
(() => {
  const ID = 'rz';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;

  const SUNV = (() => { const v = [0.38, -0.68, 0.62], n = Math.hypot(...v); return v.map((q) => q / n); })();
  const lit = (rgb, d) => { const f = (0.62 + 0.42 * Math.max(0, d)) / 0.88; return `rgb(${rgb.map((q) => Math.min(255, Math.round(q * f))).join(',')})`; };
  const rnd = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const fmt = (t) => t.toFixed(2).replace('.', ',');
  const km = (m) => (m / 1000).toFixed(2).replace('.', ',');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const BEZ = new Set(['motorway', 'motorway_link', 'trunk', 'trunk_link', 'footway', 'path', 'cycleway', 'steps', 'pedestrian', 'track', 'bridleway']);
  const MIN_L = 300, MAX_L = 30000;
  let cleanup = [];

  // kódování bodů trati do odkazu: počet kol, okruh, body lat/lon × 1e5 jako rozdíly v base36 (krátké a čitelné v URL)
  const kodTrat = (body, kola, okruh) => {
    let pa = 0, po = 0;
    const q = body.map(([la, lo]) => { const a = Math.round(la * 1e5), o = Math.round(lo * 1e5), r = `${(a - pa).toString(36)},${(o - po).toString(36)}`; pa = a; po = o; return r; });
    return `${kola}${okruh ? 'o' : ''}~${q.join('_')}`;
  };
  const dekodTrat = (s) => {
    const m = /^(\d{1,2})(o?)~([0-9a-z,_-]+)$/.exec(String(s || '').trim().toLowerCase());
    if (!m) return null;
    let a = 0, o = 0;
    const body = m[3].split('_').map((p) => { const [da, dob] = p.split(',').map((v) => parseInt(v, 36)); a += da; o += dob; return [a / 1e5, o / 1e5]; });
    if (body.length < 2 || body.length > 80 || body.some(([x, y]) => !Number.isFinite(x) || !Number.isFinite(y))) return null;
    return { kola: Math.max(1, Math.min(10, +m[1])), okruh: m[2] === 'o', body };
  };
  const hashStr = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); };

  Izomapa.registerPlugin(ID, {
    onInit(api) {
      const D = api.getPluginData(ID);
      if (!D) return;
      const cfg = api.getPluginConfig(ID) || {};
      const profanity = cfg.profanity_filter !== false ? api.getLib('profanity') : null;
      const sc = api.getLib('server_client');
      const client = cfg.server_url && sc ? sc.createClient(cfg.server_url) : null;
      const toImg = api.toImg, gz = api.gz;
      const HALF = D.polovina || 1150, CTV = new Set((D.ctverce || [[0, 0]]).map(([i, j]) => `${i}_${j}`));
      const R = { on: false, keys: new Set(), tab: [], online: false, trat: null };

      // ---------- silniční síť z dílků overlay (načítá se jen kolem kliknutí) a hledání cesty ----------
      const G = { nodes: new Map(), seg: [], nacteno: new Set(), ceka: new Map() };
      const nodeId = (x, y) => `${Math.round(x)}|${Math.round(y)}`;
      const node = (x, y) => { const k = nodeId(x, y); let n = G.nodes.get(k); if (!n) { n = { k, x, y, e: [] }; G.nodes.set(k, n); } return n; };
      function nactiDilek(key) {
        if (G.nacteno.has(key) || !CTV.has(key)) return Promise.resolve();
        if (G.ceka.has(key)) return G.ceka.get(key);
        const p = fetch(`overlay/c${key}.json`).then((r) => (r.ok ? r.json() : null)).then((d) => {
          G.nacteno.add(key);
          for (const r of (d && d.roads) || []) {
            if (BEZ.has(r.c) || !r.w || r.w.length < 2) continue;
            for (let i = 1; i < r.w.length; i++) {
              const a = node(r.w[i - 1][0], r.w[i - 1][1]), b = node(r.w[i][0], r.w[i][1]);
              if (a === b) continue;
              const l = Math.hypot(b.x - a.x, b.y - a.y);
              if (!a.e.some((q) => q.n === b)) { a.e.push({ n: b, l }); b.e.push({ n: a, l }); G.seg.push([a, b]); }
            }
          }
        }).catch(() => { G.nacteno.add(key); });
        G.ceka.set(key, p); return p;
      }
      const dilekBodu = (x, y) => [Math.floor((x + HALF) / (2 * HALF)), Math.floor((y + HALF) / (2 * HALF))];
      const nactiOkoli = (x, y) => { const [i, j] = dilekBodu(x, y), L = []; for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) L.push(nactiDilek(`${i + a}_${j + b}`)); return Promise.all(L); };
      function prichyt(x, y, max = 40) {                             // nejbližší místo na silnici (úsek a, b, poměr f)
        let best = null;
        for (const [a, b] of G.seg) {
          if (Math.abs(a.x - x) > 400 && Math.abs(b.x - x) > 400) continue;
          const dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy || 1, f = Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / l2));
          const px = a.x + dx * f, py = a.y + dy * f, d = Math.hypot(x - px, y - py);
          if (d < max && (!best || d < best.d)) best = { a, b, f, x: px, y: py, d };
        }
        return best;
      }
      function cesta(A, B) {                                         // Dijkstra mezi dvěma přichycenými body, vrací [[x, y], …]
        if ((A.a === B.a && A.b === B.b) || (A.a === B.b && A.b === B.a)) return [[A.x, A.y], [B.x, B.y]];
        const dist = new Map(), prev = new Map(), heap = [];
        const push = (n, d, p) => { if (d >= (dist.get(n) ?? Infinity)) return; dist.set(n, d); prev.set(n, p); heap.push([d, n]); let i = heap.length - 1; while (i) { const j = (i - 1) >> 1; if (heap[j][0] <= heap[i][0]) break; [heap[i], heap[j]] = [heap[j], heap[i]]; i = j; } };
        const pop = () => { const t = heap[0], l = heap.pop(); if (heap.length) { heap[0] = l; let i = 0; for (;;) { const a = 2 * i + 1, b = a + 1; let m = i; if (a < heap.length && heap[a][0] < heap[m][0]) m = a; if (b < heap.length && heap[b][0] < heap[m][0]) m = b; if (m === i) break; [heap[i], heap[m]] = [heap[m], heap[i]]; i = m; } } return t; };
        push(A.a, Math.hypot(A.a.x - A.x, A.a.y - A.y), null); push(A.b, Math.hypot(A.b.x - A.x, A.b.y - A.y), null);
        const cil = new Map([[B.a, Math.hypot(B.a.x - B.x, B.a.y - B.y)], [B.b, Math.hypot(B.b.x - B.x, B.b.y - B.y)]]);
        let konec = null, nej = Infinity, n = 0;
        while (heap.length && n++ < 200000) {
          const [d, u] = pop();
          if (d > (dist.get(u) ?? Infinity) || d >= nej) continue;
          if (cil.has(u) && d + cil.get(u) < nej) { nej = d + cil.get(u); konec = u; }
          for (const { n: v, l } of u.e) push(v, d + l, u);
        }
        if (!konec) return null;
        const o = [[B.x, B.y]]; for (let u = konec; u; u = prev.get(u)) o.push([u.x, u.y]); o.push([A.x, A.y]);
        return o.reverse();
      }

      // ---------- trať pro jízdu ----------
      function nastavTrat(t) {                                        // t: { nazev, popis, zdroj, kola, tabulka, lap: [[x, y], …], body?, okruh? }
        const lap = [];
        for (let i = 0; i < t.lap.length; i++) {
          if (i) { const a = t.lap[i - 1], b = t.lap[i], n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 5); for (let k = 1; k < n; k++) lap.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]); }
          const p = t.lap[i]; if (!lap.length || Math.hypot(p[0] - lap[lap.length - 1][0], p[1] - lap[lap.length - 1][1]) > 0.3) lap.push(p);
        }
        const w = [...lap]; for (let k = 1; k < t.kola; k++) w.push(...lap.slice(1));
        const len = [0]; for (let i = 1; i < w.length; i++) len.push(len[i - 1] + Math.hypot(w[i][0] - w[i - 1][0], w[i][1] - w[i - 1][1]));
        Object.assign(R, { trat: t, w, len, L: len[len.length - 1], lapL: len[lap.length - 1], lapPts: lap.length, HALF: 4.5, tape: null, gates: null });
        R.splits = [0.25, 0.5, 0.75].map((f) => f * R.L);
        R.LS = `izomapa-rz-${t.tabulka}`;
      }
      const at = (s) => {
        const len = R.len, w = R.w; let i = 1; while (i < len.length - 1 && len[i] < s) i++;
        const a = w[i - 1], b = w[i], f = Math.max(0, Math.min(1, (s - len[i - 1]) / ((len[i] - len[i - 1]) || 1)));
        return { x: a[0] + (b[0] - a[0]) * f, y: a[1] + (b[1] - a[1]) * f, hd: Math.atan2(b[1] - a[1], b[0] - a[0]) };
      };
      function proj(x, y, s0) {                                   // nejbližší bod trati v okně kolem dosavadního postupu (žádné zkratky)
        const len = R.len, w = R.w; let best = null, i0 = R.pi || 1;
        while (i0 > 1 && len[i0 - 1] > s0 - 40) i0--; while (i0 < w.length - 1 && len[i0] < s0 - 40) i0++;
        R.pi = i0;
        for (let i = i0; i < w.length; i++) {
          if (len[i - 1] > s0 + 60) break;
          const a = w[i - 1], b = w[i], dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy || 1;
          const f = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / l2)), d = Math.hypot(x - a[0] - dx * f, y - a[1] - dy * f);
          if (!best || d < best.d) best = { d, s: len[i - 1] + Math.sqrt(l2) * f };
        }
        return best || { d: 1e9, s: s0 };
      }

      // ---------- rozhraní ----------
      const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
      const btn = el('button', 'px-btn rz-btn', '🏁');
      btn.type = 'button'; btn.title = 'Rychlostní zkouška – postav trať a jeď'; btn.setAttribute('aria-label', 'Hra Rychlostní zkouška');
      (api.getUiSlot('sidebar-tabs') || document.body).appendChild(btn);
      const dlg = el('dialog', 'help rz-dlg');
      dlg.innerHTML = `<button type="button" class="rz-x" data-r="zavrit" aria-label="Zavřít">×</button>
        <h3>🏁 Rychlostní zkouška – ${esc(D.auto || 'Rally2')}</h3>
        <div data-r="trat"></div>
        <p class="rz-akce"><button type="button" class="px-btn" data-r="start">Na start!</button>
          <button type="button" class="px-btn" data-r="stavet">✏️ Postavit vlastní trať</button>
          <button type="button" class="px-btn" data-r="pripravena" hidden>Připravená trať</button>
          <button type="button" class="px-btn" data-r="sdilet" hidden>🔗 Sdílet trať</button></p>
        <p class="rz-muted" data-r="sdileno" hidden></p>
        <p class="rz-vysl" data-r="vysl" hidden></p>
        <p class="rz-jmeno" data-r="jmenoBox" hidden><label>Jméno do tabulky: <input data-r="jmeno" maxlength="20" autocomplete="nickname"></label> <button type="button" class="px-btn" data-r="uloz">Uložit čas</button></p>
        <h4>⏱ Výsledky <span class="rz-muted" data-r="kde"></span></h4>
        <div class="rz-scroll"><table class="rz-tab" data-r="tab"></table></div>
        <details><summary>Jak se hraje</summary>
          <p><b>Ovládání:</b> ↑ plyn, ↓ brzda, ← → řízení, mezerník ruční brzda (smyk do zatáčky), R znovu, Esc konec. Na dotykovém displeji tlačítky dole. Mimo trať auto zpomalí, náraz do domu bolí.</p>
          <p><b>Vlastní trať:</b> klikej na mapu – každý klik přidá bod a trať se k němu sama dovede po silnicích. Nastav počet kol, případně ji uzavři do okruhu, a dej „Hotovo“. Odkazem „Sdílet trať“ ji pošleš ostatním, každá trať má vlastní tabulku.</p>
          <p>Mezičasy jsou ve čtvrtině, v polovině a ve třech čtvrtinách zkoušky; u každého uvidíš ztrátu nebo náskok na vedoucího a průběžné pořadí.</p></details>`;
      document.body.appendChild(dlg);
      const $ = (k) => dlg.querySelector(`[data-r="${k}"]`);
      const hud = el('div', 'rz-hud', `<b data-h="nazev"></b> · <span data-h="kolo"></span><span data-h="cas">0,00</span> s · <span data-h="rych">0</span> km/h · <span data-h="info"></span><div class="rz-split" data-h="split"></div>`);
      hud.hidden = true; document.body.appendChild(hud);
      const H = (k) => hud.querySelector(`[data-h="${k}"]`);
      const svetla = el('div', 'rz-svetla'); svetla.hidden = true; document.body.appendChild(svetla);
      const pad = el('div', 'rz-pad');
      for (const [k, t] of [['ArrowLeft', '◀'], ['ArrowRight', '▶'], [' ', 'ruční'], ['ArrowDown', 'brzda'], ['ArrowUp', 'plyn'], ['Escape', 'konec']]) {
        const b = el('button', '', t); b.type = 'button'; b.dataset.k = k; pad.appendChild(b);
        b.addEventListener('pointerdown', (e) => { e.preventDefault(); if (k === 'Escape') return konec(false); R.keys.add(k); });
        for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) b.addEventListener(ev, () => R.keys.delete(k));
      }
      hud.appendChild(pad);
      const ed = el('div', 'rz-editor', `<b>✏️ Stavba trati</b> <span data-e="info">Klikni na silnici – start.</span>
        <div class="rz-editor-akce"><button type="button" class="px-btn" data-e="zpet">↶ Zpět</button>
        <label><input type="checkbox" data-e="okruh"> okruh</label>
        <label>kola <select data-e="kola">${[1, 2, 3, 4, 5].map((k) => `<option>${k}</option>`).join('')}</select></label>
        <button type="button" class="px-btn" data-e="hotovo">Hotovo</button> <button type="button" class="px-btn" data-e="zrusit">Zrušit</button></div>`);
      ed.hidden = true; document.body.appendChild(ed);
      const E_ = (k) => ed.querySelector(`[data-e="${k}"]`);

      function popisTrati() {
        const t = R.trat;
        if (!t) { $('trat').innerHTML = '<p>Zatím tu není připravená trať. Postav si vlastní – klikáním na mapu, po silnicích kdekoli ve městě.</p>'; $('start').hidden = true; return; }
        $('start').hidden = false;
        $('trat').innerHTML = `<p><b>${esc(t.nazev)}</b> <span class="rz-muted">(${km(R.L)} km${t.kola > 1 ? `, ${t.kola} kola` : ''}${t.okruh ? ', okruh' : ''})</span></p>${t.popis ? `<p>${esc(t.popis)}</p>` : ''}${t.zdroj ? `<p class="rz-muted rz-zdroj">${esc(t.zdroj)}</p>` : ''}`;
        $('sdilet').hidden = !t.body; $('pripravena').hidden = !(t.body && D.trat); $('sdileno').hidden = true;
      }

      // ---------- výsledky ----------
      const local = () => { try { return JSON.parse(localStorage.getItem(R.LS) || '[]'); } catch { return []; } };
      function kresli(L) {
        R.tab = L;
        const T = $('tab'); T.replaceChildren();
        T.append(el('tr', '', '<th>#</th><th>Jezdec</th><th>M1</th><th>M2</th><th>M3</th><th>Cíl</th>'));
        if (!L.length) T.append(el('tr', '', '<td></td><td>Zatím nikdo. Buď první!</td>'));
        const best = [0, 1, 2].map((k) => Math.min(...L.filter((r) => r.s).map((r) => r.s[k]))), bt = Math.min(...L.map((r) => r.t));
        L.slice(0, 15).forEach((r, i) => {
          const c = (v, b) => `<td class="${v === b ? 'best' : ''}">${v ? fmt(v) : '–'}</td>`;
          const tr = el('tr', '', `<td>${i + 1}.</td><td></td>${[0, 1, 2].map((k) => c(r.s && r.s[k], best[k])).join('')}${c(r.t, bt)}`);
          tr.children[1].textContent = r.n; T.append(tr);
        });
        $('kde').textContent = R.online ? '(společná tabulka této trati; zeleně kdo vede)' : '(v tomto prohlížeči; zeleně kdo vede)';
      }
      async function tabulka() {
        if (!R.trat) return kresli([]);
        if (client) { const q = await client.call('leaderboard', { tabulka: R.trat.tabulka }); if (q.ok && Array.isArray(q.data?.entries)) { R.online = true; return kresli(q.data.entries); } }
        R.online = false; kresli(local());
      }

      // ---------- stavba trati ----------
      const S = { on: false, body: [], useky: [] };                  // body: přichycené body, useky[i] = cesta z bodu i do i+1
      const delkaCesty = (c) => c.reduce((s, p, i) => (i ? s + Math.hypot(p[0] - c[i - 1][0], p[1] - c[i - 1][1]) : 0), 0);
      const lapStavby = () => { const o = []; for (const u of S.useky) o.push(...(o.length ? u.slice(1) : u)); if (E_('okruh').checked && S.zpet) o.push(...S.zpet.slice(1)); return o; };
      function infoStavby(txt) {
        const l = delkaCesty(lapStavby()), k = +E_('kola').value;
        E_('info').textContent = txt || (S.body.length ? `${S.body.length} bodů · kolo ${km(l)} km${k > 1 ? ` · celkem ${km(l * k)} km` : ''}` : 'Klikni na silnici – start.');
      }
      function prepocitejOkruh() {
        S.zpet = E_('okruh').checked && S.body.length > 1 ? cesta(S.body[S.body.length - 1], S.body[0]) : null;
        infoStavby();
      }
      function stavet() {
        dlg.close(); S.on = true; S.body = []; S.useky = []; S.zpet = null; ed.hidden = false;
        api.setClickCapture(true); api.setCursor('crosshair'); infoStavby();
        const v = api.getView(), [x, y] = api.imgToWorld(v.x, v.y); nactiOkoli(x, y);
      }
      function konecStavby() { S.on = false; ed.hidden = true; api.setClickCapture(false); api.setCursor(''); }
      const unClick = api.onMapClick(async (e) => {
        if (!S.on) return false;
        const [x, y] = api.imgToWorld(e.x, e.y);
        infoStavby('načítám silnice…'); await nactiOkoli(x, y);
        const p = prichyt(x, y);
        if (!p) { infoStavby('Tady není silnice – klikni blíž k ulici.'); return true; }
        if (S.body.length) {
          if (S.body.length >= 80) { infoStavby('Nejvýš 80 bodů.'); return true; }
          const c = cesta(S.body[S.body.length - 1], p);
          if (!c) { infoStavby('Sem se po silnici nedá dojet.'); return true; }
          if (delkaCesty(lapStavby()) + delkaCesty(c) > MAX_L) { infoStavby(`Trať by byla delší než ${MAX_L / 1000} km.`); return true; }
          S.useky.push(c);
        }
        S.body.push(p); prepocitejOkruh();
        return true;
      }, { priority: 10 });
      E_('zpet').addEventListener('click', () => { S.body.pop(); S.useky.length = Math.max(0, S.body.length - 1); prepocitejOkruh(); });
      E_('okruh').addEventListener('change', prepocitejOkruh);
      E_('kola').addEventListener('change', () => infoStavby());
      E_('zrusit').addEventListener('click', () => { konecStavby(); popisTrati(); tabulka(); dlg.showModal(); });
      E_('hotovo').addEventListener('click', () => {
        const lap = lapStavby(), l = delkaCesty(lap);
        if (S.body.length < 2 || l < MIN_L) { infoStavby(`Trať musí mít aspoň ${MIN_L} m.`); return; }
        const body = S.body.map((p) => api.worldToLatLon(p.x, p.y));
        konecStavby(); vlastniTrat(body, +E_('kola').value, E_('okruh').checked, lap);
        $('vysl').hidden = true; $('jmenoBox').hidden = true; tabulka(); dlg.showModal();
      });
      function vlastniTrat(body, kola, okruh, lap) {
        const kod = kodTrat(body, kola, okruh);
        nastavTrat({ nazev: 'Vlastní trať', popis: '', kola, okruh, body, kod, tabulka: `v-${hashStr(kod)}`, lap });
        popisTrati();
      }
      async function nactiZOdkazu(kod) {                             // ?rz=… : body z odkazu, cesty po silnicích se spočítají znovu
        const t = dekodTrat(kod); if (!t) return false;
        const W_ = t.body.map(([la, lo]) => api.latLonToWorld(la, lo));
        await Promise.all(W_.map(([x, y]) => nactiOkoli(x, y)));
        const P_ = W_.map(([x, y]) => prichyt(x, y, 60)); if (P_.some((p) => !p)) return false;
        const lap = [];
        for (let i = 1; i < P_.length; i++) { const c = cesta(P_[i - 1], P_[i]); if (!c) return false; lap.push(...(lap.length ? c.slice(1) : c)); }
        if (t.okruh) { const c = cesta(P_[P_.length - 1], P_[0]); if (c) lap.push(...c.slice(1)); }
        vlastniTrat(t.body, t.kola, t.okruh, lap); return true;
      }
      $('sdilet').addEventListener('click', async () => {
        const u = new URL(location.href); u.searchParams.set('rz', R.trat.kod);
        const s = u.toString(); let ok = false;
        try { await navigator.clipboard.writeText(s); ok = true; } catch {}
        $('sdileno').hidden = false; $('sdileno').textContent = ok ? 'Odkaz na trať je ve schránce.' : s;
      });
      $('stavet').addEventListener('click', stavet);
      $('pripravena').addEventListener('click', () => { pripravena(); popisTrati(); tabulka(); });

      // ---------- jízda ----------
      function start() {
        if (!R.trat) return;
        const p = at(1), p2 = at(12); p.hd = Math.atan2(p2.y - p.y, p2.x - p.x);   // na startu míří podle trati ~12 m dopředu
        const tr = document.getElementById('l-traffic');                            // uzavřená trať: bez aut, autobusů a vlaků
        if (!R.on && tr) { R.trafPrev = tr.checked; tr.checked = false; tr.dispatchEvent(new Event('change')); }
        Object.assign(R, { on: true, x: p.x, y: p.y, hd: p.hd, vx: 0, vy: 0, steer: 0, s: 0, t: 0, phase: 'odpocet', cd: 3.5, sp: [], next: 0, marks: [], mimo: 0, pi: 1, slip: 0 });
        if (!R.tape) {                                              // pásky a brány: obrazové souřadnice jednou, ne v každém snímku
          const I = (x, y, h) => toImg(x, y, gz(x, y) + h), w = R.w;
          R.tape = [1, -1].map((sg) => { const o = []; for (let i = 0; i < R.lapPts; i += 2) {
            const a = w[i], b = w[Math.min(w.length - 1, i + 1)], hd = Math.atan2(b[1] - a[1], b[0] - a[0]);
            o.push(I(a[0] - Math.sin(hd) * R.HALF * sg, a[1] + Math.cos(hd) * R.HALF * sg, 0.9)); } return o; });
          R.gates = [[2, '#4ba82e', R.trat.kola > 1 || R.trat.okruh ? 'START / CÍL' : 'START'], ...(R.trat.kola > 1 || R.trat.okruh ? [] : [[R.L - 3, '#2a2c31', 'CÍL']]),
            ...R.splits.map((s, k) => [s, '#e0a020', `M${k + 1}`]).filter(([s]) => Math.abs(s % R.lapL) > 20 && Math.abs(s % R.lapL - R.lapL) > 20)].map(([s, col, txt]) => {
            const q = at(s), sd = [-Math.sin(q.hd), Math.cos(q.hd)], e = R.HALF + 1;
            return { col, txt, A: I(q.x + sd[0] * e, q.y + sd[1] * e, 0), B: I(q.x - sd[0] * e, q.y - sd[1] * e, 0), A2: I(q.x + sd[0] * e, q.y + sd[1] * e, 5), B2: I(q.x - sd[0] * e, q.y - sd[1] * e, 5) };
          });
        }
        dlg.close(); hud.hidden = false; H('nazev').textContent = R.trat.nazev; H('split').textContent = ''; H('info').textContent = 'čekej na zelenou'; svetla.hidden = false;
        if (document.activeElement) document.activeElement.blur();
        tabulka();
        const cam = api.getCam(), [ix, iy] = toImg(p.x, p.y, gz(p.x, p.y));
        api.panTo(ix, iy, cam.mpp ? cam.w * cam.mpp / 220 : undefined, false);
      }
      function mezicas(k, t) {
        const L = R.tab.filter((r) => r.s && r.s[k]);
        if (!L.length) { H('split').textContent = `M${k + 1}: ${fmt(t)} s – zatím nejrychlejší!`; return; }
        const best = Math.min(...L.map((r) => r.s[k])), pos = 1 + L.filter((r) => r.s[k] < t).length, d = t - best;
        H('split').innerHTML = `M${k + 1}: ${fmt(t)} s <span class="${d > 0 ? 'plus' : 'minus'}">${d > 0 ? '+' : '−'}${fmt(Math.abs(d))}</span> na vedoucího · průběžně ${pos}.`;
      }
      function konec(dojel) {
        R.on = false; hud.hidden = true; svetla.hidden = true; R.keys.clear();
        const tr = document.getElementById('l-traffic');
        if (R.trafPrev !== undefined && tr) { tr.checked = R.trafPrev; tr.dispatchEvent(new Event('change')); } R.trafPrev = undefined;
        const t = R.t;
        R.vysl = dojel ? { t, s: R.sp.slice(0, 3) } : null;
        let txt = 'Závod ukončen.';
        if (dojel) {
          const L = R.tab, pos = 1 + L.filter((r) => r.t < t).length, best = L.length ? Math.min(...L.map((r) => r.t)) : null;
          txt = `Cíl! Čas ${fmt(t)} s${best !== null ? ` (${t <= best ? 'nejrychlejší!' : '+' + fmt(t - best) + ' na vedoucího'})` : ''}, průběžně ${pos}. místo.` + (R.mimo > 3 ? ` Mimo trať ${Math.round(R.mimo)} s.` : '');
        }
        popisTrati(); $('vysl').textContent = txt; $('vysl').hidden = false; $('jmenoBox').hidden = !dojel; kresli(R.tab); dlg.showModal();
      }
      function krok(dt) {
        const K = R.keys;
        if (R.phase === 'odpocet') {
          R.cd -= dt; svetla.textContent = R.cd > 2.5 ? '● ● ●' : R.cd > 1.5 ? '● ●' : R.cd > 0.5 ? '●' : 'START!';
          svetla.style.color = R.cd > 0.5 ? '#ff3b2a' : '#4ae05a';
          if (R.cd <= 0) { R.phase = 'jizda'; svetla.hidden = true; H('info').textContent = 'jeď!'; }
        } else R.t += dt;
        const fwd = [Math.cos(R.hd), Math.sin(R.hd)], side = [-fwd[1], fwd[0]];
        let vf = R.vx * fwd[0] + R.vy * fwd[1], vs = R.vx * side[0] + R.vy * side[1];
        const go = R.phase === 'jizda', pr = proj(R.x, R.y, R.s), off = pr.d > R.HALF + 1.2, hb = K.has(' ');
        const grip = (off ? 7 : 24) * (hb ? 0.35 : 1);
        // motor a brzdy (Rally2: ~290 k, 0–100 km/h asi za 4 s), odpor vzduchu a valení, mimo trať tráva/sláma
        let a = 0;
        if (go && K.has('ArrowUp')) a += 9.5 * Math.max(0.15, 1 - vf / 50);
        if (K.has('ArrowDown')) a -= vf > 0.5 ? 13 : (go ? 4 : 0);
        if (hb && vf > 0) a -= 4;
        a -= 0.0012 * vf * Math.abs(vf) + (off ? 3.5 : 0.4) * Math.sign(vf);
        vf += a * dt; if (!K.has('ArrowDown') && !K.has('ArrowUp') && Math.abs(vf) < 0.3) vf = 0;
        vf = Math.max(-6, Math.min(52, vf));
        // řízení: rejd klesá s rychlostí, natáčení vozu podle rozvoru 2,55 m, ruční brzda zatočí záď
        const want = (K.has('ArrowLeft') ? 1 : 0) - (K.has('ArrowRight') ? 1 : 0);
        R.steer += (want - R.steer) * Math.min(1, dt * 8);
        let yaw = vf / 2.55 * Math.tan(R.steer * 0.55 / (1 + Math.abs(vf) / 22));
        if (hb) yaw *= 1.45;
        R.hd += yaw * dt;
        // přilnavost: boční rychlost se tlumí nejvýš o grip × dt (jinak smyk), při smyku zůstávají stopy pneumatik
        vs -= Math.sign(vs) * Math.min(Math.abs(vs), grip * dt);
        const f2 = [Math.cos(R.hd), Math.sin(R.hd)], s2 = [-f2[1], f2[0]];
        R.vx = f2[0] * vf + s2[0] * vs; R.vy = f2[1] * vf + s2[1] * vs; R.slip = Math.abs(vs);
        let nx = R.x + R.vx * dt, ny = R.y + R.vy * dt;
        const np0 = proj(nx, ny, R.s), wall = np0.d > R.HALF + 6;               // svodidla / domy kolem trati
        if (wall) { R.vx *= -0.25; R.vy *= -0.25; if (Math.hypot(R.vx, R.vy) > 1) H('info').textContent = 'au! náraz'; nx = R.x; ny = R.y; }
        R.x = nx; R.y = ny;
        if (R.slip > 3 || (K.has('ArrowDown') && vf > 8)) { R.marks.push(toImg(R.x, R.y, gz(R.x, R.y) + 0.05)); if (R.marks.length > 600) R.marks.shift(); }
        if (off && go) { R.mimo += dt; if (vf > 5) H('info').textContent = 'mimo trať!'; } else if (go && !wall) H('info').textContent = R.slip > 4 ? 'smyk!' : 'jeď!';
        const np = wall ? pr : np0; if (np.d < R.HALF + 7 && np.s > R.s) R.s = np.s;
        if (go && R.next < 3 && R.s >= R.splits[R.next]) { R.sp.push(R.t); mezicas(R.next, R.t); R.next++; }
        if (go && R.next === 3 && R.s >= R.L - 6) return konec(true);
        H('cas').textContent = fmt(R.t); H('rych').textContent = Math.round(Math.abs(vf) * 3.6);
        H('kolo').textContent = R.trat.kola > 1 ? `kolo ${Math.min(R.trat.kola, 1 + Math.floor(R.s / R.lapL))}/${R.trat.kola} · ` : '';
        const [ix, iy] = toImg(R.x + R.vx * 0.6, R.y + R.vy * 0.6, gz(R.x, R.y));
        api.panTo(ix, iy, undefined, false);
      }
      function kresli3d(ctx, sx, ox, oy, t) {
        const S_ = (p) => [ox + p[0] * sx, oy + p[1] * sx], Pt = (x, y, h) => S_(toImg(x, y, gz(x, y) + h));
        ctx.lineWidth = Math.max(1, sx * 1.2);
        for (const tp of R.tape) {
          ctx.beginPath(); tp.forEach((p, k) => (k ? ctx.lineTo(...S_(p)) : ctx.moveTo(...S_(p))));
          ctx.setLineDash([6 * sx, 6 * sx]); ctx.strokeStyle = 'rgba(230,40,30,0.85)'; ctx.stroke();
          ctx.lineDashOffset = 6 * sx; ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.stroke(); ctx.setLineDash([]); ctx.lineDashOffset = 0;
        }
        for (const g of R.gates) {
          const A = S_(g.A), B = S_(g.B), A2 = S_(g.A2), B2 = S_(g.B2);
          ctx.strokeStyle = '#2a2c31'; ctx.lineWidth = Math.max(2, sx * 3); ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...A2); ctx.lineTo(...B2); ctx.lineTo(...B); ctx.stroke();
          ctx.fillStyle = g.col; ctx.beginPath(); ctx.moveTo(...A2); ctx.lineTo(...B2); ctx.lineTo(B2[0], B2[1] + 8 * sx); ctx.lineTo(A2[0], A2[1] + 8 * sx); ctx.fill();
          ctx.fillStyle = '#fff'; ctx.font = `700 ${Math.max(9, 7 * sx)}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText(g.txt, (A2[0] + B2[0]) / 2, (A2[1] + B2[1]) / 2 + 6 * sx);
        }
        ctx.fillStyle = 'rgba(30,30,32,0.35)';
        for (const p of R.marks) ctx.fillRect(ox + p[0] * sx - sx, oy + p[1] * sx - sx * 0.5, sx * 2, sx);
        // vůz Rally2: bílá karoserie se zeleným pásem, kabina, spoiler, světla; o 60 % větší než skutečný (v úzkých ulicích by zanikl)
        const fx = Math.cos(R.hd), fy = Math.sin(R.hd), qx = -fy, qy = fx, K_ = 1.6;
        const P = (s, tt, h) => Pt(R.x + fx * s * K_ + qx * tt * K_, R.y + fy * s * K_ + qy * tt * K_, h * K_);
        const poly = (ps, col) => { ctx.fillStyle = col; ctx.beginPath(); ps.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.closePath(); ctx.fill(); };
        const box = (s0, s1, t0, t1, h0, h1, rgb) => {
          for (const [a, b, c, d, nx, ny] of [[s1, t0, s1, t1, fx, fy], [s0, t1, s0, t0, -fx, -fy], [s0, t0, s1, t0, -qx, -qy], [s1, t1, s0, t1, qx, qy]])
            if (nx + ny < 0) poly([P(a, b, h0), P(c, d, h0), P(c, d, h1), P(a, b, h1)], lit(rgb, nx * SUNV[0] + ny * SUNV[1]));
          poly([P(s0, t0, h1), P(s1, t0, h1), P(s1, t1, h1), P(s0, t1, h1)], lit(rgb, SUNV[2]));
        };
        if (R.slip > 3) { ctx.fillStyle = 'rgba(235,235,235,0.5)'; for (let k = 0; k < 6; k++) { const [X, Y] = P(-2.3 - rnd(k + Math.floor(t * 15)) * 2, (rnd(k * 3 + Math.floor(t * 15)) - 0.5) * 2.5, 0.4); ctx.beginPath(); ctx.arc(X, Y, sx * (1.2 + rnd(k)), 0, 7); ctx.fill(); } }
        box(-2.05, 2.05, -0.9, 0.9, 0.15, 0.85, [236, 238, 236]);
        box(-2.05, 2.05, -0.92, 0.92, 0.15, 0.4, [75, 168, 46]);
        box(-0.9, 0.9, -0.78, 0.78, 0.85, 1.35, [40, 44, 50]);
        box(-0.85, 0.85, -0.8, 0.8, 1.35, 1.42, [236, 238, 236]);
        box(1.2, 2.05, -0.9, 0.9, 0.85, 0.9, [75, 168, 46]);
        box(-2.15, -1.85, -0.85, 0.85, 1.3, 1.42, [20, 22, 26]);
        ctx.fillStyle = '#fff6c8';
        for (const l of [P(2.06, 0.6, 0.6), P(2.06, -0.6, 0.6)]) ctx.fillRect(l[0] - sx * 0.6, l[1] - sx * 0.4, sx * 1.2, sx * 0.8);
        const [X, Y] = Pt(R.x, R.y, 6), k = Math.max(5, 4 * sx);       // žlutá šipka nad autem (vidět i za domy)
        ctx.fillStyle = 'rgba(255,214,40,0.9)'; ctx.strokeStyle = '#1d1f24'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(X - k, Y - k * 1.6); ctx.lineTo(X + k, Y - k * 1.6); ctx.lineTo(X, Y); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      function kresliStavbu(ctx, sx, ox, oy) {                         // náhled rozestavěné trati: oranžová čára, body, start
        const Pt = (x, y) => { const p = toImg(x, y, gz(x, y) + 0.5); return [ox + p[0] * sx, oy + p[1] * sx]; };
        const lap = lapStavby();
        if (lap.length > 1) {
          ctx.lineCap = 'round'; ctx.lineJoin = 'round';
          for (const [c, wd] of [['rgba(29,31,36,0.7)', 9], ['#f08a24', 5]]) {
            ctx.strokeStyle = c; ctx.lineWidth = Math.max(wd * 0.5, sx * wd * 0.6); ctx.beginPath();
            lap.forEach(([x, y], i) => { const [X, Y] = Pt(x, y); if (i) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); }); ctx.stroke();
          }
        }
        S.body.forEach((p, i) => {
          const [X, Y] = Pt(p.x, p.y), r = Math.max(4, sx * 3);
          ctx.fillStyle = i ? '#f2c230' : '#4ba82e'; ctx.strokeStyle = '#1d1f24'; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.fill(); ctx.stroke();
        });
      }

      // ---------- události ----------
      btn.addEventListener('click', () => { if (S.on) return; $('vysl').hidden = true; $('jmenoBox').hidden = true; popisTrati(); tabulka(); dlg.showModal(); });
      $('zavrit').addEventListener('click', () => dlg.close());
      $('start').addEventListener('click', start);
      $('uloz').addEventListener('click', async () => {
        const r = R.vysl; if (!r) return;
        const n = ($('jmeno').value || 'Anonym').trim().slice(0, 20);
        if (profanity && !profanity.isValid(n)) { $('vysl').textContent = 'Zvol prosím jiné jméno.'; return; }
        R.vysl = null; $('jmenoBox').hidden = true;
        const zaznam = { n, t: Math.round(r.t * 100) / 100, s: r.s.map((v) => Math.round(v * 100) / 100) };
        if (client) {
          const q = await client.call('submit', { tabulka: R.trat.tabulka, delka: Math.round(R.L), nickname: n, time: zaznam.t, splits: zaznam.s });
          if (q.ok && Array.isArray(q.data?.entries)) { R.online = true; return kresli(q.data.entries); }
          $('vysl').textContent = q.message || 'Společnou tabulku se nepodařilo uložit, čas zůstává v tomto prohlížeči.';
        }
        const L = local(); L.push(zaznam); L.sort((a, b) => a.t - b.t);
        try { localStorage.setItem(R.LS, JSON.stringify(L.slice(0, 30))); } catch {}
        R.online = false; kresli(L);
      });
      const RK = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ']), MAP = { a: 'ArrowLeft', d: 'ArrowRight', w: 'ArrowUp', s: 'ArrowDown' };
      const kd = (e) => {
        if (S.on && e.key === 'Escape') { e.preventDefault(); konecStavby(); return; }
        if (S.on && (e.key === 'Backspace' || (e.key === 'z' && (e.ctrlKey || e.metaKey)))) { e.preventDefault(); E_('zpet').click(); return; }
        if (!R.on) return;
        const k = MAP[e.key.toLowerCase()] || e.key;
        if (e.key === 'Escape') { e.preventDefault(); return konec(false); }
        if (e.key === 'r' || e.key === 'R') { e.preventDefault(); return start(); }
        if (RK.has(k)) { R.keys.add(k); e.preventDefault(); e.stopPropagation(); }   // šipky nesmí posouvat mapu
      };
      const ku = (e) => { const k = MAP[e.key.toLowerCase()] || e.key; if (R.on && RK.has(k)) { e.preventDefault(); e.stopPropagation(); } R.keys.delete(k); };
      addEventListener('keydown', kd, true); addEventListener('keyup', ku, true);
      const unFrame = api.onFrame((ctx, view, t) => {
        if (S.on) return kresliStavbu(ctx, view.sx, view.ox, view.oy);
        if (!R.on) return;
        krok(Math.min(view.dt || 0.016, 0.05));
        if (R.on) kresli3d(ctx, view.sx, view.ox, view.oy, t);
      }, { layer: 'world', priority: 5 });

      // připravená trať z assets/doplnky/rz.json (pokud je), trať z odkazu ?rz=… má přednost
      function pripravena() {
        if (!D.trat) return;
        const t = D.trat;
        nastavTrat({ ...t, lap: t.trasa.map(([la, lo]) => api.latLonToWorld(la, lo)) });
      }
      pripravena();
      const zOdkazu = new URLSearchParams(location.search).get('rz');
      if (zOdkazu) nactiZOdkazu(zOdkazu).then((ok) => { if (ok) { popisTrati(); tabulka(); dlg.showModal(); } });

      cleanup = [() => removeEventListener('keydown', kd, true), () => removeEventListener('keyup', ku, true), unFrame, unClick,
        () => { btn.remove(); dlg.remove(); hud.remove(); svetla.remove(); ed.remove(); }];
    },
    onDestroy() { for (const f of cleanup) try { f(); } catch {} cleanup = []; },
  });
})();
