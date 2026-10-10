// Browser bootstrap: canvas, keyboard, PC speaker, files, font selection.
import { Runtime, BrowserFS, Speaker, biosKey } from './runtime.js';
import { BUILTIN_FONT } from './font.js';
import { runPrograms } from './shell.js';
import { createKeyboard } from './touchkbd.js';

const canvas = document.getElementById('screen');
const overlay = document.getElementById('overlay');
const status = document.getElementById('status');
const fontInput = document.getElementById('fontfile');
const fontReset = document.getElementById('fontreset');
const displaySel = document.getElementById('display');
let R = null, started = false;
const speaker = new Speaker();

const kbd = document.getElementById('kbd');
const kbdToggle = document.getElementById('kbdtoggle');

// The screen is shown at a monitor's 4:3 aspect (VGA text is 720x400, graphics 640x400 pixels);
// the height is a multiple of 400 lines when it fits, so scan lines stay even.
// With the on-screen keyboard in landscape, the screen and keyboard sit side by side.
const main = document.querySelector('main'), bar = document.getElementById('bar');
function fit() {
  const vw = Math.min(window.innerWidth, document.documentElement.clientWidth), vh = window.innerHeight;
  const side = !kbd.hidden && vw > vh;
  main.classList.toggle('side', side);
  kbd.style.removeProperty('--keyh');
  const maxH = side ? Math.min(vh - 16, (vw - 48) * 0.5 * 3 / 4)
    : Math.min((vw - 32) * 3 / 4, vh - (bar.offsetHeight + kbd.offsetHeight + 16));
  const h = maxH >= 400 ? Math.floor(maxH / 400) * 400 : Math.max(100, maxH);
  canvas.style.height = h + 'px'; canvas.style.width = Math.round(h * 4 / 3) + 'px';
  if (side) {     // keys fill the height left beside the screen
    const keyH = (vh - 16 - bar.offsetHeight - 8 - 5 * 4) / 6;
    kbd.style.setProperty('--keyh', Math.max(24, Math.min(56, Math.floor(keyH))) + 'px');
  }
}
window.addEventListener('resize', fit);

// On-screen keyboard: offered on touch screens, shown by default when touch is the main input.
createKeyboard(kbd, (k) => { if (!started) { start(); return; } R.pushKey(k[0], k[1]); });
// Keys act on pointerdown, but a touch only counts as a user gesture (needed to start audio) when the
// finger lifts, so the speaker is (re)started then.
for (const ev of ['pointerup', 'touchend']) kbd.addEventListener(ev, () => { if (started) speaker.resume(); });
if (navigator.maxTouchPoints > 0 || matchMedia('(any-pointer: coarse)').matches) {
  kbdToggle.hidden = false;
  let show = matchMedia('(pointer: coarse)').matches;
  try { const s = localStorage.getItem('monopoly.kbd'); if (s) show = s === '1'; } catch (e) { /* default */ }
  kbd.hidden = !show;
  overlay.firstElementChild.textContent = 'Tap or press a key to start';
  kbdToggle.addEventListener('click', () => {
    kbd.hidden = !kbd.hidden;
    try { localStorage.setItem('monopoly.kbd', kbd.hidden ? '0' : '1'); } catch (e) { /* not persisted */ }
    fit(); canvas.focus();
  });
}
fit();

function b64ToBytes(s) { const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
function bytesToB64(u) { let s = ''; for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s); }
function saved(key, size) {
  try { const s = localStorage.getItem(key); if (s) { const f = b64ToBytes(s); if (f.length === size) return f; } } catch (e) { /* none */ }
  return null;
}
// Fonts: pcfont.bin (8x8) and pcfont16.bin (VGA 8x16), written by tools/extract_pcfont.sh from your
// own DOSBox/PC BIOS, are used when present. When both are present they are always used and the
// font controls are hidden; otherwise fonts loaded with the control below take precedence, then the
// built-in font (an original design; 8x16 = its rows doubled).
let pcFont = null, pcFont16 = null, pcFontsOnly = false;
const get = (name, size) => fetch(name).then((r) => (r.ok ? r.arrayBuffer() : null))
  .then((b) => { const u = b && new Uint8Array(b); return u && u.length === size ? u : null; }).catch(() => null);
const fontsReady = Promise.all([get('pcfont.bin', 2048), get('pcfont16.bin', 4096)])
  .then(([a, b]) => {
    pcFont = a; pcFont16 = b; pcFontsOnly = !!(a && b);
    if (pcFontsOnly) for (const el of [fontInput.parentElement, fontReset]) el.hidden = true;
    fontLabel();
  });
const userFont = (key, size) => (pcFontsOnly ? null : saved(key, size));
const font8 = () => userFont('monopoly.font', 2048) || pcFont || BUILTIN_FONT;
const font16 = () => userFont('monopoly.font16', 4096) || pcFont16;
function fontLabel() {
  const name8 = userFont('monopoly.font', 2048) ? 'user-supplied 8x8 font' : pcFont ? 'PC BIOS 8x8 font (pcfont.bin)' : 'built-in';
  const name = display() === 'vga'
    ? (userFont('monopoly.font16', 4096) ? 'user-supplied 8x16 font' : pcFont16 ? 'PC BIOS 8x16 font (pcfont16.bin)' : name8 + ', rows doubled')
    : name8;
  status.textContent = 'Font: ' + name;
}
function display() { try { return localStorage.getItem('monopoly.display') === 'cga' ? 'cga' : 'vga'; } catch (e) { return 'vga'; } }
displaySel.value = display();
displaySel.addEventListener('change', () => {
  try { localStorage.setItem('monopoly.display', displaySel.value); } catch (e) { /* not persisted */ }
  if (R) R.setDisplay(displaySel.value);
  fontLabel(); canvas.focus();
});
fontLabel();
fontInput.addEventListener('change', async () => {
  const f = fontInput.files[0]; if (!f) return;
  const u = new Uint8Array(await f.arrayBuffer());
  if (u.length === 2048) {
    try { localStorage.setItem('monopoly.font', bytesToB64(u)); } catch (e) { /* not persisted */ }
    if (R) R.setFont(u);
  } else if (u.length === 4096) {
    try { localStorage.setItem('monopoly.font16', bytesToB64(u)); } catch (e) { /* not persisted */ }
    if (R) R.setFont16(u);
  } else { status.textContent = 'Font file must be 2048 bytes (8x8) or 4096 bytes (8x16)'; return; }
  fontLabel(); fontInput.value = ''; canvas.focus();
});
fontReset.addEventListener('click', () => {
  try { localStorage.removeItem('monopoly.font'); localStorage.removeItem('monopoly.font16'); } catch (e) { /* ignore */ }
  if (R) { R.setFont(font8()); R.setFont16(font16()); }
  fontLabel(); canvas.focus();
});

window.addEventListener('keydown', (e) => {
  if (!started) { if (e.key !== 'Tab') { e.preventDefault(); start(); } return; }
  if (document.activeElement === fontInput || document.activeElement === displaySel) return;
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
  await fontsReady;
  R = new Runtime({ canvas, audio: speaker, vfs, font: font8(), font16: font16(), display: display() });
  canvas.focus();
  const res = await runPrograms(R, (name) => import('./' + name + '.js'));
  status.textContent = res.kind === 'error' ? 'Program aborted.' : 'Program ended. Reload the page to play again.';
}
