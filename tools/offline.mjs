// the live site opened once, then again with the network cut: does the map still draw?
import puppeteer from 'puppeteer-core';
const url = process.argv[2] || 'https://finncoates.github.io/london-live/?view=44.84,-0.57,14';
const b = await puppeteer.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless:'new'});
const p = await b.newPage(); await p.setViewport({width:1200, height:800});
await p.goto(url, {waitUntil:'networkidle2', timeout:90000}).catch(() => {}); await new Promise(r => setTimeout(r, 8000));
console.log('sw', await p.evaluate(() => navigator.serviceWorker.controller ? 'controlling' : 'not yet'));
await p.reload({waitUntil:'domcontentloaded'}); await new Promise(r => setTimeout(r, 5000)); // the worker controls this load
await p.setOfflineMode(true); await p.reload({waitUntil:'domcontentloaded'}).catch(e => console.log('reload', e.message)); await new Promise(r => setTimeout(r, 10000));
console.log('offline:', JSON.stringify(await p.evaluate(() => ({title:document.title, s:window.__smoke?.(), stale:document.getElementById('stale')?.textContent}))));
await p.screenshot({path: process.argv[3] || 'offline.png'}); await b.close();
