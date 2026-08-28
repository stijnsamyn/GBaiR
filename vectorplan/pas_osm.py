"""Legt het plan op de aarde door zijn gebouwen te laten samenvallen met die
van OpenStreetMap.

OSM weet niet hoe de gebouwen heten, maar wel waar ze liggen. Dat is precies
wat het plan mist. We zoeken dus de plaatsing waarbij de zwaartepunten van de
getekende gebouwen zo goed mogelijk op die van OSM vallen.

Eerst een grove gok uit de vorm van beide puntenwolken (zwaartepunt en
hoofdassen), daarna ICP: telkens elk gebouw aan zijn dichtstbijzijnde OSM-buur
koppelen en de best passende afbeelding opnieuw uitrekenen.
"""
import json, sys, math
import numpy as np
from scipy.spatial import cKDTree
S = sys.argv[1]
M_LAT = 111320.0
DOMEIN = 51686418          # way van het militaire domein in OSM
MARGE = 90                 # meter buiten het domein telt nog mee

# ---------- OSM-gebouwen op het domein ----------
el = json.load(open(S + '/uit/osm.json'))['elements']
grens = None
for e in el:
    if e.get('id') == DOMEIN and e.get('geometry'):
        grens = np.array([[q['lon'], q['lat']] for q in e['geometry']])
if grens is None: sys.exit('het domein (way %d) zit niet in osm.json' % DOMEIN)

lat0 = float(grens[:, 1].mean()); lon0 = float(grens[:, 0].mean())
kx = M_LAT * math.cos(math.radians(lat0)); ky = M_LAT
naarM = lambda lon, lat: np.stack([(np.asarray(lon) - lon0) * kx, (np.asarray(lat) - lat0) * ky], -1)
grensM = naarM(grens[:, 0], grens[:, 1])

def binnen(p, veelhoek, marge):
    """Punt in veelhoek, of er binnen `marge` meter naast."""
    x, y = p; n = len(veelhoek); raak = False
    for i in range(n):
        a, b = veelhoek[i], veelhoek[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            if x < (b[0]-a[0]) * (y-a[1]) / (b[1]-a[1]) + a[0]: raak = not raak
    if raak: return True
    d = np.min([np.hypot(*(p - veelhoek[i])) for i in range(n)])
    return d < marge

osm = []
for e in el:
    if 'building' not in e.get('tags', {}) or not e.get('geometry'): continue
    g = np.array([[q['lon'], q['lat']] for q in e['geometry']])
    m = naarM(g[:, 0], g[:, 1])
    c = m.mean(0)
    if not binnen(c, grensM, MARGE): continue
    x, y = m[:, 0], m[:, 1]
    opp = abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2
    osm.append((c, opp, e['id'], [[round(float(q['lon']), 7), round(float(q['lat']), 7)] for q in e['geometry']]))
osmopp = np.array([o for _, o, _, _ in osm])
osmid  = [i for _, _, i, _ in osm]
osmring = [r for _, _, _, r in osm]
osm = np.array([c for c, _, _, _ in osm])
print(f'OSM-gebouwen op het domein: {len(osm)}')

# ---------- gebouwen van het plan ----------
# In de eigen verhouding van de tekening, niet in het genormaliseerde vierkant:
# anders wordt het plan vóór het matchen al platgedrukt en past niets meer.
BREED, HOOG = 8945.0, 8108.0
VERH = BREED / HOOG
geb = json.load(open(S + '/uit/gebouwen.json'))
plan = np.array([[(g['zwaartepunt'][0] / BREED - .5) * VERH, .5 - g['zwaartepunt'][1] / HOOG]
                 for g in geb])
planopp = np.array([g['opp'] for g in geb], float)     # in px², straks in m²
print(f'gebouwen op het plan: {len(plan)}  (verhouding {VERH:.4f})')

# ---------- passing ----------
def pas(paren_p, paren_o):
    """Beste gelijkvormigheid (draaien, schalen, verschuiven) volgens Umeyama.

    Bewust geen volledige affiene afbeelding: die mag scheeftrekken, en dan
    praat ze verkeerde koppels goed in plaats van ze af te wijzen. Een plan
    dat klopt heeft geen scheeftrekking nodig.
    """
    mp, mo = paren_p.mean(0), paren_o.mean(0)
    A, B = paren_p - mp, paren_o - mo
    U, D, Vt = np.linalg.svd(B.T @ A / len(A))
    Sp = np.eye(2)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sp[1, 1] = -1     # geen spiegeling
    R = U @ Sp @ Vt
    schaal = float((D * np.diag(Sp)).sum() / max(A.var(0).sum(), 1e-12))
    M = schaal * R
    return np.vstack([M.T, mo - mp @ M.T])

def pas_affien(paren_p, paren_o):
    """Volledig affien -- alleen om achteraf te meten hoeveel scheeftrekking er in zit."""
    A = np.column_stack([paren_p[:, 0], paren_p[:, 1], np.ones(len(paren_p))])
    oplossing, *_ = np.linalg.lstsq(A, paren_o, rcond=None)
    return oplossing

def pas_toe(par, punten):
    A = np.column_stack([punten[:, 0], punten[:, 1], np.ones(len(punten))])
    return A @ par

def uit_par(par):
    (a, c), (b, d), (e, f) = par
    w = math.hypot(a, c) * VERH; h = math.hypot(b, d)
    h1 = math.degrees(math.atan2(-c, a)); h2 = math.degrees(math.atan2(b, d))
    scheef = (h1 - h2 + 180) % 360 - 180
    return dict(w=w, h=h, rot=h1 - scheef/2, scheef=scheef,
                lat=lat0 + f/ky, lon=lon0 + e/kx)

# grove gok uit zwaartepunt en hoofdassen van beide wolken
def gok(hoek_extra):
    mp, mo = plan.mean(0), osm.mean(0)
    Cp, Co = np.cov(plan.T), np.cov(osm.T)
    wp, Vp = np.linalg.eigh(Cp); wo, Vo = np.linalg.eigh(Co)
    Sp = Vp @ np.diag(1/np.sqrt(np.maximum(wp, 1e-12))) @ Vp.T
    So = Vo @ np.diag(np.sqrt(np.maximum(wo, 1e-12))) @ Vo.T
    t = math.radians(hoek_extra); R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    A = So @ R @ Sp
    if np.linalg.det(A) < 0: return None                 # spiegeling is niet fysisch
    return np.vstack([A.T, (mo - mp @ A.T)])

beste = None
for extra in (0, 90, 180, 270):
    par = gok(extra)
    if par is None: continue
    boom = cKDTree(osm)
    for ronde, snij in enumerate([200, 150, 120, 90, 70, 55, 45, 40, 35, 30] + [26]*20):
        heen = pas_toe(par, plan)
        afst, idx = boom.query(heen)
        kies = afst < snij
        if ronde > 6:
            # oppervlakte meeschalen met de huidige passing en grove uitschieters weren
            schaal = (math.hypot(par[0][0], par[0][1]) / VERH) ** 2 / (BREED * HOOG)
            verhouding_opp = (planopp * schaal * BREED * HOOG / (BREED * HOOG)) / np.maximum(osmopp[idx], 1)
            verhouding_opp = planopp * ((math.hypot(par[1][0], par[1][1]) / HOOG) ** 2) / np.maximum(osmopp[idx], 1)
            kies &= (verhouding_opp > .35) & (verhouding_opp < 3.0)
        if kies.sum() < 8: break
        par = pas(plan[kies], osm[idx[kies]])
    heen = pas_toe(par, plan)
    afst, idx = cKDTree(osm).query(heen)
    kies = afst < 26
    if kies.sum() < 8: continue
    rms = float(np.sqrt((afst[kies]**2).mean()))
    score = (kies.sum(), -rms)
    if beste is None or score > beste[0]:
        beste = (score, par, kies.sum(), rms, afst[kies])

if beste is None: sys.exit('geen passing gevonden')
_, par, aantal, rms, rest = beste

# hoeveel scheeftrekking zou een volledig affiene passing nog willen? Dat is de
# maat voor 'is deze tekening ingemeten of getekend'.
heen = pas_toe(par, plan)
afst, idx = cKDTree(osm).query(heen)
kies = afst < 26
scheefpar = pas_affien(plan[kies], osm[idx[kies]])
scheef_af = uit_par(scheefpar)
p = uit_par(par)
print(f'\ngekoppeld: {aantal} van de {len(plan)} gebouwen')
print(f'afwijking: gemiddeld {rms:.1f} m, mediaan {np.median(rest):.1f} m, grootste {rest.max():.1f} m')
print(f'breedte {p["w"]:.1f} m, hoogte {p["h"]:.1f} m, draaiing {p["rot"]:.2f}°')
print(f'een volledig affiene passing zou {scheef_af["scheef"]:.2f}° scheeftrekking willen '
      f'en {scheef_af["w"]/scheef_af["h"]:.4f} als verhouding (nu {p["w"]/p["h"]:.4f})')
print()
voorstel = {'versie': 2, 'lat': round(p['lat'], 7), 'lon': round(p['lon'], 7),
            'w': round(p['w'], 1), 'h': round(p['h'], 1), 'rot': round(p['rot'], 2),
            'opmerking': f'gepast op {aantal} OSM-gebouwen, gemiddeld {rms:.1f} m afwijking'}
print(json.dumps(voorstel, indent=2, ensure_ascii=False))
json.dump(voorstel, open(S + '/uit/plaatsing_voorstel.json', 'w'), indent=2, ensure_ascii=False)

# ---------- wie hoort bij wie ----------
# Elk plangebouw krijgt zijn OSM-tegenhanger toegewezen, en niet twee keer
# dezelfde: het dichtste koppel wint.
heen = pas_toe(par, plan)
afst_alle, idx_alle = cKDTree(osm).query(heen)
volgorde = np.argsort(afst_alle)
bezet, koppels = set(), {}
for i in volgorde:
    if afst_alle[i] > 26: break
    j = int(idx_alle[i])
    if j in bezet: continue
    opp_plan = planopp[i] * (p['h'] / HOOG) ** 2
    if not (.35 < opp_plan / max(osmopp[j], 1) < 3.0): continue
    bezet.add(j); koppels[int(geb[i]['id'])] = dict(osm_id=int(osmid[j]),
                                                    afstand=round(float(afst_alle[i]), 1))
print(f'\néén-op-één gekoppeld: {len(koppels)} gebouwen')

json.dump({'plaatsing': voorstel,
           'koppels': koppels,
           'osm_gebouwen': [{'id': int(osmid[j]), 'ring': osmring[j]} for j in range(len(osm))],
           'bron': 'OpenStreetMap-bijdragers, ODbL'},
          open(S + '/uit/passing.json', 'w'), separators=(',', ':'))
print('passing.json geschreven')
