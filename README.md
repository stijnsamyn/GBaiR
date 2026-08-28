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
| `kaart.enc` | **ontbreekt nog** — de versleutelde plattegrond |
| `maak-kaart.sh` | PDF → 400 dpi → bijsnijden → webp → versleutelen |
| `versleutel.mjs` | los te gebruiken als je alleen opnieuw wil versleutelen |
| `sw.js` | offline cache van de pagina, de kaart en bezochte luchtfototegels |
| `vendor/` | Leaflet 1.9.4 lokaal, zodat er geen CDN nodig is |
| `manifest.webmanifest`, `icons/` | zodat "Zet op beginscherm" een echt icoontje geeft |
| `robots.txt`, `<meta robots>` | vraagt zoekmachines de pagina niet te indexeren |

## Opzetten

```bash
./maak-kaart.sh "Kaart WTC - Straatnamen (versie 2026).pdf"   # maakt kaart.enc
python3 -m http.server 8000                                    # even lokaal bekijken
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

Alleen `kaart.enc` vervangen (`./maak-kaart.sh nieuwplan.pdf`).
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

De plattegrond staat **versleuteld** in de repo, als `kaart.enc`. Wie de
pagina opent krijgt eerst een slotscherm; pas met het juiste wachtwoord
wordt het beeld in de browser ontsleuteld. Het onversleutelde bestand komt
er niet in — `.gitignore` houdt `kaart.webp` tegen.

Wachtwoord: **ACP**. Na één keer invoeren onthoudt het toestel het, tot je
de sitegegevens wist.

Techniek: AES-256-GCM, sleutel uit PBKDF2-SHA256 met 600 000 rondes over
een willekeurige salt. Zonder het wachtwoord komt er geen beeld uit — dit
is geen schermpje dat je wegklikt.

### Wat dit wel en niet tegenhoudt

Wél: zoekmachines, en iedereen die de repo of de URL tegenkomt en gewoon
kijkt. Die krijgen een blok willekeurige bytes.

Niet: iemand die `kaart.enc` binnenhaalt en het wachtwoord wil kraken.
`ACP` is drie letters — dat zijn 17 576 mogelijkheden, en die zijn ook met
600 000 rondes in minuten door te rekenen. De versleuteling is zo sterk als
het wachtwoord, en drie letters is kort.

Wil je dat wél dichttimmeren, dan is het één handeling: kies een langere
zin en draai opnieuw

```bash
node versleutel.mjs kaart.webp "een langere zin dan drie letters"
```

Er verandert niets aan `index.html` — het wachtwoord staat daar nergens in.

## Verspreiding

**GitHub Pages kan op een gratis account alleen vanuit een publieke repo
publiceren.** De pagina zelf, de code en `kaart.enc` zijn dus voor iedereen
op te halen; alleen de inhoud van de plattegrond niet. Dit is een
plattegrond van een politie- en defensieoefenterrein, opgemaakt door CSD
Oost-Vlaanderen. `robots.txt` en de `noindex`-meta vragen zoekmachines om
weg te blijven, maar dat is een verzoek, geen slot. Ga na of er intern
regels over gelden.
