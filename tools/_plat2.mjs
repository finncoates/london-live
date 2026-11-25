import puppeteer from 'puppeteer-core';
const [,, url, crs, out] = process.argv;
const b = await puppeteer.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:'new'});
const p = await b.newPage(); await p.setViewport({width:900, height:700}); const errs = []; p.on('pageerror', e => errs.push(e.message));
await p.goto(url, {waitUntil:'domcontentloaded'}); await new Promise(r => setTimeout(r, 20000));
await p.evaluate(() => { const b = [...document.querySelectorAll('button')].find(x => /Got it/.test(x.textContent)); b && b.click(); document.querySelector('#panel, aside, .panel')?.style.setProperty('display', 'none'); });
let best = [];
for(let i = 0; i < 12; i++){ await p.evaluate(c => __platGive(c), crs); await new Promise(r => setTimeout(r, 5000)); const on = await p.evaluate(() => __platOn());
  if(on.length >= best.length){ best = on; await p.screenshot({path:out}); } }
console.log(best, errs.slice(0, 3)); await b.close();
