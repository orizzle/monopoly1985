// Compare pasrt.js Real48 arithmetic with results produced by the original 1985 runtime (DOSBox).
import * as H from '../pasrt.js';
import fs from 'fs';
const dir = process.argv[2] || new URL('./data', import.meta.url).pathname;
const R = fs.readFileSync(dir + '/REALS.BIN'), I = fs.readFileSync(dir + '/INTS.BIN');
const real = (k) => H.decodeReal(R.subarray(k * 6, k * 6 + 6));
const ints = new Int16Array(I.buffer, I.byteOffset, I.length / 2);
const c01 = H.r48(0x7d, 0xcc, 0xcc, 0xcc, 0xcc, 0x4c);
let k = 0, j = 0, bad = 0, n = 0;
for (let a = 1; a <= 60; a++) for (let b = 1; b <= 13; b++) {
  const q = H.rdiv(a * 7 + b * 13, b), p = H.rmul(q, c01), s = H.rsub(29, q);
  if (q !== real(k)) bad++; if (p !== real(k + 1)) bad++; if (s !== real(k + 2)) bad++;
  const enc = H.encodeReal(q); if (Buffer.compare(Buffer.from(enc), R.subarray(k * 6, k * 6 + 6)) !== 0) bad++;
  k += 3; n += 4;
  const r = [H.round(p), H.trunc(p), H.round(H.rmul(H.rdiv(q, 2), c01))];
  for (let t = 0; t < 3; t++) { if (r[t] !== ints[j + t]) bad++; n++; }
  j += 3;
}
for (let a = 1; a <= 400; a++) {
  const q = H.rmul(H.rdiv(a, 2), c01);
  if (q !== real(k)) bad++; if (H.round(q) !== ints[j]) bad++; n += 2; k++; j++;
}
console.log(`real48: ${n} checks, ${bad} mismatches`);
process.exit(bad ? 1 : 0);
