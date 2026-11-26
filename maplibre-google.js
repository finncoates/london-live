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
      this.ready = false; this.ml.on('load', () => { this.ready = true; if(innerWidth <= 700) div.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show'); }); // (phones: the credits behind their (i), not across the map)
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
      queueMicrotask(() => { const p = this.pend; this.pend = null; const c = this.ml.getCenter(), far = p.center && Math.hypot(p.center.lat - c.lat, (p.center.lng - c.lng)*Math.cos(c.lat*Math.PI/180)) > 3; // another city: jump, don't slide
        const o = {duration:far || (p.zoom != null && Math.abs(p.zoom - this.ml.getZoom()) > 2.5) ? 0 : 450};
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
      if(typeof ic.path === 'string'){ // a pin shape (test mode's draggable "you")
        el.style.cssText = 'width:22px;height:30px;cursor:grab'; el.innerHTML = `<svg width="22" height="30" viewBox="-11 -31 22 32"><path d="${ic.path}" fill="${ic.fillColor || '#1a73e8'}" stroke="${ic.strokeColor || '#fff'}" stroke-width="${ic.strokeWeight || 2}"/></svg>`; }
      this.mk = new maplibregl.Marker({element:el, draggable:!!o.draggable, anchor:typeof ic.path === 'string' ? 'bottom' : 'center'}).setLngLat(ll(o.position)); if(o.map) this.setMap(o.map); }
    setMap(m){ if(m) this.mk.addTo(m.ml); else this.mk.remove(); }
    setPosition(p){ this.mk.setLngLat(ll(p)); }
    getPosition(){ const q = this.mk.getLngLat(); return new LatLng(q.lat, q.lng); }
    addListener(ev, fn){ const h = () => { const q = this.mk.getLngLat(); fn({latLng:new LatLng(q.lat, q.lng)}); }; this.mk.on(ev, h); return {remove:() => this.mk.off(ev, h)}; } }
  const hexA = (c, a) => { const h = c.replace('#', ''); if(h.length !== 6) return c; return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4), 16)},${a})`; };
  // route lines (London Journey): a GeoJSON line layer each, stacked by zIndex. Google "icons" become a dotted line
  // (circles: walking) or a dashed one (short strokes), the nearest MapLibre has.
  let PLN = 0;
  class Polyline{
    constructor(o){ this.id = 'gpl' + (++PLN); this.o = {...o}; this.path = (o.path || []).map(ll); if(o.map) this.setMap(o.map); }
    _paint(){ const o = this.o, ic = o.icons && o.icons[0], sym = ic && ic.icon || {}, rep = ic ? parseFloat(ic.repeat) || 10 : 0;
      if(ic){ const dot = sym.path === 0 || sym.path === undefined || sym.path === 'circle', w = dot ? Math.max(2, (sym.scale || 2)*2) : Math.max(2, (sym.strokeWeight || 3));
        return {w, paint:{'line-color':(dot ? sym.fillColor : sym.strokeColor) || '#555', 'line-opacity':(dot ? sym.fillOpacity : sym.strokeOpacity) ?? 1, 'line-width':w,
          'line-dasharray':dot ? [0, rep/w] : [Math.max(1, (sym.scale || 3)*2/w), Math.max(1, rep/w - (sym.scale || 3)*2/w)]}, cap:dot ? 'round' : 'butt'}; }
      return {w:o.strokeWeight ?? 3, paint:{'line-color':o.strokeColor || '#000', 'line-opacity':o.strokeOpacity ?? 1, 'line-width':o.strokeWeight ?? 3}, cap:'round'}; }
    _add(){ const m = this.map.ml, z = this.o.zIndex || 0, p = this._paint();
      if(!m.getSource(this.id)) m.addSource(this.id, {type:'geojson', data:{type:'Feature', geometry:{type:'LineString', coordinates:this.path}}});
      if(m.getLayer(this.id)) m.removeLayer(this.id);
      const above = (m.getStyle().layers || []).find(L => L.id.startsWith('gpl') && (L.metadata?.z ?? 0) > z); // keep the stacking order
      m.addLayer({id:this.id, type:'line', source:this.id, metadata:{z}, layout:{'line-join':'round', 'line-cap':p.cap}, paint:p.paint}, above ? above.id : undefined); }
    setMap(map){ if(this.map && this.map !== map) this._remove(); this.map = map; if(!map) return;
      const go = () => { if(this.map !== map) return; try{ this._add(); }catch(e){} };
      if(map.ml.isStyleLoaded()) go(); else map.ml.once('idle', go);
      if(!this._re){ this._re = () => { if(this.map) go(); }; map.ml.on('style.load', this._re); } } // the look changed: draw it again
    _remove(){ const m = this.map?.ml; if(!m) return; if(this._re){ m.off('style.load', this._re); this._re = null; } try{ if(m.getLayer(this.id)) m.removeLayer(this.id); if(m.getSource(this.id)) m.removeSource(this.id); }catch(e){} this.map = null; }
    setOptions(o){ Object.assign(this.o, o); if(o.path) this.path = o.path.map(ll); if(this.map){ try{ this._add(); }catch(e){} } }
    setPath(p){ this.setOptions({path:p}); } }

  window.installMapLibreAsGoogle = () => { window.google = {maps:{Map:GMap, LatLng, LatLngBounds, OverlayView, Marker, Polyline, SymbolPath:{CIRCLE:0},
    importLibrary:() => Promise.resolve(), event:{addListenerOnce:(m, ev, fn) => { let done = false; const h = m.addListener(ev, (...a) => { if(done) return; done = true; h.remove(); fn(...a); }); return h; }}, __maplibre:true}}; };
})();
