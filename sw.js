/* Offline cache. Verhoog VERSIE na elke wijziging, anders blijft een
   toestel op de oude pagina hangen. */
const VERSIE = 'wtc-v2';
const SCHIL  = 'schil-'  + VERSIE;
const TEGELS = 'tegels-' + VERSIE;
const MAX_TEGELS = 900;

const BESTANDEN = [
  '.', 'index.html', 'manifest.webmanifest',
  'kaart.enc', 'plan.enc',
  'vendor/leaflet.css', 'vendor/leaflet.js', 'vendor/leaflet-imageoverlay-rotated.js',
  'vendor/images/layers.png', 'vendor/images/layers-2x.png',
  'vendor/images/marker-icon.png', 'vendor/images/marker-icon-2x.png', 'vendor/images/marker-shadow.png',
  'icons/icon-180.png', 'icons/icon-192.png', 'icons/icon-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(SCHIL);
    // Eén voor één: een ontbrekend bestand mag de hele installatie
    // niet laten mislukken.
    await Promise.all(BESTANDEN.map(u => c.add(u).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const namen = await caches.keys();
    await Promise.all(namen.filter(n => n !== SCHIL && n !== TEGELS).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

const isTegel = u => /arcgisonline\.com|tile\.openstreetmap\.org/.test(u);

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;

  if (isTegel(req.url)){
    // Tegels: uit cache als het kan, anders halen en bewaren.
    e.respondWith((async () => {
      const c = await caches.open(TEGELS);
      const hit = await c.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res.ok){ c.put(req, res.clone()); snoei(c); }
        return res;
      } catch(err){ return new Response('', { status:504 }); }
    })());
    return;
  }

  if (new URL(req.url).origin !== location.origin) return;

  // Eigen bestanden: cache eerst, netwerk als reserve, en ververs stil.
  e.respondWith((async () => {
    const c = await caches.open(SCHIL);
    const hit = await c.match(req, { ignoreSearch:true });
    const net = fetch(req).then(res => { if (res.ok) c.put(req, res.clone()); return res; })
                          .catch(() => hit);
    return hit || net;
  })());
});

async function snoei(c){
  const k = await c.keys();
  if (k.length > MAX_TEGELS)
    for (const oud of k.slice(0, k.length - MAX_TEGELS)) c.delete(oud);
}
