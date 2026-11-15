# Vzorový doplněk (`vzor_doplnku`)

Minimální referenční šablona doplňku pro systém doplňků v Izomapě. Demonstruje:

- `manifest.json`: definice ID, skriptů, stylů a výchozího režimu (`client` / `server`).
- `overlay_hook.py`: build-time projekce bodů, polygonů i poloměru (`radius_px = round(radius / mpp, 1)`), oddělení citlivých souřadnic a textů `answer` do `site_server/server_data/<id>.targets.json` v režimu `server`.
- `vzor.js` + `vzor.css`: komunikace s jádrem přes `window.Izomapa` a sjednocený `Verifier` adaptér (`client` vs. `server`).
- `server/SPEC.md`, `server/python/vzor_server.py`, `server/php/vzor_server.php`: jazykově nezávislý REST JSON protokol s bezstavovými HMAC tickety a 12znakovým GDPR `audit_hash`.
