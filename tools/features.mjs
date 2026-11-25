// Feature test: the map's main features used as a person would, in a headless browser. Each check prints ok/FAIL;
// exits 1 if any failed. Uses the live relay and Transitous (an answer they don't give is reported, not hidden).
//   node tools/features.mjs            (serves the working copy itself on a spare port)
import puppeteer from 'puppeteer-core';
import {spawn} from 'child_process';
import {fileURLToPath} from 'url';
import path from 'path';
import fs from 'fs';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), PORT = 8798, U = `http://127.0.0.1:${PORT}/`;
const EDGE = ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe'];
const srv = spawn(process.platform === 'win32' ? 'python' : 'python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], {cwd:ROOT, stdio:'ignore'});
await new Promise(r => setTimeout(r, 1200));
const b = await puppeteer.launch({executablePath:process.env.BROWSER || EDGE.find(p => fs.existsSync(p)), headless:'new', args:['--window-size=1200,800', ...(process.platform === 'win32' ? [] : ['--no-sandbox'])]});
await b.defaultBrowserContext().overridePermissions(U.slice(0, -1), ['geolocation', 'clipboard-read', 'clipboard-write', 'clipboard-sanitized-write']);
const sleep = ms => new Promise(r => setTimeout(r, ms)); let bad = 0;
const check = (name, ok, info) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${info ? ' · ' + info : ''}`); if(!ok) bad++; };
async function open(url, wait = 12000){ const p = await b.newPage(); await p.setViewport({width:1200, height:800}); p.errs = []; p.on('pageerror', e => p.errs.push(e.message));
  await p.evaluateOnNewDocument(() => { try{ localStorage.setItem('howtoSeen', '1'); }catch(e){} }); await p.goto(U + url, {waitUntil:'domcontentloaded'}); await sleep(wait); return p; }
const txt = (p, sel) => p.evaluate(s => (document.querySelector(s)?.innerText || '').replace(/\s+/g, ' '), sel);
try{
  // 1. a stop's departures (Bordeaux: a bus stop close up)
  let p = await open('?view=44.84,-0.575,16.5', 14000); await p.evaluate(() => __testStop(2)); await sleep(8000);
  let t = await txt(p, '#station'); check('stop card shows departures', /min|due|timetable|live/.test(t) && !/could not be loaded/.test(t), t.slice(0, 70));
  // 2. save it, see it in Your stops
  await p.click('#stStar'); await sleep(500); check('☆ saves the stop', /Your stops/i.test(await txt(p, '#favs')));
  // 3. share link copied, and it opens the same stop
  await p.click('#stShare'); await sleep(800); const link = await p.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  check('↗ copies a stop link', /[?&]stop=/.test(link), link.slice(-50));
  // 4. Escape closes the card
  await p.keyboard.press('Escape'); await sleep(400); check('Escape closes the stop card', await p.evaluate(() => document.getElementById('station').hidden));
  // 5. a vehicle's card with its next stops, and Follow keeps it centred
  await p.evaluate(() => __testVeh('tram')); await sleep(9000); t = await txt(p, '#gfollow');
  check('vehicle card lists its stops', /\d\d:\d\d/.test(t), t.slice(0, 70));
  const g = await p.evaluate(() => __gf()); const off = g.p && g.c ? Math.hypot((g.p[0]-g.c[0])*111320, (g.p[1]-g.c[1])*73000) : 1e9;
  check('Follow keeps the vehicle centred', off < 30, Math.round(off) + ' m');
  // 6. the vehicle and line switches: tram lines off, trams still there
  const trams0 = await p.evaluate(() => [...__GPSL().values()].filter(g => g.v.kind === 'tram').length);
  const sel = await p.$('[data-lin="tram"]'); if(sel){ await sel.click(); await sleep(1500); }
  const st = await p.evaluate(() => ({linesOff:JSON.parse(localStorage.getItem('linesOff') || '[]'), trams:[...__GPSL().values()].filter(g => g.v.kind === 'tram').length}));
  check('Tram lines switch hides lines, keeps trams', !!sel && st.linesOff.includes('tram') && st.trams > 0 && trams0 > 0, `${trams0} trams · lines off: ${st.linesOff}`);
  if(sel){ await p.click('[data-lin="tram"]'); await sleep(300); }
  check('no script errors (Bordeaux)', !p.errs.length, p.errs[0]); await p.close();
  // 7. the shared link opens that stop
  p = await open(link.replace(/^https?:\/\/[^/]+\//, ''), 14000); t = await txt(p, '#station'); check('shared stop link opens it', t.length > 20, t.slice(0, 50)); await p.close();
  // 8. search: a stop anywhere in Europe, then its departures
  p = await open('?view=51.505,-0.09,13'); await p.focus('#q'); await p.keyboard.type('Gare de Lyon', {delay:40}); await sleep(2500);
  t = await txt(p, '#sres'); check('search finds Gare de Lyon from London', /Gare de Lyon/.test(t), t.slice(0, 60));
  const i = await p.evaluate(() => [...document.querySelectorAll('#sres li')].findIndex(li => /Stop/.test(li.innerText)));
  if(i >= 0){ await p.click(`#sres li:nth-child(${i + 1})`); await sleep(10000); t = await txt(p, '#station'); check('…and opens its departures', /Gare de Lyon/.test(t) && t.length > 40, t.slice(0, 60)); }
  check('no script errors (London, search)', !p.errs.length, p.errs[0]); await p.close();
  // 9. the panel in French
  p = await open('?view=44.84,-0.575,14&lang=fr'); t = await txt(p, '#status'); check('French: status line translated', /mis à jour/.test(t), t.slice(0, 60)); await p.close();
  // 10. near me: the nearest stop's departures
  p = await b.newPage(); await p.setViewport({width:1200, height:800}); await p.setGeolocation({latitude:52.2297, longitude:21.0122, accuracy:20}); p.errs = []; p.on('pageerror', e => p.errs.push(e.message));
  await p.goto(U + '?view=52.2297,21.0122,12', {waitUntil:'domcontentloaded'}); await sleep(9000); await p.click('#bFit'); await sleep(14000);
  t = await txt(p, '#station'); check('Near me opens the nearest stop (Warsaw)', t.length > 30, t.slice(0, 50)); await p.close();
  // 11. Paris: vehicles don't jump (none on screen faster than 150 m/s over a minute)
  p = await open('?view=48.857,2.35,14', 15000);
  const jumps = await p.evaluate(() => new Promise(res => { const last = new Map(); let n = 0, k = 0; const iv = setInterval(() => { const now = Date.now();
    for(const [id, g] of __GPSL()){ if(!id.startsWith('tf:')) continue; const q = __gpsPos(g, now), o = last.get(id); if(o && Math.abs(q[0] - 48.857) < 0.06 && Math.abs(q[1] - 2.35) < 0.1 && Math.hypot((q[0]-o[0])*111320, (q[1]-o[1])*73000) > 150) n++; last.set(id, q); }
    if(++k >= 60){ clearInterval(iv); res(n); } }, 1000); }));
  check('Paris: few jumps on screen (≤ 15 a minute)', jumps <= 15, jumps + ' moves over 150 m/s'); await p.close();
}finally{ await b.close(); srv.kill(); }
console.log(bad ? `\n${bad} check(s) failed` : '\nall features passed'); process.exit(bad ? 1 : 0);
