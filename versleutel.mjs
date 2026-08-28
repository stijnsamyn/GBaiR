/* Versleutelt de kaart met een wachtwoord, zodat het bestand in een
 * publieke repo mag staan. Uitvoer: kaart.enc
 *
 *   node versleutel.mjs kaart.webp ACP          -> kaart.enc
 *   node versleutel.mjs plan.geojson ACP        -> plan.enc
 *   node versleutel.mjs bron.json ACP vectorplan/brondata.enc
 *
 * Bestandsopbouw:  "WTC1" | 1 byte inhoudsoort | 16 byte salt | 12 byte iv | cijfertekst+tag
 * Sleutel: PBKDF2-SHA256, 600 000 rondes, 256 bit — gelijk aan wat index.html doet.
 */
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { pbkdf2Sync, randomBytes, createCipheriv } from 'node:crypto';

const RONDES = 600000;
const SOORT  = { webp:1, png:2, jpg:3, jpeg:3, geojson:4, json:4 };
const DOEL   = { 1:'kaart.enc', 2:'kaart.enc', 3:'kaart.enc', 4:'plan.enc' };

const [bron = 'kaart.webp', wachtwoord, uitnaam] = process.argv.slice(2);
if (!wachtwoord){
  console.error('gebruik: node versleutel.mjs <beeld- of geojson-bestand> <wachtwoord> [uitvoerbestand]');
  process.exit(1);
}

const ext = bron.split('.').pop().toLowerCase();
if (!SOORT[ext]){ console.error('soort ' + ext + ' wordt niet ondersteund'); process.exit(1); }
const doel = uitnaam || DOEL[SOORT[ext]];

const plat  = readFileSync(bron);
const salt  = randomBytes(16);
const iv    = randomBytes(12);
const sleutel = pbkdf2Sync(Buffer.from(wachtwoord, 'utf8'), salt, RONDES, 32, 'sha256');

const c   = createCipheriv('aes-256-gcm', sleutel, iv);
const uit = Buffer.concat([c.update(plat), c.final(), c.getAuthTag()]);

writeFileSync(doel, Buffer.concat([
  Buffer.from('WTC1', 'ascii'), Buffer.from([SOORT[ext]]), salt, iv, uit
]));

const mb = n => (n/1e6).toFixed(2) + ' MB';
console.log(`${bron} (${mb(plat.length)})  ->  ${doel} (${mb(statSync(doel).size)})`);
console.log(`AES-256-GCM, PBKDF2-SHA256 met ${RONDES.toLocaleString('nl-BE')} rondes.`);
console.log(`Zet ${doel} in de repo. Het onversleutelde bestand niet — dat staat in .gitignore.`);
