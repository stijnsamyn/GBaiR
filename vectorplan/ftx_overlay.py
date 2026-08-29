"""Neemt de FTX-overlay over van de gescande kaart van Leopoldsburg.

Alleen wat de opsteller er zelf op getekend heeft; de ondergrond blijft achter.
OpenStreetMap levert de straten en de gebouwen al, dit levert wat OSM niet weet:
waar je niet door kan, waar een poort staat, en welke gebouwen voor de oefening
echt zijn en welke verzonnen.

Drie kleuren van de ondergrond lijken op een overlay-kleur; alle drie worden ze
op dezelfde manier ontmaskerd, namelijk aan hun kern:

* De zalmroze hoofdwegen hebben dezelfde kleur als een reeel gebouw. Ze vormen
  wel een samenhangend net -- maar dat net valt uiteen waar een straatnaam of
  een richtingspijl eroverheen ligt, en zo'n brok ziet er uit als een gebouw.
  Daarom wordt het net opgespoord op zalm plus donkere tekst samen.
* De roodbruine tekst ("Militair Kamp") heeft een zalmkleurige antialiasrand.
  Weg ermee als er felrode punten binnen de vorm liggen.
* De grijze straatnamen hebben een grijze antialiasrand in dezelfde toon als
  een fictief gebouw. Weg ermee als er donkere punten binnen de vorm liggen;
  een echt blokje is vlak grijs, zonder donkere kern.

De codes bij de gebouwen (E41, Mess, K20 ...) zijn met het oog van de scan
gelezen -- niet met OCR: de tekst is klein en loopt door lijnwerk heen. Ze
staan hieronder als aanwijspunt in scanpunten van het kader; de code gaat naar
het vlak waar dat punt in valt.
"""
import json, sys, math
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure, morphology
Image.MAX_IMAGE_PIXELS = None
S, SCAN = sys.argv[1], sys.argv[2]

# Met het oog gelezen van de scan; punt ligt in het vlak dat de code draagt.
CODES = {
    'Parking Bernheim': (3607,  653),
    'Mess':             (4990, 1224),
    'E51':              (3915, 2019),
    'E41':              (4175, 2104),
    'E53':              (3782, 2166),
    'E52':              (3929, 2164),
    'K20':              (1210, 2955),
    'K21':              (1381, 2937),
    'K22':              (1235, 3151),
    'K23':              (1397, 3125),
}
POORTCODES = {'Toegang kamp': (4042, 1440)}
# De genummerde stratenlijst uit de legende. De cijfers staan op de kaart in
# een bouwblok naast de straat, niet op de straat zelf; welke lijn er precies
# bij hoort is niet met zekerheid af te lezen, dus blijft het bij het punt
# waar het cijfer gedrukt staat.
NUMMERS = [(1, 'Kapelstraat',            ( 854, 3424)),
           (2, 'Parkingstraat',          (1094, 3399)),
           (3, 'Complexstraat',          (1286, 3380)),
           (4, 'Keukenstraat',           (1541, 3359)),
           (5, 'De Wittelaan (zuid)',    (1846, 3321)),
           (8, 'Prins Filip (oost-west)',( 918, 3301))]

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

# Het rode kader van de kaart zelf; daarbuiten staan legende en bijschriften.
rood_lijn = (r > 200) & (g < 80) & (b < 80)
rij, kol = rood_lijn.sum(1), rood_lijn.sum(0)
ry = np.nonzero(rij > W * 0.45)[0]; rx = np.nonzero(kol > H * 0.5)[0]
y0, y1, x0, x1 = ry[0], ry[-1], rx[0], rx[-1]
buiten = np.ones((H, W), bool)
buiten[y0:y1 + 1, x0:x1 + 1] = False
buiten[:int(H*0.13), int(W*0.76):] = True          # de inzet rechtsboven
buiten[int(H*0.83):, int(W*0.82):] = True          # schaalkader en versiedoos
buiten[int(H*0.90):, :int(W*0.17)] = True          # het logo en de schaalbalk linksonder

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

DONKER = morphology.binary_dilation((r < 145) & (g < 145) & (b < 145), morphology.disk(3))
FELROOD = morphology.binary_dilation((r > 190) & (g < 120), morphology.disk(3))

# Het zalmroze wegennet: eerst de tekst die erop ligt dichtgooien, anders valt
# het net uiteen in brokken die op gebouwen lijken.
zalm_alles = dichtbij((247, 170, 152), 26)
_net = morphology.binary_closing(zalm_alles | ((r < 150) & (g < 150) & (b < 150)),
                                 morphology.disk(8))
_lab, _n = ndi.label(_net)
_opp = np.bincount(_lab.ravel()); _opp[0] = 0
_weg = np.isin(_lab, np.nonzero(_opp > 20000)[0])
ZALM = zalm_alles & ~morphology.binary_dilation(_weg, morphology.disk(3))
GRIJS = (abs(r - g) < 10) & (abs(g - b) < 10) & (r > 150) & (r < 200) & ~buiten
# De blauwe blokken K20-K23 linksonder: lichtblauwe vulling, donkerblauwe rand.
BLAUW = (b > r + 45) & (b > g + 20) & (b > 170) & (r > 90) & (r < 200) & ~buiten

MINL = int(12 / schaal)          # korter dan 12 m is ruis
rondom = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def lijnen_uit(masker, dicht=9, dun_weg=0):
    """Verbindt de streepjes, dunt uit tot een punt breed, en loopt het skelet af.

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
        lijnen.append(([naar(x, y) for y, x in c], [(x, y) for y, x in c]))
    return lijnen

def blokken_uit(masker, minopp, maxopp, minvul=0.55, vuil=None):
    """Compacte vlakken: gebouwen. Wegen zijn lang en dun en vallen af.

    `vuil` is een masker van kernpunten die er niet in horen: een vorm die er
    veel van bevat is geen gebouw maar de antialiasrand van tekst."""
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
        if vuil is not None and (deel & vuil[sl]).sum() > 0.3 * opp: continue
        randen = measure.find_contours(np.pad(deel,1).astype(float), .5)
        if not randen: continue
        c = measure.approximate_polygon(max(randen, key=len), tolerance=3.0)
        if len(c) < 4: continue
        pix = [(x + sl[1].start - 1, y + sl[0].start - 1) for y, x in c]
        ring = [naar(px, py) for px, py in pix]
        if ring[0] != ring[-1]: ring.append(ring[0]); pix.append(pix[0])
        uit.append((ring, (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)))
    return uit

kenmerken = []
def voeg(soort, meetk, **eig):
    kenmerken.append({'type':'Feature','properties':dict(soort=soort, **eig),'geometry':meetk})
    return kenmerken[-1]

tel = {}
poortlijnen = []
for naam, m in MASKERS.items():
    if naam == 'geel': continue
    for lijn, pix in lijnen_uit(m, 11 if naam == 'slecht' else 7,
                                dun_weg=2 if naam in ('tevoet', 'poort') else 0):
        k = voeg('ftx_' + naam, {'type':'LineString','coordinates':lijn})
        if naam == 'poort': poortlijnen.append((k, pix))
        tel[naam] = tel.get(naam, 0) + 1

vlakken = []
def zet(soort, blokken, **eig):
    for ring, bb in blokken:
        vlakken.append((voeg(soort, {'type':'Polygon','coordinates':[ring]}, **eig), bb))
    tel[eig.get('_naam', soort)] = len(blokken)

# een reeel gebouw loopt hier op tot een kleine 4000 m2 (de Mess)
zet('ftx_gebouw', blokken_uit(ZALM, int(60/schaal**2), int(5000/schaal**2),
                              minvul=0.62, vuil=FELROOD), echt=True, _naam='reeel gebouw')
zet('ftx_gebouw', blokken_uit(GRIJS, int(60/schaal**2), int(3000/schaal**2),
                              minvul=0.68, vuil=DONKER), echt=False, _naam='fictief gebouw')
zet('ftx_blok',   blokken_uit(BLAUW, int(500/schaal**2), int(3000/schaal**2),
                              minvul=0.65), _naam='blauw blok')
for k, _ in vlakken: k['properties'].pop('_naam', None)

# de gelezen codes aan hun vlak hangen
kwijt = []
for code, (px, py) in CODES.items():
    raak = [k for k, bb in vlakken if bb[0] <= px <= bb[2] and bb[1] <= py <= bb[3]]
    if len(raak) == 1: raak[0]['properties']['code'] = code
    else: kwijt.append(code)
for code, (px, py) in POORTCODES.items():
    dicht = min(poortlijnen, key=lambda kp: min(math.hypot(x-px, y-py) for x, y in kp[1]),
                default=None)
    if dicht and min(math.hypot(x-px, y-py) for x, y in dicht[1]) < 80:
        dicht[0]['properties']['code'] = code
    else: kwijt.append(code)
for nr, naam, (px, py) in NUMMERS:
    voeg('ftx_nummer', {'type':'Point','coordinates':naar(px, py)}, nr=nr, naam=naam)
tel['nummer'] = len(NUMMERS)

fc = {'type':'FeatureCollection','stelsel':'wgs84',
      'bron':'FTX-overlay Leopoldsburg V 20240815; ondergrond niet overgenomen',
      'features':kenmerken}
json.dump(fc, open(S + '/uit/ftx_overlay.geojson','w'), separators=(',',':'), ensure_ascii=False)
print('overgenomen:', ', '.join(f'{k}: {v}' for k, v in tel.items()))
gezet = sum(1 for k in kenmerken if 'code' in k['properties'])
print(f'{len(kenmerken)} kenmerken, {gezet} met code' + (f'; niet geplaatst: {kwijt}' if kwijt else ''))
