/* Gedeelde kern van de kaartpagina en de instellingenpagina.
 *
 * Hierin zit alles wat allebei nodig hebben: waar de kaart op de aarde ligt,
 * het ontsleutelen, de kaart zelf met zijn achtergronden, en de vectorlaag.
 * Wat maar op één pagina thuishoort — gps, zoeken, uitlijnen — staat daar.
 *
 * Een pagina mag deze haken invullen, elk is vrijblijvend:
 *   melden(tekst, soort)   iets in de statusbalk zetten
 *   naOntsleutelen()       de kaart is er
 *   naTekenen()            de plaatsing is veranderd
 *   naVector()             de vectorlaag staat op de kaart
 */

/* ------------------------------------------------------------------ *
 * 1. De plaatsing van de kaart op de aarde.
 *    lat/lon = middelpunt, w/h = breedte/hoogte in meter, rot = graden
 *    met de klok mee.
 *
 *    START is enkel de terugval. De geldende plaatsing staat in
 *    plaatsing.json, met een versienummer. Verhoog dat nummer en elk
 *    toestel laat zijn eigen bijstelling los en neemt de nieuwe over --
 *    zonder die versie blijft wie ooit zelf geschoven heeft op zijn
 *    eigen waarde hangen en bereikt een nieuwe uitlijning hem nooit.
 * ------------------------------------------------------------------ */
const START = { lat: 51.1862115, lon: 4.2085574, w: 1006, h: 912, rot: 0 };

/* De pagina kan meer dan één kaart tonen; kies met ?kaart=<sleutel>.
   Een kaart heeft altijd een vectorlaag, en soms een gescande plattegrond
   eronder met een eigen plaatsing. */
const KAARTEN = {
  wtc: { titel:'WTC — straatnamen', vector:'plan.enc',
         beeld:'kaart.enc', plaatsing:'plaatsing.json' },
  leopoldsburg: { titel:'Leopoldsburg', vector:'leopoldsburg.enc' },
  houthulst: { titel:'Houthulst (proef)', vector:'houthulst.enc' }
};
const KAARTSLEUTEL = (new URLSearchParams(location.search).get('kaart') || 'wtc');
const KAART = KAARTEN[KAARTSLEUTEL] || KAARTEN.wtc;

const PLAATSING = KAART.plaatsing;
const BESTAND = KAART.beeld;    // gemaakt met: node versleutel.mjs kaart.webp <wachtwoord>
const VECTOR  = KAART.vector;   // gemaakt met: node versleutel.mjs plan.geojson <wachtwoord>
const RONDES  = 600000;         // moet gelijk zijn aan versleutel.mjs
/* ------------------------------------------------------------------ */

let melden = () => {}, naOntsleutelen = () => {}, naTekenen = () => {}, naVector = () => {};

const KEY = 'wtc_plaatsing_v1', SLEUTELKEY = 'wtc_ww_v1';
const VELDEN = ['lat','lon','w','h','rot'];
const kies = o => Object.fromEntries(
      VELDEN.filter(k => o && typeof o[k] === 'number').map(k => [k, o[k]]));
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)); } catch(e){ return null; } };

let P = Object.assign({}, START, kies(load()));
let gepubliceerd = null;          // wat er in plaatsing.json staat
let greep = null;                 // de sleepgreep van de instellingenpagina

/* --- meetkunde: middelpunt + afmeting + draaiing -> vier hoeken --- */
const M_LAT = 111320;
const mLon = lat => 111320 * Math.cos(lat * Math.PI/180);

function hoeken(p){
  const t = p.rot * Math.PI/180, c = Math.cos(t), s = Math.sin(t);
  const draai = (x,y) => [x*c + y*s, -x*s + y*c];          // met de klok mee
  const naarPunt = ([oost,noord]) =>
        L.latLng(p.lat + noord/M_LAT, p.lon + oost/mLon(p.lat));
  const hw = p.w/2, hh = p.h/2;
  return {
    lb: naarPunt(draai(-hw,  hh)),   // linksboven
    rb: naarPunt(draai( hw,  hh)),   // rechtsboven
    lo: naarPunt(draai(-hw, -hh)),   // linksonder
    ro: naarPunt(draai( hw, -hh))
  };
}
const kader = () => L.latLngBounds(Object.values(hoeken(P))).pad(.05);

/* --- kaart en achtergronden --- */
const map = L.map('map', { zoomSnap:.25, zoomControl:false, maxZoom:22, attributionControl:true });
L.control.zoom({ position:'topleft' }).addTo(map);
map.attributionControl.setPrefix('');

const lucht = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { maxZoom:22, maxNativeZoom:19, attribution:'Luchtfoto: Esri, Maxar' });
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  { maxZoom:22, maxNativeZoom:19, attribution:'&copy; OpenStreetMap' });
const LEEG_TEGEL = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==';
const leeg = L.tileLayer(LEEG_TEGEL, { attribution:'' });

const lagenkiezer = L.control.layers({ 'Geen achtergrond':leeg, 'Luchtfoto':lucht, 'OpenStreetMap':osm },
                 null, { position:'topright', collapsed:true }).addTo(map);
(window.ACHTERGROND === 'lucht' ? lucht : leeg).addTo(map);
map.fitBounds(kader());

/* ------------------------------------------------------------------ *
 * 2. Ontsleutelen. Het bestand is AES-256-GCM, sleutel uit PBKDF2.
 *    Zonder het juiste wachtwoord komt er geen beeld uit — dit is geen
 *    schermpje dat je wegklikt.
 * ------------------------------------------------------------------ */
const SOORTEN = { 1:'image/webp', 2:'image/png', 3:'image/jpeg', 4:'application/json' };

async function ontsleutelRuw(bestand, wachtwoord){
  const res = await fetch(bestand);
  if (!res.ok) throw new Error('weg');
  const b = new Uint8Array(await res.arrayBuffer());
  if (b.length < 34 || String.fromCharCode(b[0],b[1],b[2],b[3]) !== 'WTC1') throw new Error('stuk');

  const soort = SOORTEN[b[4]] || 'image/webp';
  const salt = b.slice(5,21), iv = b.slice(21,33), data = b.slice(33);

  const basis = await crypto.subtle.importKey(
        'raw', new TextEncoder().encode(wachtwoord), 'PBKDF2', false, ['deriveKey']);
  const sleutel = await crypto.subtle.deriveKey(
        { name:'PBKDF2', salt, iterations:RONDES, hash:'SHA-256' }, basis,
        { name:'AES-GCM', length:256 }, false, ['decrypt']);
  const plat = await crypto.subtle.decrypt({ name:'AES-GCM', iv }, sleutel, data);

  return { soort, plat };
}

async function ontsleutel(wachtwoord){
  const { soort, plat } = await ontsleutelRuw(BESTAND, wachtwoord);
  return URL.createObjectURL(new Blob([plat], { type:soort }));
}

/* Een kaartlaag van een megabyte krimpt ingepakt tot een vijfde. Herkennen
   doen we aan de gzip-kop, zodat oudere bestanden gewoon blijven werken. */
async function uitpakken(plat){
  const b = new Uint8Array(plat);
  if (!(b[0] === 0x1f && b[1] === 0x8b)) return b;
  if (typeof DecompressionStream === 'undefined')
    throw new Error('Deze browser kan ingepakte kaartlagen niet openen');
  const stroom = new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stroom).arrayBuffer());
}

// De vectorlaag is platte tekst zodra hij ontsleuteld is; hij zit achter
// hetzelfde wachtwoord als het beeld, en is meteen de toets of dat klopt.
async function ontsleutelVector(wachtwoord){
  const { plat } = await ontsleutelRuw(VECTOR, wachtwoord);
  return JSON.parse(new TextDecoder().decode(await uitpakken(plat)));
}

/* welke kaart je opent, kies je voor het slot */
const keuze = document.getElementById('kaartkeuze');
if (keuze){
  for (const [sleutel, k] of Object.entries(KAARTEN)){
    const o = document.createElement('option');
    o.value = sleutel; o.textContent = k.titel;
    if (sleutel === KAARTSLEUTEL) o.selected = true;
    keuze.appendChild(o);
  }
  keuze.onchange = () => {
    const u = new URL(location.href);
    u.searchParams.set('kaart', keuze.value);
    location.href = u.toString();
  };
}
document.title = KAART.titel;
const kop = document.querySelector('#slot h1');
if (kop) kop.textContent = KAART.titel;

const slot = document.getElementById('slot');
const fout = document.getElementById('slotfout');
const knop = document.getElementById('slotknop');
const veld = document.getElementById('ww');

async function probeer(wachtwoord, stil){
  knop.disabled = true; fout.textContent = '';
  if (!stil) knop.textContent = 'Ontgrendelen…';
  await new Promise(r => setTimeout(r, 20));           // even laten tekenen
  try {
    const data = await ontsleutelVector(wachtwoord);        // ook de wachtwoordtoets
    let url = null;
    if (BESTAND){ try { url = await ontsleutel(wachtwoord); } catch(e){ url = null; } }
    try { localStorage.setItem(SLEUTELKEY, wachtwoord); } catch(e){}
    slot.classList.add('weg');
    start(url);
    bouwVector(data);
    return true;
  } catch(e){
    try { localStorage.removeItem(SLEUTELKEY); } catch(err){}
    fout.textContent = e.message === 'weg'  ? 'Bestand ' + VECTOR + ' niet gevonden.'
                     : e.message === 'stuk' ? 'Bestand ' + VECTOR + ' is beschadigd.'
                     : e.message.startsWith('Deze browser') ? e.message
                     : 'Wachtwoord klopt niet.';
    knop.disabled = false; knop.textContent = 'Openen';
    veld.value = ''; if (!stil) veld.focus();
    return false;
  }
}

document.getElementById('slotform').addEventListener('submit', e => {
  e.preventDefault();
  if (veld.value) probeer(veld.value.trim(), false);
});

if (!window.isSecureContext || !crypto.subtle){
  fout.textContent = 'Vereist https. Open de pagina via GitHub Pages of localhost.';
  knop.disabled = true;
} else {
  const bewaard = (() => { try { return localStorage.getItem(SLEUTELKEY); } catch(e){ return null; } })();
  if (bewaard) probeer(bewaard, true).then(ok => { if (!ok) fout.textContent = ''; });
  else setTimeout(() => veld.focus(), 300);
}

/* ------------------------------------------------------------------ *
 * 3. Vanaf hier draait alles pas als de kaart ontsleuteld is.
 * ------------------------------------------------------------------ */
let overlay = null, verhouding = P.w / P.h, verhoudingVast = true;
let overlayVerplaatst = false;      // heeft iemand de kaart al zelf versleept?

const doorzicht = () => {
  const el = document.getElementById('op');
  return el ? +el.value : 1;
};

function start(url){
  if (url){
    const h = hoeken(P);
    overlay = L.imageOverlay.rotated(url, h.lb, h.rb, h.lo,
                { opacity:doorzicht(), interactive:false }).addTo(map);

    const proef = new Image();                  // beeldverhouding uit het bestand
    proef.onload = () => {
      verhouding = proef.naturalWidth / proef.naturalHeight;
      // alleen bijstellen als niemand -- publicatie noch toestel -- iets gezegd heeft
      if (verhoudingVast && !load() && !gepubliceerd){ P.h = P.w / verhouding; teken(); }
    };
    proef.src = url;
    map.fitBounds(kader());
  }
  naOntsleutelen();
}

function teken(){
  const h = hoeken(P);
  if (overlay) overlay.reposition(h.lb, h.rb, h.lo);
  plaatsVector();
  if (greep) greep.setLatLng([P.lat, P.lon]);
  naTekenen();
}

/* Wat je op dit toestel bijstelt, wordt bewaard mét de versie waarop het
   gebaseerd is. Komt er later een nieuwere publicatie, dan wint die. */
function bewaar(){
  try { localStorage.setItem(KEY, JSON.stringify(
        Object.assign(kies(P), { basis: gepubliceerd ? gepubliceerd.versie : 0 }))); } catch(e){}
}

const opEl = document.getElementById('op');
if (opEl) opEl.oninput = e => { if (overlay) overlay.setOpacity(+e.target.value); };

/* --- de gepubliceerde plaatsing ophalen --- */
async function haalPlaatsing(){
  if (!PLAATSING) return;
  try {
    const res = await fetch(PLAATSING, { cache:'no-cache' });
    if (!res.ok) return;
    const g = await res.json();
    if (typeof g.lat !== 'number' || typeof g.versie !== 'number') return;
    gepubliceerd = g;

    const eigen = load();
    if (eigen && (eigen.basis || 0) >= g.versie) return;   // dit toestel is nieuwer
    try { localStorage.removeItem(KEY); } catch(e){}
    P = Object.assign({}, START, kies(g));
    verhouding = P.w / P.h;
    teken();
    if (!overlay) map.fitBounds(kader());
  } catch(e){}
}

/* ------------------------------------------------------------------ *
 * 4. De vectorlaag: straten, gebouwen en zones als echte kaartdata.
 *    De coördinaten in plan.enc lopen van 0 tot 1 over het kader van
 *    de plattegrond, dus dezelfde START-plaatsing geldt voor allebei.
 * ------------------------------------------------------------------ */
let plan = null;                                   // de ontsleutelde GeoJSON
/* De kaartlaag kan in twee stelsels staan. 'wgs84' is echte lengte- en
   breedtegraad: die ligt al goed en beweegt niet mee met de uitlijning.
   'plan' is de oude vorm, genormaliseerd over het kader van de tekening. */
let stelsel = 'plan', refLat = START.lat, refLon = START.lon;
const doek = L.canvas({ padding:.4 });
const gTerrein = L.layerGroup(), gZone = L.layerGroup(), gVlak = L.layerGroup(),
      gLijn = L.layerGroup(), gStraat = L.layerGroup(), gCode = L.layerGroup();
const vormen = [];                                 // {laag, uv} om te herplaatsen
const etiketten = [];                              // {marker, uv}
let straten = [];                                  // {naam, delen:[[a,b],…]} in meters
const straatEtiket = [];                           // om per zoomstand te tonen of te verbergen
const STRAATBREEDTE = 7;    // meter; de straat wordt als een band getekend en
const BAND_MIN = 2, BAND_MAX = 64;   // schaalt dus mee met de zoom
const straatband = [];      // de banden, om hun dikte bij te stellen
const CODE_VANAF = 18;      // gebouwcodes pas van dichtbij
const VLAK_VANAF = 15.5;    // bij duizenden gebouwen pas van dichtbij tekenen
const VEEL_VLAKKEN = 800;
const NAAM_VANAF = 16.5;    // van hieraf één naam per straat
const ALLE_VANAF = 17.5;    // van hieraf elk naambordje

/* genormaliseerde plancoördinaat -> plaatselijke meters (oost, noord), vóór draaiing */
const naarMeter = ([u,v]) => [ (u - .5) * P.w, (.5 - v) * P.h ];

/* Eén ingang voor allebei de stelsels. */
const punt  = c => stelsel === 'wgs84' ? L.latLng(c[1], c[0]) : naarLatLng(c);
const meter = c => stelsel === 'wgs84'
      ? [ (c[0] - refLon) * mLon(refLat), (c[1] - refLat) * M_LAT ]
      : naarMeter(c);
const puntMeter = ll => stelsel === 'wgs84'
      ? [ (ll.lng - refLon) * mLon(refLat), (ll.lat - refLat) * M_LAT ]
      : naarVlak(ll);

function naarLatLng([u,v]){
  const t = P.rot * Math.PI/180, c = Math.cos(t), s = Math.sin(t);
  const [x,y] = naarMeter([u,v]);
  return L.latLng(P.lat + (-x*s + y*c)/M_LAT, P.lon + (x*c + y*s)/mLon(P.lat));
}

/* een punt op de aarde terug naar de genormaliseerde plancoördinaat */
function naarUV(ll){
  const [x, y] = naarVlak(ll);
  return [x / P.w + .5, .5 - y / P.h];
}

/* omgekeerd: een gps-punt terug naar het vlakke meterstelsel van het plan */
function naarVlak(ll){
  const oost  = (ll.lng - P.lon) * mLon(P.lat);
  const noord = (ll.lat - P.lat) * M_LAT;
  const t = -P.rot * Math.PI/180, c = Math.cos(t), s = Math.sin(t);
  return [ oost*c + noord*s, -oost*s + noord*c ];
}

const STIJL = {
  zone:      { color:'#d9534f', weight:1,   fillColor:'#d9534f', fillOpacity:.10 },
  gebouw:    { color:'#46525f', weight:1,   fillColor:'#8d99a6', fillOpacity:.60 },
  bijgebouw: { color:'#6e7984', weight:.8,  fillColor:'#c2cad2', fillOpacity:.50 },
  /* een straat is wit met een grijze omboording, zoals op een gewone kaart:
     eerst de brede grijze band, daar de smallere witte overheen */
  straatrand: { color:'#9aa5b1', opacity:.95, lineCap:'round', lineJoin:'round' },
  straat:     { color:'#ffffff', opacity:1,   lineCap:'round', lineJoin:'round' },
  lijn:      { color:'#7c8894', weight:1,   opacity:.85 },   // grens, percelen, wegranden
  boomrand:  { color:'#5c8a63', weight:1.2, opacity:.85 },
  spoor:     { color:'#6b7683', weight:1.5, opacity:.8, dashArray:'6 5' },
  /* de oefenkaart: wat je niet weet als je alleen de straten kent */
  ftx_gesloten: { color:'#8b5cd6', weight:4,   opacity:.85 },              // niet toegankelijk
  ftx_slecht:   { color:'#e08010', weight:4,   opacity:.85, dashArray:'9 7' },
  ftx_tevoet:   { color:'#1f9d3a', weight:5,   opacity:.95 },              // enkel te voet
  ftx_poort:    { color:'#d92020', weight:5,   opacity:.95 }               // geen doorgang
};
const TERREIN = { lijn:1, boomrand:1, spoor:1,
                  ftx_gesloten:1, ftx_slecht:1, ftx_tevoet:1, ftx_poort:1 };

function bouwVector(data){
  if (!data || !data.features) return;
  plan = data;
  if (data.stelsel === 'wgs84'){
    stelsel = 'wgs84';
    const pl = data.plaatsing;
    if (pl){ refLat = pl.lat; refLon = pl.lon; }
  }
  const perStraat = {};

  for (const k of data.features){
    const s = k.properties.soort, g = k.geometry;

    if (g.type === 'Polygon'){
      const uv = g.coordinates[0];
      const stijl = s === 'ftx_gebouw'
            ? (k.properties.echt ? { color:'#c2410c', weight:2, fillColor:'#f97316', fillOpacity:.35 }
                                 : { color:'#475569', weight:2, fillColor:'#64748b', fillOpacity:.35, dashArray:'5 4' })
            : (STIJL[s] || STIJL.gebouw);
      const laag = L.polygon(uv.map(punt),
                     Object.assign({ renderer:doek, interactive:s !== 'zone' }, stijl));
      if (s === 'ftx_gebouw')
        laag.bindTooltip(k.properties.echt ? 'reëel gebouw' : 'fictief gebouw', { direction:'top' });
      if (k.properties.code) laag.bindTooltip(k.properties.code, { direction:'top' });
      laag.addTo(s === 'zone' ? gZone : gVlak);
      vormen.push({ laag, uv, ring:true, kenmerk:k });
      if (k.properties.code){
        const m = zwaartepunt(uv);
        etiketten.push(voegEtiket(m, k.properties.code, 'code', gCode));
      }

    } else if (g.type === 'LineString' && TERREIN[s]){
      const uv = g.coordinates;
      const laag = L.polyline(uv.map(punt),
                     Object.assign({ renderer:doek, interactive:false }, STIJL[s])).addTo(gTerrein);
      vormen.push({ laag, uv, ring:false });

    } else if (g.type === 'LineString'){
      const uv = g.coordinates;
      const rand = L.polyline(uv.map(punt),
                     Object.assign({ renderer:doek, interactive:false,
                                     weight:bandDikte() + 2.5 }, STIJL.straatrand)).addTo(gLijn);
      const laag = L.polyline(uv.map(punt),
                     Object.assign({ renderer:doek, weight:bandDikte() }, STIJL.straat)).addTo(gLijn);
      vormen.push({ laag:rand, uv, ring:false });
      vormen.push({ laag, uv, ring:false });
      straatband.push(rand, laag);
      const naam = k.properties.naam;
      (perStraat[naam] = perStraat[naam] || []).push(uv);
      const e = voegEtiket(k.properties.labelpunt || midden(uv), naam, 'straat', gStraat);
      e.naam = naam; e.lengte = stukLengte(uv); e.langs = uv;
      e.kenmerk = k;                              // om te kunnen bewerken
      if (typeof k.properties.labelhoek === 'number') e.vasteHoek = k.properties.labelhoek;
      etiketten.push(e); straatEtiket.push(e);

    } else if (g.type === 'Point'){
      etiketten.push(voegEtiket(g.coordinates, k.properties.code, 'code', gCode));
    }
  }

  straten = Object.entries(perStraat).map(([naam, delen]) => ({ naam, delen }));
  straten.sort((a,b) => a.naam.localeCompare(b.naam, 'nl'));

  // per straat draagt het langste stuk de naam die als eerste verschijnt
  const langste = {};
  for (const e of straatEtiket)
    if (!langste[e.naam] || e.lengte > langste[e.naam].lengte) langste[e.naam] = e;
  for (const e of straatEtiket) e.hoofd = (langste[e.naam] === e);
  straatEtiket.sort((a,b) => (b.hoofd - a.hoofd) || (b.lengte - a.lengte));

  if (/OpenStreetMap/i.test(data.bron || ''))
    map.attributionControl.addAttribution('Gebouwen deels &copy; OpenStreetMap, ODbL');
  gTerrein.addTo(map); gZone.addTo(map); gVlak.addTo(map); gLijn.addTo(map); gStraat.addTo(map);
  lagenkiezer.addOverlay(gTerrein, 'Terrein');
  lagenkiezer.addOverlay(gZone,   'Zones');
  lagenkiezer.addOverlay(gVlak,   'Gebouwen');
  lagenkiezer.addOverlay(gLijn,   'Straten');
  lagenkiezer.addOverlay(gStraat, 'Straatnamen');
  lagenkiezer.addOverlay(gCode,   'Gebouwcodes');
  // De vectorlaag draagt de namen nu zelf; de plattegrond eronder zou ze een
  // tweede keer tonen. Hij staat dus uit, maar wel achter een eigen knop --
  // in het lagenmenu was hij niet te vinden.
  if (overlay){ lagenkiezer.addOverlay(overlay, 'Plattegrond'); map.removeLayer(overlay); }
  const knop = document.getElementById('btnPlan');
  if (knop && overlay){
    knop.hidden = false;
    knop.onclick = () => {
      const aan = !map.hasLayer(overlay);
      if (aan) overlay.addTo(map); else map.removeLayer(overlay);
      knop.setAttribute('aria-pressed', aan);
      melden(aan ? 'Plattegrond eronder' : 'Alleen de kaartlaag');
    };
  }
  if (stelsel === 'wgs84' && !overlayVerplaatst){
    const b = L.latLngBounds([]);
    gVlak.eachLayer(l => b.extend(l.getBounds()));
    gTerrein.eachLayer(l => b.extend(l.getBounds()));
    if (b.isValid()) map.fitBounds(b.pad(.04));
  }
  veelVlakken = gVlak.getLayers().length > VEEL_VLAKKEN;
  regelBand();
  regelZoom();
  naVector();
  melden(straten.length + ' straten geladen');
}

function voegEtiket(uv, tekst, soort, groep){
  const m = L.marker(punt(uv), { interactive:false, keyboard:false,
              icon: L.divIcon({ className:'etiket ' + soort, iconSize:[0,0],
                                html:'<span>' + ontsmet(tekst) + '</span>' }) }).addTo(groep);
  return { marker:m, uv };
}

/* Een straatnaam hoort langs zijn straat te liggen, en nooit op zijn kop.
   De hoek is die van het lijnstuk op het scherm; die verandert alleen als de
   plaatsing draait, niet bij zoomen. */
function draaiEtiket(e){
  if (typeof e.vasteHoek === 'number'){          // met de hand gezet
    e.hoek = e.vasteHoek;
    const el = e.marker.getElement() && e.marker.getElement().firstChild;
    if (el) el.style.transform = 'translate(-50%,-50%) rotate(' + e.hoek.toFixed(1) + 'deg)';
    return;
  }
  if (!e.langs || e.langs.length < 2) return;
  const a = map.project(punt(e.langs[0]), 18);
  const b = map.project(punt(e.langs[e.langs.length - 1]), 18);
  let hoek = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
  if (hoek > 90) hoek -= 180;
  if (hoek < -90) hoek += 180;
  e.hoek = hoek;
  const span = e.marker.getElement() && e.marker.getElement().firstChild;
  if (span) span.style.transform = 'translate(-50%,-50%) rotate(' + hoek.toFixed(1) + 'deg)';
}
const ontsmet = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function zwaartepunt(ring){
  let x = 0, y = 0;
  for (const [u,v] of ring){ x += u; y += v; }
  return [x/ring.length, y/ring.length];
}
const midden = uv => [ (uv[0][0] + uv[uv.length-1][0])/2, (uv[0][1] + uv[uv.length-1][1])/2 ];

function stukLengte(uv){                           // in meter, over het hele lijnstuk
  let s = 0;
  for (let i = 0; i < uv.length-1; i++){
    const a = meter(uv[i]), b = meter(uv[i+1]);
    s += Math.hypot(b[0]-a[0], b[1]-a[1]);
  }
  return s;
}

/* de plaatsing is veranderd (uitlijnen) — alles opnieuw op de aarde zetten */
function plaatsVector(){
  if (stelsel === 'wgs84'){          // ligt al op de aarde; de uitlijning raakt hem niet
    for (const e of etiketten) draaiEtiket(e);
    return;
  }
  for (const v of vormen)
    v.laag.setLatLngs(v.ring ? [v.uv.map(punt)] : v.uv.map(punt));
  for (const e of etiketten){ e.marker.setLatLng(punt(e.uv)); draaiEtiket(e); }
}

/* Van ver zijn 91 naambordjes één zwarte vlek. Van dichtbij mag alles.
   Daartussen: één naam per straat, op zijn langste stuk. */
let veelVlakken = false;
function regelZoom(){
  const z = map.getZoom();
  if (veelVlakken){
    const wil = z >= VLAK_VANAF;
    if (wil && !map.hasLayer(gVlak)) gVlak.addTo(map);
    if (!wil && map.hasLayer(gVlak)) map.removeLayer(gVlak);
  }
  const codes = z >= CODE_VANAF;
  if (codes && !map.hasLayer(gCode)) gCode.addTo(map);
  if (!codes && map.hasLayer(gCode)) map.removeLayer(gCode);

  // Bordjes die elkaar overlappen helpen niemand. De belangrijkste straat komt
  // eerst aan bod (straatEtiket is daarop gesorteerd), dus die wint een plek.
  // Dezelfde naam moet verder uit elkaar staan dan twee verschillende.
  const gehouden = [];
  const breed = e => 3.6 * e.naam.length + 16;      // ruwe breedte van het bordje
  for (const e of straatEtiket){
    let wil = z >= ALLE_VANAF || (z >= NAAM_VANAF && e.hoofd);
    let q = null;
    if (wil){
      q = map.latLngToContainerPoint(e.marker.getLatLng());
      if (q.x < -200 || q.y < -200 || q.x > map.getSize().x + 200 || q.y > map.getSize().y + 200){
        wil = false;                                 // buiten beeld hoeft niet
      } else for (const g of gehouden){
        const nodig = g.naam === e.naam ? 150 : (breed(e) + breed(g.el)) / 2 + 10;
        if (q.distanceTo(g.punt) < nodig){ wil = false; break; }
      }
    }
    if (wil) gehouden.push({ naam:e.naam, el:e, punt:q });
    if (wil && !gStraat.hasLayer(e.marker)){ gStraat.addLayer(e.marker); draaiEtiket(e); }
    if (!wil && gStraat.hasLayer(e.marker)) gStraat.removeLayer(e.marker);
  }
}
map.on('zoomend moveend', regelZoom);
/* Een straat is geen lijn maar een strook van een meter of zeven. Ze wordt dus
   in meters getekend en niet in beeldpunten: zoom je in, dan wordt ze breder,
   net als de gebouwen eronder. */
function pxPerMeter(){
  const c = map.getCenter(), z = map.getZoom();
  const a = map.project(c, z), b = map.project(L.latLng(c.lat, c.lng + .001), z);
  return Math.abs(b.x - a.x) / (.001 * mLon(c.lat));
}
function bandDikte(){
  return Math.max(BAND_MIN, Math.min(BAND_MAX, STRAATBREEDTE * pxPerMeter()));
}
function regelBand(){
  const d = bandDikte();
  for (let i = 0; i < straatband.length; i += 2){
    straatband[i].setStyle({ weight:d + 2.5 });      // de omboording
    straatband[i+1].setStyle({ weight:d });          // het witte wegdek
  }
}
map.on('zoomend', regelBand);

/* ------------------------- in welke straat sta ik ------------------- */
function afstandTotStuk(p, a, b){
  const dx = b[0]-a[0], dy = b[1]-a[1], L2 = dx*dx + dy*dy;
  let t = L2 ? ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / L2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0]+t*dx), p[1] - (a[1]+t*dy));
}

function dichtsteStraat(ll){
  if (!straten.length) return null;
  const p = puntMeter(ll);
  let best = null, bestd = Infinity;
  for (const s of straten)
    for (const deel of s.delen)
      for (let i = 0; i < deel.length-1; i++){
        const d = afstandTotStuk(p, meter(deel[i]), meter(deel[i+1]));
        if (d < bestd){ bestd = d; best = s.naam; }
      }
  return { naam:best, afstand:bestd };
}

/* -------------------------- offline cache ------------------------- */
if ('serviceWorker' in navigator && location.protocol === 'https:')
  navigator.serviceWorker.register('sw.js').catch(()=>{});

haalPlaatsing();
