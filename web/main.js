// Browser bootstrap: canvas, keyboard, PC speaker, files, font selection, online games.
import { Runtime, BrowserFS, Speaker, biosKey } from './runtime.js';
import { BUILTIN_FONT } from './font.js';
import { runPrograms } from './shell.js';
import { createKeyboard } from './touchkbd.js';
import { lobby } from './lobby.js';
import { Api, Gate, OnlineFS } from './online.js';

const canvas = document.getElementById('screen');
const overlay = document.getElementById('overlay');
const status = document.getElementById('status');
const fontInput = document.getElementById('fontfile');
const fontReset = document.getElementById('fontreset');
const displaySel = document.getElementById('display');
let R = null, started = false;
let sink = null;                 // where typed keys go: the menus, the game, or the online game
let online = null;
window.monopolyState = () => ({ R, online });     // for tests
const speaker = new Speaker();
const api = new Api('api.php');

const kbd = document.getElementById('kbd');
const kbdToggle = document.getElementById('kbdtoggle');

// The screen is shown at a monitor's 4:3 aspect (VGA text is 720x400, graphics 640x400 pixels);
// the height is a multiple of 400 lines when it fits, so scan lines stay even.
// With the on-screen keyboard in landscape, the screen and keyboard sit side by side.
const main = document.querySelector('main'), bar = document.getElementById('bar');
const onlineEl = document.getElementById('online');
function fit() {
  const vw = Math.min(window.innerWidth, document.documentElement.clientWidth), vh = window.innerHeight;
  const side = !kbd.hidden && vw > vh;
  main.classList.toggle('side', side);
  kbd.style.removeProperty('--keyh');
  const maxH = side ? Math.min(vh - 16, (vw - 48) * 0.5 * 3 / 4)
    : Math.min((vw - 32) * 3 / 4, vh - (bar.offsetHeight + kbd.offsetHeight + onlineEl.offsetHeight + 16));
  const h = maxH >= 400 ? Math.floor(maxH / 400) * 400 : Math.max(100, maxH);
  canvas.style.height = h + 'px'; canvas.style.width = Math.round(h * 4 / 3) + 'px';
  if (side) {     // keys fill the height left beside the screen
    const keyH = (vh - 16 - bar.offsetHeight - 8 - 5 * 4) / 6;
    kbd.style.setProperty('--keyh', Math.max(24, Math.min(56, Math.floor(keyH))) + 'px');
  }
}
window.addEventListener('resize', fit);

// On-screen keyboard: offered on touch screens, shown by default when touch is the main input.
createKeyboard(kbd, (k) => { if (!started) { start(); return; } if (sink) sink(k); });
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
  if (e.target.closest && e.target.closest('input, select, textarea, button')) return;
  const k = biosKey(e);
  if (k) { e.preventDefault(); if (sink) sink(k); }
});
overlay.addEventListener('click', () => start());

// After a reload caused by an online game getting out of step, rejoin it.
let resume = null;
try { resume = JSON.parse(sessionStorage.getItem('monopoly.resume') || 'null'); sessionStorage.removeItem('monopoly.resume'); } catch (e) { /* none */ }
if (resume) overlay.firstElementChild.textContent = 'Click or press a key to rejoin online game ' + resume.code;

const newRuntime = (vfs) => new Runtime({ canvas, audio: speaker, vfs, font: font8(), font16: font16(), display: display() });
const loadModule = (name) => import('./' + name + '.js');

async function start() {
  if (started) { speaker.resume(); return; }
  started = true;
  overlay.style.display = 'none';
  speaker.resume();
  const gra = new Uint8Array(await (await fetch('MONOGRAF.GRA')).arrayBuffer());
  const marker = new Uint8Array([0x1A]);
  const builtin = { 'MONOGRAF.GRA': gra, 'MONOCODE.CHN': marker, 'MONOCODE.000': marker };
  await fontsReady;
  // the menus run on a runtime of their own; the game then starts on a fresh one, as from DOS
  const menu = newRuntime(new BrowserFS({}));
  R = menu; sink = (k) => menu.pushKey(k[0], k[1]);
  canvas.focus();
  const choice = await lobby(menu, api, resume);
  menu.detach(); menu.noSound();
  if (choice.mode === 'online') { await playOnline(choice, builtin); return; }
  R = newRuntime(new BrowserFS(builtin));
  sink = (k) => R.pushKey(k[0], k[1]);
  const res = await runPrograms(R, loadModule);
  status.textContent = res.kind === 'error' ? 'Program aborted.' : 'Program ended. Reload the page to play again.';
}

// ---------------------------------------------------------------------------------------- online
const olStatus = document.getElementById('olstatus');
const takeover = document.getElementById('takeover');
const chatLog = document.getElementById('chatlog');
const chatForm = document.getElementById('chatform');
const chatIn = document.getElementById('chatin');

async function playOnline(choice, builtin) {
  const s = choice.session;
  R = newRuntime(new OnlineFS(builtin, s.startEv.files, new BrowserFS({})));
  const gate = new Gate(s);
  if (resume && resume.code === s.code && resume.p !== undefined) gate.trustedUpTo = resume.p;
  R.keyGate = gate; online = { s, gate };
  onlineEl.hidden = false; fit();
  let note = '', noteUntil = 0;
  const nameOf = (i) => (s.seats[i] ? s.seats[i].name : '?');
  sink = (k) => {
    if (gate.localKey(k)) return;
    note = 'it is ' + nameOf(gate.owner) + '\'s turn.'; noteUntil = performance.now() + 2000; showStatus();
  };
  // A new game: the host's copy types the players' names into the game's own name entry.
  if (s.me === 0 && !choice.load && s.H < 0) {
    // (only when the program asks for a key, so the drawing of the screen does not swallow them)
    for (const n of s.startEv.seats) { for (const ch of n) gate.local.push([ch.charCodeAt(0), 0, true]); gate.local.push([13, 0x1C, true]); }
    if (s.startEv.seats.length < 4) gate.local.push([13, 0x1C, true]);   // the game stops by itself at four
  }
  let pending = false;
  function showStatus() {
    if (pending) return; pending = true;
    requestAnimationFrame(() => {
      pending = false;
      let t = 'Online game ' + s.code + ': ';
      const by = s.seats[gate.by];
      if (gate.behind > 60) t += 'catching up…';
      else if (performance.now() < noteUntil) t += note;
      else if (gate.by === s.me) t += gate.owner === s.me ? 'your turn.' : 'you are playing for ' + nameOf(gate.owner) + '.';
      else t += nameOf(gate.owner) + '\'s turn' + (by && !by.online ? ' (offline)' : '') + '.';
      olStatus.textContent = t;
      const canTake = s.me === 0 && gate.by !== 0 && by && !by.online && by.away >= 20;
      takeover.hidden = !canTake;
      if (canTake) takeover.textContent = 'Play for ' + nameOf(gate.owner);
    });
  }
  s.onChange = showStatus; gate.onStatus = showStatus;
  takeover.onclick = () => { api.call('control', { code: s.code, token: s.token, seat: gate.owner }); canvas.focus(); };
  s.onChat = (ev) => {
    const d = document.createElement('div');
    const b = document.createElement('b'); b.textContent = ev.name + ': ';
    d.append(b, document.createTextNode(ev.text));
    chatLog.append(d); chatLog.scrollTop = chatLog.scrollHeight;
  };
  chatForm.onsubmit = (e) => { e.preventDefault(); const t = chatIn.value.trim(); if (t) s.say(t); chatIn.value = ''; };
  // p: the poll where the difference showed; the rebuilt copy trusts the log up to there
  const rejoin = (p) => {
    try { sessionStorage.setItem('monopoly.resume', JSON.stringify({ code: s.code, name: s.name, p })); } catch (e) { /* none */ }
    location.reload();
  };
  gate.onDesync = (p) => {
    olStatus.textContent = 'This copy of the game got out of step; rejoining…';
    setTimeout(() => rejoin(Math.max(p, s.H)), 1500);
  };
  s.onFatal = (e) => {
    if (e === 'desync') gate.onDesync(gate.p);
    else olStatus.textContent = 'The online game has ended.';
  };
  showStatus();
  const res = await runPrograms(R, loadModule);
  olStatus.textContent = res.kind === 'error' ? 'Program aborted.' : 'Program ended. Reload the page to play again.';
}
