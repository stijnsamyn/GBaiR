#!/usr/bin/env bash
# PDF -> beeld -> versleuteld kaart.enc, in één keer.
#
#   ./maak-kaart.sh "Kaart WTC - Straatnamen (versie 2026).pdf"          (wachtwoord ACP)
#   ./maak-kaart.sh "plan.pdf" ANDERWACHTWOORD 600
#
set -euo pipefail
PDF="${1:?geef het pad naar de PDF}"
WW="${2:-ACP}"
DPI="${3:-400}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

echo "1/4  renderen op ${DPI} dpi…"
pdftoppm -r "$DPI" -png -f 1 -l 1 "$PDF" "$TMP/vol"

echo "2/4  witte rand wegsnijden…"
python3 - "$TMP" <<'PY'
import sys, glob
from PIL import Image, ImageChops
Image.MAX_IMAGE_PIXELS = None
src = sorted(glob.glob(sys.argv[1] + '/vol*.png'))[0]
im  = Image.open(src).convert('RGB')
d   = ImageChops.difference(im, Image.new('RGB', im.size, (255,255,255))).convert('L')
box = d.point(lambda p: 255 if p > 12 else 0).getbbox()
im.crop(box).save(sys.argv[1] + '/crop.png', optimize=True)
print(f'     volledige render {im.size[0]}x{im.size[1]}  ->  bbox {box}'
      f'  ->  {box[2]-box[0]}x{box[3]-box[1]}')
PY

echo "3/4  naar webp…"
cwebp -quiet -q 88 "$TMP/crop.png" -o kaart.webp
python3 -c "
from PIL import Image; import os
im = Image.open('kaart.webp')
print(f'     kaart.webp  {im.size[0]}x{im.size[1]}  {os.path.getsize(\"kaart.webp\")/1e6:.2f} MB'
      f'  verhouding {im.size[0]/im.size[1]:.4f}')"

echo "4/4  versleutelen…"
node versleutel.mjs kaart.webp "$WW"

cat <<'EOF'

Klaar. Noteer de bbox uit stap 2: bij een nieuwe versie van het plan moet
je exact zo bijsnijden, anders klopt de plaatsing niet meer.

Nu lokaal bekijken:   python3 -m http.server 8000
EOF
