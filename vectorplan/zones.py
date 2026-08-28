"""De rood gearceerde zones als veelhoeken."""
import json, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology
sys.path.insert(0, sys.argv[1]); from lagen import lees
S = sys.argv[1]
a = lees(S + '/plan.png')
r, g, b = a[..., 0], a[..., 1], a[..., 2]
zone = (r - g > 18) & (r - b > 18) & (r > 195)          # rode arcering én de lichtroze ondergrond
zone = morphology.binary_closing(zone, morphology.disk(14))
zone = ndi.binary_fill_holes(zone)
zone = morphology.remove_small_objects(zone, 40000)      # < 500 m² is geen zone
lab, n = ndi.label(zone)
uit = []
for i, sl in enumerate(ndi.find_objects(lab), start=1):
    deel = ndi.binary_fill_holes(lab[sl] == i)
    randen = measure.find_contours(np.pad(deel, 1).astype(float), 0.5)
    if not randen: continue
    c = measure.approximate_polygon(max(randen, key=len), tolerance=12.0)
    ys = c[:, 0] + sl[0].start - 1; xs = c[:, 1] + sl[1].start - 1
    uit.append(dict(opp=int(deel.sum()),
                    rand=[[round(float(x), 1), round(float(y), 1)] for x, y in zip(xs, ys)]))
uit.sort(key=lambda d: -d['opp'])
print('zones:', len(uit), ' oppervlakken (m²):', [round(d['opp'] / 79.0) for d in uit])
json.dump(uit, open(S + '/uit/zones.json', 'w'))
