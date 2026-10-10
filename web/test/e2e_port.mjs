// Deterministic end-to-end run of the port (loader -> chain -> game) with a KEYFEED-style script.
// Each key becomes available after exactly N "no key" BIOS peeks; a blocking read gets it at once.
// When a key has the snapshot flag, the screen state is captured at the moment the key is first
// reported or read -- exactly when the KEYFEED.COM TSR captures it in DOSBox.
// usage: node test/e2e_port.mjs SCRIPT.json OUTDIR [fontInvert]
//   SCRIPT.json: [[ascii, scan, peeks, snap], ...]
// Writes OUTDIR/Pnnnn.BIN: 16384 bytes video memory + 4 bytes (mode, cursor col, cursor row, colour register)
import { Runtime, MemoryFS } from '../runtime.js';
import { runPrograms } from '../shell.js';
import fs from 'fs';

const [scriptPath, outDir, invert] = process.argv.slice(2);
const script = JSON.parse(fs.readFileSync(scriptPath, 'utf8'));
const here = new URL('.', import.meta.url).pathname;
const gra = new Uint8Array(fs.readFileSync(here + '../MONOGRAF.GRA'));
const vfs = new MemoryFS({ 'MONOGRAF.GRA': gra, 'MONOCODE.CHN': new Uint8Array([26]), 'MONOCODE.000': new Uint8Array([26]) });
// Test fonts (never shipped): glyph rows 0 and 7 encode the character code, the rest is a fixed
// pattern, so every text cell can be decoded to its character; run '1' uses the bitwise inverse so
// that every pixel drawn by the font differs between the two runs.
const TEST_FONT = new Uint8Array(2048);
for (let c = 0; c < 256; c++) {
  const g = [c, 0x5A, 0xA5, 0x3C, 0xC3, 0x66, 0x99, c ^ 0xFF];
  for (let y = 0; y < 8; y++) TEST_FONT[c * 8 + y] = g[y];
}
let font = TEST_FONT;
if (invert === '1') font = Uint8Array.from(TEST_FONT, (b) => b ^ 0xff);
const R = new Runtime({ headless: true, vfs, font });
fs.mkdirSync(outDir, { recursive: true });

let snapNo = 0;
let cur = 0;                 // index of the current script key
let snapped = false;
function snapshot() {
  const b = Buffer.alloc(16384 + 4);
  Buffer.from(R.vram.buffer, R.vram.byteOffset, 16384).copy(b, 0);
  b[16384] = R.bios.mode; b[16385] = R.bios.col; b[16386] = R.bios.row; b[16387] = R.bios.colorSel;
  fs.writeFileSync(outDir + '/P' + String(snapNo++).padStart(4, '0') + '.BIN', b);
}
// like KEYFEED.COM, only the current script key is in the keyboard queue; the next one is queued
// when it has been read (queueing all at once would overflow the 15-key BIOS buffer)
function queueNext() { if (cur < script.length) { const [a, s, n] = script[cur]; R.queueKey(a, s, n); } }
queueNext();
const origPeek = R.biosPeek.bind(R);
R.biosPeek = function () {
  const avail = origPeek();
  if (avail && !snapped && cur < script.length && script[cur][3]) { snapshot(); snapped = true; }
  return avail;
};
const origRead = R.biosRead.bind(R);
R.biosRead = function () {
  if (!snapped && cur < script.length && script[cur][3]) snapshot();
  snapped = false; cur++;
  const r = origRead();
  queueNext();
  if (cur >= script.length) setTimeout(() => finish('script done'), 2000);
  return r;
};
let done = false;
function finish(why) {
  if (done) return; done = true;
  console.log(JSON.stringify({ why, snapshots: snapNo, keysUsed: cur }));
  process.exit(0);
}
runPrograms(R, (n) => import('../' + n + '.js')).then((r) => finish('program ended: ' + JSON.stringify(r)), (e) => { console.error(e); finish('exception'); });
setTimeout(() => finish('timeout'), 120000);
