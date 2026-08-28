"""Groepeert de blauwe letters tot woordgroepen en legt van elk een rechtgezette uitsnede vast."""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import binary_closing, disk
sys.path.insert(0, sys.argv[1]); from lagen import lees, maskers
S = sys.argv[1]

a = lees(S + '/plan.png')
blauw = maskers(a)['blauw']
# letters binnen één naam aan elkaar plakken, regels onderling niet
samen = binary_closing(blauw, disk(13))
lab, n = ndi.label(samen)
print('ruwe groepen:', n)

groepen = []
for i, sl in enumerate(ndi.find_objects(lab), start=1):
    comp = (lab[sl] == i) & blauw[sl]
    opp = int(comp.sum())
    if opp < 900:                      # losse spikkels
        continue
    ys, xs = np.nonzero(comp)
    ys = ys + sl[0].start; xs = xs + sl[1].start
    x0, y0 = float(xs.mean()), float(ys.mean())
    # hoofdrichting via eigenvectoren van de spreiding
    c = np.cov(np.vstack([xs - x0, ys - y0]))
    w, v = np.linalg.eigh(c)
    hoofd = v[:, np.argmax(w)]
    hoek = float(np.degrees(np.arctan2(hoofd[1], hoofd[0])))
    if hoek > 90: hoek -= 180
    if hoek <= -90: hoek += 180
    # lengte langs en dwars op de hoofdrichting
    ca, sa = np.cos(np.radians(hoek)), np.sin(np.radians(hoek))
    langs = (xs - x0) * ca + (ys - y0) * sa
    dwars = -(xs - x0) * sa + (ys - y0) * ca
    groepen.append(dict(id=len(groepen), x=x0, y=y0, hoek=hoek, opp=opp,
                        lengte=float(langs.max() - langs.min()),
                        dikte=float(dwars.max() - dwars.min()),
                        vak=[int(sl[1].start), int(sl[0].start), int(sl[1].stop), int(sl[0].stop)]))

groepen.sort(key=lambda g: (-g['lengte']))
for i, g in enumerate(groepen): g['id'] = i
print('woordgroepen:', len(groepen))
json.dump(groepen, open(S + '/uit/naamgroepen.json', 'w'), indent=1)

# rechtgezette uitsneden om te kunnen lezen
im = Image.open(S + '/plan.png').convert('RGB')
for g in groepen:
    x0, y0, x1, y1 = g['vak']
    p = 24
    sub = im.crop((x0 - p, y0 - p, x1 + p, y1 + p))
    sub = sub.rotate(g['hoek'], resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    h = 76
    sch = h / sub.height if sub.height else 1
    if sch != 1:
        sub = sub.resize((max(1, int(sub.width * sch)), h), Image.LANCZOS)
    sub.save(f"{S}/uit/naam_{g['id']:03d}.png")
print('uitsneden weggeschreven')
