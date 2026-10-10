// Headless end-to-end run: loader -> chain -> game, with scripted keys; prints text screens.
// usage: node test/e2e.mjs "keys..." [steps]   (keys: chars, \r = Enter, | = wait for input)
import { Runtime, MemoryFS } from '../runtime.js';
import { runPrograms } from '../shell.js';
import fs from 'fs';
const here = new URL('.', import.meta.url).pathname;
const gra = new Uint8Array(fs.readFileSync(here + '../MONOGRAF.GRA'));
const vfs = new MemoryFS({ 'MONOGRAF.GRA': gra, 'MONOCODE.CHN': new Uint8Array([26]), 'MONOCODE.000': new Uint8Array([26]) });
const R = new Runtime({ headless: true, vfs });
R.biosSetCursor(24, 0);
const script = (process.argv[2] || '').replace(/\\r/g, '\r');
let waits = 0;
function screen() {
  if (R.bios.mode >= 4) return '[graphics mode 4, colorSel ' + R.bios.colorSel.toString(16) + ']';
  const rows = [];
  for (let r = 0; r < 25; r++) { let s = ''; for (let c = 0; c < 80; c++) s += String.fromCharCode(R.vram[(r * 80 + c) * 2]); rows.push(s.replace(/\s+$/, '')); }
  return rows.join('\n');
}
// feed one key each time the program blocks waiting for a key
const origWait = R._waitKey.bind(R);
let si = 0;
R._waitKey = function () {
  if (!R._kbHit() && si < script.length) {
    const ch = script[si++];
    console.log('---- screen before key', JSON.stringify(ch), '----\n' + screen());
    R.pushKey(ch.charCodeAt(0), 0);
  }
  return origWait();
};
const origKP = R.keyPressed.bind(R);
R.keyPressed = async function () {
  if (!R._kbHit() && si < script.length && (++waits % 50) === 0) {
    const ch = script[si++];
    console.log('---- screen before key', JSON.stringify(ch), '----\n' + screen());
    R.pushKey(ch.charCodeAt(0), 0);
  }
  return origKP();
};
runPrograms(R, (n) => import('../' + n + '.js')).then((r) => { console.log('RESULT', r, '\n' + screen()); process.exit(0); });
setTimeout(() => { console.log('---- final (timeout) ----\n' + screen()); process.exit(0); }, 8000);
