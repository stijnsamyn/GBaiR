#!/usr/bin/env bash
# Verwerkt aanpassingen uit instellingen.html in de kaartlaag en zet ze online.
#
#   pbpaste | ./zet-kaartlaag.sh              (wachtwoord ACP)
#   pbpaste | ./zet-kaartlaag.sh MIJNZIN
#
# Het blok komt uit "kopieer bordjes" of "kopieer gebouwen". Beide gaan de
# kaartlaag zelf in -- verzette namen als labelpunt en labelhoek, bijgestelde
# gebouwen als hun nieuwe omtrek. Er komt geen correctielaag naast.
set -euo pipefail
cd "$(dirname "$0")"
WW="${1:-ACP}"
blok="$(cat)"

node vectorplan/open.mjs "$WW" >/dev/null
node -e '
const fs = require("fs");
let blok; try { blok = JSON.parse(process.argv[1]); }
catch(e){ console.error("Dat is geen geldige JSON."); process.exit(1); }
const fc = JSON.parse(fs.readFileSync("plan.geojson","utf8"));
let namen = 0, gebouwen = 0, over = 0;

for (const [i, w] of Object.entries(blok.bordjes || {})){
  const k = fc.features[+i];
  if (!k || k.properties.soort !== "straat"){ over++; continue; }
  if (w.punt) k.properties.labelpunt = w.punt;
  if (typeof w.hoek === "number") k.properties.labelhoek = w.hoek;
  else delete k.properties.labelhoek;
  namen++;
}
for (const [i, w] of Object.entries(blok.gebouwen || {})){
  const k = fc.features[+i];
  if (!k || k.geometry.type !== "Polygon" || !Array.isArray(w.ring)){ over++; continue; }
  k.geometry.coordinates = [w.ring];
  k.properties.bijgesteld = true;
  gebouwen++;
}
if (!namen && !gebouwen){
  console.error("Niets herkend — hoort dit blok bij deze kaartlaag?"); process.exit(1);
}
fs.writeFileSync("plan.geojson", JSON.stringify(fc));
console.log([namen && `${namen} bordje(s)`, gebouwen && `${gebouwen} gebouw(en)`]
            .filter(Boolean).join(" en ") + " verwerkt"
            + (over ? `, ${over} overgeslagen` : ""));
' "$blok"

node versleutel.mjs plan.geojson "$WW"
rm -f plan.geojson

git add plan.enc
git commit -q -m "Kaartlaag bijgesteld vanuit de instellingenpagina"
git push -q origin main
echo "Gepubliceerd. Na een minuut staat het op GitHub Pages."
