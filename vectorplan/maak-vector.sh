#!/usr/bin/env bash
# PDF -> vectorlaag -> versleuteld plan.enc.
#
#   ./vectorplan/maak-vector.sh "Kaart WTC - Straatnamen (versie 2026).pdf" [werkmap] [wachtwoord]
#
# Nodig: pdftoppm (poppler), python met numpy, scipy, scikit-image, shapely, pillow,
# en node voor het versleutelen. Zet die python-pakketten desnoods in een venv:
#   python3 -m venv .venv && .venv/bin/pip install numpy scipy scikit-image shapely pillow
#   PY=.venv/bin/python ./vectorplan/maak-vector.sh plan.pdf
set -euo pipefail
PDF="${1:?geef het pad naar de PDF}"
WERK="${2:-vectorplan/werk}"
WW="${3:-ACP}"
PY="${PY:-python3}"
HIER="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$WERK/uit"

echo "1/9  renderen op 1000 dpi…"
[ -f "$WERK/master-1.png" ] || pdftoppm -r 1000 -png -f 1 -l 1 "$PDF" "$WERK/master"
[ -f "$WERK/r400-1.png"  ] || pdftoppm -r 400  -png -f 1 -l 1 "$PDF" "$WERK/r400"

echo "2/9  bijsnijden op hetzelfde kader als kaart.webp…"
"$PY" - "$WERK" <<'PY'
import sys
from PIL import Image, ImageChops
Image.MAX_IMAGE_PIXELS = None
W = sys.argv[1]
# Het kader is de bijsnijding zoals maak-kaart.sh die op 400 dpi maakt; op 1000 dpi
# is dat exact 2,5x. Zo vallen de vectorlaag en de plattegrond samen.
klein = Image.open(W + '/r400-1.png').convert('RGB')
d = ImageChops.difference(klein, Image.new('RGB', klein.size, (255,255,255))).convert('L')
vak = d.point(lambda p: 255 if p > 12 else 0).getbbox()
groot = Image.open(W + '/master-1.png').convert('RGB')
kader = tuple(int(round(v * 2.5)) for v in vak)
groot.crop(kader).save(W + '/plan.png')
print(f'     400 dpi bbox {vak}  ->  kader {kader}  ->  {kader[2]-kader[0]}x{kader[3]-kader[1]}')
PY

echo "3/9  blauwe straatnamen zoeken…";  "$PY" "$HIER/namen.py"    "$WERK"
echo "4/9  zwarte gebouwcodes zoeken…";  "$PY" "$HIER/codes.py"    "$WERK"
echo "5/9  gebouwen, zones en terreinlijnwerk…"
"$PY" "$HIER/gebouwen.py" "$WERK"
"$PY" "$HIER/zones.py"    "$WERK"
"$PY" "$HIER/terrein.py"  "$WERK"

# De gelezen teksten zijn handwerk en horen bij de nummering van hierboven.
# Verandert de tekening, dan schuiven de nummers en moeten de uitsneden opnieuw
# gelezen worden — zie de bladen die blad2.py maakt.
cp -n "$HIER/data/naamtekst.json" "$HIER/data/codetekst.json" "$WERK/uit/" 2>/dev/null || true

echo "6/9  codes bij hun gebouw leggen en straatassen laten groeien…"
"$PY" "$HIER/koppel.py"  "$WERK"
"$PY" "$HIER/straten.py" "$WERK"

echo "7/9  OpenStreetMap ophalen en het plan erop passen…"
"$PY" "$HIER/osm.py"     "$WERK"
"$PY" "$HIER/pas_osm.py" "$WERK"

echo "8/9  samenvoegen tot één kaartlaag in echte coördinaten…"
"$PY" "$HIER/bouw.py"    "$WERK"

echo "9/9  versleutelen…"
cp "$WERK/uit/plan.geojson" plan.geojson
node versleutel.mjs plan.geojson "$WW"
# Alleen de tussenbestanden bewaren, niet plan.geojson zelf: dat is de
# onversleutelde kaartlaag en hoort niet in een publieke repo.
for f in naamgroepen naamtekst codegroepen codetekst gebouwen zones terrein straatankers passing; do
  cp "$WERK/uit/$f.json" "$HIER/data/"
done

echo
cp "$WERK/uit/plaatsing_voorstel.json" ./plaatsing_voorstel.json
echo
echo "Klaar. plan.enc staat klaar voor de repo; plan.geojson niet — die staat in .gitignore."
echo "In plaatsing_voorstel.json staat de gevonden plaatsing van de plattegrond-"
echo "afbeelding; zet die met ./zet-plaatsing.sh online als ze beter is dan de huidige."
