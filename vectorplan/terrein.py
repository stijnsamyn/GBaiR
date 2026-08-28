"""Het overige lijnwerk: terreingrens, perceelgrenzen, wegranden, boomranden.

Alles wat nog zwart op het plan staat nadat de gebouwen en de tekst eraf zijn,
is tekening van het terrein zelf. Dat wordt hier tot één pixel dun gemaakt en
daarna als lijnen uitgelezen. Wiebelige lijnen zijn boomranden en krijgen een
veel grovere vereenvoudiging: ze hoeven alleen herkenbaar te zijn, niet exact.
"""
import json, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology
sys.path.insert(0, sys.argv[1]); from lagen import lees
S = sys.argv[1]
PXM = 8.89
MIN_LENGTE = int(4 * PXM)        # korter dan 4 m is een streepje, geen lijn

a = lees(S + '/plan.png')
r, g, b = a[..., 0], a[..., 1], a[..., 2]
inkt = (r < 130) & (g < 130) & (b < 130)
grijs = (abs(r - g) < 16) & (abs(g - b) < 16) & (abs(r - b) < 16)
vulling = (grijs & (r >= 130) & (r <= 236)) | \
          ((r - g > 20) & (r - g < 90) & (abs(g - b) < 16) & (g > 130) & (g < 225))

# De gebouwen hebben we al; hun omtrek ligt vlak naast de vulling, dus die
# vulling wat uitzetten volstaat. Niet dichtvullen: de gebouwen vormen samen
# een gesloten net, en dan zou het hele terrein als 'gedekt' gelden.
# eerst de grijze zoom langs elke zwarte lijn weg, anders geldt al het
# lijnwerk als vulling en blijft er niets over
vulling = morphology.binary_opening(vulling, morphology.disk(4))
gedekt = morphology.binary_dilation(vulling, morphology.disk(8))

# de bloktekst ook: kleine compacte zwarte klodders
lab, n = ndi.label(inkt)
opp = ndi.sum(inkt, lab, range(1, n + 1))
tekst = np.zeros_like(inkt)
for i, sl in enumerate(ndi.find_objects(lab), start=1):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if 18 <= h <= 110 and 8 <= w <= 110 and 150 <= opp[i - 1] <= 4500:
        tekst[sl] |= (lab[sl] == i)
tekst = morphology.binary_dilation(tekst, morphology.disk(6))

rest = inkt & ~gedekt & ~tekst
rest = morphology.remove_small_objects(rest, 120)
skelet = morphology.skeletonize(rest)
print('overgebleven lijnpixels:', int(skelet.sum()))

# --- skelet aflopen tot losse lijnen ---
buren = ndi.convolve(skelet.astype(np.uint8), np.ones((3, 3), np.uint8), mode='constant') - skelet
knoop = skelet & (buren != 2)                      # uiteinden en kruisingen
ys, xs = np.nonzero(skelet)
inSkelet = set(zip(ys.tolist(), xs.tolist()))
knoopset = set(zip(*[v.tolist() for v in np.nonzero(knoop)]))
H, W = skelet.shape
rondom = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

gebruikt = set()
lijnen = []
def loop(start, eerste):
    pad = [start, eerste]
    gebruikt.add((start, eerste)); gebruikt.add((eerste, start))
    hier, vorig = eerste, start
    while hier not in knoopset:
        volgende = None
        for dy, dx in rondom:
            k = (hier[0] + dy, hier[1] + dx)
            if k != vorig and k in inSkelet: volgende = k; break
        if volgende is None: break
        gebruikt.add((hier, volgende)); gebruikt.add((volgende, hier))
        pad.append(volgende); vorig, hier = hier, volgende
    return pad

for k in knoopset:
    for dy, dx in rondom:
        buur = (k[0] + dy, k[1] + dx)
        if buur in inSkelet and (k, buur) not in gebruikt:
            lijnen.append(loop(k, buur))
# gesloten lussen zonder enkel knooppunt (bv. een omheining rondom)
over = inSkelet - {p for l in lijnen for p in l}
while over:
    start = next(iter(over))
    pad, hier, vorig = [start], start, None
    while True:
        volgende = None
        for dy, dx in rondom:
            k = (hier[0] + dy, hier[1] + dx)
            if k != vorig and k in over and k not in pad[1:]: volgende = k; break
        if volgende is None: break
        pad.append(volgende); vorig, hier = hier, volgende
    lijnen.append(pad)
    over -= set(pad)
print('ruwe lijnen:', len(lijnen))

uit = []
for pad in lijnen:
    if len(pad) < MIN_LENGTE: continue
    p = np.array(pad, float)
    recht = np.hypot(*(p[0] - p[-1]))
    kronkel = len(pad) / max(recht, 1)
    soort = 'boomrand' if kronkel > 1.9 else 'lijn'
    tol = 14.0 if soort == 'boomrand' else 4.0
    c = measure.approximate_polygon(p, tolerance=tol)
    if len(c) < 2: continue
    uit.append(dict(soort=soort, punten=[[round(float(x), 1), round(float(y), 1)] for y, x in c]))

uit.sort(key=lambda d: -len(d['punten']))
print('lijnen:', len(uit), ' waarvan boomrand:', sum(1 for d in uit if d['soort'] == 'boomrand'),
      ' hoekpunten:', sum(len(d['punten']) for d in uit))
json.dump(uit, open(S + '/uit/terrein.json', 'w'))
