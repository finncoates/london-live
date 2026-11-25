import puppeteer from 'puppeteer-core';
const [,, url, out, wait = '15000'] = process.argv;
const b = await puppeteer.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:'new'});
const p = await b.newPage(); await p.setViewport({width:900, height:700}); const errs = []; p.on('pageerror', e => errs.push(e.message));
await p.goto(url, {waitUntil:'domcontentloaded'}); await new Promise(r => setTimeout(r, +wait));
const r = await p.evaluate(() => { let n = 0, piled = 0; const L = [...(window.__GPSL ? __GPSL().values() : [])];
  const P = L.map(g => ({g, c:window.__gpsPos ? __gpsPos(g) : null})); return {n:L.length, fan:L.filter(g => g.fanO).length}; });
await p.screenshot({path:out}); console.log(JSON.stringify(r), errs.slice(0, 3)); await b.close();
