// The menus before the game: play on this computer, or create or join an online game. They are
// drawn on the PC text screen in the game's own style (its title box, colours and name entry).
import { Session } from './online.js';

const W = 46;                                   // width of the text window inside the brown box
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The game's TitleBox: grey-edged brown "Monopoly" box, green subtitle, then the large box below.
function screen(R, subtitle, hint = '') {
  R.cflag = 0;
  R.textMode(3); R.window(1, 1, 80, 25); R.textBackground(0); R.clrScr();
  if (hint) { R.textColor(8); R.gotoXY(1, 25); R.wrStr(hint); }
  R.window(25, 6, 55, 10); R.textBackground(7); R.clrScr();
  R.window(26, 7, 54, 9); R.textBackground(6); R.clrScr();
  R.textColor(15); R.gotoXY(11, 2); R.wrStr('Monopoly');
  R.window(1, 1, 80, 25); R.gotoXY(41 - (subtitle.length >> 1), 13); R.textColor(2); R.textBackground(0); R.wrStr(subtitle);
  R.window(15, 14, 65, 23); R.textBackground(7); R.clrScr();
  R.window(16, 15, 64, 22); R.textBackground(6); R.clrScr();
  R.window(19, 16, 64, 22);
}
function center(R, row, text, color) {
  R.gotoXY(1 + ((W - text.length) >> 1), row); R.textColor(color); R.wrStr(text);
}
function line(R, row, parts) {             // [[text, color], ...] starting at column 1 of the window
  R.gotoXY(1, row); R.clrEol();
  let len = 0; for (const [t] of parts) len += t.length;
  R.gotoXY(1 + ((W - len) >> 1), row);
  for (const [t, c] of parts) { R.textColor(c); R.wrStr(t); }
}
async function key(R) {
  const c = await R.readKbd();
  if (c === 27 && R.pendingScan) return { ext: await R.readKbd() };
  return { ch: c };
}
// A key, or null after ms milliseconds (for screens that change while waiting).
async function keyWithin(R, ms) {
  const end = performance.now() + ms;
  while (performance.now() < end) { if (R._kbHit()) return key(R); await sleep(30); }
  return null;
}
// Name entry as in the game: dots, typed text in white, Backspace erases.
async function field(R, x, y, len, upper = false) {
  R.textColor(7); R.gotoXY(x, y); R.wrStr('.'.repeat(len));
  R.textColor(15); R.gotoXY(x, y);
  let s = '';
  for (;;) {
    const k = await key(R);
    if (k.ext !== undefined) continue;
    if (k.ch === 13) { if (s.trim()) return s.trim(); continue; }
    if (k.ch === 27) return null;
    if (k.ch === 8) {
      if (s) { s = s.slice(0, -1); R.gotoXY(x + s.length, y); R.wrStr(' '); R.gotoXY(x + s.length, y); }
      continue;
    }
    let c = String.fromCharCode(k.ch);
    if (upper) { c = c.toUpperCase(); if (!/[A-Z]/.test(c)) continue; }
    if (k.ch >= 32 && k.ch < 127 && s.length < len && !(c === ' ' && !s)) { s += c; R.wrStr(c); }
  }
}
// Like the game's red alert window: a low beep and <Press Any Key>.
async function alert(R, ...lines) {
  R.window(16, 15, 64, 22); R.textBackground(4); R.clrScr();
  R.window(19, 16, 64, 22);
  lines.forEach((t, i) => center(R, 2 + i, t, 15));
  R.sound(100); await sleep(500); R.noSound();
  center(R, 7, '<Press Any Key>', 15);
  await key(R);
}

const ERRORS = {
  network: ['The game server cannot be reached.'],
  nogame: ['There is no online game with that code.'],
  full: ['That game already has four players.'],
  started: ['That game has already started.'],
  nametaken: ['Someone in that game already has', 'that name.'],
  name: ['Names are 1 to 10 letters, digits', 'or signs.'],
  busy: ['The game server is busy.', 'Try again later.'],
};
function errorLines(e) { return ERRORS[e] || ['The game server refused (' + e + ').']; }

function rememberSession(s) {
  try { localStorage.setItem('monopoly.online', JSON.stringify({ code: s.code, name: s.name, token: s.token })); } catch (e) { /* none */ }
}
function savedToken(code, name) {
  try {
    const o = JSON.parse(localStorage.getItem('monopoly.online') || 'null');
    if (o && o.code === code && o.name.toUpperCase() === name.toUpperCase()) return o.token;
  } catch (e) { /* none */ }
  return undefined;
}

// Returns {mode: 'local'} or {mode: 'online', session, load}.
export async function lobby(R, api, resume = null) {
  if (resume) {
    const s = await joinGame(R, api, resume.code, resume.name);
    if (s) return s;
  }
  for (;;) {
    screen(R, 'Welcome to the Monopoly Game');
    center(R, 1, 'How do you want to play?', 14);
    line(R, 3, [['L', 15], ['  Play on this computer   ', 7]]);
    line(R, 4, [['C', 15], ['  Create an online game   ', 7]]);
    line(R, 5, [['J', 15], ['  Join an online game     ', 7]]);
    R.gotoXY(36, 5);
    let k;
    do { k = await key(R); } while (k.ext !== undefined || !'LCJ'.includes(String.fromCharCode(k.ch).toUpperCase()));
    const c = String.fromCharCode(k.ch).toUpperCase();
    if (c === 'L') return { mode: 'local' };
    const r = c === 'C' ? await createGame(R, api) : await joinScreen(R, api);
    if (r) return r;
  }
}

async function askName(R, subtitle, row = 3) {
  center(R, row, 'What is your name?', 14);
  R.textColor(7); R.gotoXY(14, row + 2); R.wrStr('> ');
  return field(R, 16, row + 2, 10);
}

async function createGame(R, api) {
  screen(R, 'Create an online game', '  Esc goes back.');
  const name = await askName(R);
  if (name === null) return null;
  center(R, 7, 'Connecting...', 7);
  const r = await api.call('create', { name });
  if (!r.ok) { await alert(R, ...errorLines(r.error)); return null; }
  const s = new Session(api, { code: r.code, token: r.token, seat: r.seat, name });
  rememberSession(s);
  return waitingRoom(R, s);
}

async function joinScreen(R, api) {
  screen(R, 'Join an online game', '  Esc goes back.');
  center(R, 1, 'What is the game code?', 14);
  R.textColor(7); R.gotoXY(19, 2); R.wrStr('> ');
  const code = await field(R, 21, 2, 4, true);
  if (code === null) return null;
  if (code.length !== 4) { await alert(R, 'A game code has four letters.'); return null; }
  const name = await askName(R, '', 4);
  if (name === null) return null;
  return joinGame(R, api, code, name);
}

async function joinGame(R, api, code, name) {
  screen(R, 'Join an online game');
  center(R, 4, 'Connecting...', 7);
  const r = await api.call('join', { code, name, token: savedToken(code, name) });
  if (!r.ok) { await alert(R, ...errorLines(r.error)); return null; }
  const s = new Session(api, { code: r.code, token: r.token, seat: r.seat, name });
  rememberSession(s);
  return waitingRoom(R, s);
}

// The players of the game as they join; the host starts it.
async function waitingRoom(R, s) {
  s.run();
  const host = s.me === 0;
  screen(R, 'Online game', '  Esc leaves the online game.');
  let shown = '', load = false;
  for (;;) {
    if (s.closed) { await alert(R, 'The host has closed this game.'); return null; }
    if (s.startEv) return { mode: 'online', session: s, load: s.startEv.load };
    const state = JSON.stringify(s.seats);
    if (state !== shown) {
      shown = state;
      line(R, 1, [['Game code:  ', 14], [s.code, 15]]);
      if (host) line(R, 2, [['Give this code to the other players.', 7]]);
      else line(R, 2, [['Waiting for ' + (s.seats[0] ? s.seats[0].name : 'the host') + ' to start the game.', 7]]);
      for (let i = 0; i < 4; i++) {
        R.gotoXY(1, 3 + i); R.clrEol();
        const p = s.seats[i];
        if (!p) continue;
        R.gotoXY(13, 3 + i); R.textColor(7); R.wrStr((i + 1) + '> ');
        R.textColor(p.online ? 15 : 8); R.wrStr(p.name);
        if (i === s.me) { R.textColor(7); R.wrStr('  (you)'); }
      }
      if (host) {
        R.gotoXY(1, 7); R.clrEol();
        if (s.seats.length >= 2) line(R, 7, [['S', 15], [' starts a new game, ', 7], ['F2', 15], [' a saved one.', 7]]);
        else line(R, 7, [['Waiting for players to join...', 7]]);
      }
      R.gotoXY(25, 1);
    }
    const k = await keyWithin(R, 200);
    if (!k) continue;
    if (k.ch === 27) { await s.leave(); return null; }
    if (host && s.seats.length >= 2 && (k.ext === 60 || (k.ch !== undefined && String.fromCharCode(k.ch).toUpperCase() === 'S'))) {
      load = k.ext === 60;
      const { localSaves } = await import('./online.js');
      const r = await s.api.call('start', { code: s.code, token: s.token, files: localSaves(), load });
      if (!r.ok) { await alert(R, ...errorLines(r.error)); screen(R, 'Online game', '  Esc leaves the online game.'); shown = ''; continue; }
      while (!s.startEv && !s.closed) { s.flushSoon(); await sleep(50); }
    }
  }
}
