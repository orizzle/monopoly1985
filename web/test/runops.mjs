// Headless runner: executes a probe op list against the runtime and writes the dump file
// in the same format as the DOSBox probe (see dosbox_compare.py).
import { Runtime, MemoryFS } from '../runtime.js';
import fs from 'fs';

const [, , opsFile, outFile, fontFile] = process.argv;
const ops = JSON.parse(fs.readFileSync(opsFile, 'utf8'));
const opts = { headless: true, vfs: new MemoryFS({}) };
if (fontFile) opts.font = new Uint8Array(fs.readFileSync(fontFile));
const R = new Runtime(opts);
// state at program start under DOSBox: BIOS mode 3, cursor on the last line
R.biosSetCursor(24, 0);
R.programStart();
const out = [];
const pics = {};
let picBase = 0x1000;
const strs = {};
const dump = () => {
  for (const b of R.vram) out.push(b);
  out.push(R.bios.mode, R.bios.col, R.bios.row, R.bios.colorSel, R.whereX(), R.whereY());
};
async function main() {
for (const op of ops) {
  const [k, ...a] = op;
  switch (k) {
    case 'tm': R.textMode(a[0]); break;
    case 'win': R.window(...a); break;
    case 'clr': R.clrScr(); break;
    case 'eol': R.clrEol(); break;
    case 'gxy': R.gotoXY(a[0], a[1]); break;
    case 'tc': R.textColor(a[0]); break;
    case 'tb': R.textBackground(a[0]); break;
    case 'lv': R.lowVideo(); break;
    case 'hv': R.highVideo(); break;
    case 'wr': R.wrStr(a[0], 0); break;
    case 'wrs': R.wrStr(a[0], a[1]); break;
    case 'wri': R.wrInt(a[0], a[1]); break;
    case 'wrc': R.wrChar(a[0], a[1]); break;
    case 'ln': R.wrLn(); break;
    case 'gcm': R.graphColorMode(); break;
    case 'pal': R.palette(a[0]); break;
    case 'pic': { pics[a[0]] = picBase; a[1].forEach((b, i) => R.wb(picBase + i, b)); picBase += 0x2000; break; }
    case 'put': R.putPic(pics[a[0]], a[1], a[2]); break;
    case 'get': { R.getPic(pics[a[0]], a[1], a[2], a[3], a[4]); for (let i = 0; i < a[5]; i++) out.push(R.rb(pics[a[0]] + i)); break; }
    case 'keys': for (const [c, s] of a[0]) R.pushKey(c, s); break;
    case 'rdln': { await R.rdBeginLn(); strs[a[1]] = await R.rdStr(a[0]); await R.rdLn(); break; }
    case 'rd': { await R.rdBegin(); strs[a[1]] = await R.rdStr(a[0]); break; }
    case 'wrv': R.wrStr(strs[a[0]] || '', 0); break;
    case 'dump': dump(); break;
    case 'ioerr': try { R.runError(1, a[0], a[1]); } catch (e) { /* program aborted */ } R.programStart(); break;
    default: throw new Error('op ' + k);
  }
}
fs.writeFileSync(outFile, Buffer.from(out));
}
main().catch((e) => { console.error(e); process.exit(1); });
