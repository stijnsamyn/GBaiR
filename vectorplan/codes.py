"""Zoekt de zwarte bloktekst (MG-codes): losse lettertekens, daarna tot woorden gegroepeerd."""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import morphology
sys.path.insert(0, sys.argv[1]); from lagen import lees
sys.path.insert(0, sys.argv[1]); from uitsnede import strook
S = sys.argv[1]

a = lees(S + '/plan.png')
r, g, b = a[..., 0], a[..., 1], a[..., 2]
zwart = (r < 120) & (g < 120) & (b < 120)
lab, n = ndi.label(zwart)
print('zwarte componenten:', n)

# lettertekens: klein en compact; lijnwerk hangt aan elkaar in enorme componenten
opp = ndi.sum(zwart, lab, range(1, n + 1))
letters = np.zeros_like(zwart)
gehouden = 0
for i, sl in enumerate(ndi.find_objects(lab), start=1):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if 18 <= h <= 110 and 8 <= w <= 110 and 150 <= opp[i - 1] <= 4500:
        letters[sl] |= (lab[sl] == i); gehouden += 1
print('letterkandidaten:', gehouden)

samen = morphology.binary_closing(letters, morphology.disk(21))   # 'MG' en het nummer horen bij elkaar
lab2, n2 = ndi.label(samen)
groepen = []
for i, sl in enumerate(ndi.find_objects(lab2), start=1):
    comp = (lab2[sl] == i) & letters[sl]
    if comp.sum() < 700: continue
    ys, xs = np.nonzero(comp); ys = ys + sl[0].start; xs = xs + sl[1].start
    x0, y0 = float(xs.mean()), float(ys.mean())
    c = np.cov(np.vstack([xs - x0, ys - y0]))
    w_, v = np.linalg.eigh(c); hoofd = v[:, np.argmax(w_)]
    hoek = float(np.degrees(np.arctan2(hoofd[1], hoofd[0])))
    if hoek > 90: hoek -= 180
    if hoek <= -90: hoek += 180
    ca, sa = np.cos(np.radians(hoek)), np.sin(np.radians(hoek))
    langs = (xs - x0) * ca + (ys - y0) * sa; dwars = -(xs - x0) * sa + (ys - y0) * ca
    groepen.append(dict(x=x0, y=y0, hoek=hoek, opp=int(comp.sum()),
                        lengte=float(langs.max() - langs.min()), dikte=float(dwars.max() - dwars.min())))
groepen.sort(key=lambda d: (d['y'], d['x']))
for i, d in enumerate(groepen): d['id'] = i
json.dump(groepen, open(S + '/uit/codegroepen.json', 'w'), indent=1)
print('codegroepen:', len(groepen))

im = Image.open(S + '/plan.png').convert('RGB')
for d in groepen:
    strook(im, d['x'], d['y'], d['hoek'], d['lengte'], d['dikte'], pad=30, doel=46).save(
        f"{S}/uit/code_{d['id']:03d}.png")
print('stroken klaar')
