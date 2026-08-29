#!/usr/bin/env bash
# Bouwt de kaartlagen opnieuw, kijkt na, en zet ze online.
#
#   ./publiceer.sh            controleren en publiceren
#   ./publiceer.sh --droog    alleen controleren, niets pushen
#
# De volgorde is met opzet: eerst versleutelen, dan nakijken, dan pas pushen.
# Deze repo is publiek en bevat een plan van een politie- en defensieterrein,
# dus een fout gaat er niet ongemerkt in.
set -euo pipefail
cd "$(dirname "$0")"
WW="${WACHTWOORD:-ACP}"
DROOG=0; [ "${1:-}" = "--droog" ] && DROOG=1

echo "1/4  onversleutelde kaartlagen mogen niet in de repo"
mis=0
for f in $(git ls-files); do
  case "$f" in
    *.geojson|brondata.json) echo "   FOUT: $f staat in de repo"; mis=1;;
  esac
done
# platte planinhoud in bestanden die wél in de repo staan
for f in $(git ls-files | grep -vE '\.enc$'); do
  # alleen echte namen tellen, geen variabelen als GEEN_STRAAT
  if grep -qE "'[A-Z][A-Z .'-]*(STRAAT|LAAN|PLEIN|DREEF|WEG)'|\"MG [0-9]+\"|'MG [0-9]+'" "$f" 2>/dev/null; then
    echo "   FOUT: $f bevat leesbare planinhoud"; mis=1
  fi
done
[ $mis -eq 0 ] && echo "   schoon" || { echo "Gestopt."; exit 1; }

echo "2/4  versleutelde lagen aanwezig en leesbaar"
for f in plan.enc leopoldsburg.enc houthulst.enc kaart.enc vectorplan/brondata.enc; do
  [ -f "$f" ] || { echo "   FOUT: $f ontbreekt"; exit 1; }
  printf "   %-26s %8s bytes\n" "$f" "$(wc -c < "$f" | tr -d ' ')"
done
node vectorplan/open.mjs "$WW" plan.enc /tmp/_p.geojson >/dev/null && rm -f /tmp/_p.geojson \
  && echo "   plan.enc opent met het wachtwoord" || { echo "   FOUT: plan.enc opent niet"; exit 1; }

echo "3/4  de servicewerker moet elke laag kennen"
for f in plan.enc leopoldsburg.enc houthulst.enc; do
  grep -q "$f" sw.js || { echo "   FOUT: $f staat niet in sw.js"; exit 1; }
done
huidig=$(grep -oE "wtc-v[0-9]+" sw.js | head -1)
echo "   $huidig, alle lagen vermeld"

if [ $DROOG -eq 1 ]; then echo; echo "Droge loop: niets gepusht."; exit 0; fi

echo "4/4  vastleggen en online zetten"
if [ -z "$(git status --porcelain)" ]; then
  echo "   niets gewijzigd"
else
  git add -A
  git commit -q -m "${BERICHT:-Kaartlagen bijgewerkt}"
fi
git push -q origin main
echo
echo "Gepusht. Na een minuut staat het op https://stijnsamyn.github.io/GBaiR/"
