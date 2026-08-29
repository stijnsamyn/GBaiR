"""Bouwt een kaartlaag rechtstreeks uit OpenStreetMap, in dezelfde vorm als
de laag die uit een getekend plan komt.

Voor een gebied waar OSM de straten en gebouwen al kent is dat genoeg: er valt
niets te traceren. Voor een oefendorp met verzonnen namen is het dat niet --
daar levert OSM alleen de ligging.

   python3 vectorplan/osm_kaart.py <werkmap> <naam> <zuid,west,noord,oost>

Data (c) OpenStreetMap-bijdragers, ODbL.
"""
import json, sys, os, math, urllib.request, urllib.parse
WERK, NAAM, BAK = sys.argv[1], sys.argv[2], [float(v) for v in sys.argv[3].split(',')]
RUW = f'{WERK}/uit/osm_{NAAM}.json'
os.makedirs(WERK + '/uit', exist_ok=True)

VRAAG = f'''[out:json][timeout:240];
(
  way["building"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["highway"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["landuse"~"military|forest|grass|meadow|cemetery|residential|industrial"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["natural"~"wood|water|scrub"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["leisure"~"park|pitch|sports_centre"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["railway"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["barrier"~"wall|fence"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
);
out geom;'''

if os.path.exists(RUW):
    print('al opgehaald:', RUW)
else:
    print('Overpass bevragen…')
    req = urllib.request.Request('https://overpass-api.de/api/interpreter',
            data=urllib.parse.urlencode({'data': VRAAG}).encode(),
            headers={'User-Agent': 'GBaiR-vectorplan/1.0'})
    with urllib.request.urlopen(req, timeout=300) as r:
        json.dump(json.loads(r.read().decode()), open(RUW, 'w'))

el = json.load(open(RUW))['elements']

# Een halve meter is ruim genoeg om te voet op te navigeren, en scheelt de helft
# van het bestand. Vereenvoudigen haalt de overtollige knikjes uit OSM-omtrekken.
from shapely.geometry import LineString, Polygon
TOL = 0.5 / 111320.0
def rond(g, gesloten=False):
    r = [(q['lon'], q['lat']) for q in g]
    if len(r) > 3:
        vorm = Polygon(r).buffer(0) if gesloten else LineString(r)
        if gesloten:
            vorm = vorm.simplify(TOL, preserve_topology=True)
            if vorm.geom_type == 'MultiPolygon':
                vorm = max(vorm.geoms, key=lambda q: q.area)
            r = list(vorm.exterior.coords) if not vorm.is_empty else r
        else:
            # topologie bewaren, anders vallen kruispuntknopen weg
            r = list(vorm.simplify(TOL, preserve_topology=True).coords)
    return [[round(x, 5), round(y, 5)] for x, y in r]
def sluit(r):
    return r + [r[0]] if r[0] != r[-1] else r

WEGSOORT = {'motorway','trunk','primary','secondary','tertiary','unclassified',
            'residential','living_street','service','pedestrian','track','path','footway','cycleway'}
GROEN = {'forest','wood','grass','meadow','park','scrub','cemetery','pitch','sports_centre'}

kenmerken, tel = [], {}
def voeg(soort, meetkunde, **eig):
    kenmerken.append({'type':'Feature','properties':dict(soort=soort, **eig),'geometry':meetkunde})
    tel[soort] = tel.get(soort, 0) + 1

for e in el:
    t = e.get('tags', {}); g = e.get('geometry')
    if not g or len(g) < 2: continue
    gesloten = ('building' in t) or (g[0]['lat'] == g[-1]['lat'] and g[0]['lon'] == g[-1]['lon'])
    p = rond(g, gesloten)
    if len(p) < 2: continue
    if 'building' in t:
        code = t.get('ref') or t.get('name')
        voeg('gebouw', {'type':'Polygon','coordinates':[sluit(p)]},
             bron='osm', **({'code': code} if code else {}))
    elif 'highway' in t:
        if t['highway'] not in WEGSOORT: continue
        naam = t.get('name') or t.get('ref')
        if naam:
            voeg('straat', {'type':'LineString','coordinates':p}, naam=naam)
        else:
            # Naamloze dienstwegen en paden wél tekenen, maar zonder naam. Laat
            # je ze weg, dan meldt de app daar de naam van een buurstraat --
            # gemeten: ruim een kwart van die punten kreeg stellig een verkeerde
            # naam. Als 'pad' tekent de kaart ze en zwijgt de app er terecht.
            voeg('pad', {'type':'LineString','coordinates':p}, wat=t['highway'])
    elif 'railway' in t:
        voeg('spoor', {'type':'LineString','coordinates':p})
    elif t.get('barrier'):
        voeg('lijn', {'type':'LineString','coordinates':p})
    else:
        wat = t.get('landuse') or t.get('natural') or t.get('leisure')
        if wat == 'military':   voeg('zone', {'type':'Polygon','coordinates':[sluit(p)]})
        elif wat == 'water':    voeg('water', {'type':'Polygon','coordinates':[sluit(p)]})
        elif wat in GROEN:      voeg('groen', {'type':'Polygon','coordinates':[sluit(p)]})

lat = [q[1] for k in kenmerken for q in
       (k['geometry']['coordinates'][0] if k['geometry']['type'] == 'Polygon' else k['geometry']['coordinates'])]
lon = [q[0] for k in kenmerken for q in
       (k['geometry']['coordinates'][0] if k['geometry']['type'] == 'Polygon' else k['geometry']['coordinates'])]
mid = {'lat': round((min(lat)+max(lat))/2, 7), 'lon': round((min(lon)+max(lon))/2, 7)}

fc = {'type':'FeatureCollection','stelsel':'wgs84','plaatsing':mid,
      'bron':'(c) OpenStreetMap-bijdragers, ODbL',
      'features':kenmerken}
uit = f'{WERK}/uit/{NAAM}.geojson'
json.dump(fc, open(uit, 'w'), separators=(',',':'), ensure_ascii=False)
straatnamen = {k['properties']['naam'] for k in kenmerken if k['properties']['soort'] == 'straat'}
print(f'{len(kenmerken)} kenmerken -> {os.path.getsize(uit)/1024:.0f} kB')
print('  ' + ', '.join(f'{k}: {v}' for k, v in sorted(tel.items())))
print(f'  {len(straatnamen)} straatnamen')
