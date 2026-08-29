"""Voegt alles samen tot één GeoJSON in echte coördinaten.

Het recept is voor alle drie de kaarten hetzelfde:

  1. OpenStreetMap levert de basis — álle gebouwen en álle benoemde straten in
     het kaartgebied, opgehaald met osm_kaart.py, precies zoals Leopoldsburg en
     Houthulst dat doen.
  2. Van de papieren kaart komt alleen wat er méér op staat. Voor WTC is dat:
     de 60 straatnamen (OSM kent er geen enkele op het domein), de MG-codes,
     de rood gearceerde zones, het terreinlijnwerk, en gebouwen alleen daar
     waar OSM er geen heeft.

Waar OSM het gebouw al kent, nemen we dus die omtrek: die ligt juist op de
aarde, en dat is precies wat de tekening mist. Van het plan houden we dan
alleen wat OSM niet heeft — de MG-code. Al het overige (straten, namen,
terreinlijnen, zones) wordt met de gevonden plaatsing omgerekend naar lengte-
en breedtegraad.

   python3 vectorplan/bouw.py <werkmap> [uitvoernaam=plan.geojson]

Gebouwomtrekken, straten en terreinvlakken van OSM: (c) OpenStreetMap-
bijdragers, ODbL.
"""
import json, sys, math, os, subprocess
import numpy as np
from scipy.spatial import cKDTree

S = sys.argv[1]
UITNAAM = sys.argv[2] if len(sys.argv) > 2 else 'plan.geojson'
BREED, HOOG = 8945.0, 8108.0
M_LAT = 111320.0
OSMNAAM = 'wtc'
BAK = '51.1780,4.1990,51.1930,4.2180'      # zoals in kaarten.json
SNIJ, OPP_ONDER, OPP_BOVEN = 26.0, .35, 3.0   # dezelfde maten als pas_osm.py

# ---------- 1. de basis: OpenStreetMap ----------
basis_pad = f'{S}/uit/{OSMNAAM}.geojson'
if not os.path.exists(basis_pad):
    print('OSM-basis ontbreekt — osm_kaart.py draaien…')
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'osm_kaart.py'), S, OSMNAAM, BAK], check=True)
basis = json.load(open(basis_pad))['features']
kx0 = 111320.0 * math.cos(math.radians(51.1855))   # ruwe meterschaal voor controles

kenmerken = []
def voeg(soort, meetkunde, **eig):
    kenmerken.append({'type': 'Feature', 'properties': dict(soort=soort, **eig),
                      'geometry': meetkunde})

for k in basis:
    k['properties'].setdefault('bron', 'osm')
    kenmerken.append(k)
osm_gebouwen = [k for k in basis if k['properties']['soort'] == 'gebouw']
tel_basis = {}
for k in basis: tel_basis[k['properties']['soort']] = tel_basis.get(k['properties']['soort'], 0) + 1
osm_straatnamen = {k['properties']['naam'] for k in basis if k['properties']['soort'] == 'straat'}
print('basis uit OSM: ' + ', '.join(f'{a}: {b}' for a, b in sorted(tel_basis.items())))
print(f'  {len(osm_straatnamen)} benoemde straten, {len(osm_gebouwen)} gebouwen')

# ---------- de plaatsing van de tekening ----------
pas = json.load(open(S + '/uit/passing.json'))
P = pas['plaatsing']
KOPPEL = {int(k): v for k, v in pas['koppels'].items()}
t = math.radians(P['rot']); ct, st = math.cos(t), math.sin(t)
kx = M_LAT * math.cos(math.radians(P['lat']))

def naar(p):
    """plancoördinaat in pixels -> [lon, lat]"""
    u, v = p[0] / BREED, p[1] / HOOG
    x, y = (u - .5) * P['w'], (.5 - v) * P['h']
    oost, noord = x * ct + y * st, -x * st + y * ct
    return [round(P['lon'] + oost / kx, 7), round(P['lat'] + noord / M_LAT, 7)]

def ring(punten):
    r = [naar(p) for p in punten]
    if r[0] != r[-1]: r.append(r[0])
    return [r]

# Welk OSM-gebouw in de basis hoort bij welke OSM-way? De basis draagt geen
# id's mee (osm_kaart.py is voor alle drie de kaarten hetzelfde), dus leggen we
# de ruwe Overpass-uitvoer ernaast. osm_kaart.py loopt die elementen in volgorde
# af en maakt per gebouw precies één vlak, dus de rangorde is de koppeling.
# Voor de zekerheid meten we het na met het midden van de omhullende rechthoek:
# osm_kaart.py rondt af op vijf decimalen (~een halve meter), en daar is een
# oppervlaktezwaartepunt van een klein gebouwtje veel gevoeliger voor.
def mid(r):
    a = np.asarray(r, float)
    return np.array([(a[:, 0].min() + a[:, 0].max()) / 2, (a[:, 1].min() + a[:, 1].max()) / 2])

def vmid(r):
    """gemiddelde van de hoekpunten, zoals pas_osm.py dat doet"""
    a = np.asarray(r, float)
    if len(a) > 2 and (a[0] == a[-1]).all(): a = a[:-1]
    return a.mean(0)

ruw = json.load(open(f'{S}/uit/osm_{OSMNAAM}.json'))['elements']
ruwe_gebouwen = [e for e in ruw if 'building' in e.get('tags', {}) and e.get('geometry')
                 and len(e['geometry']) >= 2]
id_naar_kenmerk, ver, verst = {}, 0, 0.0
if len(ruwe_gebouwen) != len(osm_gebouwen):
    sys.exit(f'basis en ruwe OSM lopen uiteen ({len(osm_gebouwen)} vlakken, '
             f'{len(ruwe_gebouwen)} ways) — osm_kaart.py opnieuw draaien')
for e, k in zip(ruwe_gebouwen, osm_gebouwen):
    a = mid([[q['lon'], q['lat']] for q in e['geometry']])
    b = mid(k['geometry']['coordinates'][0])
    d = math.hypot((a[0] - b[0]) * kx0, (a[1] - b[1]) * M_LAT)
    verst = max(verst, d)
    if d > 3.0: ver += 1; continue
    id_naar_kenmerk[e['id']] = k
print(f'  {len(id_naar_kenmerk)} van de {len(ruwe_gebouwen)} OSM-ways aan hun vlak gekoppeld '
      f'(grootste verschuiving {verst:.2f} m)')
if ver: print(f'  {ver} ways weken meer dan 3 m af en zijn overgeslagen')

# ---------- straten van het plan ----------
ankers = json.load(open(S + '/uit/straatankers.json'))
def richting(seg):
    (x1, y1), (x2, y2) = seg
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
def hoekverschil(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)
def samenvoegen(segs):
    veranderd = True
    while veranderd:
        veranderd = False
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                A, B = np.array(segs[i], float), np.array(segs[j], float)
                if hoekverschil(richting(A), richting(B)) > 8: continue
                d = A[1] - A[0]; L = np.hypot(*d)
                if L < 1: continue
                e = d / L; n = np.array([-e[1], e[0]])
                if max(abs(n @ (B[0] - A[0])), abs(n @ (B[1] - A[0]))) > 26: continue
                tt = [e @ (B[0] - A[0]), e @ (B[1] - A[0])]
                if min(tt) > L + 70 or max(tt) < -70: continue
                proj = (np.vstack([A, B]) - A[0]) @ e
                segs[i] = [list(A[0] + proj.min() * e), list(A[0] + proj.max() * e)]
                segs.pop(j); veranderd = True; break
            if veranderd: break
    return segs

straten = {}
for A in ankers: straten.setdefault(A['naam'], []).append(A['as'])
voor = sum(len(v) for v in straten.values())
for naam in straten: straten[naam] = samenvoegen(straten[naam])
print(f'straatstukken van het plan: {voor} -> {sum(len(v) for v in straten.values())} '
      f'({len(straten)} straatnamen)')
dubbel = sorted(set(straten) & osm_straatnamen)
if dubbel: print(f'  ook al in OSM: {", ".join(dubbel)}')
for naam, segs in sorted(straten.items()):
    for seg in segs:
        voeg('straat', {'type': 'LineString', 'coordinates': [naar(p) for p in seg]},
             naam=naam, bron='plan')

# ---------- gebouwen ----------
geb = json.load(open(S + '/uit/gebouwen.json'))

# Wat pas_osm.py al koppelde is leidend. Voor de rest kijken we of er in de
# volledige bak alsnog een OSM-gebouw op dezelfde plek ligt: die was in de oude
# uitsnede (domein + 90 m) misschien niet eens meegenomen.
DOELVLAK = {}                    # plangebouw-id -> het OSM-vlak dat het al is
bezet = {v['osm_id'] for v in KOPPEL.values() if v['osm_id'] in id_naar_kenmerk}
vrij = [i for i, e in enumerate(ruwe_gebouwen)
        if e['id'] in id_naar_kenmerk and e['id'] not in bezet]
def opp_m2(lonlat):
    a = np.asarray(lonlat, float)
    x, y = (a[:, 0] - P['lon']) * kx, (a[:, 1] - P['lat']) * M_LAT
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2
def naar_m(ll):
    return [(ll[0] - P['lon']) * kx, (ll[1] - P['lat']) * M_LAT]
vrij_mid = np.array([naar_m(vmid([[q['lon'], q['lat']] for q in ruwe_gebouwen[i]['geometry']]))
                     for i in vrij], float).reshape(-1, 2) if vrij else np.zeros((0, 2))
vrij_opp = np.array([opp_m2([[q['lon'], q['lat']] for q in ruwe_gebouwen[i]['geometry']]) for i in vrij])
boom_vrij = cKDTree(vrij_mid) if len(vrij_mid) else None

erbij = 0
for d in geb:
    if d['id'] in KOPPEL: continue
    m = naar_m(naar(d['zwaartepunt']))
    if boom_vrij is None: break
    afst, j = boom_vrij.query(m)
    if afst > SNIJ: continue
    j = int(j)
    if vrij[j] is None: continue
    o = d['opp'] * (P['h'] / HOOG) ** 2
    if not (OPP_ONDER < o / max(vrij_opp[j], 1) < OPP_BOVEN): continue
    KOPPEL[d['id']] = {'osm_id': ruwe_gebouwen[vrij[j]]['id'], 'afstand': round(float(afst), 1),
                       'extra': True}
    vrij_mid[j] = 1e9; boom_vrij = cKDTree(vrij_mid)     # niet twee keer dezelfde
    erbij += 1
if erbij: print(f'  {erbij} plangebouwen alsnog aan een OSM-gebouw gekoppeld (volledige bak)')

# Een zwaartepunt kan naast een langgerekt gebouw vallen terwijl de vlakken
# elkaar wel degelijk dekken. Daarom nog een ronde op overlapping. Wederzijds:
# een klein plangebouwtje dat toevallig binnen een groot OSM-vlak valt is niet
# hetzelfde gebouw, en zijn code hoort dan niet over dat hele blok te komen.
from shapely.geometry import shape, Polygon as SPoly
from shapely.strtree import STRtree
osm_vorm = [shape(k['geometry']).buffer(0) for k in osm_gebouwen]
nog_vrij = {id(k) for k in osm_gebouwen} - {id(id_naar_kenmerk[v['osm_id']])
                                            for v in KOPPEL.values() if v['osm_id'] in id_naar_kenmerk}
boom_vorm = STRtree(osm_vorm)
overlap, blijft_dubbel = 0, []
for d in geb:
    if d['id'] in KOPPEL: continue
    g = SPoly(ring(d['rand'])[0]).buffer(0)
    if g.is_empty or g.area <= 0: continue
    beste = (0, None)
    for j in boom_vorm.query(g):
        j = int(j); i = g.intersection(osm_vorm[j]).area
        if i / g.area > beste[0]: beste = (i / g.area, j, i / max(osm_vorm[j].area, 1e-18))
    if beste[1] is None: continue
    if beste[0] >= .5 and beste[2] >= .3 and id(osm_gebouwen[beste[1]]) in nog_vrij:
        DOELVLAK[d['id']] = osm_gebouwen[beste[1]]
        nog_vrij.discard(id(osm_gebouwen[beste[1]]))
        overlap += 1
    elif beste[0] >= .5:
        blijft_dubbel.append(d.get('codes'))
if overlap: print(f'  {overlap} plangebouwen gedekt door een OSM-vlak (overlapping)')
if blijft_dubbel:
    print(f'  {len(blijft_dubbel)} getekende gebouwen dekken deels een OSM-gebouw maar zijn '
          f'niet hetzelfde: ' + ', '.join(' / '.join(c) if c else 'zonder code' for c in blijft_dubbel))

uit_osm = uit_plan = 0
for d in geb:
    codes = d.get('codes')
    k = KOPPEL.get(d['id'])
    doel = id_naar_kenmerk.get(k['osm_id']) if k else DOELVLAK.get(d['id'])
    if doel is not None:                    # OSM kent dit gebouw: alleen de code erbij
        if codes:
            oud = doel['properties'].get('code')
            nieuw = ' / '.join(codes)
            doel['properties']['code'] = nieuw if not oud or oud in codes else f'{oud} / {nieuw}'
        uit_osm += 1
    else:                                   # alleen op de tekening
        voeg(d['soort'], {'type': 'Polygon', 'coordinates': ring(d['rand'])},
             bron='plan', **({'code': ' / '.join(codes)} if codes else {}))
        uit_plan += 1
print(f'gebouwen: {len(osm_gebouwen)} uit OSM (waarvan {uit_osm} met een MG-code van het plan), '
      f'{uit_plan} alleen uit de tekening')

# ---------- codes zonder eigen vlak ----------
geplaatst = {c for d in geb for c in d.get('codes', [])}
tekst = json.load(open(S + '/uit/codetekst.json'))
groepen = {g['id']: g for g in json.load(open(S + '/uit/codegroepen.json'))}
los, kwijt = 0, []
for k, v in tekst.items():
    if v in geplaatst: continue
    g = groepen.get(int(k))
    if g is None: kwijt.append(v); continue
    los += 1
    voeg('gebouwpunt', {'type': 'Point', 'coordinates': naar([g['x'], g['y']])},
         code=v, bron='plan')

# ---------- terreinlijnwerk en zones van het plan ----------
try:
    for d in json.load(open(S + '/uit/terrein.json')):
        voeg(d['soort'], {'type': 'LineString', 'coordinates': [naar(q) for q in d['punten']]},
             bron='plan')
except FileNotFoundError:
    print('geen terrein.json — lijnwerk overgeslagen')
for z in json.load(open(S + '/uit/zones.json')):
    voeg('zone', {'type': 'Polygon', 'coordinates': ring(z['rand'])}, bron='plan')

# ---------- controle: komen alle gelezen codes ergens terecht? ----------
op_kaart = set()
for k in kenmerken:
    c = k['properties'].get('code')
    if c: op_kaart.update(x.strip() for x in c.split(' / '))
gelezen = set(tekst.values())
mist = sorted(gelezen - op_kaart)
print(f'MG-codes: {len(gelezen)} gelezen, {len(gelezen & op_kaart)} op de kaart '
      f'({len(gelezen) - los - len(kwijt) - len(mist)} op een vlak, {los} als punt)')
if mist: print('  NIET geplaatst: ' + ', '.join(mist))
if kwijt: print('  geen tekstgroep gevonden voor: ' + ', '.join(kwijt))

fc = {'type': 'FeatureCollection',
      'stelsel': 'wgs84',
      'plaatsing': P,
      'bron': 'Kaart WTC - Straatnamen (versie 2026), 1000 dpi; '
              'gebouwen, straten en terreinvlakken (c) OpenStreetMap-bijdragers, ODbL',
      'features': kenmerken}
uit = f'{S}/uit/{UITNAAM}'
json.dump(fc, open(uit, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'{len(kenmerken)} kenmerken -> {uit} ({os.path.getsize(uit)/1024:.0f} kB)')
