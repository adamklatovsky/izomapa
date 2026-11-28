# Doplněk `vlacek`: výletní vláček

Silniční turistický vláček (lokomotiva a vagónky) jezdí po silnicích mezi zastávkami podle jízdního řádu.
Jde o **ilustrační provoz, ne živou polohu**: jedna otočka jízdního řádu se opakuje celý den podle hodin v Praze.
Všichni návštěvníci tak vidí totéž a v provozní době poloha zhruba odpovídá jízdnímu řádu.

## Zapnutí

Zkopíruj `priklady/vlacek.sample.json` do `assets/doplnky/vlacek.json` a uprav ho.
Pak spusť `overlay.py` a `build_html.py`. Render není potřeba.

Doplněk potřebuje silnice z Overture (`data_all/segment.parquet` nebo `data/segment.parquet`). Bez nich se vypne.

## Data (`assets/doplnky/vlacek.json`)

| klíč | význam |
|---|---|
| `nazev`, `popis`, `url` | Ukáže se po kliknutí na vláček. `url` je jen web provozovatele, telefon ani e-mail na mapu nepatří. |
| `zastavky` | `[{"nazev", "lat", "lon"}]`. Bod dej na silnici a ověř ho na ortofotu ČÚZK. |
| `smery` | `[{"nazev", "zastavky": [indexy], "jizdy": [["10:00", "10:05", …], …]}]`, jeden čas na každou zastávku směru. |
| `perioda_min` | Volitelné. Po kolika minutách se otočka opakuje. Výchozí je rozdíl prvních dvou jízd prvního směru. |
| `rychlost`, `rychlost_max` | km/h. Rychlost se dopočítá z jízdního řádu, ale drží se mezi 0,7 × `rychlost` a `rychlost_max`. |
| `stani_s` | Jak dlouho stojí na mezilehlé zastávce. |
| `obdobi` | Roční období mapy, kdy jezdí. Výchozí je `["summer"]`. |
| `vagony` | Počet vagónků (0–6). |
| `barvy` | `lokomotiva`, `kabina`, `vagony`, `strecha`, `ramy` jako `#rrggbb`. |
| `enabled` | `false` doplněk vypne. |

Všechny směry se spojí do jednoho okruhu. Když směr končí tam, kde další začíná, je společná konečná jen jednou.
Okruh se nakonec vrátí na začátek.

Trasu mezi zastávkami dopočítá `road_route.Graph`, stejně jako u trasy autobusů bez `shapes.txt`.
Když je zastávka daleko od silnice, `overlay.py` vypíše varování o rovném úseku. Zastávku pak posuň.
Když trasa vede přes půdorys budovy (zmenšený o 1 m), vypíše `overlay.py` varování taky.
Pro jízdu tam a zpět do slepé ulice (přístaviště, hotel) dej zastávku do obou směrů.

## Chování v prohlížeči

- Jezdí jen ve zvoleném období, ve dne, a ne v dešti ani ve sněhu. Mimo jízdy stojí na konečné.
- Kreslí se jako ostatní vozidla, tedy jen zblízka (`sx > 0.12`). Lokomotiva a vagónky jedou po trase s odstupem
  a v zatáčkách se lomí. Jedou kousek vpravo od osy silnice.
- Každý vůz zvlášť zakryjí domy a stromy před ním (`Izomapa.drawOccluded`).
- Po kliknutí se ukáže název, popis a odkaz na provozovatele.

## Doksy – Staré Splavy (data v ukázce)

- Provozovatel: https://www.vlacekdoksy.cz/ (oranžová mašinka, tři vagónky, 36 míst, za silného deště nejezdí).
- Jízdní řád léta 2024 (obrázky „SMER1/2“), použitý i v sezóně 2025:
  [archiv webu provozovatele z 19. 7. 2025](http://web.archive.org/web/20250719083427/https://www.vlacekdoksy.cz/)
  a https://www.machovojezero-ubytovani.info/zabava/relaxace/vyletni-vlacek-u-machova-jezera.
- Trasa: Doksy, nádvoří zámku → náměstí → Staré Splavy, autobusové nádraží
  ([Deník, 3. 7. 2021](https://ceskolipsky.denik.cz/zpravy_region/vyletni-vlacek-se-vraci-bude-vozit-turisty-u-machova-jezera-20210703.html)).
- Barvy vagónků jsou odhad, ověřenou fotku současné soupravy se najít nepodařilo.
- Polohy zastávek „u zmrzliny“ a „odbočka kemp“ jsou odhad podle jízdního řádu a ortofota.
