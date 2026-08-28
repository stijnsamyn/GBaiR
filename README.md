# WTC — straatnamen op de gsm

De plattegrond van het oefenterrein (Kwartier Westakkers, Grote Baan 111,
Sint-Niklaas) als webpagina, met je eigen positie erop. Geen app, geen
account, geen abonnement.

De straatnamen op het plan zijn de fictieve namen van het oefendorp. Ze
staan in geen enkele kaartdienst — vandaar deze pagina.

## Wat er in zit

| Bestand | Wat het doet |
|---|---|
| `index.html` | de hele toepassing; bovenaan staat `START`, de plaatsing van de kaart |
| `kaart.enc` | de versleutelde plattegrond, als beeld |
| `plan.enc` | de versleutelde **vectorlaag**: straten, gebouwen en zones als kaartdata |
| `maak-kaart.sh` | PDF → 400 dpi → bijsnijden → webp → versleutelen |
| `vectorplan/` | de pijplijn die van dezelfde PDF de vectorlaag maakt |
| `versleutel.mjs` | los te gebruiken als je alleen opnieuw wil versleutelen |
| `sw.js` | offline cache van de pagina, de kaart en bezochte luchtfototegels |
| `vendor/` | Leaflet 1.9.4 lokaal, zodat er geen CDN nodig is |
| `manifest.webmanifest`, `icons/` | zodat "Zet op beginscherm" een echt icoontje geeft |
| `robots.txt`, `<meta robots>` | vraagt zoekmachines de pagina niet te indexeren |

## Opzetten

```bash
./maak-kaart.sh "Kaart WTC - Straatnamen (versie 2026).pdf"           # maakt kaart.enc
./vectorplan/maak-vector.sh "Kaart WTC - Straatnamen (versie 2026).pdf"  # maakt plan.enc
python3 -m http.server 8000                                            # even lokaal bekijken
```

Op `http://localhost:8000` werkt GPS ook. Op een gewoon `file://`-bestand
**niet** — geolocatie vereist https of localhost. Dat is de valkuil waar
iedereen één keer in trapt.

## Online zetten

```bash
git init -b main
git add .
git commit -m "WTC straatnamenkaart"
git remote add origin https://github.com/stijnsamyn/GBaiR.git
git push -u origin main
```

Daarna in de repo: **Settings → Pages → Source: Deploy from a branch →
`main` / `/ (root)`**. Na een minuut staat de pagina op
`https://stijnsamyn.github.io/GBaiR/`.

Op de iPhone: openen in Safari → Deel → **Zet op beginscherm**. Bij het
eerste gebruik vraagt Safari toestemming voor je locatie; die moet je
geven. Zet in Instellingen → Safari ook "Exacte locatie" aan.

## De vectorlaag

De pagina toont geen ingescand beeld meer, maar echte kaartdata: **60 straten,
131 gebouwvlakken met hun `MG`-code, en 3 zones**. Dat is 52 kB in plaats van
784 kB, het blijft scherp op elke zoom, en het levert drie dingen op die een
beeld niet kan:

* **Zoeken.** Het veld bovenaan zoekt op straatnaam én op gebouwcode. Tik een
  stuk van een naam of een `MG`-nummer en de kaart springt erheen met een
  oranje ring.
* **In welke straat sta je.** De statusbalk toont naast de gps-nauwkeurigheid
  de dichtstbijzijnde straat — binnen 18 m als `· <straat>`, daarbuiten als
  `· bij <straat>`.
* **Leesbare namen.** Ze staan altijd horizontaal in plaats van gedraaid mee
  met de straat, en ze verschijnen naar zoomniveau: niets als je het hele
  terrein ziet, één naam per straat vanaf zoom 16, alle bordjes vanaf 17,5.
  Gebouwcodes komen erbij vanaf zoom 18. Dezelfde naam twee keer vlak naast
  elkaar wordt onderdrukt.

De oude plattegrond staat er nog wel in en is **uit bij het openen** — anders
toont hij elke naam een tweede keer. Zet hem aan met het lagenknopje
rechtsboven; hij heeft detail dat de vectorlaag niet heeft (boomranden,
perceelgrenzen, het spoor).

De coördinaten in `plan.enc` lopen van 0 tot 1 over hetzelfde kader als
`kaart.webp`. Daardoor geldt `START` voor allebei en verschuift de uitlijnmodus
de vectoren mee met het beeld.

### Hoe die laag gemaakt is

De PDF is een "Print To PDF" van een CAD-tekening: vier beeldstroken, geen
fonts, geen vectorpaden. Er valt dus niets uit te lezen; alles komt uit het
beeld, op 1000 dpi (de PDF bevat 2,5× meer detail dan wat `maak-kaart.sh`
gebruikt).

| Stap | Hoe |
|---|---|
| straatnamen | blauwe letters groeperen, rechtzetten, en lezen |
| gebouwen | grijze en roze vlakken; arceergaten dichten, dan opensnijden op de zwarte omtrek |
| gebouwcodes | zwarte bloktekst, gescheiden van het lijnwerk op grootte |
| straatassen | de naam staat middenop de weg — vanuit het label langs zijn eigen richting groeien tot de doorgang dichtloopt |

De namen en codes zijn met de hand van de uitsneden gelezen, niet met OCR: die
tekst is klein, staat onder willekeurige hoeken en loopt door lijnwerk heen, en
een verkeerd gelezen straatnaam is erger dan geen. Dat handwerk zit in
`vectorplan/brondata.enc`. Uitpakken:

```bash
node vectorplan/pak-uit.mjs ACP     # zet vectorplan/data/ terug
```

Verandert de tekening, dan verschuiven de labelnummers en moet dat lezen
opnieuw: `vectorplan/blad2.py` maakt contactbladen van alle uitsneden.

## De kaart uitlijnen

Dit vervangt de hele QGIS-stap. Er is geen georeferencer nodig.

1. Open de pagina, tik rechtsonder op **⊹**.
2. Kies rechtsboven **Luchtfoto** als achtergrond.
3. Sleep de blauwe greep naar het midden van het terrein.
4. Stem bij met de pijltjes, `+`/`−` (grootte) en `↺`/`↻` (draaiing).
   Met **stap: fijn** ga je van 10 m naar 1 m, van 2 % naar 0,2 %,
   van 1° naar 0,1°.
5. Tik **kopieer** en plak het blok in `index.html` bij `const START`.

Zolang je dat laatste niet doet, staat de correctie alleen in de
`localStorage` van jouw toestel. Plak je hem in het bestand, dan klopt het
meteen voor iedereen die de pagina opent.

Herkenbare ankerpunten op de luchtfoto: het voetbalveld linksonder op het
plan, de langgerekte ovale structuur rechtsboven, en de toegangsweg
("Ingang") links.

### Startwaarden

`START` staat nu op het volledige militaire domein volgens OpenStreetMap
(way 51686418, `landuse=military`):

```
lat 51,1819896 – 51,1904335   (940 m)
lon 4,2013514  – 4,2157634    (1006 m)
```

Dat is een startpunt, geen meting.

### Klopt het plan niet overal tegelijk?

Meet twee afstanden die ver uit elkaar liggen — de lengte van het
voetbalveld en die van de ovale structuur — en vergelijk de verhouding met
de luchtfoto. Klopt die niet, dan is het plan getekend en niet gemeten, en
gaat geen enkele lineaire plaatsing overal tegelijk passen. Leg het dan
goed in de zone waar je het vaakst staat en aanvaard afwijking aan de
randen.

## Bij een nieuwe versie van het plan

`kaart.enc` én `plan.enc` vervangen (`./maak-kaart.sh nieuwplan.pdf` en
`./vectorplan/maak-vector.sh nieuwplan.pdf`).
`START` blijft geldig zolang de tekening
hetzelfde kader heeft — dus snijd exact op dezelfde manier bij, en noteer
de bbox die `maak-kaart.sh` afdrukt.

Verhoog na elke wijziging ook `VERSIE` in `sw.js`, anders blijven toestellen
op de oude versie hangen.

## Nauwkeurigheid

Gsm-GPS is 5 à 10 m in open terrein en slechter tussen gebouwen. Genoeg om
te weten in welke straat je staat, niet om twee gebouwen naast elkaar uit
elkaar te houden. De statusbalk linksboven toont de gemeten nauwkeurigheid
en kleurt oranje boven 25 m.

## Het wachtwoord

De plattegrond staat **versleuteld** in de repo, als `kaart.enc`, en de
vectorlaag als `plan.enc`. Wie de pagina opent krijgt eerst een slotscherm; pas
met het juiste wachtwoord wordt alles in de browser ontsleuteld. De
onversleutelde bestanden komen er niet in — `.gitignore` houdt `kaart.webp`,
`plan.geojson` en `vectorplan/data/` tegen.

Dat laatste is niet vrijblijvend. Een GeoJSON is platte tekst: alle
straatnamen en gebouwcodes staan er leesbaar en doorzoekbaar in. Onversleuteld
in een publieke repo zou dat het slot op `kaart.enc` meteen zinloos maken. Om
dezelfde reden staat er geen enkele straatnaam in de scripts zelf — de
koppeltabel zit in `koppel.json`, binnen `brondata.enc`.

Wachtwoord: **ACP**. Na één keer invoeren onthoudt het toestel het, tot je
de sitegegevens wist.

Techniek: AES-256-GCM, sleutel uit PBKDF2-SHA256 met 600 000 rondes over
een willekeurige salt. Zonder het wachtwoord komt er geen beeld uit — dit
is geen schermpje dat je wegklikt.

### Wat dit wel en niet tegenhoudt

Wél: zoekmachines, en iedereen die de repo of de URL tegenkomt en gewoon
kijkt. Die krijgen een blok willekeurige bytes.

Niet: iemand die `kaart.enc` of `plan.enc` binnenhaalt en het wachtwoord wil kraken.
`ACP` is drie letters — dat zijn 17 576 mogelijkheden, en die zijn ook met
600 000 rondes in minuten door te rekenen. De versleuteling is zo sterk als
het wachtwoord, en drie letters is kort.

Wil je dat wél dichttimmeren, dan is het één handeling: kies een langere
zin en draai opnieuw

```bash
node versleutel.mjs kaart.webp   "een langere zin dan drie letters"
node versleutel.mjs plan.geojson "een langere zin dan drie letters"
node vectorplan/pak-uit.mjs ACP    # eerst uitpakken met het oude wachtwoord
```

Alle drie de bestanden moeten hetzelfde wachtwoord krijgen. Er verandert niets
aan `index.html` — het wachtwoord staat daar nergens in.

## Verspreiding

**GitHub Pages kan op een gratis account alleen vanuit een publieke repo
publiceren.** De pagina zelf, de code, `kaart.enc`, `plan.enc` en
`vectorplan/brondata.enc` zijn dus voor iedereen op te halen; alleen de inhoud
ervan niet. Dit is een
plattegrond van een politie- en defensieoefenterrein, opgemaakt door CSD
Oost-Vlaanderen. `robots.txt` en de `noindex`-meta vragen zoekmachines om
weg te blijven, maar dat is een verzoek, geen slot. Ga na of er intern
regels over gelden.
