// Unit tests for runtime pieces not visible in video memory.
import { Runtime, MemoryFS } from '../runtime.js';
let fail = 0;
const eq = (a, b, msg) => { if (JSON.stringify(a) !== JSON.stringify(b)) { fail++; console.log('FAIL', msg, a, b); } else console.log('ok  ', msg); };
async function main() {
  const R = new Runtime({ headless: true, vfs: new MemoryFS({}) });
  R.programStart();
  // deterministic keyboard: key visible only after 3 peeks; a blocking read takes it at once
  R.queueKey(65, 0x1E, 3);
  eq([await R.keyPressed(), await R.keyPressed(), await R.keyPressed(), await R.keyPressed()], [false, false, false, true], 'queueKey afterPeeks');
  R.queueKey(66, 0x30, 100);
  eq([await R.readKbd(), await R.readKbd()], [65, 66], 'AH=0 read ignores remaining peek count');
  // extended key: #27 then scan code (F1 = 59)
  R.pushKey(0, 0x3B);
  eq([await R.readKbd(), await R.keyPressed(), await R.readKbd()], [27, true, 59], 'extended key -> #27, scan');
  // a key waiting while text is written is consumed by the console output check
  R.pushKey(0x58, 0x2D); R.wrStr('x'); eq(R.keys.length, 0, 'key swallowed by console output');
  // Random from the start-up seed 0: first Random(30000) = 6924 (measured under DOSBox)
  const R2 = new Runtime({ headless: true }); eq(R2.random(30000), 6924, 'Random seed 0');
  // Sound divisor
  R.sound(440); eq(R.divisor, Math.floor(0x1234DD / 440), 'Sound divisor'); R.sound(18); eq(R.divisor, Math.floor(0x1234DD / 440), 'Sound(<=18) ignored');
  eq(Runtime.dosName(' c:\\save\\MyGame.Save1 '), 'MYGAME.SAV', 'DOS 8.3 names');
  // typed file round trip, partial record zero-fill, EOF error code
  const fa = 0x2000, buf = 0x3000;
  R.assign(fa, 'test.dat'); R.rewrite(fa, 4); R.ws(buf, 'abc', 3); R.writeRec(fa, buf); R.close(fa);
  R.reset(fa, 6); R.readRec(fa, buf); eq([R.ioResult(), Array.from(R.mem.slice(buf, buf + 6))], [0, [3, 97, 98, 99, 0, 0]], 'partial record zero-filled');
  R.readRec(fa, buf); eq(R.ioResult(), 0x99, 'read past EOF = $99');
  R.assign(fa, 'nofile'); R.reset(fa, 4); eq(R.ioResult(), 1, 'missing file = $01');
  console.log(fail ? fail + ' FAILED' : 'all passed'); process.exit(fail ? 1 : 0);
}
main();
