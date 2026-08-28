/* Versleutelt de kaart met een wachtwoord, zodat het bestand in een
 * publieke repo mag staan. Uitvoer: kaart.enc
 *
 *   node versleutel.mjs kaart.webp ACP
 *
 * Bestandsopbouw:  "WTC1" | 1 byte beeldsoort | 16 byte salt | 12 byte iv | cijfertekst+tag
 * Sleutel: PBKDF2-SHA256, 600 000 rondes, 256 bit — gelijk aan wat index.html doet.
 */
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { pbkdf2Sync, randomBytes, createCipheriv } from 'node:crypto';

const RONDES = 600000;
const SOORT  = { webp:1, png:2, jpg:3, jpeg:3 };

const [bron = 'kaart.webp', wachtwoord] = process.argv.slice(2);
if (!wachtwoord){
  console.error('gebruik: node versleutel.mjs <beeldbestand> <wachtwoord>');
  process.exit(1);
}

const ext = bron.split('.').pop().toLowerCase();
if (!SOORT[ext]){ console.error('beeldsoort ' + ext + ' wordt niet ondersteund'); process.exit(1); }

const plat  = readFileSync(bron);
const salt  = randomBytes(16);
const iv    = randomBytes(12);
const sleutel = pbkdf2Sync(Buffer.from(wachtwoord, 'utf8'), salt, RONDES, 32, 'sha256');

const c   = createCipheriv('aes-256-gcm', sleutel, iv);
const uit = Buffer.concat([c.update(plat), c.final(), c.getAuthTag()]);

writeFileSync('kaart.enc', Buffer.concat([
  Buffer.from('WTC1', 'ascii'), Buffer.from([SOORT[ext]]), salt, iv, uit
]));

const mb = n => (n/1e6).toFixed(2) + ' MB';
console.log(`${bron} (${mb(plat.length)})  ->  kaart.enc (${mb(statSync('kaart.enc').size)})`);
console.log(`AES-256-GCM, PBKDF2-SHA256 met ${RONDES.toLocaleString('nl-BE')} rondes.`);
console.log('Zet kaart.enc in de repo. Het onversleutelde bestand niet — dat staat in .gitignore.');
