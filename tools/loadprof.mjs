// What a place downloads in its first N seconds, grouped by kind: node tools/loadprof.mjs "lat,lon,z" [seconds] [base url]
import puppeteer from 'puppeteer-core';
const [view, secs = 20, base = 'https://finncoates.github.io/london-live/'] = process.argv.slice(2);
const b = await puppeteer.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:'new'});
const p = await b.newPage(); await p.setViewport({width:1200, height:800}); const c = await p.createCDPSession(); await c.send('Network.enable'); await c.send('Network.setCacheDisabled', {cacheDisabled:true});
const reqs = new Map(); const t0 = Date.now();
c.on('Network.responseReceived', e => reqs.set(e.requestId, {url:e.response.url, t:Date.now() - t0, bytes:0}));
c.on('Network.loadingFinished', e => { const r = reqs.get(e.requestId); if(r){ r.bytes = e.encodedDataLength; r.done = Date.now() - t0; } });
await p.goto(base + '?view=' + view, {waitUntil:'domcontentloaded'}); let first = null;
for(let k = 0; k < secs*2; k++){ await new Promise(r => setTimeout(r, 500)); const s = await p.evaluate(() => window.__smoke?.()).catch(() => null); if(!first && s && (s.cityLines || s.tfl > 5)) first = Date.now() - t0; }
const g = {}; for(const r of reqs.values()){ const u = r.url.replace(/\?.*/, ''); const k = /cities\/busnet\//.test(u) ? 'bus tiles' : /cities\/stops\//.test(u) ? 'stop tiles' : /cities\/nr\//.test(u) ? 'rail tiles' : /cities\/tfl\//.test(u) ? 'tfl lines' : /cities\/[^/]+\.json$/.test(u) ? 'city files' : /workers\.dev/.test(u) ? 'relay' : /openfreemap|tiles\.|\.pbf|font|glyph|sprite/.test(u) ? 'base map' : /\.js$|\.html$|\/$/.test(u) ? 'code' : 'other';
  (g[k] ||= {n:0, kb:0, last:0}); g[k].n++; g[k].kb += r.bytes/1024; g[k].last = Math.max(g[k].last, r.done || r.t); }
if(process.env.RELAY) for(const r of [...reqs.values()].filter(r => /workers.dev/.test(r.url)).sort((a,b)=>a.t-b.t)) console.log(String(r.t).padStart(6), String(r.done-r.t).padStart(6), (r.bytes/1024).toFixed(0).padStart(5), r.url.replace(/https:..[^/]+/, '').slice(0, 90));
console.log(view, 'lines drawn after', first, 'ms');
for(const [k, v] of Object.entries(g).sort((a, b) => b[1].kb - a[1].kb)) console.log(k.padEnd(11), String(v.n).padStart(4), 'req', (v.kb/1024).toFixed(2).padStart(7), 'MB  last at', (v.last/1000).toFixed(1), 's');
await b.close();
