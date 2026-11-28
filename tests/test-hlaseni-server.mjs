import assert from 'node:assert/strict';
import fs from 'node:fs';
const worker = (await import('../hlaseni/worker.js')).default;
const ASSETS = { fetch: async () => new Response('assets') };
const auth = 'Basic ' + Buffer.from('admin:heslo').toString('base64');

// administrace: změna stavu z cizí stránky; na upstream/main prošel i formulář enctype=text/plain s tělem jako JSON,
// tady application/json, ať test nezávisí na kontrole Content-Type (jiná větev)
let updates = 0;
const fake = { prepare: () => ({ bind: () => ({ run: async () => { updates++; return { meta: { changes: 1 } }; } }) }) };
const env = { DB: fake, ASSETS, ADMIN_PASSWORD: 'heslo' };
const set = (headers, body = '{"target":"pt:1,1","status":"zamitnuto","x":"="}\r\n') =>
  worker.fetch(new Request('https://mapa.cz/api/admin/status', { method: 'POST', headers: { authorization: auth, 'content-type': 'application/json', ...headers }, body }), env);
assert.equal((await set({ origin: 'https://zla.example' })).status, 403, 'cizí Origin');
assert.equal((await set({ origin: 'null' })).status, 403, 'Origin null (sandbox, data:)');
assert.equal(updates, 0);
assert.equal((await set({ origin: 'https://mapa.cz' })).status, 200, 'vlastní Origin');
assert.equal((await set({})).status, 200, 'bez Origin (curl)');
assert.equal((await set({}, '{"target":')).status, 400, 'vadné JSON');
assert.equal((await set({}, 'null')).status, 400, 'JSON null');
assert.equal(updates, 2);

// limit 3/h na skutečném SQLite se schématem z migrace (node:sqlite je až od Node 22.5)
let sqlite; try { sqlite = await import('node:sqlite'); } catch { console.log('OK: Origin a JSON v administraci (limit přeskočen, chybí node:sqlite)'); process.exit(0); }
const db = new sqlite.DatabaseSync(':memory:');
for (const f of fs.readdirSync('hlaseni/migrations').sort()) db.exec(fs.readFileSync('hlaseni/migrations/' + f, 'utf8'));
// jako D1: prepare(sql)[.bind(...)].first/all/run, run vrací { meta: { changes } }
const D1 = { prepare: (sql) => { const st = db.prepare(sql), q = (...a) => ({
  first: async () => st.get(...a), all: async () => ({ results: st.all(...a) }),
  run: async () => ({ meta: { changes: Number(st.run(...a).changes) } }) }); return { ...q(), bind: q }; } };
const senv = { DB: D1, ASSETS, SALT: 'tajne' };
let n = 0;
const rep = (ip, target = 'pt:50.' + n++ + ',15.05') => worker.fetch(new Request('https://mapa.cz/api/report', { method: 'POST',
  headers: { 'content-type': 'application/json', 'cf-connecting-ip': ip }, body: JSON.stringify({ target, note: 'tady nic není' }) }), senv);
const st = async (ip, t) => (await rep(ip, t)).status;
// limit v jednom příkazu INSERT … WHERE: čtvrté hlášení za hodinu se neuloží
assert.deepEqual((await Promise.all([1, 2, 3, 4, 5, 6].map(() => st('198.51.100.7')))).sort(), [200, 200, 200, 429, 429, 429]);
assert.equal(db.prepare('SELECT COUNT(*) n FROM reports').get().n, 3);
// IPv6: celá /64 sdílí limit (i zkrácený zápis, velká písmena, úvodní nuly)
assert.equal(await st('2001:db8:0:0::1'), 200);
assert.equal(await st('2001:DB8::2'), 200);
assert.equal(await st('2001:0db8:0000:0000:ffff:1:2:3'), 200);
assert.equal(await st('2001:db8::abcd'), 429, 'jiná adresa ze stejné /64');
assert.equal(await st('2001:db8:0:1::1'), 200, 'jiná /64');
assert.equal(await st('::ffff:203.0.113.1'), 200, 'IPv4 v IPv6 zůstává celá');
assert.equal(await st('::ffff:203.0.113.2'), 200);
// stejné místo dvakrát za den = 409, ne 429
assert.equal(await st('192.0.2.1', 'pt:1,1'), 200);
assert.equal(await st('192.0.2.1', 'pt:1,1'), 409);
// otisk zařízení se po hodině smaže, aby nešlo propojit hlášení napříč dny
db.exec("UPDATE reports SET created = datetime('now', '-2 hours') WHERE id = 1");
assert.equal(await st('192.0.2.9'), 200);
assert.equal(db.prepare('SELECT dev FROM reports WHERE id = 1').get().dev, null);
assert.ok(db.prepare('SELECT COUNT(*) n FROM reports WHERE dev IS NOT NULL').get().n > 0, 'čerstvé otisky zůstávají kvůli limitu');
console.log('OK: Origin a JSON v administraci, limit v jednom příkazu, IPv6 /64, 409, mazání otisku');
