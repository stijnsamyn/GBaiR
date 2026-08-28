"""Zet de uitsneden op contactbladen, met hun nummer ernaast, om ze te kunnen lezen."""
import json, sys, glob, os
from PIL import Image, ImageDraw
S = sys.argv[1]; voorvoegsel = sys.argv[2]; perblad = int(sys.argv[3])
bestanden = sorted(glob.glob(f'{S}/uit/{voorvoegsel}_*.png'))
MARGE = 70
for b in range(0, len(bestanden), perblad):
    groep = bestanden[b:b + perblad]
    R = max(Image.open(f).height for f in groep) + 8
    breed = max(Image.open(f).width for f in groep) + MARGE + 20
    blad = Image.new('RGB', (max(breed, 420), R * len(groep) + 10), 'white')
    t = ImageDraw.Draw(blad)
    for i, f in enumerate(groep):
        im = Image.open(f); y = 5 + i * R
        blad.paste(im, (MARGE, y + (R - im.height) // 2))
        t.text((8, y + 30), os.path.basename(f).split('_')[1].split('.')[0], fill='red')
        t.line((0, y, blad.width, y), fill=(220, 220, 220))
    uit = f'{S}/uit/blad_{voorvoegsel}_{b // perblad:02d}.png'
    blad.save(uit); print(uit, blad.size)
