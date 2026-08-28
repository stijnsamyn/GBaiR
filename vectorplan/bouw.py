"""Voegt alles samen tot één GeoJSON in echte coördinaten.

Waar OpenStreetMap het gebouw al kent, nemen we die omtrek: die ligt juist op
de aarde, en dat is precies wat de tekening mist. Van het plan houden we dan
alleen wat OSM niet heeft — de MG-code. Gebouwen die OSM niet kent komen wel
uit de tekening.

Al het overige (straten, namen, terreinlijnen, zones) wordt met de gevonden
plaatsing omgerekend naar lengte- en breedtegraad. Daardoor hangt de kaartlaag
niet meer af van een uitlijning achteraf.

Gebouwomtrekken en terreinvlakken van OSM: (c) OpenStreetMap-bijdragers, ODbL.
"""
import json, sys, math, os
import numpy as np
S = sys.argv[1]
BREED, HOOG = 8945.0, 8108.0
M_LAT = 111320.0

pas = json.load(open(S + '/uit/passing.json'))
P = pas['plaatsing']
KOPPEL = {int(k): v for k, v in pas['koppels'].items()}
OSMRING = {g['id']: g['ring'] for g in pas['osm_gebouwen']}
t = math.radians(P['rot']); ct, st = math.cos(t), math.sin(t)
kx = M_LAT * math.cos(math.radians(P['lat']))

def naar(p):
    """plancoördinaat in pixels -> [lon, lat]"""
    u, v = p[0] / BREED, p[1] / HOOG
    x, y = (u - .5) * P['w'], (.5 - v) * P['h']
    oost, noord = x * ct + y * st, -x * st + y * ct
    return [round(P['lon'] + oost / kx, 7), round(P['lat'] + noord / M_LAT, 7)]

kenmerken = []
def voeg(soort, meetkunde, **eig):
    kenmerken.append({'type': 'Feature', 'properties': dict(soort=soort, **eig),
                      'geometry': meetkunde})

def ring(punten):
    r = [naar(p) for p in punten]
    if r[0] != r[-1]: r.append(r[0])
    return [r]

# ---------- straten ----------
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
print(f'straatstukken: {voor} -> {sum(len(v) for v in straten.values())} ({len(straten)} straten)')
for naam, segs in sorted(straten.items()):
    for seg in segs:
        voeg('straat', {'type': 'LineString', 'coordinates': [naar(p) for p in seg]}, naam=naam)

# ---------- gebouwen ----------
geb = json.load(open(S + '/uit/gebouwen.json'))
uit_osm = uit_plan = 0
gebruikt = set()
for d in geb:
    codes = d.get('codes')
    eig = {'code': ' / '.join(codes)} if codes else {}
    k = KOPPEL.get(d['id'])
    if k:                                    # OSM kent dit gebouw: neem die omtrek
        gebruikt.add(k['osm_id'])
        r = OSMRING[k['osm_id']]
        if r[0] != r[-1]: r = r + [r[0]]
        voeg('gebouw', {'type': 'Polygon', 'coordinates': [r]}, bron='osm', **eig)
        uit_osm += 1
    else:                                    # alleen op de tekening
        voeg(d['soort'], {'type': 'Polygon', 'coordinates': ring(d['rand'])}, bron='plan', **eig)
        uit_plan += 1
# gebouwen die OSM wel kent en de tekening niet benoemt
extra = 0
for g in pas['osm_gebouwen']:
    if g['id'] in gebruikt: continue
    r = g['ring']
    if r[0] != r[-1]: r = r + [r[0]]
    voeg('gebouw', {'type': 'Polygon', 'coordinates': [r]}, bron='osm')
    extra += 1
print(f'gebouwen: {uit_osm} uit OSM met code, {uit_plan} uit de tekening, {extra} uit OSM zonder code')

# ---------- codes zonder eigen vlak ----------
geplaatst = {c for d in geb for c in d.get('codes', [])}
tekst = json.load(open(S + '/uit/codetekst.json'))
groepen = {g['id']: g for g in json.load(open(S + '/uit/codegroepen.json'))}
los = 0
for k, v in tekst.items():
    if v in geplaatst: continue
    g = groepen[int(k)]; los += 1
    voeg('gebouwpunt', {'type': 'Point', 'coordinates': naar([g['x'], g['y']])}, code=v)

# ---------- terreinlijnwerk en zones ----------
try:
    for d in json.load(open(S + '/uit/terrein.json')):
        voeg(d['soort'], {'type': 'LineString', 'coordinates': [naar(q) for q in d['punten']]})
except FileNotFoundError:
    print('geen terrein.json — lijnwerk overgeslagen')
for z in json.load(open(S + '/uit/zones.json')):
    voeg('zone', {'type': 'Polygon', 'coordinates': ring(z['rand'])})

fc = {'type': 'FeatureCollection',
      'stelsel': 'wgs84',
      'plaatsing': P,
      'bron': 'Kaart WTC - Straatnamen (versie 2026), 1000 dpi; '
              'gebouwomtrekken deels (c) OpenStreetMap-bijdragers, ODbL',
      'features': kenmerken}
uit = S + '/uit/plan.geojson'
json.dump(fc, open(uit, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f'{len(kenmerken)} kenmerken ({los} losse codes) -> {os.path.getsize(uit)/1024:.0f} kB')
