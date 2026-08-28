"""Snijdt elke woordgroep als een rechte strook uit: draaien om het zwaartepunt, dan de band eruit."""
import json, sys
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

def strook(im, cx, cy, hoek, lengte, dikte, pad=22, doel=52):
    zij = int(max(lengte, dikte) * 1.5 + 4 * pad)
    vak = (int(cx - zij / 2), int(cy - zij / 2), int(cx + zij / 2), int(cy + zij / 2))
    sub = im.crop(vak)                                    # buiten het beeld vult PIL zwart, daarom wit erachter
    vlak = Image.new('RGB', sub.size, (255, 255, 255)); vlak.paste(sub); sub = vlak
    sub = sub.rotate(hoek, resample=Image.BICUBIC, center=(sub.width / 2, sub.height / 2), fillcolor=(255, 255, 255))
    hw, hh = (lengte / 2 + pad), (dikte / 2 + pad)
    band = sub.crop((int(sub.width / 2 - hw), int(sub.height / 2 - hh),
                     int(sub.width / 2 + hw), int(sub.height / 2 + hh)))
    sch = doel / max(dikte, 10)
    return band.resize((max(1, int(band.width * sch)), max(1, int(band.height * sch))), Image.LANCZOS)

if __name__ == '__main__':
    S = sys.argv[1]
    im = Image.open(S + '/plan.png').convert('RGB')
    for g in json.load(open(S + '/uit/naamgroepen.json')):
        strook(im, g['x'], g['y'], g['hoek'], g['lengte'], g['dikte']).save(f"{S}/uit/naam_{g['id']:03d}.png")
    print('stroken klaar')
