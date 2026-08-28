"""Haalt van OpenStreetMap wat er van het terrein bekend is.

OSM kent de straatnamen en de MG-codes van het oefendorp niet -- die staan
alleen op dit plan. Wat OSM wel heeft, en wij niet, is een juiste ligging op
de aarde. Daarom halen we de gebouwen en de terreinvlakken op: niet om de
tekening te vervangen, maar om ze erop te kunnen leggen.

Data (c) OpenStreetMap-bijdragers, ODbL.
"""
import json, sys, os, urllib.request, urllib.parse
S = sys.argv[1]
UIT = S + '/uit/osm.json'
# ruime bak rond het militaire domein (way 51686418), met marge voor wat er
# net buiten valt, zoals de militaire woningen
BAK = (51.1795, 4.1975, 51.1925, 4.2195)

VRAAG = f'''[out:json][timeout:120];
(
  way["building"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["landuse"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["natural"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["leisure"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
  way["highway"]({BAK[0]},{BAK[1]},{BAK[2]},{BAK[3]});
);
out geom;'''

if os.path.exists(UIT):
    print('osm.json bestaat al — niet opnieuw opgehaald')
else:
    print('Overpass bevragen…')
    req = urllib.request.Request('https://overpass-api.de/api/interpreter',
            data=urllib.parse.urlencode({'data': VRAAG}).encode(),
            headers={'User-Agent': 'GBaiR-vectorplan/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        json.dump(json.loads(r.read().decode()), open(UIT, 'w'))

el = json.load(open(UIT))['elements']
soorten = {'gebouw': [], 'terrein': [], 'weg': []}
for e in el:
    t = e.get('tags', {}); g = e.get('geometry')
    if not g or len(g) < 2: continue
    lijn = [[round(q['lon'], 7), round(q['lat'], 7)] for q in g]
    if 'building' in t: soorten['gebouw'].append(lijn)
    elif 'highway' in t: soorten['weg'].append((lijn, t.get('name')))
    elif t.get('landuse') or t.get('natural') or t.get('leisure'):
        soorten['terrein'].append((lijn, t.get('landuse') or t.get('natural') or t.get('leisure')))

kenmerken = []
for ring in soorten['gebouw']:
    if ring[0] != ring[-1]: ring = ring + [ring[0]]
    kenmerken.append({'type':'Feature','properties':{'soort':'osm_gebouw'},
                      'geometry':{'type':'Polygon','coordinates':[ring]}})
for ring, wat in soorten['terrein']:
    if ring[0] != ring[-1]: ring = ring + [ring[0]]
    kenmerken.append({'type':'Feature','properties':{'soort':'osm_terrein','wat':wat},
                      'geometry':{'type':'Polygon','coordinates':[ring]}})
for lijn, naam in soorten['weg']:
    e = {'soort':'osm_weg'}
    if naam: e['naam'] = naam
    kenmerken.append({'type':'Feature','properties':e,
                      'geometry':{'type':'LineString','coordinates':lijn}})

fc = {'type':'FeatureCollection',
      'bron':'OpenStreetMap-bijdragers, ODbL',
      'features':kenmerken}
json.dump(fc, open(S + '/uit/osm.geojson','w'), separators=(',',':'))
print(f"gebouwen {len(soorten['gebouw'])}, terreinvlakken {len(soorten['terrein'])}, "
      f"wegen {len(soorten['weg'])}  ->  {os.path.getsize(S+'/uit/osm.geojson')/1024:.0f} kB")
