"""Tekent de gevonden veelhoeken over het plan, om te kunnen nakijken."""
import json, sys
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None
S = sys.argv[1]; f = float(sys.argv[2]) if len(sys.argv) > 2 else 0.16
vak = [int(v) for v in sys.argv[3].split(',')] if len(sys.argv) > 3 else None

im = Image.open(S + '/plan.png').convert('RGB')
if vak: im = im.crop(vak)
im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
t = ImageDraw.Draw(im, 'RGBA')
dx, dy = (vak[0], vak[1]) if vak else (0, 0)
for d in json.load(open(S + '/uit/gebouwen.json')):
    p = [((x - dx) * f, (y - dy) * f) for x, y in d['rand']]
    kleur = (0, 170, 0) if d['soort'] == 'gebouw' else (255, 140, 0)
    t.polygon(p, fill=kleur + (70,), outline=kleur + (255,))
im.save(S + '/uit/controle.png'); print(im.size)
