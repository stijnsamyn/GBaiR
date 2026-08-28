/* Maakt plan.enc weer leesbaar, om de kaartlaag rechtstreeks aan te passen.
 *
 *   node vectorplan/open.mjs ACP          -> plan.geojson
 *
 * Aanpassen kan daarna met de hand, in QGIS, of met de naameditor op
 * instellingen.html. Terug versleutelen:
 *
 *   node versleutel.mjs plan.geojson ACP  -> plan.enc
 *
 * plan.geojson staat in .gitignore: het bevat alle straatnamen en codes in
 * platte tekst en hoort niet in een publieke repo.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { pbkdf2Sync, createDecipheriv } from 'node:crypto';

const wachtwoord = process.argv[2];
const bron = process.argv[3] || 'plan.enc';
const doel = process.argv[4] || 'plan.geojson';
if (!wachtwoord){ console.error('gebruik: node vectorplan/open.mjs <wachtwoord> [bron] [doel]'); process.exit(1); }

const b = readFileSync(bron);
if (b.subarray(0,4).toString('ascii') !== 'WTC1'){ console.error(bron + ' is beschadigd'); process.exit(1); }
const salt = b.subarray(5,21), iv = b.subarray(21,33);
const data = b.subarray(33, b.length-16), tag = b.subarray(b.length-16);
const sleutel = pbkdf2Sync(Buffer.from(wachtwoord,'utf8'), salt, 600000, 32, 'sha256');
const d = createDecipheriv('aes-256-gcm', sleutel, iv); d.setAuthTag(tag);

let plat;
try { plat = Buffer.concat([d.update(data), d.final()]); }
catch { console.error('wachtwoord klopt niet'); process.exit(1); }

const fc = JSON.parse(plat.toString('utf8'));
writeFileSync(doel, JSON.stringify(fc, null, 1));
const tel = {};
for (const f of fc.features) tel[f.properties.soort] = (tel[f.properties.soort] || 0) + 1;
console.log(`${bron} -> ${doel}  (${fc.features.length} kenmerken)`);
console.log(Object.entries(tel).map(([k,v]) => `  ${k}: ${v}`).join('\n'));
