"""Haalt de gevulde vlakken (gebouwen) uit het plan als veelhoeken.

De arcering in de rode zones onderbreekt de vulling, dus die gaten moeten dicht;
maar de zwarte omtrek tussen twee aanpalende gebouwen moet juist blijven staan,
anders lopen ze aan elkaar. Vandaar: eerst dichten langs de arceerrichting,
daarna opnieuw opensnijden op het zwarte lijnwerk.
"""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure, morphology
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else '.')
from lagen import lees

S = sys.argv[1]
MINOPP = 900          # ~9 m² bij 8,9 px/m; kleiner is tekening, geen gebouw

a = lees(S + '/plan.png')
r, g, b = a[..., 0], a[..., 1], a[..., 2]
grijs = (abs(r - g) < 16) & (abs(g - b) < 16) & (abs(r - b) < 16)
roze  = (r - g > 20) & (r - g < 90) & (abs(g - b) < 16) & (g > 130) & (g < 225)
zwart = (r < 120) & (g < 120) & (b < 120)

lagen = {
    'gebouw':    (grijs & (r >= 130) & (r <= 205)) | (roze & (g >= 130) & (g <= 205)),
    'bijgebouw':  grijs & (r > 205) & (r <= 236),
}

snee = morphology.binary_dilation(zwart, morphology.disk(2))

uit = []
for soort, m in lagen.items():
    m = morphology.binary_opening(m, morphology.disk(4))          # de grijze zoom langs elk lijntje weg
    m = morphology.binary_closing(m, morphology.disk(6))           # de arcering laat ~6 px open; meer niet
    m = ndi.binary_fill_holes(m) & ~snee                           # en weer opensnijden op de omtrek
    m = morphology.remove_small_objects(m, MINOPP)
    lab, n = ndi.label(m)
    print(f'{soort}: {n} vlakken')
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        deel = (lab[sl] == i)
        opp = int(deel.sum())
        if opp < MINOPP: continue
        # boomranden en wegzomen laten lange, dunne, rafelige snippers na; die zijn geen gebouw
        ys_, xs_ = np.nonzero(deel)
        mx, my = xs_.mean(), ys_.mean()
        w_, v_ = np.linalg.eigh(np.cov(np.vstack([xs_ - mx, ys_ - my])))
        hoofd = v_[:, np.argmax(w_)]
        ca, sa = hoofd[0], hoofd[1]
        langs = (xs_ - mx) * ca + (ys_ - my) * sa
        dwars = -(xs_ - mx) * sa + (ys_ - my) * ca
        lengte, dikte = np.ptp(langs), np.ptp(dwars)
        # groot en rafelig mag (gebouwen in de arcering), klein en rafelig is ruis
        if dikte < 14 or (opp < 5000 and opp < 0.5 * lengte * dikte):
            continue
        randen = measure.find_contours(np.pad(deel, 1).astype(float), 0.5)
        if not randen: continue
        c = measure.approximate_polygon(max(randen, key=len), tolerance=5.0)
        if len(c) < 4: continue
        ys = c[:, 0] + sl[0].start - 1; xs = c[:, 1] + sl[1].start - 1
        uit.append(dict(soort=soort, opp=opp,
                        zwaartepunt=[round(float(xs.mean()), 1), round(float(ys.mean()), 1)],
                        rand=[[round(float(x), 1), round(float(y), 1)] for x, y in zip(xs, ys)]))
uit.sort(key=lambda d: -d['opp'])
for i, d in enumerate(uit): d['id'] = i
json.dump(uit, open(S + '/uit/gebouwen.json', 'w'))
print('totaal vlakken:', len(uit), ' hoekpunten:', sum(len(d['rand']) for d in uit))
