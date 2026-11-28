// dashboard památek: poškozený rozhodnuti.json se nepřepíše, běžný zápis projde, Host/Origin kontroly platí
import assert from 'node:assert/strict';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import http from 'node:http'; import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
// server bere kořen ze svého umístění, proto kopie do dočasného adresáře (uživatelova rozhodnutí se nedotkne)
const T = fs.mkdtempSync(path.join(os.tmpdir(), 'izo-pam-'));
fs.mkdirSync(path.join(T, 'nastroje'));
fs.copyFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../nastroje/pamatky_server.mjs'), path.join(T, 'nastroje/pamatky_server.mjs'));
const RJ = path.join(T, 'podklady-soukrome/pamatky/rozhodnuti.json');
const PORT = 20000 + Math.floor(Math.random() * 20000);
const srv = spawn(process.execPath, [path.join(T, 'nastroje/pamatky_server.mjs')], { env: { ...process.env, PORT: String(PORT) }, stdio: ['ignore', 'pipe', 'inherit'] });
await new Promise((ok, ko) => { srv.stdout.once('data', ok); srv.once('exit', (c) => ko(new Error(`server skončil (${c}), port ${PORT} obsazený?`))); });
const H = `127.0.0.1:${PORT}`;
const post = (body, h = {}) => fetch(`http://${H}/rozhodnuti`, { method: 'POST', headers: { 'content-type': 'application/json', ...h }, body: JSON.stringify(body) });
try {
  let r = await post({ slug: 'kostel', stav: 'ok', komentar: 'věž žluťoučká' });
  assert.equal(r.status, 200, 'chybějící soubor = prázdný');
  r = await post({ slug: 'radnice', stav: 'predelat' });
  let d = JSON.parse(fs.readFileSync(RJ, 'utf8'));
  assert.deepEqual(Object.keys(d), ['kostel', 'radnice']); assert.equal(d.kostel.komentar, 'věž žluťoučká');
  const vadny = fs.readFileSync(RJ, 'utf8').slice(0, -5);
  fs.writeFileSync(RJ, vadny);
  r = await post({ slug: 'kasna', stav: 'ok' });
  assert.equal(r.status, 500, 'poškozený soubor = chyba');
  assert.equal(fs.readFileSync(RJ, 'utf8'), vadny, 'poškozený soubor zůstal beze změny');
  assert.ok(!fs.existsSync(RJ + '.tmp'));
  fs.writeFileSync(RJ, '{}');
  // tělo rozdělené uprostřed vícebajtového znaku
  const b = Buffer.from('{"slug":"kasna","stav":"ok","komentar":"ž"}'), k = b.indexOf(Buffer.from('ž')) + 1;
  await new Promise((ok, ko) => { const q = http.request({ host: '127.0.0.1', port: PORT, path: '/rozhodnuti', method: 'POST', headers: { 'content-type': 'application/json' } }, (x) => { x.resume(); x.on('end', ok); }).on('error', ko);
    q.write(b.subarray(0, k)); setTimeout(() => q.end(b.subarray(k)), 50); });
  assert.equal(JSON.parse(fs.readFileSync(RJ, 'utf8')).kasna.komentar, 'ž', 'znak přes hranici kusů');
  fs.writeFileSync(RJ, '{}');
  r = await post({ slug: 'kasna', stav: 'x' }); assert.equal(r.status, 400, 'neplatný stav');
  r = await post({ slug: 'kasna', stav: 'ok' }, { origin: 'https://zla.example' }); assert.equal(r.status, 403, 'cizí Origin');
  // fetch hlavičku Host přepsat nedovolí (DNS rebinding se jinak nedá napodobit)
  const st = await new Promise((ok, ko) => http.request({ host: '127.0.0.1', port: PORT, path: '/rozhodnuti', method: 'POST', headers: { host: 'zla.example', 'content-type': 'application/json' } },
    (x) => { x.resume(); ok(x.statusCode); }).on('error', ko).end('{"slug":"kasna","stav":"ok"}'));
  assert.equal(st, 403, 'cizí Host');
  assert.equal(fs.readFileSync(RJ, 'utf8'), '{}', 'odmítnuté požadavky nic nezapsaly');
  console.log('OK: poškozený soubor 500 beze změny, zápis, Host/Origin');
} finally { srv.kill(); fs.rmSync(T, { recursive: true, force: true }); }
