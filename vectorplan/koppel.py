"""Legt elke gelezen code bij het vlak waar hij in ligt."""
import json, sys
from shapely.geometry import Polygon, Point
S = sys.argv[1]
tekst = json.load(open(S + '/uit/codetekst.json'))
groepen = {g['id']: g for g in json.load(open(S + '/uit/codegroepen.json'))}
geb = json.load(open(S + '/uit/gebouwen.json'))
vlakken = [(d, Polygon(d['rand']).buffer(0)) for d in geb]
for d, _ in vlakken: d.pop('codes', None)
los = []
for k, t in tekst.items():
    g = groepen[int(k)]; p = Point(g['x'], g['y'])
    binnen = [d for d, poly in vlakken if poly.contains(p)]
    if not binnen:
        d, poly = min(vlakken, key=lambda dp: dp[1].distance(p))
        binnen = [d] if poly.distance(p) < 160 else []
    if binnen: binnen[0].setdefault('codes', []).append(t)
    else: los.append(t)
print('gekoppeld:', sum(len(d.get('codes', [])) for d in geb), '/', len(tekst), ' los:', los)
print('vlakken met >1 code:', [(d['id'], d['codes']) for d in geb if len(d.get('codes', [])) > 1])
print('vlakken zonder code:', sum(1 for d in geb if not d.get('codes')))
json.dump(geb, open(S + '/uit/gebouwen.json', 'w'))
