// Realistic fake Darwin boards (same JSON shape as the Live Departure Board REST service),
// with times around "now", for testing the relay and the maps before the real key arrives.
const pad = n => String(n).padStart(2, '0');
const hhmm = ms => { const d = new Date(ms); const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/London', hourCycle:'h23', hour:'2-digit', minute:'2-digit'}).formatToParts(d).map(x => [x.type, x.value])); return p.hour + ':' + p.minute; };

// a few real London routes: [operator, code, [[crs, name, minutesFromStart], ...]]
export const ROUTES = [
  ['Southern', 'SN', [['VIC','London Victoria',0],['CLJ','Clapham Junction',6],['ECR','East Croydon',15],['GTW','Gatwick Airport',30],['BTN','Brighton',58]]],
  ['Thameslink', 'TL', [['BDM','Bedford',0],['LTN','Luton Airport Parkway',20],['STP','London St Pancras International',42],['ZFD','Farringdon',46],['BFR','London Blackfriars',51],['LBG','London Bridge',55],['ECR','East Croydon',68],['GTW','Gatwick Airport',82]]],
  ['South Western Railway', 'SW', [['WAT','London Waterloo',0],['VXH','Vauxhall',3],['CLJ','Clapham Junction',7],['WIM','Wimbledon',13],['SUR','Surbiton',20],['WOK','Woking',33]]],
  ['Southeastern', 'SE', [['CHX','London Charing Cross',0],['WAE','London Waterloo East',2],['LBG','London Bridge',6],['LEW','Lewisham',14],['DFD','Dartford',33]]],
  ['c2c', 'CC', [['FST','London Fenchurch Street',0],['LHS','Limehouse',4],['WHM','West Ham',8],['BKG','Barking',13],['UPM','Upminster',21]]],
  ['Greater Anglia', 'LE', [['LST','London Liverpool Street',0],['SRA','Stratford',7],['RMF','Romford',18],['SNF','Shenfield',29],['CHM','Chelmsford',38]]],
];

// trains on each route, starting every `every` minutes; delay in minutes for some
export function boards(now = Date.now(), every = 12){
  const services = [];
  ROUTES.forEach(([op, code, stops], ri) => {
    for(let k = -6; k <= 3; k++){
      const start = now + (k*every - ri*3)*60000, delay = (k + ri) % 4 === 0 ? 4 : 0;
      services.push({op, code, stops, start, delay, id:`${code}${ri}${k + 10}`});
    }
  });
  const byCrs = {};
  for(const s of services){
    s.stops.forEach(([crs, name], i) => {
      const t = s.start + s.stops[i][2]*60000;
      if(t + s.delay*60000 < now - 60000) return; // already left this station: not on its board
      const cp = ([c, n, m]) => { const st = s.start + m*60000, done = st + s.delay*60000 < now;
        return {locationName:n, crs:c, st:hhmm(st), et:done ? null : (s.delay ? hhmm(st + s.delay*60000) : 'On time'), at:done ? (s.delay ? hhmm(st + s.delay*60000) : 'On time') : null}; };
      (byCrs[crs] ||= []).push({
        std:hhmm(t), etd:s.delay ? hhmm(t + s.delay*60000) : 'On time', platform:String(1 + (i % 9)),
        operator:s.op, operatorCode:s.code, serviceID:s.id + crs, isCancelled:false, // like Darwin: a different id on every board
        delayReason:s.delay ? 'This train has been delayed by a signalling problem' : null,
        origin:[{locationName:s.stops[0][1], crs:s.stops[0][0]}], destination:[{locationName:s.stops.at(-1)[1], crs:s.stops.at(-1)[0]}],
        previousCallingPoints:i ? [{callingPoint:s.stops.slice(0, i).map(cp)}] : undefined,
        subsequentCallingPoints:i < s.stops.length - 1 ? [{callingPoint:s.stops.slice(i + 1).map(cp)}] : undefined,
        _t:t,
      });
    });
  }
  const out = {};
  for(const [crs, list] of Object.entries(byCrs)){
    list.sort((a, b) => a._t - b._t); list.forEach(x => delete x._t);
    out[crs] = {generatedAt:new Date(now).toISOString(), locationName:list[0] && crs, crs, trainServices:list.slice(0, 10)};
  }
  return out;
}
