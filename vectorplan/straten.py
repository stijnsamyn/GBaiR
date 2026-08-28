"""Bouwt uit de gelezen labels de straatgeometrie.

De tekenaar zet de naam middenop de weg, in de richting van de weg. Dat is het
betrouwbaarste houvast dat het plan geeft: uit elk label groeit een as langs zijn
eigen richting, tot de doorgang aan weerszijden dichtloopt.
"""
import json, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology
sys.path.insert(0, sys.argv[1]); from lagen import lees
S = sys.argv[1]
STAP, HALF, DREMPEL, MAXLENGTE = 4, 22, 0.40, 1600
ZIJKANT, GEDULD = 110, 18      # een weg heeft randen; zonder rand zijn we in open veld

# Namen die over twee regels of twee richtingen staan horen bij één straat.
# Die tabel staat in koppel.json en niet hier: dit bestand zit in een publieke
# repo en mag geen straatnamen bevatten.
_k = json.load(open(S + '/uit/koppel.json'))
KOPPEL      = {int(k): v for k, v in _k['twee_regels'].items()}
GEEN_STRAAT = {int(k): v for k, v in _k['geen_straat'].items()}
GESPLITST   = {int(k): v for k, v in _k['gesplitst'].items()}

a = lees(S + '/plan.png')
r, g, b = a[..., 0], a[..., 1], a[..., 2]
inkt = (r < 130) & (g < 130) & (b < 130)
grijs = (abs(r - g) < 16) & (abs(g - b) < 16) & (abs(r - b) < 16)
gevuld = (grijs & (r >= 130) & (r <= 236)) | ((r - g > 20) & (r - g < 90) & (abs(g - b) < 16) & (g > 130) & (g < 225))
bezet = inkt | gevuld
H, W = bezet.shape

groepen = {x['id']: x for x in json.load(open(S + '/uit/naamgroepen.json'))}
tekst = json.load(open(S + '/uit/naamtekst.json'))
blauw = (b - r > 60) & (b - g > 60) & (b > 120)

def splits(gid, straal=7):
    """Twee namen die elkaar kruisen zijn tot één groep samengeklonterd; hier weer los."""
    v = groepen[gid]; x0, y0, x1, y1 = v['vak']
    deel = blauw[y0:y1, x0:x1]
    lab, n = ndi.label(morphology.binary_closing(deel, morphology.disk(straal)))
    stukken = []
    for i in range(1, n + 1):
        m = (lab == i) & deel
        if m.sum() < 900: continue
        ys, xs = np.nonzero(m); mx, my = xs.mean() + x0, ys.mean() + y0
        w_, vec = np.linalg.eigh(np.cov(np.vstack([xs - xs.mean(), ys - ys.mean()])))
        hd = vec[:, np.argmax(w_)]
        hoek = float(np.degrees(np.arctan2(hd[1], hd[0])))
        hoek = hoek - 180 if hoek > 90 else (hoek + 180 if hoek <= -90 else hoek)
        ca, sa = np.cos(np.radians(hoek)), np.sin(np.radians(hoek))
        lg = (xs + x0 - mx) * ca + (ys + y0 - my) * sa
        stukken.append(dict(x=float(mx), y=float(my), hoek=hoek, lengte=float(np.ptp(lg)), opp=int(m.sum())))
    return sorted(stukken, key=lambda d: -d['lengte'])

def rand_nabij(px, py, nx, ny):
    """Staat er binnen ZIJKANT px nog een rand langs de weg? Eén kant volstaat:
    aan een plein of een berm valt de andere kant weg zonder dat de weg ophoudt."""
    d = np.arange(HALF, ZIJKANT)
    for teken in (+1, -1):
        xs = np.clip((px + teken * d * nx).astype(int), 0, W - 1)
        ys = np.clip((py + teken * d * ny).astype(int), 0, H - 1)
        if bezet[ys, xs].any():
            return True
    return False

def groei(x, y, hoek):
    """Loopt vanuit het label beide kanten op tot de doorgang dichtloopt of
    tot de weg zijn randen verliest — dan staan we in open veld."""
    ca, sa = np.cos(np.radians(hoek)), np.sin(np.radians(hoek))
    nx, ny = -sa, ca
    d = np.linspace(-HALF, HALF, 11)
    uiteinden = []
    for teken in (+1, -1):
        s, randloos, laatste_goed = 0.0, 0, 0.0
        while s < MAXLENGTE:
            s += STAP
            px, py = x + teken * s * ca, y + teken * s * sa
            xs = np.clip((px + d * nx).astype(int), 0, W - 1)
            ys = np.clip((py + d * ny).astype(int), 0, H - 1)
            if bezet[ys, xs].mean() > DREMPEL:
                s -= STAP; break
            if rand_nabij(px, py, nx, ny):
                randloos, laatste_goed = 0, s
            else:
                randloos += 1
                if randloos > GEDULD:
                    s = laatste_goed; break
        uiteinden.append((x + teken * s * ca, y + teken * s * sa))
    return uiteinden

ankers = []
for gid, v in groepen.items():
    if gid in GEEN_STRAAT: continue
    naam = KOPPEL.get(gid) or tekst[str(gid)].lstrip('?')
    delen = splits(gid) if v['dikte'] > 90 else [v]
    for d in delen:
        ankers.append(dict(gid=gid, naam=naam, x=d['x'], y=d['y'], hoek=d['hoek'], lengte=d['lengte']))

# waar twee namen elkaar kruisen zijn ze als één groep gevonden; toewijzen op richting
for gid, regel in GESPLITST.items():
    for A in [x for x in ankers if x['gid'] == gid]:
        A['naam'] = regel['steil'] if abs(A['hoek']) > regel['grens_hoek'] else regel['vlak']

for A in ankers:
    (p, q) = groei(A['x'], A['y'], A['hoek'])
    A['as'] = [[round(p[0], 1), round(p[1], 1)], [round(q[0], 1), round(q[1], 1)]]
    A['aslengte'] = round(float(np.hypot(q[0] - p[0], q[1] - p[1])), 1)

json.dump(ankers, open(S + '/uit/straatankers.json', 'w'), indent=1)
namen = sorted({A['naam'] for A in ankers})
print(f'ankers: {len(ankers)}   straten: {len(namen)}')
print('mediane aslengte: %.0f px (%.0f m)' % (np.median([A['aslengte'] for A in ankers]),
                                              np.median([A['aslengte'] for A in ankers]) / 8.89))
print(', '.join(namen))
