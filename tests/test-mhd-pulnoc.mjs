import assert from 'node:assert/strict';
import fs from 'node:fs';
// MHD po půlnoci: včerejší spoje jen z jízdního řádu platného včera (mhd.json má všechna období, mhd.py je neprořezává)
const js=fs.readFileSync('web/js/70-animace.js','utf8');
const fn=(n)=>js.match(new RegExp(`  function ${n}\\(.*?\\n  \\}\\n`,'s'))?.[0];
const src=js.match(/const ymd = \(d, k\) => \{[^\n]*?\};/)[0]+fn('mhdServices')+fn('mhdDay')+fn('mhdActive')+fn('stopDepartures');
let now;
const MHD={services:{
  skola:[[1,1,1,1,1,1,1],20260901,20261231,[],[]],     // školní rok
  prazdniny:[[1,1,1,1,1,1,1],20260701,20260831,[],[]],  // prázdniny (prošlé)
},routes:[['5',3]],shapes:[{w:[[0,0],[1,1]]}],names:['A','B'],
  // [linka, tvar, služba, odjezd s, časy, cíl, zastávky [id, s], čekání]: stejný spoj ve 23:40 v obou obdobích, jede 40 min
  trips:[[0,0,'prazdniny',85200,[0,0,2400,1],1,[0,0,1,2400],0],[0,0,'skola',85200,[0,0,2400,1],1,[0,0,1,2400],0]]};
MHD.dur=MHD.trips.map((t)=>t[4][t[4].length-2]);MHD.maxDur=2400;MHD.maxWait=0;
const {mhdActive,stopDepartures}=Function('MHD','pragueNow',src+'return {mhdActive,stopDepartures};')(MHD,()=>now);
// pondělí 30. 11. 2026 v 00:10: jede jen včerejší (nedělní) spoj ze školního roku
now={d:20261130,wd:0,s:600};
assert.deepEqual(mhdActive().map((a)=>MHD.trips[a[0]][2]),['skola']);
// karta zastávky ve 23:30: zítřejší spoj ve 23:40 jen jednou
now={d:20261130,wd:0,s:84600};
assert.equal(stopDepartures(0).length,1);
// prošlý jízdní řád (leden 2027): aspoň podle dne v týdnu, i pro včerejšek
now={d:20270112,wd:1,s:600};
assert.equal(mhdActive().length,2);
// přechod času (poslední neděle v říjnu a březnu): posun data nezávisí na letním čase
const ymd=Function(js.match(/const ymd = \(d, k\) => \{[^\n]*?\};/)[0]+' return ymd;')();
assert.equal(ymd(20261026,-1),20261025);assert.equal(ymd(20261025,1),20261026);
assert.equal(ymd(20270329,-1),20270328);assert.equal(ymd(20270328,1),20270329);
console.log('OK: MHD po půlnoci podle platného jízdního řádu');
