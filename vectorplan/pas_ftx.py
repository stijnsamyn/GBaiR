"""Legt de gescande FTX-kaart van Leopoldsburg op de aarde.

Wat niet werkte, en waarom, want dat spaart de volgende poging tijd:

* Kruiscorrelatie op groen. Rond Leopoldsburg is bijna alles bos: 59 % van het
  zoekgebied is groen, dus dat signaal onderscheidt niets en de passing kiest de
  kleinste schaal, waarbij de scan in één bos gekrompen wordt.
* De gedrukte schaal geloven. Er staat 1:10 000 op, wat op 400 dpi 0,635 m per
  beeldpunt zou geven. Gemeten tussen twee ver uiteen liggende kruispunten is
  het 0,448 -- de kaart is bij het plaatsen in Publisher verkleind.
* Een gelijkvormigheid passen zonder de y-as om te keren. Beeld-y loopt omlaag,
  noord omhoog; zonder spiegeling wringt de passing er 5° draaiing in.

Wat wel werkt: een handvol kruispunten van benoemde straten als controlepunt
(hun plek komt uit OSM, hun beeldpunt van de scan), en daarna fijnstellen door
de zalmroze hoofdwegen van de ondergrond over de hoofdwegen van OSM te schuiven.
Dat laatste haalde de laatste 30 m eruit en verdrievoudigde de overlap.

De ondergrond zelf is (c) 2006-2015 TomTom / Michelin en hoort niet in een
publieke repo; alleen de overlay is van de opsteller.
"""
import json, sys, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
S, SCAN, WEGEN = sys.argv[1], sys.argv[2], sys.argv[3]
KADER = (0, 678, 6580, 4678)          # het kaartdeel van de scan, zonder legende

# scanpunt -> werkelijke plek, met de hand aangewezen op kruispunten van
# benoemde straten; de plek komt uit OpenStreetMap
PUNTEN = [((1195, 1783), (51.116112, 5.258761)),   # Nicolaylaan x Koningsstraat
          ((5909,  809), (51.119822, 5.288785)),   # Hechtelsesteenweg x Kamperbaan
          ((5814, 3014), (51.111051, 5.288720)),   # Graaf v Vlaanderenlaan x De Bruynlaan
          ((3471, 1536), (51.116901, 5.273392)),   # Kon. Leopold I-laan x Kon. Elisabethlaan
          ((4057, 2398), (51.113514, 5.277242))]   # Kon. Leopold II-laan x Baron Rucquoylaan

lat0 = sum(p[1][0] for p in PUNTEN) / len(PUNTEN)
lon0 = sum(p[1][1] for p in PUNTEN) / len(PUNTEN)
kx = 111320 * math.cos(math.radians(lat0)); ky = 111320

Pp = np.array([[x, -y] for (x, y), _ in PUNTEN], float)      # y omkeren: noord is omhoog
Qq = np.array([[(lo - lon0) * kx, (la - lat0) * ky] for _, (la, lo) in PUNTEN])
mp, mq = Pp.mean(0), Qq.mean(0); A, B = Pp - mp, Qq - mq
U, D, Vt = np.linalg.svd(B.T @ A / len(A)); Sg = np.eye(2)
if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sg[1, 1] = -1
R = U @ Sg @ Vt
schaal = float((D * np.diag(Sg)).sum() / max(A.var(0).sum(), 1e-12))
M = schaal * R; t = mq - mp @ M.T
rest = [math.hypot(*((np.array([x, -y]) @ M.T + t) - np.array([(lo-lon0)*kx, (la-lat0)*ky])))
        for (x, y), (la, lo) in PUNTEN]
print(f'{schaal:.4f} m per scanpunt, draaiing {math.degrees(math.atan2(R[1,0], R[0,0])):.2f}°, '
      f'rest gemiddeld {np.mean(rest):.1f} m')

Mi = np.linalg.inv(M)
naarpix = lambda la, lo: (lambda v: (v[0], -v[1]))(
        (np.array([(lo - lon0) * kx, (la - lat0) * ky]) - t) @ Mi.T)

# ---- fijnstellen op de hoofdwegen ----
a = np.asarray(Image.open(SCAN).convert('RGB').crop(KADER)).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
zalm = (r > 225) & (g > 140) & (g < 200) & (b > 120) & (b < 185) & (r - g > 45)
zalm = ndi.binary_opening(zalm, np.ones((5, 5)))
lab, _ = ndi.label(zalm)
opp = np.bincount(lab.ravel()); opp[0] = 0
wegvlak = np.isin(lab, np.nonzero(opp > 4000)[0])     # lange vlakken zijn wegen, geen gebouwen

H, W = wegvlak.shape
doek = Image.new('1', (W, H), 0); d = ImageDraw.Draw(doek)
for e in json.load(open(WEGEN))['elements']:
    if e.get('tags', {}).get('highway') not in {'primary','secondary','tertiary','trunk'}: continue
    if not e.get('geometry'): continue
    d.line([naarpix(q['lat'], q['lon']) for q in e['geometry']], fill=1, width=26)
osmweg = np.asarray(doek)

beste = None
for dy in range(-160, 161, 4):
    for dx in range(-160, 161, 4):
        sam = int((np.roll(np.roll(osmweg, dy, 0), dx, 1) & wegvlak).sum())
        if beste is None or sam > beste[0]: beste = (sam, dx, dy)
sam, dx, dy = beste
basis = int((osmweg & wegvlak).sum())
print(f'fijnstelling {dx},{dy} scanpunten ({dx*schaal:.0f}, {dy*schaal:.0f} m); '
      f'overlap {basis} -> {sam}')
t = t + np.array([-dx, dy]) @ M.T

json.dump({'lat0': lat0, 'lon0': lon0, 'M': M.tolist(), 't': t.tolist(),
           'schaal': round(schaal, 4), 'spiegel_y': True, 'kader_px': list(KADER),
           'rest_m': [round(v, 1) for v in rest], 'fijnstelling_px': [dx, dy]},
          open(S + '/uit/scanpassing.json', 'w'), indent=1)
print('scanpassing.json geschreven')
