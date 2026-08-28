"""Contactblad in kolommen, zodat het blad ongeveer vierkant blijft en leesbaar downschaalt."""
import sys, glob, os
from PIL import Image, ImageDraw
S, voorvoegsel, rijen, kol = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
bestanden = sorted(glob.glob(f'{S}/uit/{voorvoegsel}_*.png'))
perblad = rijen * kol
for b in range(0, len(bestanden), perblad):
    groep = bestanden[b:b + perblad]
    R = max(Image.open(f).height for f in groep) + 10
    K = max(Image.open(f).width for f in groep) + 78
    blad = Image.new('RGB', (K * kol, R * rijen), 'white')
    t = ImageDraw.Draw(blad)
    for i, f in enumerate(groep):
        im = Image.open(f); c, r = divmod(i, rijen)
        x, y = c * K, r * R
        blad.paste(im, (x + 66, y + (R - im.height) // 2))
        t.text((x + 6, y + R // 2 - 6), os.path.basename(f).split('_')[1].split('.')[0], fill='red')
        t.line((x, y, x + K, y), fill=(215, 215, 215)); t.line((x, y, x, y + R), fill=(215, 215, 215))
    uit = f'{S}/uit/kblad_{voorvoegsel}_{b // perblad:02d}.png'
    blad.save(uit); print(uit, blad.size)
