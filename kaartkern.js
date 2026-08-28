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

const PLAATSING = 'plaatsing.json';
const BESTAND = 'kaart.enc';   // gemaakt met: node versleutel.mjs kaart.webp <wachtwoord>
const VECTOR  = 'plan.enc';    // gemaakt met: node versleutel.mjs plan.geojson <wachtwoord>
const RONDES  = 600000;        // moet gelijk zijn aan versleutel.mjs
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

// De vectorlaag is platte tekst zodra hij ontsleuteld is; hij zit achter
// hetzelfde wachtwoord als het beeld. Ontbreekt hij, dan werkt de rest gewoon.
async function ontsleutelVector(wachtwoord){
  try {
    const { plat } = await ontsleutelRuw(VECTOR, wachtwoord);
    return JSON.parse(new TextDecoder().decode(plat));
  } catch(e){ return null; }
}

const slot = document.getElementById('slot');
const fout = document.getElementById('slotfout');
const knop = document.getElementById('slotknop');
const veld = document.getElementById('ww');

async function probeer(wachtwoord, stil){
  knop.disabled = true; fout.textContent = '';
  if (!stil) knop.textContent = 'Ontgrendelen…';
  await new Promise(r => setTimeout(r, 20));           // even laten tekenen
  try {
    const url = await ontsleutel(wachtwoord);
    try { localStorage.setItem(SLEUTELKEY, wachtwoord); } catch(e){}
    slot.classList.add('weg');
    start(url);
    ontsleutelVector(wachtwoord).then(bouwVector);
    return true;
  } catch(e){
    try { localStorage.removeItem(SLEUTELKEY); } catch(err){}
    fout.textContent = e.message === 'weg'  ? 'Bestand ' + BESTAND + ' niet gevonden.'
                     : e.message === 'stuk' ? 'Bestand ' + BESTAND + ' is beschadigd.'
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

const doorzicht = () => {
  const el = document.getElementById('op');
  return el ? +el.value : 1;
};

function start(url){
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
const doek = L.canvas({ padding:.4 });
const gZone   = L.layerGroup(), gVlak = L.layerGroup(), gLijn = L.layerGroup(),
      gStraat = L.layerGroup(), gCode = L.layerGroup();
const vormen = [];                                 // {laag, uv} om te herplaatsen
const etiketten = [];                              // {marker, uv}
let straten = [];                                  // {naam, delen:[[a,b],…]} in meters
const straatEtiket = [];                           // om per zoomstand te tonen of te verbergen
const CODE_VANAF = 18;      // gebouwcodes pas van dichtbij
const NAAM_VANAF = 16;      // van hieraf één naam per straat
const ALLE_VANAF = 17.5;    // van hieraf elk naambordje

/* genormaliseerde plancoördinaat -> plaatselijke meters (oost, noord), vóór draaiing */
const naarMeter = ([u,v]) => [ (u - .5) * P.w, (.5 - v) * P.h ];

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
  straat:    { color:'#4a86d8', weight:2.5, opacity:.55 }
};

function bouwVector(data){
  if (!data || !data.features) return;
  plan = data;
  const perStraat = {};

  for (const k of data.features){
    const s = k.properties.soort, g = k.geometry;

    if (g.type === 'Polygon'){
      const uv = g.coordinates[0];
      const laag = L.polygon(uv.map(naarLatLng),
                     Object.assign({ renderer:doek, interactive:s !== 'zone' }, STIJL[s] || STIJL.gebouw));
      if (k.properties.code) laag.bindTooltip(k.properties.code, { direction:'top' });
      laag.addTo(s === 'zone' ? gZone : gVlak);
      vormen.push({ laag, uv, ring:true });
      if (k.properties.code){
        const m = zwaartepunt(uv);
        etiketten.push(voegEtiket(m, k.properties.code, 'code', gCode));
      }

    } else if (g.type === 'LineString'){
      const uv = g.coordinates;
      const laag = L.polyline(uv.map(naarLatLng), Object.assign({ renderer:doek }, STIJL.straat)).addTo(gLijn);
      vormen.push({ laag, uv, ring:false });
      const naam = k.properties.naam;
      (perStraat[naam] = perStraat[naam] || []).push(uv);
      const e = voegEtiket(midden(uv), naam, 'straat', gStraat);
      e.naam = naam; e.lengte = stukLengte(uv);
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

  gZone.addTo(map); gVlak.addTo(map); gLijn.addTo(map); gStraat.addTo(map);
  lagenkiezer.addOverlay(gZone,   'Zones');
  lagenkiezer.addOverlay(gVlak,   'Gebouwen');
  lagenkiezer.addOverlay(gLijn,   'Straten');
  lagenkiezer.addOverlay(gStraat, 'Straatnamen');
  lagenkiezer.addOverlay(gCode,   'Gebouwcodes');
  // De vectorlaag draagt de namen nu zelf; de plattegrond eronder zou ze
  // een tweede keer tonen. Hij blijft één tik ver, via het lagenknopje.
  if (overlay){ lagenkiezer.addOverlay(overlay, 'Plattegrond'); map.removeLayer(overlay); }
  regelZoom();
  naVector();
  melden(straten.length + ' straten geladen');
}

function voegEtiket(uv, tekst, soort, groep){
  const m = L.marker(naarLatLng(uv), { interactive:false, keyboard:false,
              icon: L.divIcon({ className:'etiket ' + soort, iconSize:[0,0],
                                html:'<span>' + ontsmet(tekst) + '</span>' }) }).addTo(groep);
  return { marker:m, uv };
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
    const a = naarMeter(uv[i]), b = naarMeter(uv[i+1]);
    s += Math.hypot(b[0]-a[0], b[1]-a[1]);
  }
  return s;
}

/* de plaatsing is veranderd (uitlijnen) — alles opnieuw op de aarde zetten */
function plaatsVector(){
  for (const v of vormen)
    v.laag.setLatLngs(v.ring ? [v.uv.map(naarLatLng)] : v.uv.map(naarLatLng));
  for (const e of etiketten) e.marker.setLatLng(naarLatLng(e.uv));
}

/* Van ver zijn 91 naambordjes één zwarte vlek. Van dichtbij mag alles.
   Daartussen: één naam per straat, op zijn langste stuk. */
function regelZoom(){
  const z = map.getZoom();
  const codes = z >= CODE_VANAF;
  if (codes && !map.hasLayer(gCode)) gCode.addTo(map);
  if (!codes && map.hasLayer(gCode)) map.removeLayer(gCode);

  // dezelfde naam twee keer vlak naast elkaar helpt niemand
  const gehouden = [];
  for (const e of straatEtiket){
    let wil = z >= ALLE_VANAF || (z >= NAAM_VANAF && e.hoofd);
    if (wil && !e.hoofd){
      const q = map.latLngToContainerPoint(e.marker.getLatLng());
      for (const g of gehouden)
        if (g.naam === e.naam && q.distanceTo(g.punt) < 150){ wil = false; break; }
    }
    if (wil) gehouden.push({ naam:e.naam, punt:map.latLngToContainerPoint(e.marker.getLatLng()) });
    if (wil && !gStraat.hasLayer(e.marker)) gStraat.addLayer(e.marker);
    if (!wil && gStraat.hasLayer(e.marker)) gStraat.removeLayer(e.marker);
  }
}
map.on('zoomend moveend', regelZoom);
/* ------------------------- in welke straat sta ik ------------------- */
function afstandTotStuk(p, a, b){
  const dx = b[0]-a[0], dy = b[1]-a[1], L2 = dx*dx + dy*dy;
  let t = L2 ? ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / L2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0]+t*dx), p[1] - (a[1]+t*dy));
}

function dichtsteStraat(ll){
  if (!straten.length) return null;
  const p = naarVlak(ll);
  let best = null, bestd = Infinity;
  for (const s of straten)
    for (const deel of s.delen)
      for (let i = 0; i < deel.length-1; i++){
        const d = afstandTotStuk(p, naarMeter(deel[i]), naarMeter(deel[i+1]));
        if (d < bestd){ bestd = d; best = s.naam; }
      }
  return { naam:best, afstand:bestd };
}

/* -------------------------- offline cache ------------------------- */
if ('serviceWorker' in navigator && location.protocol === 'https:')
  navigator.serviceWorker.register('sw.js').catch(()=>{});

haalPlaatsing();
