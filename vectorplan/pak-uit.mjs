/* Haalt vectorplan/data/ weer uit brondata.enc.
 *
 *   node vectorplan/pak-uit.mjs ACP
 *
 * De gelezen straatnamen en gebouwcodes zijn handwerk en staan daarom wel in de
 * repo, maar versleuteld — platte tekst in een publieke repo zou het slot op
 * kaart.enc en plan.enc zinloos maken.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { pbkdf2Sync, createDecipheriv } from 'node:crypto';

const wachtwoord = process.argv[2];
if (!wachtwoord){ console.error('gebruik: node vectorplan/pak-uit.mjs <wachtwoord>'); process.exit(1); }

const b = readFileSync('vectorplan/brondata.enc');
if (b.subarray(0,4).toString('ascii') !== 'WTC1'){ console.error('brondata.enc is beschadigd'); process.exit(1); }
const salt = b.subarray(5,21), iv = b.subarray(21,33);
const data = b.subarray(33, b.length-16), tag = b.subarray(b.length-16);
const sleutel = pbkdf2Sync(Buffer.from(wachtwoord,'utf8'), salt, 600000, 32, 'sha256');
const d = createDecipheriv('aes-256-gcm', sleutel, iv); d.setAuthTag(tag);

let plat;
try { plat = Buffer.concat([d.update(data), d.final()]); }
catch { console.error('wachtwoord klopt niet'); process.exit(1); }

mkdirSync('vectorplan/data', { recursive:true });
const bundel = JSON.parse(plat.toString('utf8'));
for (const [naam, inhoud] of Object.entries(bundel)){
  writeFileSync('vectorplan/data/' + naam, JSON.stringify(inhoud));
  console.log('  vectorplan/data/' + naam);
}
console.log(Object.keys(bundel).length + ' bestanden teruggezet.');
