import assert from 'node:assert/strict';
import fs from 'node:fs';
// drobná čistá logika prohlížeče z web/js (slepí web/sestav.py)
const js=fs.readdirSync('web/js').filter(f=>f.endsWith('.js')).sort().map(f=>fs.readFileSync('web/js/'+f,'utf8')).join('');
// pražské datum RRRRMMDD posunuté o den (včera/zítra pro jízdní řády), přes konec měsíce, roku a přestupný rok
const ymdSrc=js.match(/const ymd = \(d, k\) => \{[^\n]*?\};/)?.[0];assert.ok(ymdSrc);
const ymd=Function(ymdSrc+' return ymd;')();
assert.equal(ymd(20261127,-1),20261126);assert.equal(ymd(20261127,1),20261128);
assert.equal(ymd(20260301,-1),20260228);assert.equal(ymd(20280301,-1),20280229);
assert.equal(ymd(20261231,1),20270101);assert.equal(ymd(20270101,-1),20261231);
// pořadí v hledání: každý druh z indexu má číslo, jinak komparátor vrací NaN
const order=Function('return '+js.match(/const order = (\{[^}]*\});/)[1])();
const kinds=new Set([...js.matchAll(/kind: '([^']+)'/g)].map(m=>m[1]).concat(['adresa','budova']));
for(const k of kinds)assert.ok(Number.isFinite(order[k]),'chybí pořadí pro '+k);
// adresy do hledání: po chybě sítě se načtou při dalším pokusu, po úspěchu jen jednou a vadný soubor nepřidá nic
const addrSrc=js.match(/let addrLoad = null;[\s\S]*?\.catch\(\(\) => \{ addrLoad = null; \}\)\);/)?.[0];assert.ok(addrSrc);
const index=[];let odpoved;
const loadAddr=Function('fetch','index','VER','norm',addrSrc+' return loadAddr;')(async()=>odpoved(),index,'?v=1',(t)=>t.normalize('NFD'));
odpoved=()=>{throw new TypeError('offline');};await loadAddr();assert.equal(index.length,0);
odpoved=()=>({json:async()=>[['Hlavní 1','c0_0',1,2,0],[null]]});await loadAddr();assert.equal(index.length,0,'vadný soubor nesmí přidat část adres');
odpoved=()=>({json:async()=>[['Hlavní 1','c0_0',1,2,0],['Nádraží','c0_0',3,4,1,'zastávka']]});await loadAddr();await loadAddr();
assert.deepEqual(index.map(r=>r.label+'/'+r.kind),['Hlavní 1/adresa','Nádraží/zastávka']);
console.log('OK: posun pražského data o den, pořadí všech druhů v hledání, načtení adres po chybě sítě');
