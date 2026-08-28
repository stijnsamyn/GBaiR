#!/usr/bin/env bash
# Publiceert een nieuwe uitlijning, zodat ze voor iedereen geldt.
#
#   ./zet-plaatsing.sh                 leest het blok van de standaardinvoer
#   pbpaste | ./zet-plaatsing.sh       op een Mac, meteen van het klembord
#
# Het blok komt uit instellingen.html, knop "kopieer". Het versienummer staat er
# al verhoogd in; daardoor laat elk toestel bij het volgende openen zijn eigen
# bijstelling los en neemt deze over.
set -euo pipefail
cd "$(dirname "$0")"

nieuw="$(cat)"
node -e '
const t = process.argv[1];
let g; try { g = JSON.parse(t); } catch(e){ console.error("Dat is geen geldige JSON."); process.exit(1); }
for (const k of ["versie","lat","lon","w","h","rot"])
  if (typeof g[k] !== "number"){ console.error(`veld ${k} ontbreekt of is geen getal`); process.exit(1); }
let oud = 0;
try { oud = JSON.parse(require("fs").readFileSync("plaatsing.json","utf8")).versie || 0; } catch(e){}
if (g.versie <= oud){
  console.error(`versie ${g.versie} is niet hoger dan de gepubliceerde ${oud} — dan verandert er niets voor wie al bijgesteld heeft`);
  process.exit(1);
}
require("fs").writeFileSync("plaatsing.json", JSON.stringify(g, null, 2) + "\n");
console.log(`plaatsing.json -> versie ${g.versie} (was ${oud})`);
' "$nieuw"

git add plaatsing.json
git commit -q -m "Plaatsing bijgewerkt naar versie $(node -p "require('./plaatsing.json').versie")"
git push -q origin main
echo "Gepubliceerd. Na een minuut staat het op GitHub Pages."
