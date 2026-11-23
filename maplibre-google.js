// London Live: the small part of the Google Maps JavaScript API the maps use, on top of MapLibre GL
// (free, open source) with free OpenStreetMap vector tiles from OpenFreeMap. The pages draw their own lines
// and trains on canvases above the map; this only supplies the base map, the camera, events, the projection
// and the station rings. Load MapLibre first, then call installMapLibreAsGoogle().
//
// Zoom: MapLibre's zoom z shows what Google shows at zoom z + 1 (512 px tiles), so every zoom is shifted by one.
// Styles: setOptions({styles}) takes a look id from mapLookId() in the page: 'light' | 'dark' | 'grey' | 'greydark'
// | 'satellite', with '+quiet' to hide places and labels (street names stay).
(function(){
  const TILES = 'https://tiles.openfreemap.org/styles/';
  const LOOK = {light:'liberty', dark:'dark', grey:'positron', greydark:'dark'};
  // Esri World Imagery for the satellite look (attribution required; see ROADMAP for the free key before a big launch)
  const ESRI = window.ESRI_KEY ? '?token=' + window.ESRI_KEY : '';
  const SAT = {version:8, glyphs:'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources:{sat:{type:'raster', tileSize:256, maxzoom:19, attribution:'Imagery © Esri, Maxar, Earthstar Geographics',
                  tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' + ESRI]},
             ref:{type:'raster', tileSize:256, maxzoom:19, tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}' + ESRI]}},
    layers:[{id:'sat', type:'raster', source:'sat'}, {id:'ref', type:'raster', source:'ref', paint:{'raster-opacity':0.9}}]};
  // the clutter "Hide places & labels" removes: shops, landmarks, stations and area names (street names stay)
  const QUIET_LAYERS = /^(poi|place|water_name|waterway_name|aerodrome|aeroway|housenumber|mountain_peak|park|landuse_overlay)/;
  const QUIET_SOURCE = new Set(['poi', 'place', 'water_name', 'aerodrome_label', 'housenumber', 'mountain_peak', 'park']);
  // the dark look a step lighter, like the app's own dark map (roads and water readable under the coloured lines)
  const DARK_TWEAK = {background:'#1d2026', water:'#0e1626'};

  class LatLng{ constructor(lat, lng){ this._a = +lat; this._o = +lng; } lat(){ return this._a; } lng(){ return this._o; } toJSON(){ return {lat:this._a, lng:this._o}; } }
  const ll = p => p instanceof LatLng ? [p.lng(), p.lat()] : typeof p.lat === 'function' ? [p.lng(), p.lat()] : [p.lng, p.lat];
  class LatLngBounds{ constructor(){ this.s = 90; this.w = 180; this.n = -90; this.e = -180; }
    extend(p){ const [o, a] = ll(p); this.s = Math.min(this.s, a); this.n = Math.max(this.n, a); this.w = Math.min(this.w, o); this.e = Math.max(this.e, o); return this; }
    getSouthWest(){ return new LatLng(this.s, this.w); } getNorthEast(){ return new LatLng(this.n, this.e); }
    contains(p){ const [o, a] = ll(p); return a >= this.s && a <= this.n && o >= this.w && o <= this.e; }
    getCenter(){ return new LatLng((this.s + this.n)/2, (this.w + this.e)/2); } }

  class GMap{
    constructor(div, o){
      this.div = div; this.pend = null; this._parse(o.styles);
      this.ml = new maplibregl.Map({container:div, style:this.styleName === 'sat' ? SAT : TILES + this.styleName, center:ll(o.center), zoom:(o.zoom ?? 11) - 1,
        attributionControl:{compact:true}, dragRotate:false, pitchWithRotate:false, maxPitch:0, fadeDuration:150, renderWorldCopies:false});
      this.ml.touchZoomRotate.disableRotation(); this.ml.keyboard.disableRotation();
      this.ready = false; this.ml.on('load', () => { this.ready = true; });
      this.ml.on('style.load', () => this._styleTweaks()); // once per style (setting layer properties must not re-trigger it)
    }
    _parse(id){ this.look = id || 'light'; const [base, q] = this.look.split('+'); this.quiet = q === 'quiet'; this.base = base;
      this.styleName = base === 'satellite' ? 'sat' : (LOOK[base] || 'liberty'); }
    getDiv(){ return this.div; }
    getCenter(){ const c = this.pend?.center || this.ml.getCenter(); return new LatLng(c.lat ?? c[1], c.lng ?? c[0]); }
    getZoom(){ return Math.round((this.pend?.zoom ?? this.ml.getZoom()) + 1); } // Google gives whole zoom levels
    getBounds(){ const b = this.ml.getBounds(), r = new LatLngBounds(); r.s = b.getSouth(); r.n = b.getNorth(); r.w = b.getWest(); r.e = b.getEast(); return r; }
    // panTo and setZoom right after each other make one smooth move (not two that cancel each other)
    _later(k, v){ (this.pend ||= {})[k] = v; if(this.pend.t) return; this.pend.t = true;
      queueMicrotask(() => { const p = this.pend; this.pend = null; const o = {duration:p.zoom != null && Math.abs(p.zoom - this.ml.getZoom()) > 2.5 ? 0 : 450};
        if(p.center) o.center = p.center; if(p.zoom != null) o.zoom = p.zoom; this.ml.easeTo(o); }); }
    panTo(p){ this._later('center', {lng:ll(p)[0], lat:ll(p)[1]}); }
    setZoom(z){ this._later('zoom', z - 1); }
    setCenter(p){ if(this.pend) this.pend.center = null; this.ml.jumpTo({center:ll(p)}); }
    fitBounds(b, pad){ this.ml.fitBounds([[b.w, b.s], [b.e, b.n]], {padding:pad ?? 20, duration:500, maxZoom:17}); }
    setOptions(o){ if('styles' in o && o.styles !== this.look) this._setLook(o.styles); }
    _setLook(id){ const was = this.styleName; this._parse(id);
      if(this.styleName === was){ this._styleTweaks(); return; }
      this.ml.setStyle(this.styleName === 'sat' ? SAT : TILES + this.styleName, {diff:false}); }
    _styleTweaks(){ const m = this.ml; let st; try{ st = m.getStyle(); }catch(e){ return; } if(!st) return;
      for(const L of st.layers || []){
        if(L.type === 'symbol' || /label|name/.test(L.id)){ const quiet = this.quiet && (QUIET_LAYERS.test(L.id) || QUIET_SOURCE.has(L['source-layer']));
          try{ m.setLayoutProperty(L.id, 'visibility', quiet ? 'none' : 'visible'); }catch(e){} }
        if(this.base === 'dark' && this.styleName === 'dark'){ // the app's dark colours
          try{ if(L.type === 'background') m.setPaintProperty(L.id, 'background-color', DARK_TWEAK.background);
            if(L.type === 'fill' && /water/.test(L.id)) m.setPaintProperty(L.id, 'fill-color', DARK_TWEAK.water); }catch(e){} } } }
    addListener(ev, fn){
      const name = {idle:'idle', click:'click', dragstart:'dragstart', zoom_changed:'zoom', bounds_changed:'move'}[ev] || ev;
      const h = name === 'click' ? e => fn({pixel:{x:e.point.x, y:e.point.y}, latLng:new LatLng(e.lngLat.lat, e.lngLat.lng)}) : name === 'idle' ? () => fn() : e => fn(e);
      // Google's "idle" also comes once the map first settles; MapLibre's after every finished move
      this.ml.on(name === 'idle' ? 'moveend' : name, h); if(name === 'idle') this.ml.once('idle', h);
      return {remove:() => { this.ml.off(name === 'idle' ? 'moveend' : name, h); }}; }
  }
  // the page reads screen positions through an (empty) overlay's projection
  class OverlayView{ setMap(m){ this.map = m; } getProjection(){ const m = this.map; if(!m || !m.ready) return null;
    return {fromLatLngToContainerPixel:p => { const q = m.ml.project(ll(p)); return {x:q.x, y:q.y}; }}; } }
  // station rings: a circle icon (Google's SymbolPath.CIRCLE) as an HTML marker
  class Marker{ constructor(o){ const ic = o.icon || {}, r = (ic.scale || 8), el = document.createElement('div');
      el.style.cssText = `width:${2*r}px;height:${2*r}px;border-radius:50%;box-sizing:border-box;pointer-events:none;` +
        `border:${ic.strokeWeight ?? 2}px solid ${ic.strokeColor || '#333'};background:${ic.fillColor || 'transparent'};`;
      if(ic.fillOpacity != null && ic.fillColor){ el.style.background = 'transparent'; el.style.boxShadow = `inset 0 0 0 ${r}px ${hexA(ic.fillColor, ic.fillOpacity)}`; }
      this.mk = new maplibregl.Marker({element:el}).setLngLat(ll(o.position)); if(o.map) this.setMap(o.map); }
    setMap(m){ if(m) this.mk.addTo(m.ml); else this.mk.remove(); } }
  const hexA = (c, a) => { const h = c.replace('#', ''); if(h.length !== 6) return c; return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4), 16)},${a})`; };
  class Polyline{ constructor(){} setMap(){} setOptions(){} } // (not used by the live map: its lines are drawn on a canvas)

  window.installMapLibreAsGoogle = () => { window.google = {maps:{Map:GMap, LatLng, LatLngBounds, OverlayView, Marker, Polyline, SymbolPath:{CIRCLE:0},
    importLibrary:() => Promise.resolve(), event:{addListenerOnce:(m, ev, fn) => { let done = false; const h = m.addListener(ev, (...a) => { if(done) return; done = true; h.remove(); fn(...a); }); return h; }}, __maplibre:true}}; };
})();
