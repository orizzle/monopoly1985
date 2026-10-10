// Browser bootstrap: canvas, keyboard, PC speaker, files, font selection.
import { Runtime, BrowserFS, Speaker, biosKey } from './runtime.js';
import { BUILTIN_FONT } from './font.js';
import { runPrograms } from './shell.js';

const canvas = document.getElementById('screen');
const overlay = document.getElementById('overlay');
const status = document.getElementById('status');
const fontInput = document.getElementById('fontfile');
const fontReset = document.getElementById('fontreset');
let R = null, started = false;
const speaker = new Speaker();

function fit() {
  const ui = document.getElementById('bar').offsetHeight + 16;
  const fitScale = Math.min((window.innerWidth - 32) / 640, (window.innerHeight - ui) / 400);
  const s = fitScale >= 1 ? Math.floor(fitScale) : Math.max(0.25, fitScale);   // integer scaling when it fits
  canvas.style.width = 640 * s + 'px'; canvas.style.height = 400 * s + 'px';
}
window.addEventListener('resize', fit); fit();

function b64ToBytes(s) { const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
function bytesToB64(u) { let s = ''; for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s); }
function savedFont() {
  try { const s = localStorage.getItem('monopoly.font'); if (s) { const f = b64ToBytes(s); if (f.length === 2048) return f; } } catch (e) { /* none */ }
  return null;
}
// pcfont.bin (written by tools/extract_pcfont.sh from your own DOSBox/PC BIOS) is the default font
// when present; a font loaded with the control below takes precedence; otherwise the built-in font.
let pcFont = null;
const pcFontReady = fetch('pcfont.bin').then((r) => (r.ok ? r.arrayBuffer() : null))
  .then((b) => { const u = b && new Uint8Array(b); if (u && u.length === 2048) pcFont = u; })
  .catch(() => {}).then(() => fontLabel());
function defaultFont() { return pcFont || BUILTIN_FONT; }
function fontLabel() {
  status.textContent = savedFont() ? 'Font: user-supplied 8x8 font' : pcFont ? 'Font: PC BIOS font (pcfont.bin)' : 'Font: built-in';
}
fontLabel();
fontInput.addEventListener('change', async () => {
  const f = fontInput.files[0]; if (!f) return;
  const u = new Uint8Array(await f.arrayBuffer());
  if (u.length !== 2048) { status.textContent = 'Font file must be exactly 2048 bytes (256 glyphs x 8 rows)'; return; }
  try { localStorage.setItem('monopoly.font', bytesToB64(u)); } catch (e) { /* not persisted */ }
  if (R) R.setFont(u);
  fontLabel(); fontInput.value = ''; canvas.focus();
});
fontReset.addEventListener('click', () => {
  try { localStorage.removeItem('monopoly.font'); } catch (e) { /* ignore */ }
  if (R) R.setFont(defaultFont());
  fontLabel(); canvas.focus();
});

window.addEventListener('keydown', (e) => {
  if (!started) { if (e.key !== 'Tab') { e.preventDefault(); start(); } return; }
  if (document.activeElement === fontInput) return;
  const k = biosKey(e);
  if (k) { e.preventDefault(); R.pushKey(k[0], k[1]); }
});
overlay.addEventListener('click', () => start());

async function start() {
  if (started) { speaker.resume(); return; }
  started = true;
  overlay.style.display = 'none';
  speaker.resume();
  const gra = new Uint8Array(await (await fetch('MONOGRAF.GRA')).arrayBuffer());
  const marker = new Uint8Array([0x1A]);
  const vfs = new BrowserFS({ 'MONOGRAF.GRA': gra, 'MONOCODE.CHN': marker, 'MONOCODE.000': marker });
  await pcFontReady;
  R = new Runtime({ canvas, audio: speaker, vfs, font: savedFont() || defaultFont() });
  canvas.focus();
  const res = await runPrograms(R, (name) => import('./' + name + '.js'));
  status.textContent = res.kind === 'error' ? 'Program aborted.' : 'Program ended. Reload the page to play again.';
}
