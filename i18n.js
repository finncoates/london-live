// The panel in the visitor's language (French, German, Dutch, Spanish, Italian, Polish, Portuguese): from the browser's
// language, or ?lang=fr. Names (stops, lines, places) are never translated; a sentence not listed stays in English
// rather than half-translated. Loaded before the page's own script: window.T(text) and window.LANG.
(function(){
  const Q = new URLSearchParams(location.search), want = (Q.get('lang') || navigator.language || 'en').slice(0, 2).toLowerCase();
  const L = ['fr', 'de', 'nl', 'es', 'it', 'pl', 'pt'];
  const LANG = window.LANG = L.includes(want) ? want : 'en';
  // English → [fr, de, nl, es, it, pl, pt]
  const S = {
    // transport types (chips, departure groups)
    'Buses':['Bus', 'Busse', 'Bussen', 'Autobuses', 'Autobus', 'Autobusy', 'Autocarros'],
    'Trams':['Trams', 'Straßenbahnen', 'Trams', 'Tranvías', 'Tram', 'Tramwaje', 'Elétricos'],
    'Metro':['Métro', 'U-Bahn', 'Metro', 'Metro', 'Metro', 'Metro', 'Metro'],
    'Ferries':['Ferries', 'Fähren', 'Veerboten', 'Ferris', 'Traghetti', 'Promy', 'Ferries'],
    'Boats':['Bateaux', 'Schiffe', 'Boten', 'Barcos', 'Battelli', 'Statki', 'Barcos'],
    'Bikes & scooters':['Vélos & trottinettes', 'Räder & Roller', 'Fietsen & steps', 'Bicis y patinetes', 'Bici e monopattini', 'Rowery i hulajnogi', 'Bicicletas e trotinetes'],
    'Road works':['Travaux', 'Baustellen', 'Wegwerkzaamheden', 'Obras', 'Lavori stradali', 'Roboty drogowe', 'Obras'],
    'Coach routes':['Lignes d’autocars', 'Fernbuslinien', 'Touringcarlijnen', 'Rutas de autocar', 'Linee di pullman', 'Trasy autokarów', 'Rotas de expressos'],
    'Timetable':['Horaires', 'Fahrplan', 'Dienstregeling', 'Horario', 'Orario', 'Rozkład', 'Horário'],
    'Train lines':['Lignes de train', 'Bahnlinien', 'Treinlijnen', 'Líneas de tren', 'Linee ferroviarie', 'Linie kolejowe', 'Linhas de comboio'],
    'Metro lines':['Lignes de métro', 'U-Bahn-Linien', 'Metrolijnen', 'Líneas de metro', 'Linee metro', 'Linie metra', 'Linhas de metro'],
    'Tram lines':['Lignes de tram', 'Straßenbahnlinien', 'Tramlijnen', 'Líneas de tranvía', 'Linee tram', 'Linie tramwajowe', 'Linhas de elétrico'],
    'Bus routes':['Lignes de bus', 'Buslinien', 'Buslijnen', 'Líneas de autobús', 'Linee bus', 'Trasy autobusów', 'Linhas de autocarro'],
    'Coaches':['Autocars', 'Fernbusse', 'Touringcars', 'Autocares', 'Pullman', 'Autokary', 'Expressos'],
    'Boat routes':['Lignes de bateau', 'Schiffslinien', 'Bootroutes', 'Rutas de barco', 'Linee di battelli', 'Trasy statków', 'Rotas de barco'],
    'Trains':['Trains', 'Züge', 'Treinen', 'Trenes', 'Treni', 'Pociągi', 'Comboios'],
    'Metro & trams':['Métro & tramways', 'U-Bahn & Straßenbahn', 'Metro & trams', 'Metro y tranvías', 'Metro e tram', 'Metro i tramwaje', 'Metro e elétricos'],
    'Buses & coaches':['Bus & autocars', 'Busse & Fernbusse', 'Bussen & touringcars', 'Autobuses y autocares', 'Autobus e pullman', 'Autobusy i autokary', 'Autocarros e expressos'],
    'Vehicles':['Véhicules', 'Fahrzeuge', 'Voertuigen', 'Vehículos', 'Veicoli', 'Pojazdy', 'Veículos'],
    'Lines':['Lignes', 'Linien', 'Lijnen', 'Líneas', 'Linee', 'Linie', 'Linhas'],
    'Routes':['Itinéraires', 'Strecken', 'Routes', 'Rutas', 'Percorsi', 'Trasy', 'Percursos'],
    'A new version of the map is ready.':['Une nouvelle version de la carte est prête.', 'Eine neue Version der Karte ist da.', 'Er is een nieuwe versie van de kaart.', 'Hay una nueva versión del mapa.', 'È pronta una nuova versione della mappa.', 'Nowa wersja mapy jest gotowa.', 'Há uma nova versão do mapa.'],
    'Update':['Mettre à jour', 'Aktualisieren', 'Bijwerken', 'Actualizar', 'Aggiorna', 'Aktualizuj', 'Atualizar'],
    'Other':['Autres', 'Sonstige', 'Overig', 'Otros', 'Altro', 'Inne', 'Outros'],
    'Departures':['Départs', 'Abfahrten', 'Vertrek', 'Salidas', 'Partenze', 'Odjazdy', 'Partidas'],
    'Bus':['Bus', 'Bus', 'Bus', 'Autobús', 'Autobus', 'Autobus', 'Autocarro'],
    'Tram':['Tram', 'Straßenbahn', 'Tram', 'Tranvía', 'Tram', 'Tramwaj', 'Elétrico'],
    'Train':['Train', 'Zug', 'Trein', 'Tren', 'Treno', 'Pociąg', 'Comboio'],
    'Boat':['Bateau', 'Schiff', 'Boot', 'Barco', 'Battello', 'Statek', 'Barco'],
    'Vehicle':['Véhicule', 'Fahrzeug', 'Voertuig', 'Vehículo', 'Veicolo', 'Pojazd', 'Veículo'],
    // headings, sections
    'BUSES':['BUS', 'BUSSE', 'BUSSEN', 'AUTOBUSES', 'AUTOBUS', 'AUTOBUSY', 'AUTOCARROS'],
    'BIKES & SCOOTERS':['VÉLOS & TROTTINETTES', 'RÄDER & ROLLER', 'FIETSEN & STEPS', 'BICIS Y PATINETES', 'BICI E MONOPATTINI', 'ROWERY I HULAJNOGI', 'BICICLETAS E TROTINETES'],
    'Find':['Chercher', 'Suchen', 'Zoeken', 'Buscar', 'Cerca', 'Szukaj', 'Procurar'],
    'Search a stop, line or place':['Rechercher un arrêt, une ligne ou un lieu', 'Haltestelle, Linie oder Ort suchen', 'Zoek een halte, lijn of plaats', 'Buscar una parada, línea o lugar', 'Cerca fermata, linea o luogo', 'Szukaj przystanku, linii lub miejsca', 'Procurar paragem, linha ou lugar'],
    "What's moving here, as a list":['Ce qui circule ici, en liste', 'Was hier fährt, als Liste', 'Wat hier rijdt, als lijst', 'Lo que circula aquí, en lista', 'Cosa si muove qui, in elenco', 'Co tu jeździ – lista', 'O que circula aqui, em lista'],
    'Your stops':['Vos arrêts', 'Ihre Haltestellen', 'Jouw haltes', 'Tus paradas', 'Le tue fermate', 'Twoje przystanki', 'As suas paragens'],
    'Nothing live here yet':['Rien en direct ici pour l’instant', 'Hier noch nichts live', 'Hier nog niets live', 'Aún no hay nada en directo aquí', 'Ancora niente in tempo reale qui', 'Na razie nic na żywo', 'Ainda nada em tempo real aqui'],
    'Loading lines…':['Chargement des lignes…', 'Linien werden geladen…', 'Lijnen laden…', 'Cargando líneas…', 'Caricamento linee…', 'Wczytywanie linii…', 'A carregar linhas…'],
    // stop cards
    'Loading departures…':['Chargement des départs…', 'Abfahrten werden geladen…', 'Vertrektijden laden…', 'Cargando salidas…', 'Caricamento partenze…', 'Wczytywanie odjazdów…', 'A carregar partidas…'],
    'No departures from here in the next while.':['Aucun départ d’ici dans l’immédiat.', 'Von hier in nächster Zeit keine Abfahrten.', 'Hier voorlopig geen vertrek.', 'No hay salidas desde aquí por ahora.', 'Nessuna partenza da qui a breve.', 'Brak odjazdów w najbliższym czasie.', 'Sem partidas daqui para já.'],
    'No stop found here in the timetables.':['Aucun arrêt trouvé ici dans les horaires.', 'Hier keine Haltestelle im Fahrplan gefunden.', 'Hier geen halte gevonden in de dienstregeling.', 'No se encontró ninguna parada aquí en los horarios.', 'Nessuna fermata trovata qui negli orari.', 'Nie znaleziono tu przystanku w rozkładach.', 'Nenhuma paragem encontrada aqui nos horários.'],
    'Departures could not be loaded right now.':['Impossible de charger les départs pour le moment.', 'Abfahrten konnten gerade nicht geladen werden.', 'Vertrektijden konden nu niet worden geladen.', 'No se pudieron cargar las salidas ahora.', 'Impossibile caricare le partenze ora.', 'Nie udało się teraz wczytać odjazdów.', 'Não foi possível carregar as partidas agora.'],
    'due':['imminent', 'jetzt', 'nu', 'ya', 'in arrivo', 'teraz', 'agora'],
    'live':['en direct', 'live', 'live', 'en vivo', 'in tempo reale', 'na żywo', 'em tempo real'],
    'timetable':['horaire prévu', 'Fahrplan', 'dienstregeling', 'horario', 'orario', 'rozkład', 'horário'],
    // the vehicle card
    'live GPS':['GPS en direct', 'Live-GPS', 'live gps', 'GPS en vivo', 'GPS in tempo reale', 'GPS na żywo', 'GPS em tempo real'],
    'live timings':['horaires en direct', 'Echtzeit', 'realtime', 'horarios en vivo', 'orari in tempo reale', 'czasy na żywo', 'horários em tempo real'],
    'Follow':['Suivre', 'Folgen', 'Volgen', 'Seguir', 'Segui', 'Śledź', 'Seguir'],
    'Following':['Suivi', 'Wird verfolgt', 'Volgend', 'Siguiendo', 'Seguendo', 'Śledzę', 'A seguir'],
    'Share':['Partager', 'Teilen', 'Delen', 'Compartir', 'Condividi', 'Udostępnij', 'Partilhar'],
    'Loading its stops…':['Chargement des arrêts…', 'Haltestellen werden geladen…', 'Haltes laden…', 'Cargando paradas…', 'Caricamento fermate…', 'Wczytywanie przystanków…', 'A carregar paragens…'],
    'Link copied':['Lien copié', 'Link kopiert', 'Link gekopieerd', 'Enlace copiado', 'Link copiato', 'Link skopiowany', 'Ligação copiada'],
    // the how-to card
    'How to read the map':['Comment lire la carte', 'So liest man die Karte', 'Zo lees je de kaart', 'Cómo leer el mapa', 'Come leggere la mappa', 'Jak czytać mapę', 'Como ler o mapa'],
    'Solid: where the vehicle really is (live GPS)':['Plein : position réelle du véhicule (GPS en direct)', 'Gefüllt: wo das Fahrzeug wirklich ist (Live-GPS)', 'Gevuld: waar het voertuig echt is (live gps)', 'Relleno: dónde está realmente el vehículo (GPS en vivo)', 'Pieno: dove si trova davvero il veicolo (GPS in tempo reale)', 'Pełny: gdzie pojazd naprawdę jest (GPS na żywo)', 'Cheio: onde o veículo está realmente (GPS em tempo real)'],
    'Pale with a coloured edge: placed from the timetable (with live delays where the network shares them)':['Pâle avec un contour coloré : placé selon l’horaire (avec les retards en direct quand le réseau les partage)', 'Blass mit farbigem Rand: nach Fahrplan platziert (mit Live-Verspätungen, wo das Netz sie teilt)', 'Licht met gekleurde rand: geplaatst volgens de dienstregeling (met live vertragingen waar het net die deelt)', 'Pálido con borde de color: situado según el horario (con retrasos en vivo donde la red los comparte)', 'Chiaro con bordo colorato: posizionato secondo l’orario (con i ritardi in tempo reale dove la rete li condivide)', 'Blady z kolorową obwódką: umieszczony według rozkładu (z opóźnieniami na żywo, gdzie przewoźnik je udostępnia)', 'Claro com contorno colorido: colocado pelo horário (com atrasos em tempo real onde a rede os partilha)'],
    'HOWTO3':['Touchez un véhicule pour ses prochains arrêts ou pour le <b>suivre</b> · touchez un arrêt pour ses départs · <b>⌖</b> pour ce qui est près de vous', 'Fahrzeug antippen: nächste Halte oder <b>Folgen</b> · Haltestelle antippen: Abfahrten · <b>⌖</b>: was in der Nähe ist', 'Tik op een voertuig voor de volgende haltes of om het te <b>volgen</b> · tik op een halte voor vertrektijden · <b>⌖</b> voor wat in de buurt is', 'Toca un vehículo para ver sus próximas paradas o <b>seguirlo</b> · toca una parada para ver sus salidas · <b>⌖</b> para lo que tienes cerca', 'Tocca un veicolo per le prossime fermate o per <b>seguirlo</b> · tocca una fermata per le partenze · <b>⌖</b> per ciò che hai vicino', 'Dotknij pojazdu, by zobaczyć kolejne przystanki lub go <b>śledzić</b> · dotknij przystanku, by zobaczyć odjazdy · <b>⌖</b> – co jest w pobliżu', 'Toque num veículo para ver as próximas paragens ou <b>segui-lo</b> · toque numa paragem para ver as partidas · <b>⌖</b> para o que está perto de si'],
    'Got it':['Compris', 'Verstanden', 'Begrepen', 'Entendido', 'Ho capito', 'Rozumiem', 'Percebi'],
    'Install as an app':['Installer l’appli', 'Als App installieren', 'Installeren als app', 'Instalar como app', 'Installa come app', 'Zainstaluj jako aplikację', 'Instalar como app'],
    // outage notes (abroad)
    'Some live GPS feeds here aren’t available right now: vehicles are placed from the timetable instead.':['Certains flux GPS en direct ne sont pas disponibles pour le moment : les véhicules sont placés selon l’horaire.', 'Einige Live-GPS-Quellen sind gerade nicht verfügbar: Fahrzeuge werden stattdessen nach Fahrplan platziert.', 'Sommige live gps-bronnen zijn nu niet beschikbaar: voertuigen worden volgens de dienstregeling geplaatst.', 'Algunas fuentes de GPS en vivo no están disponibles ahora: los vehículos se sitúan según el horario.', 'Alcuni flussi GPS in tempo reale non sono disponibili ora: i veicoli sono posizionati secondo l’orario.', 'Niektóre źródła GPS na żywo są teraz niedostępne: pojazdy są umieszczane według rozkładu.', 'Algumas fontes de GPS em tempo real não estão disponíveis agora: os veículos são colocados pelo horário.'],
    'The European timetable service (Transitous) isn’t answering: some trams, buses and trains may be missing.':['Le service d’horaires européen (Transitous) ne répond pas : certains trams, bus et trains peuvent manquer.', 'Der europäische Fahrplandienst (Transitous) antwortet nicht: einige Straßenbahnen, Busse und Züge können fehlen.', 'De Europese dienstregelingservice (Transitous) reageert niet: sommige trams, bussen en treinen kunnen ontbreken.', 'El servicio europeo de horarios (Transitous) no responde: pueden faltar algunos tranvías, autobuses y trenes.', 'Il servizio europeo degli orari (Transitous) non risponde: alcuni tram, autobus e treni potrebbero mancare.', 'Europejski serwis rozkładów (Transitous) nie odpowiada: może brakować niektórych tramwajów, autobusów i pociągów.', 'O serviço europeu de horários (Transitous) não responde: podem faltar alguns elétricos, autocarros e comboios.'],
  };
  const i = L.indexOf(LANG);
  window.T = s => i < 0 ? s : (S[s] ? S[s][i] : s);
  // patterns with numbers or names in them: [English regex, [fr…pt] with $1…]
  const P = [
    [/^(.+) live map$/, ['$1 en direct', '$1 live', '$1 live', '$1 en directo', '$1 in tempo reale', '$1 na żywo', '$1 em tempo real']],
    [/^(\d+) min late$/, ['$1 min de retard', '+$1 Min.', '$1 min vertraagd', '$1 min de retraso', '$1 min di ritardo', 'opóźnienie $1 min', '$1 min de atraso']],
    [/^(\d+) min early$/, ['$1 min d’avance', '$1 Min. zu früh', '$1 min te vroeg', '$1 min antes', '$1 min in anticipo', '$1 min przed czasem', '$1 min adiantado']],
    [/^and (\d+) more notices? from the operators$/, ['et $1 autres avis des exploitants', 'und $1 weitere Hinweise der Betreiber', 'en nog $1 meldingen van de vervoerders', 'y $1 avisos más de los operadores', 'e altri $1 avvisi degli operatori', 'i jeszcze $1 komunikaty przewoźników', 'e mais $1 avisos dos operadores']],
    [/^(Tram|Bus|Metro|Train|Boat|Vehicle) ([^·]+)$/, null], // 'Tram B': the kind translated, the line's name kept
    [/^to (.+)$/, ['→ $1', '→ $1', '→ $1', '→ $1', '→ $1', '→ $1', '→ $1']],
  ];
  // the status line's counts ('7 trains · 463 trams, buses & ferries · updated 08:48'): nouns, one by one
  const W = {trains:['trains', 'Züge', 'treinen', 'trenes', 'treni', 'pociągi', 'comboios'], train:['train', 'Zug', 'trein', 'tren', 'treno', 'pociąg', 'comboio'],
    trams:['trams', 'Straßenbahnen', 'trams', 'tranvías', 'tram', 'tramwaje', 'elétricos'], buses:['bus', 'Busse', 'bussen', 'autobuses', 'autobus', 'autobusy', 'autocarros'],
    bus:['bus', 'Bus', 'bus', 'autobús', 'autobus', 'autobus', 'autocarro'], metros:['métros', 'U-Bahnen', 'metro’s', 'metros', 'metro', 'metro', 'metros'],
    ferries:['ferries', 'Fähren', 'veerboten', 'ferris', 'traghetti', 'promy', 'ferries'], coaches:['cars', 'Fernbusse', 'touringcars', 'autocares', 'pullman', 'autokary', 'expressos'],
    coach:['car', 'Fernbus', 'touringcar', 'autocar', 'pullman', 'autokar', 'expresso'], boats:['bateaux', 'Schiffe', 'boten', 'barcos', 'battelli', 'statki', 'barcos'],
    updated:['mis à jour', 'aktualisiert', 'bijgewerkt', 'actualizado', 'aggiornato', 'zaktualizowano', 'atualizado'], and:['et', 'und', 'en', 'y', 'e', 'i', 'e']};
  const one = s => { if(S[s]) return S[s][i];
    for(const [re, to] of P){ const m = s.match(re); if(!m) continue; return to ? s.replace(re, to[i]) : S[m[1]][i] + ' ' + m[2]; }
    return null; };
  // a text: whole if known, else its ' · ' parts one by one (a departure's 'B · live', a vehicle's 'TBM · live GPS')
  const tr = t => { const s = t.trim(); if(!s) return t; let out = one(s);
    if(out == null && s.includes(' · ')){ const parts = s.split(' · '), o = parts.map(x => one(x.trim()) ?? x); if(o.some((x, k) => x !== parts[k])) out = o.join(' · '); }
    return out == null ? t : t.replace(s, out); };
  // Polish counts take one form for 2–4 (not 12–14) and another for 5 and up: 'pociągi' 2–4, 'pociągów' 5+
  const PLG = {trains:'pociągów', trams:'tramwajów', buses:'autobusów', ferries:'promów', coaches:'autokarów', boats:'statków', metros:'metra'};
  const plural = (n, w) => { if(LANG !== 'pl' || !PLG[w]) return W[w][i]; const d = n % 10, h = n % 100; return d >= 2 && d <= 4 && !(h >= 12 && h <= 14) ? W[w][i] : PLG[w]; };
  // a status text node (' trains · ') follows its count, in bold: the count decides the form
  const trStatus = (t, n) => t.replace(/\b(trains|train|trams|buses|bus|metros|ferries|coaches|coach|boats)\b/g, w => plural(n, w)).replace(/ & /g, ' ' + W.and[i] + ' ').replace(/\bupdated\b/g, W.updated[i]);
  // where the pass looks: the panel's own words, never a stop's or line's name
  const SEL = '#ttl, #status, #mModes, .mcat-h, .dep-h, .deps small, .deps b, #station > .muted, #station .alerts small, #gfollow small, #gfollow button, #gfollow .ft, #favs h3, #vlist summary, .search label, #howto, #outage, #upd, #err';
  const done = new WeakMap();
  const pass = root => { if(i < 0 || !root) return; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n;
    while((n = w.nextNode())){ const el = n.parentElement; if(!el || !el.closest(SEL) || done.get(n) === n.nodeValue) continue;
      const v = el.closest('#status') && !S[n.nodeValue.trim()] ? trStatus(n.nodeValue, +((n.previousSibling && n.previousSibling.textContent) || '').replace(/\D/g, '') || 5) : tr(n.nodeValue); if(v !== n.nodeValue) n.nodeValue = v; done.set(n, n.nodeValue); } };
  window.I18N_PASS = pass;
  if(i >= 0) document.addEventListener('DOMContentLoaded', () => { document.documentElement.lang = LANG; const panel = document.getElementById('panel') || document.body; pass(panel);
    let q = false; new MutationObserver(() => { if(q) return; q = true; requestAnimationFrame(() => { q = false; pass(panel); }); }).observe(panel, {childList:true, subtree:true, characterData:true}); });
})();
