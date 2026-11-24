// Smoke test: the map opened in a headless browser in a few places; fails (exit 1) on a script error, or a place
// whose lines don't load. Run before every push (.git/hooks/pre-push), so a broken page never goes live.
//   node tools/smoke.mjs            (serves the working copy itself on a spare port)
import puppeteer from 'puppeteer-core';
import {spawn} from 'child_process';
import {fileURLToPath} from 'url';
import path from 'path';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), PORT = 8799;
const EDGE = ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe'];
const exe = (await import('fs')).default; const browserPath = process.env.BROWSER || EDGE.find(p => exe.existsSync(p));
// timetable trams/metros/boats over 300 m from their drawn line (none expected; the relay may be down or the hour quiet:
// no vehicles is not a failure). Waits while the timetable hasn't arrived yet.
const offTrack = s => s.offLine == null || !s.offLine.n ? 'WAIT timetable' : s.offLine.of > Math.max(1, s.offLine.n*0.02) ? `${s.offLine.of} of ${s.offLine.n} timetable vehicles off their line` : null;
// [name, view, check(state, title) -> problem or null]
const PLACES = [
  ['London', '51.505,-0.09,13', (s, t) => !/London/.test(t) ? 'title ' + t : s.tfl < 10 ? `only ${s.tfl} TfL lines drawn` : null],
  ['Paris', '48.857,2.35,14', (s, t) => !/Paris/.test(t) ? 'title ' + t : s.cityLines < 50 ? `only ${s.cityLines} lines` : offTrack(s)],
  ['Bordeaux', '44.84,-0.57,14', (s, t) => !/Bordeaux/.test(t) ? 'title ' + t : s.cityLines < 5 ? `only ${s.cityLines} lines` : offTrack(s)],
  ['Zürich', '47.377,8.54,14', (s, t) => /Z.R/.test(t) || !/Z.rich/.test(t) ? 'title ' + t : s.cityLines < 10 ? `only ${s.cityLines} lines` : null],
  ['Lisbon', '38.72,-9.14,14', (s, t) => !/Lisbo/.test(t) ? 'title ' + t : s.cityLines < 5 ? `only ${s.cityLines} lines` : null],
];
// noise that isn't the page's fault: the relay only answers the live site, favicons, missing optional tiles
const IGNORE = /CORS|Access-Control|favicon|status of 404|404 |net::ERR|Failed to fetch|429|rate limit/i;
const srv = spawn(process.platform === 'win32' ? 'python' : 'python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], {cwd: ROOT, stdio: 'ignore'});
await new Promise(r => setTimeout(r, 1200));
const browser = await puppeteer.launch({executablePath: browserPath, headless: 'new', args: ['--no-first-run', '--window-size=1200,800', ...(process.platform === 'win32' ? [] : ['--no-sandbox'])]});
let bad = 0;
try {
  for(const [name, view, check] of PLACES){
    const page = await browser.newPage(); await page.setViewport({width: 1200, height: 800}); const errs = [];
    page.on('pageerror', e => errs.push('script: ' + e.message));
    page.on('console', m => { if(m.type() === 'error' && !IGNORE.test(m.text())) errs.push('console: ' + m.text().slice(0, 160)); });
    const t0 = Date.now(); await page.goto(`http://127.0.0.1:${PORT}/?view=${view}`, {waitUntil: 'domcontentloaded', timeout: 60000});
    let s = null, title = '', why = 'no state';
    for(let k = 0; k < 40; k++){ // up to 40 s for the lines to load
      await new Promise(r => setTimeout(r, 1000));
      s = await page.evaluate(() => window.__smoke ? window.__smoke() : null).catch(() => null); title = await page.title();
      why = s ? check(s, title) : 'no state (page script did not run)'; if(!why || errs.some(e => e.startsWith('script'))) break; }
    if(why === 'WAIT timetable') why = null; // (the relay didn't answer in time: not the page's fault)
    const problem = errs.find(e => e.startsWith('script')) || why || errs[0];
    console.log(`${problem ? 'FAIL' : 'ok  '} ${name.padEnd(9)} ${((Date.now() - t0)/1000).toFixed(0).padStart(3)} s  ${s ? `lines ${s.cityLines} · TfL ${s.tfl} · files ${s.cityFiles}${s.offLine ? ` · timetable on line ${s.offLine.n - s.offLine.of}/${s.offLine.n}` : ''}` : ''}${problem ? '  ← ' + problem : ''}`);
    if(problem) bad++; await page.close(); }
} finally { await browser.close(); srv.kill(); }
if(bad){ console.log(`\n${bad} place(s) failed: not pushing. (Skip once with: git push --no-verify)`); process.exit(1); }
console.log('smoke test passed');
