# Vyhlídkový let (`vyhlidkovy_let`)

Hra: hráč pilotuje dvouplošník An-2 „Andula“. Vzlétne z dráhy místního letiště, obletí co nejvíc míst ze seznamu Místa
(`mista.json`) a přistane zpátky. Nad dalším cílem je žlutý kroužek a šipka u letadla ukazuje směr k němu. Ve výšce
aspoň 300 m může vysadit tři skupiny parašutistů. Náraz do domu (budova vyšší než letadlo) nebo přistání mimo dráhu
body půlí. Výsledky se ukládají do „Hangáru slávy“ v prohlížeči.

## Zapnutí

- Města s doplňkem `letiste`: stačí `{"vyhlidkovy_let": true}` v `assets/doplnky.json`. Hra převezme aktivní dráhu
  z `assets/doplnky/letiste.json`.
- Vlastní dráha nebo název: `assets/doplnky/vyhlidkovy_let.json` (doplněk se tím zapne sám):

```json
{
  "nazev": "Andula nad Boleslaví",
  "letiste": "letiště Mladá Boleslav",
  "draha": { "a": [50.4000228, 14.9002772], "b": [50.3952702, 14.8931922], "sirka": 24 }
}
```

`a` je začátek rozjezdu, `b` konec dráhy. Bez dráhy začíná let ve 200 m nad středem pohledu a přistávat se nedá.
Cíle jsou místa z `mista.json` do 9 km od startu (nejvýš 60). Bez míst se doplněk nezapne.

Ovládání: ← → zatáčení, ↑ ↓ stoupání a klesání, W / S plyn, mezerník výsadek, Esc konec. Na dotykovém displeji jsou
tlačítka dole.

## Jak to funguje

- `overlay_hook.py` předá dráhu, místa a seznam čtverců mapy.
- `vyhlidkovy_let.js` počítá let v `onFrame` (vrstva `sky`, tedy nad budovami) a posouvá pohled přes `panTo`. Budovy
  pro test nárazu (obrys `hull` a výška `h`) si načítá z `overlay/c<i>_<j>.json` jen kolem letadla. Sprite An-2 je
  stejný jako v doplňku `letiste`.
