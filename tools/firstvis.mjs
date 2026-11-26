// when a place first shows its vehicles: node tools/firstvis.mjs "lat,lon,z" [base]
import puppeteer from 'puppeteer-core';
const [view, base = 'https://finncoates.github.io/london-live/'] = process.argv.slice(2);
const b = await puppeteer.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:'new'});
const p = await b.newPage(); await p.setViewport({width:1200, height:800}); const t0 = Date.now();
await p.goto(base + '?view=' + view, {waitUntil:'domcontentloaded', timeout:90000}); const dcl = Date.now() - t0; let lines = null, veh = null;
for(let k = 0; k < 120 && veh == null; k++){ await new Promise(r => setTimeout(r, 250));
  const s = await p.evaluate(() => ({s:window.__smoke?.(), txt:document.getElementById('sub')?.textContent || document.body.innerText.slice(0, 300)})).catch(() => null);
  if(!s) continue; if(lines == null && s.s && (s.s.cityLines || s.s.tfl > 5)) lines = Date.now() - t0;
  if(veh == null && /[1-9]\d* (trains|trams|buses|metros)/.test(s.txt)) veh = Date.now() - t0; }
console.log(view, 'page', dcl, 'ms · lines', lines, 'ms · vehicles', veh, 'ms'); await b.close();
