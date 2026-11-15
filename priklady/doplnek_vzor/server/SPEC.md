# Specifikace Server-Side protokolu pro doplňky Izomapy

Tento dokument definuje jazykově nezávislý JSON REST kontrakt mezi klientským doplňkem v prohlížeči a backendem (PHP, Python, Node.js, Go, Rust atd.).

## 1. Přenositelný bezstavový HMAC ticket

Server neudržuje session v paměti. Veškerý stav rozehrané úrovně nese klient v podepsaném řetězci:

```text
ticket = base64url(JSON_payload) + "." + hex(HMAC_SHA256(base64url_payload, SECRET_KEY))
```

(`base64url` bez koncových znaků `=`).

### Obsah `JSON_payload`

```json
{
  "lvl": "1",
  "diff": "easy",
  "season": "summer",
  "ord": [2, 0, 3, 1],
  "step": 1,
  "miss": 0,
  "t0": 1763200000120,
  "tl": 1763200005400,
  "done": false,
  "el": 0
}
```

- `lvl`: identifikátor úrovně
- `diff`, `season`: obtížnost a roční období uložené při `start` (nelze podvrhnout při `finish`)
- `ord`: serverem zamíchané pořadí indexů otázek
- `step`: index aktuálně hledané otázky v `ord`
- `miss`: počet chybných kliknutí
- `t0`: serverový čas startu v milisekundách
- `tl`: serverový čas posledního kliku v milisekundách (rate-limit `>= 300 ms`)
- `done`: zda je úroveň dokončena
- `el`: výsledný serverový čas úrovně v milisekundách

## 2. Akce API (`POST` s JSON tělem)

### `start`
Vstup:
```json
{ "action": "start", "levelId": "1", "difficulty": "easy", "season": "summer" }
```
Výstup:
```json
{ "order": [1, 0], "questionIds": ["oblast_1", "bod_1"], "ticket": "..." }
```

### `verify`
Vstup:
```json
{ "action": "verify", "x": 1420.5, "y": 890.2, "ticket": "..." }
```
Výstup při zásahu (`hit: true`):
```json
{
  "hit": true,
  "completed": false,
  "elapsedMs": 12450,
  "targetHint": { "x": 1415, "y": 885 },
  "answer": "Název nalezeného místa",
  "ticket": "..."
}
```
Výstup při minutí (`hit: false` – **nesmí** obsahovat `targetHint` ani `answer`):
```json
{ "hit": false, "completed": false, "ticket": "..." }
```

### `finish`
Vstup:
```json
{ "action": "finish", "nickname": "Petr", "tickets": ["t_lvl1", "t_lvl2"] }
```
Výstup:
```json
{ "saved": true, "totalTimeMs": 45200, "rank": 3, "certificateId": "A9F3C1" }
```

### `leaderboard`
Vstup:
```json
{ "action": "leaderboard" }
```
Výstup:
```json
{
  "entries": [
    { "nickname": "Petr", "totalTimeMs": 45200, "difficulty": "easy", "season": "summer", "certificateId": "A9F3C1", "createdAt": "2026-11-15 10:00:00" }
  ]
}
```

## 3. GDPR-safe anonymizovaný otisk (`audit_hash`)

Backend nikdy neukládá surovou IP adresu. Pro anti-spam a audit se počítá týdenně rotovaný 12znakový HMAC otisk:

```text
audit_hash = substr(hex(HMAC_SHA256(client_ip + "|" + YYYY-WW, SECRET_KEY)), 0, 12)
```
