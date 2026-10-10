// Online play. Every player's browser runs its own copy of the game; since the program is
// deterministic, the copies stay identical as long as each receives the same keys at the same
// point. The point is the keyboard poll: the runtime numbers every KeyPressed and every wait for a
// key (Read(Kbd), ReadLn), and keys reach the program only there (Runtime.keyGate). The dice depend
// on how often the program polled before a key arrived, so they come out the same everywhere.
//
// The player whose turn it is (by the game's own CurPlayer) decides each poll: "this key" or "no
// key". Those decisions go to a small PHP backend (api.php) as a shared log; the other copies follow
// the log and wait when they have caught up with it. Each logged key carries a hash of the game's
// data so that any difference between the copies is noticed at once.

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CUR_PLAYER = 0x0262, NUM_PLAYERS = 0x3921, PLAYERS = 0x3897, PLAYER_SIZE = 34, UNAME = 21;

export class Api {
  constructor(url = 'api.php') { this.url = url; }
  async call(a, body = {}) {
    let r;
    try {
      r = await fetch(this.url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ a, ...body }), cache: 'no-store' });
    } catch (e) { return { ok: false, error: 'network' }; }
    try { return await r.json(); } catch (e) { return { ok: false, error: 'network' }; }
  }
}

// FNV-1a over the data segment and the random seed: the state the game's decisions depend on.
export function stateHash(R) {
  let h = 0x811C9DC5;
  const m = R.mem;
  for (let i = 0; i < 0x10000; i++) h = Math.imul(h ^ m[i], 0x01000193);
  h = Math.imul(h ^ (R.seed >>> 0), 0x01000193);
  return h >>> 0;
}

// One online game: players, the shared key log and the connection to the backend.
export class Session {
  constructor(api, { code, token, seat, name }) {
    Object.assign(this, { api, code, token, me: seat, name });
    this.seats = [];            // [{name, online, away, by}] from the backend
    this.startEv = null;        // {seats, files, load} once the host has started the game
    this.ctl = [];              // control changes: the host plays for an absent player from poll 'from'
    this.keys = new Map();      // poll -> [ascii, scan, as, hash]
    this.H = -1;                // every poll up to H is decided
    this.ko = 0; this.eo = 0;   // read offsets in the backend's logs
    this.outKeys = []; this.outH = null; this.outChat = [];
    this.waiters = [];
    this.onChange = null; this.onChat = null; this.onFatal = null;
    this.closed = false;
    this.queue = Promise.resolve();
  }
  changed() { const w = this.waiters; this.waiters = []; for (const f of w) f(); if (this.onChange) this.onChange(); }
  waitChange() { return new Promise((r) => this.waiters.push(r)); }
  controller(seat, p) {
    let by = seat;
    for (const c of this.ctl) if (c.seat === seat && c.from <= p) by = c.by;
    return by;
  }
  // One request to the backend (requests are serialized); extra = keys/horizon that must be acknowledged.
  sync(extra = null) {
    const run = async () => {
      if (this.closed) return { ok: false, error: 'closed' };
      const keys = extra ? extra.keys || [] : this.outKeys.splice(0);
      const hz = extra ? extra.h : this.outH; if (!extra) this.outH = null;
      const chat = extra ? null : this.outChat.shift();
      const body = { code: this.code, token: this.token, ko: this.ko, eo: this.eo };
      if (keys.length) body.keys = keys;
      if (hz) { body.h = hz.h; body.has = hz.has; }
      if (chat) body.chat = chat;
      const r = await this.api.call('sync', body);
      if (!r.ok) {
        if (r.error === 'network') {           // try again with the next request
          if (!extra) { this.outKeys.unshift(...keys); if (hz && !this.outH) this.outH = hz; if (chat) this.outChat.unshift(chat); }
          return r;
        }
        if (r.error === 'nogame' || r.error === 'notplayer') { this.closed = true; if (this.onFatal) this.onFatal(r.error); return r; }
        if (!extra && (keys.length || hz)) { if (this.onFatal) this.onFatal('desync'); }   // our own decisions were refused
        return r;
      }
      this._apply(r);
      return r;
    };
    this.queue = this.queue.then(run, run);
    return this.queue;
  }
  _apply(r) {
    for (const [p, a, s, as, hash] of r.keys) if (!this.keys.has(p)) this.keys.set(p, [a, s, as, hash]);
    this.ko = r.ko;
    for (const ev of r.events) {
      if (ev.t === 'start') this.startEv = ev;
      else if (ev.t === 'control') this.ctl.push({ seat: ev.seat, by: ev.by, from: ev.from });
      else if (ev.t === 'chat' && this.onChat) this.onChat(ev);
    }
    this.eo = r.eo;
    if (r.H > this.H) this.H = r.H;
    this.seats = r.seats;
    this.changed();
  }
  // Background requests: fast while a game runs, slower in the waiting room.
  run() {
    const loop = async () => {
      while (!this.closed) {
        const t0 = performance.now();
        await this.sync();
        const gap = this.startEv ? 100 : 700;
        const wait = gap - (performance.now() - t0);
        if (wait > 0) await new Promise((r) => { this.kick = r; setTimeout(r, wait); });
        this.kick = null;
      }
    };
    loop();
  }
  flushSoon() { if (this.kick) this.kick(); }
  say(text) { this.outChat.push(text); this.flushSoon(); }
  async leave() { this.closed = true; await this.api.call('leave', { code: this.code, token: this.token }); }
}

// Runtime.keyGate for an online game.
export class Gate {
  constructor(session) {
    this.s = session;
    this.seatNames = session.startEv.seats.map((n) => n.toUpperCase());
    this.p = 0;                 // number of the next keyboard poll
    this.local = [];            // keys typed here, waiting for a poll: [ascii, scan, onlyWhenAsked]
    this.sawZero = false; this.inGame = false;
    this.owner = 0; this.by = 0;
    this.behind = 0;
    this.onDesync = null; this.onStatus = null;
    this.trustedUpTo = -1;      // after a resync: polls up to here are taken from the log without question
    // tests: record the state every n polls, to compare the copies (window.monopolyTraceEvery = n)
    this.traceEvery = globalThis.monopolyTraceEvery || 0; this.trace = {};
  }
  // The player whose turn it is, from the game's own data: the host while the players are being
  // entered (and while loading), then the player named Player[CurPlayer].
  ownerSeat(R) {
    if (R.program !== 'game') return 0;
    const n = R.rw(NUM_PLAYERS);
    if (n === 0) { this.sawZero = true; this.inGame = false; }
    else if (this.sawZero && R.bios.mode === 4 && n >= 2 && n <= 4) this.inGame = true;
    if (!this.inGame) return 0;
    const cur = R.rw(CUR_PLAYER);
    if (cur < 1 || cur > n) return 0;
    const i = this.seatNames.indexOf(R.rs(PLAYERS + (cur - 1) * PLAYER_SIZE + UNAME));
    return i < 0 ? 0 : i;
  }
  // A key typed on this computer: kept only if it is this player's turn (like a BIOS buffer).
  localKey(k) {
    if (this.by !== this.s.me) return false;
    if (this.local.length < 15) this.local.push(k);
    this.s.changed();
    return true;
  }
  // A keyboard poll of the program: KeyPressed, a wait for a key (blocking), or the end of a Delay
  // or CPU-timed loop (quiet: the runtime has just waited, no extra yield).
  async poll(R, blocking, quiet = false) {
    const p = this.p++;
    if (this.traceEvery && p % this.traceEvery === 0)
      this.trace[p] = [stateHash(R), R.rw(0x264), R.rw(0x266), R.seed >>> 0];
    const prevIdle = this.idle;               // the previous poll was a KeyPressed that got no key
    this.idle = !blocking && !quiet;
    const owner = this.ownerSeat(R);
    for (;;) {
      const by = this.s.controller(owner, p);
      if (owner !== this.owner || by !== this.by) { this.owner = owner; this.by = by; if (this.onStatus) this.onStatus(); }
      if (p <= this.s.H) {                                   // decided: follow the log
        const e = this.s.keys.get(p);
        if (e) {
          this.idle = false;
          // A different hash means the copies differ. A copy just rebuilt from the log is right by
          // construction, so up to the point where it was rebuilt the other copy was out of step.
          if (e[3] !== stateHash(R) && p > this.trustedUpTo) { if (this.onDesync) this.onDesync(p); await new Promise(() => {}); }
          R.queueKey(e[0], e[1]);
        }
        this._pace(R, p);
        if (quiet) return;
        if (R.ff) await R._ffYield(); else await R._yield();
        return;
      }
      if (by === this.s.me) {                                // this computer decides
        R.setFastForward(false);
        // keys typed by this program (the players' names) only when the game is waiting for one:
        // a read, or a KeyPressed loop polling again without anything else in between
        const asked = blocking || (!quiet && prevIdle);
        if (this.local.length && R.keys.length < 15 && (asked || !this.local[0][2])) {
          const k = this.local.shift();
          this.idle = false;
          const entry = [p, k[0], k[1], owner, stateHash(R)];
          if (owner === this.s.me) {                         // own turn: at once, sent in the background
            this.s.keys.set(p, entry.slice(1)); this.s.H = p;
            this.s.outKeys.push(entry); this.s.flushSoon();
            R.queueKey(k[0], k[1]);
            if (!quiet) await R._yield();
            return;
          }
          const r = await this.s.sync({ keys: [entry] });    // for an absent player: only once accepted
          if (!r.ok) { this.local.unshift(k); await sleep(300); }
          continue;
        }
        if (!blocking) {
          if (owner === this.s.me) { this.s.H = p; this.s.outH = { h: p, has: owner }; if (!quiet) await R._yield(); return; }
          const r = await this.s.sync({ h: { h: p, has: owner } });
          if (!r.ok) await sleep(300);
          continue;
        }
        if (this.s.outKeys.length || this.s.outH) this.s.flushSoon();   // let the others catch up while we wait
      }
      if (this.onStatus) this.onStatus();
      await this.s.waitChange();
    }
  }
  // Far behind the log (joining late, coming back): run without waiting for Delay, without sound.
  _pace(R, p) {
    this.behind = this.s.H - p;
    if (this.behind > 60) R.setFastForward(true);
    else if (this.behind < 4) R.setFastForward(false);
  }
}

// Files of an online game: the host's saved games (sent at the start) and the game's own files,
// the same for every player. Games saved during play are also kept in this browser's storage.
export class OnlineFS {
  constructor(builtin, files, local) {
    this.files = new Map(Object.entries(builtin).map(([k, v]) => [k.toUpperCase(), v]));
    for (const [k, v] of Object.entries(files || {})) {
      const b = atob(v); const u = new Uint8Array(b.length);
      for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i);
      this.files.set(k.toUpperCase(), u);
    }
    this.local = local;
  }
  read(name) { return this.files.get(name.toUpperCase()) || null; }
  write(name, data) { this.files.set(name.toUpperCase(), data); if (this.local) this.local.write(name, data); }
}

// Saved games in this browser's storage (BrowserFS), for sending to the other players at the start.
export function localSaves(prefix = 'monopoly.fs.') {
  const files = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k.startsWith(prefix) && k.length - prefix.length <= 12) files[k.slice(prefix.length)] = localStorage.getItem(k);
    }
  } catch (e) { /* no storage */ }
  return files;
}
