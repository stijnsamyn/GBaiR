# WTC — straatnamen op de gsm

De plattegrond van het oefenterrein (Kwartier Westakkers, Grote Baan 111,
Sint-Niklaas) als webpagina, met je eigen positie erop. Geen app, geen
account, geen abonnement.

De straatnamen op het plan zijn de fictieve namen van het oefendorp. Ze
staan in geen enkele kaartdienst — vandaar deze pagina.

## Wat er in zit

| Bestand | Wat het doet |
|---|---|
| `index.html` | de kaartpagina: positie, zoeken, straatnamen |
| `instellingen.html` | de kaart op de aarde leggen — uitlijnen en controlepunten |
| `kaartkern.js` | wat beide pagina's delen: plaatsing, ontsleutelen, vectorlaag |
| `stijl.css` | de opmaak van beide pagina's |
| `plaatsing.json` | waar de kaart ligt, met een versienummer |
| `zet-plaatsing.sh` | publiceert een nieuwe uitlijning voor iedereen |
| `kaart.enc` | de versleutelde plattegrond, als beeld |
| `plan.enc` | de versleutelde **vectorlaag**: straten, gebouwen en zones als kaartdata |
| `maak-kaart.sh` | PDF → 400 dpi → bijsnijden → webp → versleutelen |
| `vectorplan/` | de pijplijn die van dezelfde PDF de vectorlaag maakt |
| `vectorplan/osm.py`, `pas_osm.py` | OpenStreetMap ophalen en het plan erop leggen |
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
209 gebouwen, 336 terreinlijnen en 3 zones**, in echte lengte- en breedtegraad.
Dat is 133 kB in plaats van 784 kB, het blijft scherp op elke zoom, en het
levert drie dingen op die een beeld niet kan:

* **Zoeken.** Het veld bovenaan zoekt op straatnaam én op gebouwcode. Tik een
  stuk van een naam of een `MG`-nummer en de kaart springt erheen met een
  oranje ring.
* **In welke straat sta je.** De statusbalk toont naast de gps-nauwkeurigheid
  de dichtstbijzijnde straat — binnen 18 m als `· <straat>`, daarbuiten als
  `· bij <straat>`.
* **Leesbare namen.** Ze lopen langs hun straat mee en staan nooit op hun kop.
  Ze verschijnen naar zoomniveau: niets als je het hele terrein ziet, één naam
  per straat vanaf zoom 16,5, alle bordjes vanaf 17,5. Gebouwcodes komen erbij
  vanaf zoom 18. Bordjes die elkaar zouden overlappen vallen weg, de
  belangrijkste straat eerst.

De oude plattegrond staat er nog wel in en is **uit bij het openen** — anders
toont hij elke naam een tweede keer. Zet hem aan met het lagenknopje
rechtsboven; hij heeft detail dat de vectorlaag niet heeft (boomranden,
perceelgrenzen, het spoor).

### Waar de gebouwen vandaan komen

Waar OpenStreetMap het gebouw al kent, gebruiken we **die** omtrek. Die ligt
juist op de aarde, en dat is precies wat een tekening niet kan geven. Van het
plan komt dan alleen wat OSM níet heeft: de `MG`-code.

| | |
|---|---|
| 78 | uit OSM, met de code van het plan erbij |
| 53 | uit de tekening — OSM kent ze niet |
| 78 | uit OSM, zonder code — het plan benoemt ze niet |

OSM kan de inhoud van dit plan niet leveren: binnen het domein staan daar
**156 gebouwen, 8 wegen en nul namen of refs**. De straatnamen die OSM er wel
heeft zijn de echte wegen eromheen, geen enkele van de 60 namen van het
oefendorp. Omgekeerd kan het plan de ligging niet leveren. Samen wel.

Gebouwomtrekken van OpenStreetMap staan onder ODbL; de bronvermelding staat
in de kaart en hier.

### De coördinaten

`plan.enc` staat in **echte lengte- en breedtegraad**. De kaartlaag hangt dus
niet meer af van een uitlijning achteraf — ze ligt goed zodra ze geladen is.
`plaatsing.json` gaat alleen nog over de plattegrond-afbeelding die je eronder
kan leggen.

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
| terreinlijnen | wat er aan zwart lijnwerk overblijft als gebouwen en tekst eraf zijn, uitgedund tot één pixel en afgelopen |
| ligging | de gebouwen van het plan op die van OSM leggen (ICP), zie hieronder |

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

Dat gebeurt op een eigen pagina, **`instellingen.html`** — vanaf de kaart
bereikbaar met **⚙** rechtsonder. Er is geen QGIS of georeferencer nodig.

### Eén keer uitlijnen, en het geldt voor iedereen

De plaatsing staat niet meer in `index.html` maar in **`plaatsing.json`**, met
een versienummer erbij:

```json
{ "versie": 1, "lat": 51.1862115, "lon": 4.2085574,
  "w": 1006, "h": 912, "rot": 0, "opmerking": "…" }
```

Dat versienummer is de kern. Wie op zijn eigen toestel bijstelt, krijgt die
bijstelling bewaard **mét de versie waarop ze gebaseerd is**. Publiceer je een
hoger nummer, dan laat elk toestel bij het volgende openen zijn eigen waarde
los en neemt de jouwe over. Zonder dat mechanisme zou wie ooit één keer
geschoven heeft voor altijd op zijn eigen plaatsing blijven hangen, en zou een
nieuwe uitlijning hem nooit bereiken.

Publiceren:

```bash
pbpaste | ./zet-plaatsing.sh      # het blok uit "kopieer" staat op het klembord
```

Dat controleert de inhoud, weigert een versie die niet hoger ligt dan de
gepubliceerde, en commit en pusht.

### Met de hand bijstellen

Sleep de blauwe greep naar het midden van het terrein en stem bij met de
pijltjes, `+`/`−` (grootte) en `↺`/`↻` (draaiing). Met **stap: fijn** ga je van
10 m naar 1 m, van 2 % naar 0,2 %, van 1° naar 0,1°.

Herkenbare ankerpunten op de luchtfoto: het voetbalveld linksonder op het plan,
de langgerekte ovale structuur rechtsboven, en de toegangsweg ("Ingang") links.

### Automatisch, op OpenStreetMap

`vectorplan/pas_osm.py` legt het plan op zijn plaats door de zwaartepunten van
de getekende gebouwen te laten samenvallen met die van OSM. Eerst een grove gok
uit de vorm van beide puntenwolken, dan ICP: telkens elk gebouw aan zijn
dichtstbijzijnde buur koppelen en de passing opnieuw uitrekenen.

Twee dingen zijn daarbij nodig gebleken. De passing moet **een gelijkvormigheid
zijn, geen affiene afbeelding** — die laatste mag scheeftrekken en praat dan
verkeerde koppels goed in plaats van ze af te wijzen. En het plan moet in **zijn
eigen verhouding** meedoen, niet genormaliseerd, anders wordt het vóór het
matchen al platgedrukt.

Het resultaat op deze tekening:

```
gekoppeld            100 van de 131 gebouwen
afwijking            mediaan 5,6 m, gemiddeld 10,4 m
scheeftrekking       0,53°   (die een vrije affiene passing zou willen)
verhouding           1,1088  (de tekening zelf: 1,1032)
```

**Daarmee is de vraag hieronder beantwoord: het plan is ingemeten, niet los
getekend.** Over 1,1 km wil de vrije passing maar een halve graad scheefte en
een half procent verhoudingsverschil. Eén plaatsing klopt dus overal tegelijk.
De 5,6 m die overblijft is ongeveer de nauwkeurigheid van OSM zelf, want die
gebouwen zijn van luchtfoto's overgetrokken.

### Met controlepunten

Nauwkeuriger dan met de hand schuiven, en het beantwoordt meteen de vraag of
het plan überhaupt kán passen.

1. Tik **punten prikken**. Het paneel klapt in zodat je de kaart ziet.
2. Tik een herkenbare plek **op de tekening**, dan diezelfde plek **op de
   luchtfoto**. Er verschijnt een blauw en een oranje punt met een stippellijn
   ertussen.
3. Herhaal dat drie tot zes keer, verspreid over het terrein — niet op één lijn.
4. Tik **bereken passing**.

De plek op de tekening wordt bewaard als plancoördinaat (0–1), niet als
lengte- en breedtegraad. Anders zou hij meeschuiven zodra de passing de kaart
verlegt, en dat is juist wat we meten. De punten blijven op je toestel staan,
ook na sluiten.

De passing lost de best passende affiene afbeelding op en leest daar breedte,
hoogte en draaiing uit. Ze meldt drie dingen:

| | wat het betekent |
|---|---|
| gemiddelde afwijking | hoe goed het past, in meter |
| grootste afwijking | waar het het slechtst past |
| scheeftrekking | hoeveel de affiene afbeelding scheeftrekt |

Blijft de scheeftrekking onder ~1° en de gemiddelde afwijking onder ~12 m, dan
is het plan gewoon verschoven, geschaald en gedraaid, en klopt de plaatsing
overal. Zit je erboven, dan is de tekening getekend en niet ingemeten — dan
gaat **geen enkele** lineaire plaatsing overal tegelijk passen. Leg ze dan goed
in de zone waar je het vaakst staat, of laat de vectorlaag rubbersheeten bij
het bouwen.

### Startwaarden

Zolang er niet ingemeten is, staat de plaatsing op het volledige militaire
domein volgens OpenStreetMap (way 51686418, `landuse=military`):

```
lat 51,1819896 – 51,1904335   (940 m)
lon 4,2013514  – 4,2157634    (1006 m)
```

Dat is een startpunt, geen meting.

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
