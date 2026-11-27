# Rychlostní zkouška (`rz`)

Hra na mapě: rallyové auto (Rally2) na trati rychlostní zkoušky. Trať si hráč **postaví kdekoli na mapě**: kliká body
a mezi nimi se trať sama vede po silnicích. Nastaví počet kol, případně okruh, a jede. Fyzika počítá se smykem a ruční
brzdou. Mimo trať auto zpomalí, domy a svodidla podél trati ho zastaví. Start má odpočet, mezičasy jsou ve ¼, ½ a ¾
zkoušky a ukazují ztrátu na vedoucího a průběžné pořadí. Hotovou trať jde sdílet odkazem (`?rz=…`, body jsou v adrese)
a každá trať má vlastní tabulku výsledků.

Volitelně lze přidat i **připravenou trať**, která se nabídne jako výchozí, třeba skutečnou městskou RZ místní rallye.
Ukázka v `priklady/rz.json` je městská RZ Bohemia Rally v Mladé Boleslavi (2 kola, 4 km).

## Zapnutí

- Jen stavba vlastních tratí: v `assets/doplnky.json` přidejte `{"rz": true}`.
- S připravenou tratí: vytvořte `assets/doplnky/rz.json` (doplněk se tím zapne sám) podle `priklady/rz.json`:

```json
{
  "nazev": "RZ Městská",
  "popis": "Krátký popis trati (zobrazí se v dialogu).",
  "zdroj": "Odkud je trasa (např. mapka pořadatele) – zobrazí se drobně.",
  "kola": 2,
  "tabulka": "rz-mestska-2025",
  "auto": "Škoda Fabia RS Rally2",
  "trasa": [[50.412031, 14.904284], [50.412071, 14.904295], "…"]
}
```

`trasa` je lomená čára [lat, lon] po silnicích, jedno kolo (200 m – 30 km). Stačí body v zatáčkách, hra si ji zahustí.
Dá se nakreslit třeba v geojson.io po ulicích z OpenStreetMap. Jednodušší je postavit trať přímo ve hře, zkopírovat
odkaz a body z něj převést. `tabulka` je klíč výsledků (`a–z`, `0–9`, `-`); při změně trasy zvolte nový, aby se
nemíchaly časy ze staré trati.

Pak `python overlay.py` (nebo `./postav.sh render`).

## Společná tabulka (volitelné)

Bez serveru si každý prohlížeč vede tabulku sám (localStorage). Pro společnou tabulku nastavte v `assets/doplnky.json`:

```json
{ "rz": { "server_url": "/api/rz" } }
```

Protokol je v `server/SPEC.md`. Vzorová implementace pro Cloudflare Pages Functions + KV je v
`server/cloudflare/rz.js`. Zkopírujte ji do `functions/api/rz.js` a navažte KV jako `RZ`. Jména hráčů filtruje
knihovna `profanity` (vypnete ji pomocí `"profanity_filter": false`).

## Jak to funguje

- `overlay_hook.py`: předá prohlížeči seznam čtverců mapy a velikost čtverce, aby si hra uměla načíst silnice
  z `overlay/c<i>_<j>.json`, a k tomu připravenou trať.
- `rz.js`: stavba trati (přichycení kliknutí k nejbližší silnici do 40 m, nejkratší cesta Dijkstrou po síti z dílků
  overlay, které se načítají jen kolem kliknutí), jízda (krok fyziky v `onFrame`, posun pohledu přes `panTo`), kreslení
  pásek, bran, stop pneumatik a vozu do vrstvy `world` a tabulka výsledků.
- Silnice bez dálnic, rychlostních silnic a pěších a polních cest.
- Po dobu jízdy se vypne vrstva dopravy (`#l-traffic`), aby byla trať uzavřená. Po skončení se vrátí.

Ovládání: ↑ plyn, ↓ brzda, ← → řízení, mezerník ruční brzda, R znovu, Esc konec (WASD funguje také). Na dotykovém
displeji jsou tlačítka dole. Při stavbě trati vrací Backspace poslední bod a Esc stavbu zruší.
