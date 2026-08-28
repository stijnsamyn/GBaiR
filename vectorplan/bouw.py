"""Voegt alles samen tot één GeoJSON in genormaliseerde plancoördinaten.

De coördinaten lopen van 0 tot 1 over het kader van het plan — hetzelfde kader
als kaart.webp. De pagina rekent ze met START om naar lengte- en breedtegraad,
zodat de vectorlaag en de plattegrond precies samenvallen en dezelfde
uitlijnmodus voor allebei geldt.
"""
import json, sys
import numpy as np
S = sys.argv[1]
BREED, HOOG = 8945.0, 8108.0

def norm(p):
    return [round(p[0] / BREED, 5), round(p[1] / HOOG, 5)]

# ---- straatassen van dezelfde naam aaneenschakelen ----
ankers = json.load(open(S + '/uit/straatankers.json'))
def richting(seg):
    (x1, y1), (x2, y2) = seg
    h = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
    return h
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
                t = [0.0, L, e @ (B[0] - A[0]), e @ (B[1] - A[0])]
                if min(t[2], t[3]) > L + 70 or max(t[2], t[3]) < -70: continue
                punten = np.vstack([A, B])
                proj = (punten - A[0]) @ e
                segs[i] = [list(A[0] + proj.min() * e), list(A[0] + proj.max() * e)]
                segs.pop(j); veranderd = True; break
            if veranderd: break
    return segs

straten = {}
for A in ankers:
    straten.setdefault(A['naam'], []).append(A['as'])
tot_voor = sum(len(v) for v in straten.values())
for naam in straten: straten[naam] = samenvoegen(straten[naam])
tot_na = sum(len(v) for v in straten.values())
print(f'straatstukken: {tot_voor} -> {tot_na} na aaneenschakelen ({len(straten)} straten)')

kenmerken = []
for naam, segs in sorted(straten.items()):
    for seg in segs:
        kenmerken.append({'type': 'Feature',
                          'properties': {'soort': 'straat', 'naam': naam},
                          'geometry': {'type': 'LineString', 'coordinates': [norm(p) for p in seg]}})

# ---- gebouwen ----
geb = json.load(open(S + '/uit/gebouwen.json'))
for d in geb:
    rand = [norm(p) for p in d['rand']]
    if rand[0] != rand[-1]: rand.append(rand[0])
    eig = {'soort': d['soort']}
    if d.get('codes'): eig['code'] = ' / '.join(d['codes'])
    kenmerken.append({'type': 'Feature', 'properties': eig,
                      'geometry': {'type': 'Polygon', 'coordinates': [rand]}})

# ---- codes zonder eigen vlak, als punt ----
geplaatst = {c for d in geb for c in d.get('codes', [])}
tekst = json.load(open(S + '/uit/codetekst.json'))
groepen = {g['id']: g for g in json.load(open(S + '/uit/codegroepen.json'))}
los = 0
for k, t in tekst.items():
    if t in geplaatst: continue
    g = groepen[int(k)]; los += 1
    kenmerken.append({'type': 'Feature', 'properties': {'soort': 'gebouwpunt', 'code': t},
                      'geometry': {'type': 'Point', 'coordinates': norm([g['x'], g['y']])}})

# ---- zones ----
for z in json.load(open(S + '/uit/zones.json')):
    rand = [norm(p) for p in z['rand']]
    if rand[0] != rand[-1]: rand.append(rand[0])
    kenmerken.append({'type': 'Feature', 'properties': {'soort': 'zone'},
                      'geometry': {'type': 'Polygon', 'coordinates': [rand]}})

fc = {'type': 'FeatureCollection',
      'kader': {'breedte_px': BREED, 'hoogte_px': HOOG, 'bron': 'Kaart WTC - Straatnamen (versie 2026), 1000 dpi'},
      'features': kenmerken}
uit = S + '/uit/plan.geojson'
json.dump(fc, open(uit, 'w'), separators=(',', ':'), ensure_ascii=False)
import os
print(f'{len(kenmerken)} kenmerken  ({los} losse codes)  -> {os.path.getsize(uit)/1024:.0f} kB')
