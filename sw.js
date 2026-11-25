// London Live service worker: the map opens with no signal (on the Underground, abroad without data), and repeat
// visits draw faster.
//   the page and its code       network first (a new version shows at once), the saved copy when offline
//   city data, map tiles, fonts saved copy at once, refreshed in the background (stale-while-revalidate)
//   live data (the relay, TfL)  never saved: positions are only ever live or timetable-now
const V = 'v1', SHELL = 'shell-' + V, DATA = 'data-' + V, TILES = 'tiles-' + V;
const LIMIT = {[DATA]: 4000, [TILES]: 3000};
self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(['./', './maplibre-google.js', './i18n.js', './manifest.webmanifest'])).catch(() => {}).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => ![SHELL, DATA, TILES].includes(k)).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
const trim = async name => { const c = await caches.open(name), ks = await c.keys(); for(let i = 0; i < ks.length - LIMIT[name]; i++) await c.delete(ks[i]); };
let trimT = 0;
function swr(e, name){
  e.respondWith(caches.open(name).then(async c => {
    const hit = await c.match(e.request);
    const net = fetch(e.request).then(r => { if(r.ok || r.type === 'opaque'){ c.put(e.request, r.clone()); if(Date.now() - trimT > 30000){ trimT = Date.now(); trim(name); } } return r; });
    if(hit){ e.waitUntil(net.catch(() => {})); return hit; }
    return net; }));
}
self.addEventListener('fetch', e => {
  if(e.request.method !== 'GET') return;
  const u = new URL(e.request.url);
  if(/workers\.dev$|tfl\.gov\.uk$|transitous|raildata/.test(u.hostname)) return; // live: straight to the network
  if(u.origin === location.origin){
    if(/\/cities\/.+\.json$|\/tube-depths\.json$/.test(u.pathname)) return swr(e, DATA);
    if(/\.(png|svg|ico)$/.test(u.pathname)) return swr(e, DATA);
    // the page and code: newest when online
    e.respondWith(fetch(e.request).then(r => { if(r.ok){ const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); } return r; })
      .catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match('./'))));
    return; }
  // the street map: its tiles, style, fonts and icons (OpenFreeMap), and the map library from its CDN
  if(/openfreemap|tiles\.|fonts\.(googleapis|gstatic)|unpkg\.com|jsdelivr|cdnjs/.test(u.hostname)) return swr(e, TILES);
});
