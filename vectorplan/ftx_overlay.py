"""Neemt de FTX-overlay over van de gescande kaart van Leopoldsburg.

Alleen wat de opsteller er zelf op getekend heeft; de ondergrond blijft achter.
OpenStreetMap levert de straten en de gebouwen al, dit levert wat OSM niet weet:
waar je niet door kan, waar een poort staat, en welke gebouwen voor de oefening
echt zijn en welke verzonnen.

De zalmroze hoofdwegen van de ondergrond hebben dezelfde kleur als een reëel
gebouw. Het onderscheid zit in de vorm: een weg is lang en dun, een gebouw is
een compact blok.
"""
import json, sys, math
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure, morphology
Image.MAX_IMAGE_PIXELS = None
S, SCAN = sys.argv[1], sys.argv[2]

pas = json.load(open(S + '/uit/scanpassing.json'))
lat0, lon0 = pas['lat0'], pas['lon0']
M = np.array(pas['M']); t = np.array(pas['t']); schaal = pas['schaal']
kx = 111320 * math.cos(math.radians(lat0)); ky = 111320
def naar(x, y):
    e, n = np.array([x, -y]) @ M.T + t
    return [round(lon0 + e / kx, 6), round(lat0 + n / ky, 6)]

a = np.asarray(Image.open(SCAN).convert('RGB').crop(tuple(pas['kader_px']))).astype(int)
H, W, _ = a.shape
r, g, b = a[..., 0], a[..., 1], a[..., 2]
buiten = np.zeros((H, W), bool)
buiten[:int(H*0.13), int(W*0.76):] = True          # de inzet rechtsboven
buiten[int(H*0.83):, int(W*0.82):] = True          # schaalkader en versiedoos
buiten[int(H*0.90):, :int(W*0.17)] = True          # het logo en de schaalbalk linksonder
buiten[int(H*0.955):, :] = True                    # de onderrand met de bronvermelding
buiten[:, :int(W*0.008)] = True                    # de randen van het blad
buiten[:, int(W*0.995):] = True
buiten[:int(H*0.004), :] = True
buiten[int(H*0.996):, :] = True

def dichtbij(kleur, tol):
    return (abs(r - kleur[0]) < tol) & (abs(g - kleur[1]) < tol) & (abs(b - kleur[2]) < tol) & ~buiten

# Paars heeft meer rood dan groen en meer blauw dan rood; de blauwe K-blokken
# op de kaart hebben dat eerste niet, en vallen daardoor af.
paars = dichtbij((179, 157, 203), 40) & (r > g + 6) & (b > r + 6)
MASKERS = {
    'gesloten':  paars,                            # niet toegankelijk of onbestaand
    'slecht':    dichtbij((240, 144,  16), 55),    # oranje streepjes: slechte staat
    'tevoet':    dichtbij(( 62, 167,  33), 55),    # groene kern: enkel te voet
    'poort':     dichtbij((197,  70,   2), 50),    # rode kern: hekwerk of poort
    'geel':      dichtbij((242, 236,  15), 45),    # de gele omranding van beide
}
# De hoofdwegen van de ondergrond zijn even zalmroze als een reëel gebouw.
# Ze vormen wel één samenhangend net; een gebouw staat op zichzelf.
zalm_alles = dichtbij((247, 170, 152), 26)
_lab, _n = ndi.label(morphology.binary_closing(zalm_alles, morphology.disk(2)))
_opp = np.bincount(_lab.ravel()); _opp[0] = 0
_weg = np.isin(_lab, np.nonzero(_opp > 20000)[0])
ZALM = zalm_alles & ~morphology.binary_dilation(_weg, morphology.disk(3))
GRIJS = (abs(r - g) < 10) & (abs(g - b) < 10) & (r > 150) & (r < 200) & ~buiten

MINL = int(12 / schaal)          # korter dan 12 m is ruis
rondom = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def lijnen_uit(masker, dicht=9, dun_weg=0):
    """Verbindt de streepjes, dunt uit tot één punt breed, en loopt het skelet af.

    Groene en rode markeringen zijn dikke balkjes; de groene plaatsnamen op de
    ondergrond zijn dunne letters. Wegopenen haalt die letters eruit."""
    if dun_weg: masker = morphology.binary_opening(masker, morphology.disk(dun_weg))
    m = morphology.binary_closing(masker, morphology.disk(dicht))
    m = morphology.remove_small_objects(m, 120)
    sk = morphology.skeletonize(m)
    buren = ndi.convolve(sk.astype(np.uint8), np.ones((3,3), np.uint8), mode='constant') - sk
    inSk = set(zip(*[v.tolist() for v in np.nonzero(sk)]))
    knoop = set(zip(*[v.tolist() for v in np.nonzero(sk & (buren != 2))]))
    gebruikt, uit = set(), []
    def loop(start, eerste):
        pad = [start, eerste]; gebruikt.add((start,eerste)); gebruikt.add((eerste,start))
        hier, vorig = eerste, start
        while hier not in knoop:
            v = None
            for dy, dx in rondom:
                k = (hier[0]+dy, hier[1]+dx)
                if k != vorig and k in inSk: v = k; break
            if v is None: break
            gebruikt.add((hier,v)); gebruikt.add((v,hier))
            pad.append(v); vorig, hier = hier, v
        return pad
    for k in knoop:
        for dy, dx in rondom:
            bu = (k[0]+dy, k[1]+dx)
            if bu in inSk and (k,bu) not in gebruikt: uit.append(loop(k,bu))
    over = inSk - {p for l in uit for p in l}
    while over:
        st = next(iter(over)); pad=[st]; hier, vorig = st, None
        while True:
            v = None
            for dy, dx in rondom:
                k = (hier[0]+dy, hier[1]+dx)
                if k != vorig and k in over and k not in pad[1:]: v = k; break
            if v is None: break
            pad.append(v); vorig, hier = hier, v
        uit.append(pad); over -= set(pad)
    lijnen = []
    for pad in uit:
        if len(pad) < MINL: continue
        c = measure.approximate_polygon(np.array(pad, float), tolerance=4.0)
        if len(c) < 2: continue
        lijnen.append([naar(x, y) for y, x in c])
    return lijnen

def blokken_uit(masker, minopp, maxopp, minvul=0.55):
    """Compacte vlakken: gebouwen. Wegen zijn lang en dun en vallen af."""
    m = morphology.binary_closing(masker, morphology.disk(3))
    m = ndi.binary_fill_holes(m)
    m = morphology.remove_small_objects(m, minopp)
    lab, n = ndi.label(m)
    uit = []
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        deel = (lab[sl] == i); opp = int(deel.sum())
        if not (minopp <= opp <= maxopp): continue
        h, w = deel.shape
        if opp < minvul * h * w: continue                  # rafelig of langgerekt: geen gebouw
        if max(h, w) > 6 * min(h, w): continue
        ys, xs = np.nonzero(deel)
        randen = measure.find_contours(np.pad(deel,1).astype(float), .5)
        if not randen: continue
        c = measure.approximate_polygon(max(randen, key=len), tolerance=3.0)
        if len(c) < 4: continue
        ring = [naar(x + sl[1].start - 1, y + sl[0].start - 1) for y, x in c]
        if ring[0] != ring[-1]: ring.append(ring[0])
        uit.append(ring)
    return uit

kenmerken = []
def voeg(soort, meetk, **eig):
    kenmerken.append({'type':'Feature','properties':dict(soort=soort, **eig),'geometry':meetk})

tel = {}
for naam, m in MASKERS.items():
    if naam == 'geel': continue
    for lijn in lijnen_uit(m, 11 if naam == 'slecht' else 7,
                           dun_weg=2 if naam in ('tevoet', 'poort') else 0):
        voeg('ftx_' + naam, {'type':'LineString','coordinates':lijn})
        tel[naam] = tel.get(naam, 0) + 1

# een gebouw is hier ongeveer 15 tot 3000 m²
mn, mx = int(15/schaal**2), int(3000/schaal**2)
for ring in blokken_uit(ZALM, int(60/schaal**2), mx, minvul=0.62):
    voeg('ftx_gebouw', {'type':'Polygon','coordinates':[ring]}, echt=True)
tel['reeel gebouw'] = sum(1 for k in kenmerken if k['properties'].get('echt') is True)
for ring in blokken_uit(GRIJS, int(60/schaal**2), mx, minvul=0.68):
    voeg('ftx_gebouw', {'type':'Polygon','coordinates':[ring]}, echt=False)
tel['fictief gebouw'] = sum(1 for k in kenmerken if k['properties'].get('echt') is False)

fc = {'type':'FeatureCollection','stelsel':'wgs84',
      'bron':'FTX-overlay Leopoldsburg V 20240815; ondergrond niet overgenomen',
      'features':kenmerken}
json.dump(fc, open(S + '/uit/ftx_overlay.geojson','w'), separators=(',',':'), ensure_ascii=False)
print('overgenomen:', ', '.join(f'{k}: {v}' for k, v in tel.items()))
print(f'{len(kenmerken)} kenmerken')
