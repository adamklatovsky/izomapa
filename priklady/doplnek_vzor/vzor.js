(() => {
  const PLUGIN_ID = 'vzor_doplnku';
  const Izomapa = window.Izomapa;
  if (!Izomapa) return;

  function pointInPolygon(x, y, pts) {
    let inside = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const [xi, yi] = pts[i], [xj, yj] = pts[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function matchQuestion(q, x, y) {
    const r = q.radius_px || 175;
    if (q.xy && Math.hypot(x - q.xy[0], y - q.xy[1]) <= r) return { x: q.xy[0], y: q.xy[1] };
    for (const t of q.targets || []) {
      if (t.type === 'point' && Math.hypot(x - t.xy[0], y - t.xy[1]) <= (t.radius_px || r)) return { x: t.xy[0], y: t.xy[1] };
      if (t.type === 'polygon' && pointInPolygon(x, y, t.points)) return { x, y };
    }
    return null;
  }

  function createVerifier(cfg, data) {
    if (cfg.mode === 'server' && cfg.server_url) {
      const post = (body) => fetch(cfg.server_url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      }).then((r) => r.json());
      return {
        start: (levelId, difficulty, season) => post({ action: 'start', levelId, difficulty, season }),
        verify: (x, y, ticket) => post({ action: 'verify', x, y, ticket }),
        finish: (nickname, tickets) => post({ action: 'finish', nickname, tickets }),
        leaderboard: () => post({ action: 'leaderboard' })
      };
    }
    let activeLevel = null, order = [], step = 0, startedAt = 0;
    return {
      async start(levelId) {
        activeLevel = (data.levels || []).find((l) => String(l.lvl) === String(levelId));
        order = (activeLevel?.questions || []).map((_, i) => i);
        step = 0; startedAt = Date.now();
        return { order, ticket: 'client' };
      },
      async verify(x, y) {
        const q = activeLevel?.questions[order[step]];
        const hitPt = q ? matchQuestion(q, x, y) : null;
        if (!hitPt) return { hit: false, completed: false, ticket: 'client' };
        step++;
        const completed = step >= order.length;
        return { hit: true, completed, elapsedMs: Date.now() - startedAt, targetHint: hitPt, answer: q.answer || q.text, ticket: 'client' };
      },
      async finish(nickname) {
        return { saved: true, totalTimeMs: Date.now() - startedAt, rank: 1, certificateId: 'CLIENT', nickname };
      },
      async leaderboard() { return { entries: [] }; }
    };
  }

  Izomapa.registerPlugin(PLUGIN_ID, {
    onInit(api) {
      const data = api.getPluginData(PLUGIN_ID);
      const cfg = api.getPluginConfig(PLUGIN_ID);
      if (!data || !data.levels?.length) return;

      const verifier = createVerifier(cfg, data);
      const slot = api.getUiSlot('sidebar-tabs');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'vzor-tab';
      btn.textContent = '★';
      btn.title = data.title || PLUGIN_ID;
      slot?.appendChild(btn);

      const panel = document.createElement('aside');
      panel.className = 'vzor-panel';
      panel.hidden = true;
      panel.innerHTML = `<strong data-role="title"></strong><p data-role="status">Připraveno</p><button type="button" class="px-btn" data-role="start">Start</button>`;
      panel.querySelector('[data-role="title"]').textContent = data.title || PLUGIN_ID;
      document.body.appendChild(panel);

      let ticket = null, savedEnv = null, unsub = null;
      btn.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        if (!panel.hidden) {
          savedEnv = api.getEnvironment();
          api.setPinsVisible(false);
          api.setClickCapture(true);
          api.setCursor('crosshair');
          unsub = api.onMapClick(async (e) => {
            if (!ticket) return true;
            const res = await verifier.verify(e.x, e.y, ticket);
            ticket = res.ticket || ticket;
            panel.querySelector('[data-role="status"]').textContent = res.hit ? `Zásah: ${res.answer || 'OK'}` : 'Vedle';
            return true;
          }, { priority: 10 });
        } else {
          if (unsub) { unsub(); unsub = null; }
          api.setClickCapture(false);
          api.setCursor('');
          api.setPinsVisible(true);
          if (savedEnv) api.setEnvironment(savedEnv);
        }
      });

      panel.querySelector('[data-role="start"]').addEventListener('click', async () => {
        const lvl = data.levels[0];
        const res = await verifier.start(lvl.lvl, 'easy', api.getEnvironment().season);
        ticket = res.ticket;
        if (lvl.camera) api.panTo(lvl.camera.x, lvl.camera.y, lvl.camera.zoom);
        panel.querySelector('[data-role="status"]').textContent = 'Hledání spuštěno…';
      });
    }
  });
})();
