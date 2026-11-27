# Server společné tabulky doplňku „Rychlostní zkouška“

Volitelný. Bez `server_url` vede každý prohlížeč tabulku sám (localStorage). Klient volá server přes knihovnu
`knihovny/server_client` (JSON `POST`, odpověď `{ ok, … }`, chyba `{ ok: false, error, message }`).

Každá trať má vlastní tabulku `tabulka` (`[a-z0-9-]{1,40}`): připravená trať název z `assets/doplnky/rz.json`,
vlastní trať `v-<hash bodů trati>`.

- `{ action: "leaderboard", tabulka }` → `{ ok: true, entries: [{ n, t, s: [m1, m2, m3], d }] }` (nejlepších 30, seřazeno podle `t`)
- `{ action: "submit", tabulka, delka, nickname, time, splits: [m1, m2, m3] }` → `{ ok: true, entries, rank }`

Server má odmítnout nevěrohodné záznamy: mezičasy rostoucí a menší než cílový čas, průměrná rychlost nejvýš 200 km/h
(`time ≥ delka / 55`), čas do hodiny, jméno do 20 znaků bez `<`, `>` a řídicích znaků. Hra běží v prohlížeči, takže to
není ochrana proti cílenému podvodu, jen proti chybám a hrubým nesmyslům.

Vzorová implementace pro Cloudflare Pages Functions + KV: `cloudflare/rz.js`.
