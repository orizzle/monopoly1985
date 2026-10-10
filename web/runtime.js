// Monopoly (1985) web port — machine + Turbo Pascal 3 runtime emulation.
//
// The program modules produced by tools/pas2js.py call into this runtime (see CONTRACT.md).
// Layers:
//   * PC hardware/BIOS: CGA video memory (16 KB at B800) with BIOS INT 10h semantics,
//     keyboard buffer (INT 16h), PC speaker (PIT channel 2), DOS clock, a small DOS file system.
//   * Turbo Pascal 3.0 (1985) runtime behaviour: CRT window/attributes, console output with
//     Ctrl-S/Ctrl-C checking, Kbd/KeyPressed, the console line editor used by Read/ReadLn,
//     Write formatting, Delay, Sound/NoSound, Random, typed files and I/O error codes.
//   * The GRAPH.P extended graphics calls used by the game: GraphColorMode, Palette, GetPic, PutPic.
// Everything here is an independent implementation written from observed behaviour.

import { BUILTIN_FONT } from './font.js';

export class HaltSignal extends Error {
  constructor(code = 0) { super('Halt'); this.code = code; }
}
export class ChainSignal extends Error {
  constructor(name) { super('Chain ' + name); this.name = name; this.file = name; }
}
export class RuntimeErrorSignal extends Error {
  constructor(text) { super(text); this.text = text; }
}

export const CGA_RGB = [
  0x000000, 0x0000AA, 0x00AA00, 0x00AAAA, 0xAA0000, 0xAA00AA, 0xAA5500, 0xAAAAAA,
  0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555, 0xFF55FF, 0xFFFF55, 0xFFFFFF,
];

const DS = 0x00000, CS = 0x10000, SS = 0x20000;
const PIT_HZ = 1193181;           // speaker frequency = PIT_HZ / divisor
const SOUND_CONST = 0x1234DD;     // runtime divides this by the requested frequency
const LAG_MS = 20;                // the virtual clock may lag real time by this much (late timers)
const CPU_KHZ = 14318.18 / 3;     // 8088 clock of the IBM PC: 4.77 MHz = 4772.7 clocks per ms
// 8x16 font from an 8x8 one (each row doubled): the fallback VGA text font when no 8x16 font is given
function font16From8(f8) {
  const f = new Uint8Array(4096);
  for (let c = 0; c < 256; c++) for (let y = 0; y < 16; y++) f[c * 16 + y] = f8[c * 8 + (y >> 1)];
  return f;
}
const ATTR_COLOR = [0x0E, 0x07, 0x07, 0x4F];   // installed attribute table, colour modes
const ATTR_BW = [0x0F, 0x07, 0x07, 0x70];      // b/w and monochrome modes
const INSTALL_MODE = 3;                         // monopoly.com is installed for "Color display 80x25"

const hex2 = (v) => (v & 0xFF).toString(16).toUpperCase().padStart(2, '0');
const hex4 = (v) => (v & 0xFFFF).toString(16).toUpperCase().padStart(4, '0');

export class Runtime {
  constructor(opts = {}) {
    this.headless = !!opts.headless;
    this.mem = new Uint8Array(3 * 65536);
    this.sp = SS + 0x10000;
    // --- video / BIOS ---
    this.vram = new Uint8Array(0x4000);
    this.bios = { mode: 3, cols: 80, row: 0, col: 0, colorSel: 0x30 };
    this._clearText();
    // --- TP3 CRT state ---
    this.crt = { x1: 0, y1: 0, xmax: 80, ymax: 25, mode: 3, flag: 0xFF, attr: 0x0E, tab: ATTR_COLOR.slice() };
    // --- GRAPH.P state ---
    this.gfx = { x1: 0, y1: 0, x2: 319, y2: 199, sel: 0, ctab: new Uint8Array(256).map((_, i) => i) };
    // --- keyboard ---
    this.keys = [];            // BIOS buffer of [ascii, scan]
    this.pendingScan = 0;      // runtime: scan code of an extended key, delivered after #27
    this.cflag = 1;            // runtime: Ctrl-C / Ctrl-S checking during console I/O ({$C+})
    this.pausePending = false;
    this.keyWaiters = [];
    // Online play: when set, keys reach the program only through keyGate.poll() at its keyboard polls
    // (KeyPressed, Read(Kbd)/ReadLn waits), so every player's copy receives them at the same point.
    this.keyGate = null;
    this.ff = false;           // fast-forward (online catch-up): Delay and CPU time are not waited for, no sound
    // --- console line input (runtime line editor + Input buffer) ---
    this.bufLen = 126;
    this.lineBuf = new Uint8Array(128);   // persists between lines (Ctrl-D / Ctrl-R recall)
    this.inPos = 0; this.inEnd = 0; this.inPending = false; this.inChar = 0;
    // --- I/O, files ---
    this.ioErr = 0;
    this.files = new Map();    // file variable address -> state
    this.vfs = opts.vfs || new MemoryFS();
    // --- random, time, sound ---
    this.seed = 0;             // RandSeed: zero in memory when the program is started
    this.vnow = 0;             // virtual time (ms) advanced by Delay
    this.speakerOn = false; this.divisor = 0;
    this.audio = opts.audio || null;
    // --- font / rendering ---
    this.font = opts.font || BUILTIN_FONT;
    // VGA display (default in the browser): text modes use an 8x16 font in 9x16 cells (720x400)
    this.display = opts.display === 'cga' ? 'cga' : 'vga';
    // speed of the CPU-timed sound loops: 'dosbox' (DOSBox's default speed, like a fast PC) or 'pc'
    // (the 4.77 MHz IBM PC the game was written for)
    this.speed = opts.speed === 'pc' ? 'pc' : 'dosbox';
    this._font16Derived = !(opts.font16 && opts.font16.length === 4096);
    this.font16 = this._font16Derived ? font16From8(this.font) : opts.font16;
    this.canvas = opts.canvas || null;
    if (this.canvas) this._initCanvas();
    this.onHalt = null;
  }

  // ======================================================================= memory
  rb(a) { return this.mem[a]; }
  wb(a, v) { this.mem[a] = v & 255; }
  rw(a) { return ((this.mem[a] | (this.mem[a + 1] << 8)) << 16) >> 16; }
  ww(a, v) { this.mem[a] = v & 255; this.mem[a + 1] = (v >> 8) & 255; }
  rs(a) {
    const n = this.mem[a]; let s = '';
    for (let i = 1; i <= n; i++) s += String.fromCharCode(this.mem[a + i]);
    return s;
  }
  ws(a, s, max) {
    const n = Math.min(s.length, max);
    this.mem[a] = n;
    for (let i = 0; i < n; i++) this.mem[a + 1 + i] = s.charCodeAt(i) & 255;
  }
  // Turbo Pascal 6-byte real: byte 0 exponent (bias 129, 0 = zero), bytes 1..5 mantissa, sign in bit 7 of byte 5.
  rr(a) {
    const m = this.mem; const e = m[a];
    if (e === 0) return 0;
    const sign = m[a + 5] & 0x80 ? -1 : 1;
    let f = ((m[a + 5] & 0x7F) * 2 ** 32 + m[a + 4] * 2 ** 24 + m[a + 3] * 2 ** 16 + m[a + 2] * 2 ** 8 + m[a + 1]) / 2 ** 39;
    return sign * (1 + f) * 2 ** (e - 129);
  }
  wr(a, x) {
    const m = this.mem;
    if (x === 0 || !isFinite(x)) { for (let i = 0; i < 6; i++) m[a + i] = 0; return; }
    const sign = x < 0 ? 0x80 : 0; x = Math.abs(x);
    let e = Math.floor(Math.log2(x)); let f = x / 2 ** e;
    if (f >= 2) { f /= 2; e++; } if (f < 1) { f *= 2; e--; }
    let mant = Math.round((f - 1) * 2 ** 39);
    if (mant >= 2 ** 39) { mant = 0; e++; }
    if (e + 129 <= 0) { for (let i = 0; i < 6; i++) m[a + i] = 0; return; }
    m[a] = e + 129;
    for (let i = 1; i <= 4; i++) { m[a + i] = mant % 256; mant = Math.floor(mant / 256); }
    m[a + 5] = (mant & 0x7F) | sign;
  }
  // TP3 Move: overlap-safe, direction chosen by comparing the 16-bit offsets.
  move(dst, src, n) {
    n &= 0xFFFF; if (!n) return;
    if ((src & 0xFFFF) < (dst & 0xFFFF)) for (let i = n - 1; i >= 0; i--) this.mem[dst + i] = this.mem[src + i];
    else for (let i = 0; i < n; i++) this.mem[dst + i] = this.mem[src + i];
  }
  fill(a, n, v) { for (let i = 0; i < (n & 0xFFFF); i++) this.mem[a + i] = v & 255; }
  enter(n) { this.sp -= n; return this.sp; }
  leave(n) { this.sp += n; }

  // ======================================================================= program start (RT_Init)
  // Called by the shell before each program's main (initial start and after Chain).
  programStart() {
    this.cflag = 1; this.pendingScan = 0; this.pausePending = false;
    this.ioErr = 0; this.bufLen = 126;
    this.inPos = this.inEnd = 0; this.inPending = false;
    this.files.clear();
    this.noSound();
    this.textMode(INSTALL_MODE);     // CrtInit
  }

  // ======================================================================= BIOS video
  _clearText() { for (let i = 0; i < 0x4000; i += 2) { this.vram[i] = 0x20; this.vram[i + 1] = 0x07; } }
  biosSetMode(m) {
    m &= 0x7F;
    const b = this.bios;
    b.mode = m; b.cols = (m <= 1 || m === 4 || m === 5) ? 40 : 80;
    if (m >= 4) this.vram.fill(0); else this._clearText();
    b.row = 0; b.col = 0;
    b.colorSel = m === 6 ? 0x3F : 0x30;
  }
  biosSetCursor(row, col) { this.bios.row = row & 255; this.bios.col = col & 255; }
  _isGfx() { return this.bios.mode >= 4 && this.bios.mode !== 7; }
  // AH=06/07: scroll window up/down (rows/cols clamped to the screen like the reference BIOS)
  biosScroll(up, n, attr, r1, c1, r2, c2) {
    const b = this.bios, rows = 25, cols = b.cols;
    if (r2 >= rows) r2 = rows - 1;
    if (c2 >= cols) c2 = cols - 1;
    if (r1 > r2 || c1 > c2) return;
    const h = r2 - r1 + 1;
    if (n === 0 || n > h) n = h;
    const copyRow = (dst, src) => this._copyRow(dst, src, c1, c2);
    const fillRow = (r) => this._fillRow(r, c1, c2, attr);
    if (up) {
      for (let r = r1; r + n <= r2; r++) copyRow(r, r + n);
      for (let r = r2 - n + 1; r <= r2; r++) fillRow(r);
    } else {
      for (let r = r2; r - n >= r1; r--) copyRow(r, r - n);
      for (let r = r1; r < r1 + n; r++) fillRow(r);
    }
  }
  _copyRow(dst, src, c1, c2) {
    const v = this.vram;
    if (!this._isGfx()) {
      for (let c = c1; c <= c2; c++) {
        const d = (dst * 80 + c) * 2, s = (src * 80 + c) * 2;
        v[d] = v[s]; v[d + 1] = v[s + 1];
      }
    } else {
      const bytes = (c2 - c1 + 1) * 2;
      for (let i = 0; i < 4; i++) {
        const d = dst * 320 + i * 80 + c1 * 2, s = src * 320 + i * 80 + c1 * 2;
        for (let x = 0; x < bytes; x++) {
          v[(d + x) & 0x3FFF] = v[(s + x) & 0x3FFF];
          v[(d + x + 0x2000) & 0x3FFF] = v[(s + x + 0x2000) & 0x3FFF];
        }
      }
    }
  }
  _fillRow(r, c1, c2, attr) {
    const v = this.vram;
    if (!this._isGfx()) {
      for (let c = c1; c <= c2; c++) { const d = (r * 80 + c) * 2; v[d] = 0x20; v[d + 1] = attr; }
    } else {
      const bytes = (c2 - c1 + 1) * 2, fillb = (attr & 3) * 0x55;   // colour replicated to 4 pixels
      for (let i = 0; i < 4; i++) {
        const d = r * 320 + i * 80 + c1 * 2;
        for (let x = 0; x < bytes; x++) { v[(d + x) & 0x3FFF] = fillb; v[(d + x + 0x2000) & 0x3FFF] = fillb; }
      }
    }
  }
  // AH=09: write character and attribute at the cursor (cursor not moved)
  biosWriteCharAttr(ch, attr, count = 1) {
    const b = this.bios;
    if (!this._isGfx()) {
      let p = (b.row * 80 + b.col) * 2;
      for (let k = 0; k < count; k++) { this.vram[p & 0x3FFF] = ch; this.vram[(p + 1) & 0x3FFF] = attr; p += 2; }
    } else {
      for (let k = 0; k < count; k++) this._drawGlyph(b.col + k, b.row, ch, attr);
    }
  }
  _drawGlyph(col, row, ch, attr) {
    const color = attr & 3, xor = attr & 0x80;
    for (let y = 0; y < 8; y++) {
      const bits = this.font[ch * 8 + y];
      const py = row * 8 + y;
      for (let x = 0; x < 8; x++) {
        const on = (bits >> (7 - x)) & 1;
        const px = col * 8 + x;
        if (xor) { if (on) this.setPixel(px, py, this.getPixel(px, py) ^ color); }
        else this.setPixel(px, py, on ? color : 0);
      }
    }
  }
  // CGA mode 4 pixel access with plain address arithmetic (x beyond 319 runs into the next bytes)
  _pixAddr(x, y) { return ((y & 1) * 0x2000 + (y >> 1) * 80 + (x >> 2)) & 0x3FFF; }
  getPixel(x, y) { return (this.vram[this._pixAddr(x, y)] >> (6 - 2 * (x & 3))) & 3; }
  setPixel(x, y, c) {
    const a = this._pixAddr(x, y), sh = 6 - 2 * (x & 3);
    this.vram[a] = (this.vram[a] & ~(3 << sh)) | ((c & 3) << sh);
  }
  // AH=0E: teletype output (only BEL reaches it from the runtime)
  biosTeletype(ch) {
    if (ch === 7) { this._beep(); return; }
    const b = this.bios;
    if (ch === 13) b.col = 0;
    else if (ch === 10) b.row++;
    else if (ch === 8) { if (b.col > 0) b.col--; }
    else {
      if (!this._isGfx()) this.vram[((b.row * 80 + b.col) * 2) & 0x3FFF] = ch;
      else this._drawGlyph(b.col, b.row, ch, 3);
      if (++b.col >= b.cols) { b.col = 0; b.row++; }
    }
    if (b.row >= 25) {
      b.row = 24;
      const attr = this._isGfx() ? 0 : this.vram[((24 * 80 + b.col) * 2 + 1) & 0x3FFF];
      this.biosScroll(true, 1, attr, 0, 0, 24, b.cols - 1);
    }
  }
  // AH=0B: colour select register (BH=0 background/intensity, BH=1 palette)
  biosPalette(bh, bl) {
    const b = this.bios;
    if (bh === 0) b.colorSel = (b.colorSel & 0x20) | (bl & 0x1F);
    else b.colorSel = (b.colorSel & 0xDF) | ((bl & 1) << 5);
  }
  _beep() { // BIOS bell: ~896 Hz for about half a second
    const was = this.speakerOn, div = this.divisor;
    this._speaker(true, 0x533);
    setTimeout(() => { if (was) this._speaker(true, div); else this._speaker(false); }, 500);
  }

  // ======================================================================= TP3 CRT
  textMode(m) {
    m &= 255;
    const c = this.crt;
    c.x1 = 0; c.y1 = 0; c.flag2 = 0xFF;
    let tab = ATTR_COLOR, cols = 80, flag = 0;
    if (m === 7) { tab = ATTR_BW; cols = 80; flag = 0; }
    else if (m === 2) { tab = ATTR_BW; cols = 80; flag = 0; }
    else {
      if (m >= 4) m = 3;
      flag = 0xFF;
      if (m === 3) cols = 80;
      else { cols = 40; if (m !== 1) { m = 0; flag = 0; tab = ATTR_BW; } }
    }
    c.mode = m; c.flag = flag; c.xmax = cols;          // note: the bottom limit (ymax) is kept
    c.tab = tab.slice();
    if (this.bios.mode !== c.mode) this.biosSetMode(c.mode);
    c.attr = c.tab[0];                                  // HighVideo
  }
  window(x1, y1, x2, y2) {
    const c = this.crt; x1 &= 255; y1 &= 255; x2 &= 255; y2 &= 255;
    if (y2 <= 25) c.ymax = y2;
    if (x2 <= 80) c.xmax = x2;
    if (y1 < c.ymax) c.y1 = (y1 - 1) & 255;
    if (x1 < c.xmax) c.x1 = (x1 - 1) & 255;
  }
  clrScr() {
    const c = this.crt;
    if (this.bios.mode !== c.mode) { this.textMode(c.mode); return; }
    this.biosScroll(true, 0, c.attr, c.y1, c.x1, (c.ymax - 1) & 255, (c.xmax - 1) & 255);
    this.biosSetCursor(c.y1, c.x1);
  }
  clrEol() {
    const c = this.crt, b = this.bios;
    this.biosScroll(true, 0, c.attr, b.row, b.col, b.row, (c.xmax - 1) & 255);
  }
  insLine() { this._scrollLine(false); }
  delLine() { this._scrollLine(true); }
  _scrollLine(up) {
    const c = this.crt, b = this.bios;
    const r2 = (c.ymax - 1) & 255;
    this.biosScroll(up, b.row === r2 ? 0 : 1, c.attr, b.row, c.x1, r2, (c.xmax - 1) & 255);
  }
  gotoXY(x, y) {
    const c = this.crt;
    let d = ((((y & 255) - 1) & 255) << 8) | (((x & 255) - 1) & 255);
    d = (d + ((c.y1 << 8) | c.x1)) & 0xFFFF;
    const row = d >> 8, col = d & 255;
    if (row < c.ymax && col < c.xmax) this.biosSetCursor(row, col);
  }
  whereX() { return (this.bios.col - this.crt.x1 + 1) & 255; }
  whereY() { return (this.bios.row - this.crt.y1 + 1) & 255; }
  textColor(v) {
    let al = v & 0x1F;
    if (al & 0x10) al = (al & 0x0F) | 0x80;
    this.crt.attr = (this.crt.attr & 0x70) | al;
  }
  textBackground(v) { this.crt.attr = (this.crt.attr & 0x8F) | ((v & 7) << 4); }
  lowVideo() { this.crt.attr = this.crt.tab[1]; }
  highVideo() { this.crt.attr = this.crt.tab[0]; }
  normVideo() { this.highVideo(); }

  // console output of one character (window, attribute, wrap, scroll), then Ctrl-S/Ctrl-C check
  conOut(ch, check = true) {
    ch &= 255;
    const c = this.crt, b = this.bios;
    let row = b.row, col = b.col;
    if (ch === 13) col = c.x1;
    else if (ch === 10) {
      row = (row + 1) & 255;
      if (row >= c.ymax) { row = (row - 1) & 255; this._conScroll(); }
    } else if (ch === 8) {
      if (col !== c.x1) col = (col - 1) & 255;
    } else if (ch === 7) {
      this.biosTeletype(7);
      if (check) this._ctrlCheck();
      return;
    } else {
      this.biosWriteCharAttr(ch, c.attr, 1);
      col = (col + 1) & 255;
      if (col >= c.xmax) {
        col = c.x1; row = (row + 1) & 255;
        if (row >= c.ymax) { row = (row - 1) & 255; this._conScroll(); }
      }
    }
    this.biosSetCursor(row, col);
    if (check) this._ctrlCheck();
  }
  _conScroll() {
    const c = this.crt;
    this.biosScroll(true, 1, c.attr, c.y1, c.x1, (c.ymax - 1) & 255, (c.xmax - 1) & 255);
  }
  // after each console character: a pending key is read and discarded, ^S pauses, ^C aborts
  _ctrlCheck() {
    if (this.cflag !== 1) return;
    if (!this._kbHit()) return;
    const k = this._conInSync();
    if (k === 0x13) {
      if (this.pendingScan !== 0 || this.keys.length) this._conInSync();   // next key already there
      else this.pausePending = true;                                      // wait at the next await
    }
  }
  conOutStr(s, check = true) { for (let i = 0; i < s.length; i++) this.conOut(s.charCodeAt(i), check); }

  // ======================================================================= Write formatting
  _pad(s, w) { w = (w << 16) >> 16; return w > s.length ? ' '.repeat(w - s.length) + s : s; }
  wrStr(s, w = 0) { this.conOutStr(this._pad(s, w)); }
  wrChar(code, w = 0) { this.conOutStr(this._pad(String.fromCharCode(code & 255), w)); }
  wrInt(v, w = 0) { this.conOutStr(this._pad(String((v << 16) >> 16), w)); }
  wrBool(b, w = 0) { this.conOutStr(this._pad(b ? 'TRUE' : 'FALSE', w)); }
  wrReal(x, w = -1, d = -1) { this.conOutStr(this.realStr ? this.realStr(x, w, d) : this._realStr(x, w, d)); }
  wrLn() { this.conOut(13); this.conOut(10); }
  // TP3-style real formatting (default ' d.ddddddddddE+xx'); web/tp3real.js may replace realStr.
  _realStr(x, w, d) {
    if (d >= 0 && w >= 0) return this._pad(x.toFixed(Math.min(d, 24)), w);
    let digits = 10;
    if (w >= 0) digits = Math.max(1, Math.min(10, w - 7));
    let s = Math.abs(x).toExponential(digits).toUpperCase();
    s = s.replace(/E([+-])(\d)$/, 'E$10$2');
    s = (x < 0 ? '-' : ' ') + s;
    return w >= 0 ? this._pad(s, w) : s;
  }

  // ======================================================================= keyboard
  // BIOS keyboard buffer. Each entry may become visible only after a number of peeks
  // (INT 16h AH=1) — used by deterministic tests; browser keys are visible at once.
  pushKey(ascii, scan) { return this.queueKey(ascii, scan, 0); }
  queueKey(ascii, scan, afterPeeks = 0) {
    if (afterPeeks === 0 && this.keys.length >= 15) return false;     // BIOS buffer full
    this.keys.push({ a: ascii & 255, s: scan & 255, after: afterPeeks | 0 });
    const w = this.keyWaiters; this.keyWaiters = [];
    for (const f of w) f();
    return true;
  }
  biosPeek() {
    this.peeks = (this.peeks || 0) + 1;
    if (!this.keys.length) return false;
    const k = this.keys[0];
    if (k.after > 0) { k.after--; return false; }
    return true;
  }
  biosRead() { const k = this.keys.shift(); return [k.a, k.s]; }   // caller ensures a key exists
  _kbHit() { return this.pendingScan !== 0 || this.biosPeek(); }
  _waitKey() {
    if (this.pendingScan !== 0 || this.keys.length) return Promise.resolve();
    return new Promise((r) => this.keyWaiters.push(r));
  }
  // runtime console input: extended keys -> #27 now, scan code next time
  _conInSync() {
    let al;
    if (this.pendingScan) { al = this.pendingScan; this.pendingScan = 0; }
    else {
      const [a, s] = this.biosRead();
      al = a;
      if (a === 0) { this.pendingScan = s; al = s ? 0x1B : 3; if (!s) this.pendingScan = 0; }
    }
    if (this.cflag === 1 && al === 3) this.userBreak();
    return al;
  }
  async _conIn() {
    await this._handlePause();
    await this._waitKeyGated();
    return this._conInSync();
  }
  async _waitKeyGated() {
    if (!this.keyGate) { await this._waitKey(); return; }
    while (this.pendingScan === 0 && !this.keys.length) await this.keyGate.poll(this, true);
  }
  async _handlePause() {
    if (!this.pausePending) return;
    this.pausePending = false;
    await this._waitKeyGated();
    this._conInSync();
  }
  async _yield() {
    await new Promise((r) => (typeof setImmediate === 'function' && this.headless) ? setImmediate(r) : setTimeout(r, 0));
  }
  async readKbd() { return this._conIn(); }
  async keyPressed() {
    await this._handlePause();
    if (this.keyGate) await this.keyGate.poll(this, false); else await this._yield();
    return this._kbHit();
  }

  // ======================================================================= console line input
  // runtime line editor; dh=false: Enter terminates with ^Z (Read/ReadLn begin),
  // dh=true: Enter echoes CR LF and stores CR LF (refill while reading Input).
  async _lineEdit(dh) {
    let max = this.bufLen; if (max > 126) max = 126;
    this.bufLen = 126;
    const buf = this.lineBuf;
    let bx = 0, cl = 0;
    this.inPos = 0;
    const echo = (ch) => { const f = this.cflag; this.cflag = 0; this.conOut(ch); this.cflag = f; };
    for (;;) {
      const k = await this._conIn();
      let dl = 1, kind = null;
      if (k === 8 || k === 0x7F) kind = 'del';
      else if (k === 4) kind = 'rec';
      else {
        dl = 0;
        if (k === 0x18 || k === 0x1B) kind = 'del';
        else if (k === 0x12) kind = 'rec';
        else if (k === 0x1A) { if (!dh) continue; buf[bx] = 0x1A; bx++; break; }
        else if (k === 0x0D) {
          if (!dh) { buf[bx] = 0x1A; bx++; break; }
          this.conOut(13); this.conOut(10);
          buf[bx] = 0x0D; buf[bx + 1] = 0x0A; bx += 2; break;
        } else if (k < 0x20) continue;
        else if (cl === max) continue;
        else {
          const ah = buf[bx]; buf[bx] = k; cl++; bx++;
          if (ah < 0x20) buf[bx] = ah;
          echo(k);
          continue;
        }
      }
      if (kind === 'del') {
        for (;;) {
          cl--;
          if (cl < 0) { cl = 0; break; }
          this.conOut(8); this.conOut(0x20); this.conOut(8);
          bx--; dl = (dl - 1) & 255;
          if (dl === 0) break;
        }
      } else {
        for (;;) {
          const al = buf[bx];
          if (al < 0x20) break;
          echo(al); cl++; bx++;
          dl = (dl - 1) & 255;
          if (dl === 0) break;
        }
      }
    }
    this.inEnd = bx;
  }
  async _inGet() {
    if (this.ioErr) return 0x1A;
    if (this.inPending) return this.inChar;
    if (this.inPos >= this.inEnd) await this._lineEdit(true);
    this.inChar = this.lineBuf[this.inPos++];
    this.inPending = true;
    return this.inChar;
  }
  async rdBegin() { this.inPending = false; await this._lineEdit(false); }
  async rdBeginLn() { await this.rdBegin(); this.conOut(13); this.conOut(10); }
  async rdStr(max) {
    let s = '';
    for (let n = max & 255; n > 0; n--) {
      const c = await this._inGet();
      if (c === 0x0D || c === 0x1A) break;
      this.inPending = false;
      s += String.fromCharCode(c);
    }
    return s;
  }
  async rdLn() {
    for (;;) {
      const c = await this._inGet();
      if (c === 0x1A) return;
      this.inPending = false;
      if (c === 0x0A) return;
      if (c === 0x0D) break;
    }
    const c = await this._inGet();
    if (c === 0x0A) this.inPending = false;
  }

  // ======================================================================= time, sound, random
  _now() { return (typeof performance !== 'undefined' ? performance : Date).now(); }
  async delay(ms) {
    ms &= 0xFFFF;
    await this._handlePause();
    if (this.headless) { this.vnow += ms; await this._yield(); return; }
    if (this.ff) { this.vnow += ms; await this._ffYield(); if (this.keyGate) await this.keyGate.poll(this, false, true); return; }
    const now = this._now();
    if (this.vnow < now - 50 || this.vnow > now + 60000) this.vnow = now;
    this.vnow += ms;
    // Browser timers fire no sooner than ~4 ms, so short delays (e.g. 301 x Delay(2) in the pass-GO
    // sweep) must not sleep one by one: run ahead and sleep only once the virtual clock leads real
    // time by a few ms. Speaker changes are scheduled on the audio clock at their virtual times, so
    // the sound stays exact.
    const wait = this.vnow - this._now();
    if (wait >= 8) { await new Promise((r) => setTimeout(r, wait)); this.lastYield = this._now(); }
    else if (this._now() - (this.lastYield || 0) > 16) { await this._yield(); this.lastYield = this._now(); }
    // keys typed during a Delay reach the BIOS buffer here, as they do in a single-player game
    if (this.keyGate) await this.keyGate.poll(this, false, true);
  }
  // fast-forward: yield to the browser only every few ms of real time
  async _ffYield() {
    const now = this._now();
    if (now - (this.lastYield || 0) > 25) { await new Promise((r) => setTimeout(r, 0)); this.lastYield = this._now(); }
  }
  setFastForward(on) {
    on = !!on; if (on === this.ff) return;
    this.ff = on;
    if (!on) this.vnow = this._now();
    if (this.audio) this.audio.set(on ? false : this.speakerOn, PIT_HZ / (this.divisor || 65536));
  }
  sound(hz) {
    hz &= 0xFFFF;
    if (hz <= 0x12) return;
    this._speaker(true, Math.floor(SOUND_CONST / hz) & 0xFFFF);
  }
  noSound() { this._speaker(false); }
  _speaker(on, div) {
    this.speakerOn = on; if (on) this.divisor = div;
    const now = this._now();
    if (this.audio && !this.ff) this.audio.set(on, on ? PIT_HZ / (div || 65536) : 0, this.vnow < now - LAG_MS ? now : this.vnow);
  }
  // CPU time of the original program on a 4.77 MHz IBM PC (8088), measured for the loops whose
  // sound depends on CPU speed (see tools/measure_sound_loops.py): advances the virtual clock
  // without blocking; speaker changes are scheduled on that clock
  cpu(clocks, fast) {
    if (fast !== undefined && this.speed !== 'pc') clocks = fast;
    if (this.headless || this.ff) { this.vnow += clocks / CPU_KHZ; return; }
    const now = this._now();
    // a timer that woke a few ms late (catchUp) does not add to the sound's length; the speaker
    // schedules 30 ms ahead, so the virtual clock may lag real time by less than that
    if (this.vnow < now - LAG_MS) this.vnow = now;
    this.vnow += clocks / CPU_KHZ;
  }
  // let real time catch up with the virtual clock (end of a CPU-timed loop)
  async catchUp() {
    if (this.headless) return;
    if (!this.ff) {
      const wait = this.vnow - this._now();
      if (wait > 1) await new Promise((r) => setTimeout(r, wait));
    } else await this._ffYield();
    if (this.keyGate) await this.keyGate.poll(this, false, true);
  }
  random(n) {
    this.seed = (this.seed * 129 + 0x361962E9) % 4294967296;
    n &= 0xFFFF;
    if (n === 0) return 0;
    return ((this.seed >>> 16) >>> 1) % n;
  }
  randomize() {
    const d = new Date();
    const cx = (d.getHours() << 8) | d.getMinutes();
    const dx = (d.getSeconds() << 8) | Math.floor(d.getMilliseconds() / 10);
    this.seed = ((cx << 16) | dx) >>> 0;
  }

  // ======================================================================= files
  _fs(fa) {
    let f = this.files.get(fa);
    if (!f) { f = { name: '', recSize: 0, pos: 0, data: null }; this.files.set(fa, f); }
    return f;
  }
  // DOS-style name: drive/path dropped, upper case, name truncated to 8 and extension to 3 characters.
  static dosName(name) {
    let s = name.replace(/^\s+|\s+$/g, '').toUpperCase();
    s = s.replace(/^[A-Z]:/, '').replace(/^.*\\/, '');
    const dot = s.indexOf('.');
    const base = (dot < 0 ? s : s.slice(0, dot)).slice(0, 8);
    const ext = dot < 0 ? '' : s.slice(dot + 1).slice(0, 3);
    return ext ? base + '.' + ext : base;
  }
  assign(fa, name) { const f = this._fs(fa); f.name = name; }
  _closeHandle(f) {
    if (f.data && f.dirty) this.vfs.write(Runtime.dosName(f.name), f.data.slice(0, f.size));
    f.data = null; f.dirty = false;
  }
  reset(fa, recSize) { this._open(fa, recSize, false); }
  rewrite(fa, recSize) { this._open(fa, recSize, true); }
  _open(fa, recSize, create) {
    const f = this._fs(fa);
    f.recSize = 0; this._closeHandle(f);
    if (this.ioErr) return;
    const nm = Runtime.dosName(f.name);
    const valid = /^[A-Z0-9_$&#@!%'`(){}~^-]{1,8}(\.[A-Z0-9_$&#@!%'`(){}~^-]{0,3})?$/.test(nm);
    if (create) {
      if (!valid) { this.ioErr = 0xF1; return; }
      f.data = new Uint8Array(256); f.size = 0; f.dirty = true;
      this.vfs.write(nm, new Uint8Array(0));
    } else {
      const d = valid ? this.vfs.read(nm) : null;
      if (!d) { this.ioErr = 1; return; }
      f.data = new Uint8Array(Math.max(256, d.length)); f.data.set(d); f.size = d.length; f.dirty = false;
    }
    f.pos = 0; f.recSize = recSize & 0xFFFF;
  }
  _typedBegin(fa) {
    const f = this._fs(fa);
    if (f.recSize === 0) this.ioErr = 4;
    return f;
  }
  readRec(fa, addr) {
    const f = this._typedBegin(fa);
    if (this.ioErr) return;
    const n = Math.min(f.recSize, Math.max(0, f.size - f.pos));
    if (n === 0) { this.ioErr = 0x99; return; }
    for (let i = 0; i < n; i++) this.mem[addr + i] = f.data[f.pos + i];
    for (let i = n; i < f.recSize; i++) this.mem[addr + i] = 0;
    f.pos += n;
  }
  writeRec(fa, addr) {
    const f = this._typedBegin(fa);
    if (this.ioErr) return;
    const need = f.pos + f.recSize;
    if (need > f.data.length) { const d = new Uint8Array(Math.max(need, f.data.length * 2)); d.set(f.data); f.data = d; }
    for (let i = 0; i < f.recSize; i++) f.data[f.pos + i] = this.mem[addr + i];
    f.pos = need; if (need > f.size) f.size = need; f.dirty = true;
  }
  close(fa) { const f = this._fs(fa); f.recSize = 0; this._closeHandle(f); }
  chain(fa) {
    const f = this._fs(fa);
    if (this.ioErr) return;
    const nm = Runtime.dosName(f.name);
    if (!this.vfs.read(nm)) { this.ioErr = 1; return; }
    this.noSound();
    throw new ChainSignal(nm);
  }
  ioResult() { const r = this.ioErr; this.ioErr = 0; return r; }
  ioCheck(pc = 0) { if (this.ioErr) this.runError(1, this.ioErr, pc); }

  // ======================================================================= errors, halt
  _resetConsole() {
    this.cflag = 0; this.pendingScan = 0; this.ioErr = 0;
    this.inPos = this.inEnd = 0; this.bufLen = 126;
  }
  // kind 0 = user break, 1 = I/O error, 2 = run-time error
  runError(kind, code, pc = 0) {
    this._resetConsole();
    let s;
    if (kind === 0) s = '^C\r\nUser Break';
    else s = (kind === 1 ? '\r\nI/O' : '\r\nRun-time') + ' error ' + hex2(code);
    s += ', PC=' + hex4(pc) + '\r\nProgram aborted\r\n';
    this.conOutStr(s, false);
    throw new RuntimeErrorSignal(s);
  }
  userBreak(pc = 0) { this.runError(0, 0, pc); }
  // Called by the shell for errors thrown by compiled code (pasrt.js RunError: kind, code, pc).
  reportError(e) {
    try { this.runError(e.kind, e.code, e.pc); } catch (sig) { return sig; }
    return null;
  }
  halt() { throw new HaltSignal(0); }

  // ======================================================================= GRAPH.P externals
  graphColorMode() {
    this.biosSetMode(4);
    this.biosPalette(1, 0);
    const g = this.gfx;
    g.x1 = 0; g.y1 = 0; g.x2 = 319; g.y2 = 199; g.sel = 0;
    this.biosPalette(0, g.sel);
    for (let i = 0; i < 256; i++) g.ctab[i] = i;
  }
  palette(n) {
    const g = this.gfx;
    let bl = n & 255;
    g.sel &= 0xEF;
    const ah = this.bios.mode === 4 ? 2 : 1;
    if (bl >= ah) { bl -= ah; g.sel |= 0x10; }
    this.biosPalette(1, bl);
    this.biosPalette(0, g.sel);
  }
  _bpp() { return this.bios.mode === 6 ? 1 : 2; }
  getPic(addr, x1, y1, x2, y2) {
    const g = this.gfx, bpp = this._bpp();
    x1 = Math.max(x1, g.x1); y1 = Math.max(y1, g.y1);
    x2 = Math.min(x2, g.x2); y2 = Math.min(y2, g.y2);
    this.ww(addr, 0);
    const w = x2 - x1 + 1, h = y2 - y1 + 1;
    if (w < 0 || h < 0) return;
    const ppb = 8 / bpp, rowBytes = Math.ceil(w * bpp / 8);
    this.ww(addr, bpp); this.ww(addr + 2, w); this.ww(addr + 4, h);
    let p = addr + 6;
    for (let k = 0; k < h; k++) {
      const y = y2 - k;
      for (let i = 0; i < rowBytes; i++) {
        let byte = 0;
        for (let j = 0; j < ppb; j++) byte = (byte << bpp) | this._getPx(x1 + i * ppb + j, y, bpp);
        this.mem[p++] = byte;
      }
    }
  }
  putPic(addr, x, y) {
    const g = this.gfx, bpp = this._bpp();
    if ((this.mem[addr] & 255) !== bpp) return;
    const w = this.rw(addr + 2), h = this.rw(addr + 4);
    if (w === 0) return;
    if (x > g.x2) return;
    if (x + w - 1 < g.x1) return;
    const ppb = 8 / bpp, rowBytes = Math.ceil(w * bpp / 8), mask = (1 << bpp) - 1;
    for (let k = 0; k < (h & 0xFFFF); k++) {
      const sy = y - k;
      if (sy > g.y2 || sy < g.y1) continue;
      const row = addr + 6 + k * rowBytes;
      for (let i = 0; i < w; i++) {
        const sx = x + i;
        if (sx < g.x1 || sx > g.x2) continue;
        const byte = g.ctab[this.mem[row + ((i / ppb) | 0)]];
        const v = (byte >> (8 - bpp * (1 + (i % ppb)))) & mask;
        this._setPx(sx, sy, v, bpp);
      }
    }
  }
  _getPx(x, y, bpp) {
    if (bpp === 2) return this.getPixel(x, y);
    const a = ((y & 1) * 0x2000 + (y >> 1) * 80 + (x >> 3)) & 0x3FFF;
    return (this.vram[a] >> (7 - (x & 7))) & 1;
  }
  _setPx(x, y, v, bpp) {
    if (bpp === 2) { this.setPixel(x, y, v); return; }
    const a = ((y & 1) * 0x2000 + (y >> 1) * 80 + (x >> 3)) & 0x3FFF, sh = 7 - (x & 7);
    this.vram[a] = (this.vram[a] & ~(1 << sh)) | ((v & 1) << sh);
  }

  // ======================================================================= rendering
  _initCanvas() {
    this.canvas.width = 640; this.canvas.height = 400;
    this.vgaImg = new ImageData(720, 400);
    this.vgaImg32 = new Uint32Array(this.vgaImg.data.buffer);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.off = document.createElement('canvas');
    this.off.width = 640; this.off.height = 200;
    this.offCtx = this.off.getContext('2d');
    this.img = this.offCtx.createImageData(640, 200);
    this.img32 = new Uint32Array(this.img.data.buffer);
    this.rgba = CGA_RGB.map((c) => (0xFF000000 | ((c & 0xFF) << 16) | (c & 0xFF00) | ((c >> 16) & 0xFF)) >>> 0);
    const frame = () => { if (this.detached) return; this.render(); requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
  }
  // Fill a 640x200 RGBA32 buffer from VRAM; returns it (used by the canvas and by tests).
  renderTo(out, t = this._now()) {
    const b = this.bios, v = this.vram;
    const frameNo = Math.floor(t / (1000 / 59.92));
    if (!this._isGfx()) {
      const cursorOn = (frameNo & 8) === 0, blinkOn = (frameNo & 16) === 0;
      const cols = b.cols, cw = 640 / cols;
      for (let row = 0; row < 25; row++) {
        for (let col = 0; col < cols; col++) {
          const p = (row * cols + col) * 2;
          const ch = v[p], at = v[p + 1];
          const fgc = this.rgba[at & 15], bgc = this.rgba[(at >> 4) & 7];
          const fg = (at & 0x80) && !blinkOn ? bgc : fgc;
          for (let y = 0; y < 8; y++) {
            let bits = this.font[ch * 8 + y];
            if (cursorOn && row === b.row && col === b.col && y >= 6) bits = 0xFF;
            const base = (row * 8 + y) * 640 + col * cw;
            for (let x = 0; x < 8; x++) {
              const c = (bits >> (7 - x)) & 1 ? (y >= 6 && cursorOn && row === b.row && col === b.col ? fgc : fg) : bgc;
              if (cw === 8) out[base + x] = c; else { out[base + 2 * x] = c; out[base + 2 * x + 1] = c; }
            }
          }
        }
      }
    } else {
      const sel = b.colorSel, inten = sel & 0x10 ? 8 : 0;
      const pal = sel & 0x20 ? [3, 5, 7] : [2, 4, 6];
      const colors = [this.rgba[sel & 15], this.rgba[pal[0] + inten], this.rgba[pal[1] + inten], this.rgba[pal[2] + inten]];
      if (b.mode === 6) { colors[0] = this.rgba[0]; colors[1] = this.rgba[sel & 15]; }
      for (let y = 0; y < 200; y++) {
        const ra = (y & 1) * 0x2000 + (y >> 1) * 80;
        for (let xb = 0; xb < 80; xb++) {
          const byte = v[ra + xb], o = y * 640 + xb * 8;
          if (b.mode === 6) {
            for (let k = 0; k < 8; k++) out[o + k] = colors[(byte >> (7 - k)) & 1];
          } else {
            for (let k = 0; k < 4; k++) { const c = colors[(byte >> (6 - 2 * k)) & 3]; out[o + 2 * k] = c; out[o + 2 * k + 1] = c; }
          }
        }
      }
    }
    return out;
  }
  // VGA text mode: 9x16 character cells, 720x400. Columns 9 of characters C0h..DFh repeat column 8
  // (line drawing); the cursor covers scan lines 13-14; 70 Hz frames for the blink timing.
  renderVGAText(out, t = this._now()) {
    const b = this.bios, v = this.vram, f = this.font16;
    const frameNo = Math.floor(t / (1000 / 70.086));
    const cursorOn = (frameNo & 8) === 0, blinkOn = (frameNo & 16) === 0;
    const cols = b.cols, dbl = cols === 40 ? 2 : 1;
    for (let row = 0; row < 25; row++) {
      for (let col = 0; col < cols; col++) {
        const p = (row * cols + col) * 2;
        const ch = v[p], at = v[p + 1];
        const fgc = this.rgba[at & 15], bgc = this.rgba[(at >> 4) & 7];
        const fg = (at & 0x80) && !blinkOn ? bgc : fgc;
        const isCur = cursorOn && row === b.row && col === b.col;
        const line = ch >= 0xC0 && ch <= 0xDF;
        for (let y = 0; y < 16; y++) {
          let bits = f[ch * 16 + y] << 1;
          if (line) bits |= bits >> 1 & 1;
          let color = fg;
          if (isCur && (y === 13 || y === 14)) { bits = 0x1FF; color = fgc; }
          const base = (row * 16 + y) * 720 + col * 9 * dbl;
          for (let x = 0; x < 9; x++) {
            const c = (bits >> (8 - x)) & 1 ? color : bgc;
            if (dbl === 1) out[base + x] = c; else { out[base + 2 * x] = c; out[base + 2 * x + 1] = c; }
          }
        }
      }
    }
    return out;
  }
  render() {
    if (this.display === 'vga' && !this._isGfx()) {
      if (this.canvas.width !== 720) this.canvas.width = 720;
      this.renderVGAText(this.vgaImg32);
      this.ctx.putImageData(this.vgaImg, 0, 0);
      return;
    }
    if (this.canvas.width !== 640) { this.canvas.width = 640; this.ctx.imageSmoothingEnabled = false; }
    this.renderTo(this.img32);
    this.offCtx.putImageData(this.img, 0, 0);
    this.ctx.drawImage(this.off, 0, 0, 640, 200, 0, 0, 640, 400);
  }
  setFont(bytes) {
    const derived = this.font16 === undefined || this._font16Derived;
    this.font = bytes && bytes.length === 2048 ? bytes : BUILTIN_FONT;
    if (derived) { this.font16 = font16From8(this.font); this._font16Derived = true; }
  }
  setFont16(bytes) {
    if (bytes && bytes.length === 4096) { this.font16 = bytes; this._font16Derived = false; }
    else { this.font16 = font16From8(this.font); this._font16Derived = true; }
  }
  setDisplay(d) { this.display = d === 'cga' ? 'cga' : 'vga'; }
  setSpeed(s) { this.speed = s === 'pc' ? 'pc' : 'dosbox'; }
  detach() { this.detached = true; }       // stop drawing to the canvas (another runtime takes it over)
}

// ========================================================================= file systems
export class MemoryFS {
  constructor(files = {}) { this.files = new Map(Object.entries(files).map(([k, v]) => [k.toUpperCase(), v])); }
  read(name) { return this.files.get(name.toUpperCase()) || null; }
  write(name, data) { this.files.set(name.toUpperCase(), data); }
}
// Built-in game files are read-only images; everything else is kept in localStorage.
export class BrowserFS {
  constructor(builtin = {}, prefix = 'monopoly.fs.') {
    this.builtin = new Map(Object.entries(builtin).map(([k, v]) => [k.toUpperCase(), v]));
    this.prefix = prefix;
  }
  read(name) {
    name = name.toUpperCase();
    let s = null;
    try { s = localStorage.getItem(this.prefix + name); } catch (e) { s = null; }
    if (s !== null) { const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
    return this.builtin.get(name) || null;
  }
  write(name, data) {
    name = name.toUpperCase();
    let s = ''; for (let i = 0; i < data.length; i++) s += String.fromCharCode(data[i]);
    try { localStorage.setItem(this.prefix + name, btoa(s)); } catch (e) { /* storage unavailable */ }
  }
}

// ========================================================================= PC speaker
export class Speaker {
  constructor() {
    this.ctx = null; this.osc = null; this.gain = null; this.on = false; this.freq = 0;
  }
  resume() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      this.ctx = new AC();
      this.osc = this.ctx.createOscillator(); this.osc.type = 'square';
      this.gain = this.ctx.createGain(); this.gain.gain.value = 0;
      this.osc.connect(this.gain).connect(this.ctx.destination);
      this.osc.start();
      // Firefox builds the oscillator's wave tables the first time each pitch range plays, and on a
      // slow machine that can drop out the sound (heard in the jail siren's fast low glides): sweep
      // the whole range once, silently, before the first sound
      const t0 = this.ctx.currentTime;
      this.osc.frequency.setValueAtTime(18, t0);
      this.osc.frequency.exponentialRampToValueAtTime(20000, t0 + 0.2);
      this.lastT = t0 + 0.2;
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    this.set(this.on, this.freq);
  }
  set(on, freq, atMs) {
    this.on = on; if (on) this.freq = freq;
    if (!this.ctx) return;
    // atMs: performance.now()-based time of the change (may lie in the future for CPU-timed loops).
    // Events are placed on the audio clock through a base point (audioBase <-> vBase), so their
    // relative timing is exact (the dice rattle is 1 ms blips 40 ms apart). If an event would be
    // late, or the two clocks drift apart, the whole timeline is re-based a little into the future
    // instead of clamping single events (which would squeeze them together).
    const nowMs = performance.now();
    if (atMs === undefined) atMs = nowMs;
    const ct = this.ctx.currentTime;
    let t = this.audioBase === undefined ? -1 : this.audioBase + (atMs - this.vBase) / 1000;
    const expectAhead = Math.max(0, (atMs - nowMs) / 1000);
    if (t < ct + 0.002 || Math.abs((t - ct) - expectAhead) > 0.25) {
      this.audioBase = ct + 0.03 + expectAhead; this.vBase = atMs;
      t = this.audioBase;
    }
    t = Math.max(t, this.lastT || 0);
    this.lastT = t;
    if (on) this.osc.frequency.setValueAtTime(freq, t);
    this.gain.gain.setValueAtTime(on ? 0.15 : 0, t);
  }
}

// ========================================================================= browser keyboard mapping
const SCAN = {
  Escape: 0x01, Digit1: 0x02, Digit2: 0x03, Digit3: 0x04, Digit4: 0x05, Digit5: 0x06, Digit6: 0x07,
  Digit7: 0x08, Digit8: 0x09, Digit9: 0x0A, Digit0: 0x0B, Minus: 0x0C, Equal: 0x0D, Backspace: 0x0E,
  Tab: 0x0F, KeyQ: 0x10, KeyW: 0x11, KeyE: 0x12, KeyR: 0x13, KeyT: 0x14, KeyY: 0x15, KeyU: 0x16,
  KeyI: 0x17, KeyO: 0x18, KeyP: 0x19, BracketLeft: 0x1A, BracketRight: 0x1B, Enter: 0x1C, NumpadEnter: 0x1C,
  KeyA: 0x1E, KeyS: 0x1F, KeyD: 0x20, KeyF: 0x21, KeyG: 0x22, KeyH: 0x23, KeyJ: 0x24, KeyK: 0x25,
  KeyL: 0x26, Semicolon: 0x27, Quote: 0x28, Backquote: 0x29, Backslash: 0x2B, KeyZ: 0x2C, KeyX: 0x2D,
  KeyC: 0x2E, KeyV: 0x2F, KeyB: 0x30, KeyN: 0x31, KeyM: 0x32, Comma: 0x33, Period: 0x34, Slash: 0x35,
  NumpadMultiply: 0x37, Space: 0x39, F1: 0x3B, F2: 0x3C, F3: 0x3D, F4: 0x3E, F5: 0x3F, F6: 0x40,
  F7: 0x41, F8: 0x42, F9: 0x43, F10: 0x44, Home: 0x47, ArrowUp: 0x48, PageUp: 0x49, NumpadSubtract: 0x4A,
  ArrowLeft: 0x4B, ArrowRight: 0x4D, NumpadAdd: 0x4E, End: 0x4F, ArrowDown: 0x50, PageDown: 0x51,
  Insert: 0x52, Delete: 0x53,
  Numpad0: 0x52, Numpad1: 0x4F, Numpad2: 0x50, Numpad3: 0x51, Numpad4: 0x4B, Numpad5: 0x4C,
  Numpad6: 0x4D, Numpad7: 0x47, Numpad8: 0x48, Numpad9: 0x49, NumpadDecimal: 0x53, NumpadDivide: 0x35,
};
const EXTENDED = new Set(['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'Home', 'End',
  'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Insert', 'Delete']);
// KeyboardEvent -> [ascii, scan] as the PC BIOS would deliver it, or null
export function biosKey(e) {
  const scan = SCAN[e.code] || 0;
  if (e.altKey) return scan && !EXTENDED.has(e.code) ? [0, scan] : null;
  if (EXTENDED.has(e.code) || (e.code.startsWith('Numpad') && e.key.length !== 1 && e.code !== 'NumpadEnter')) {
    if (e.code.startsWith('Numpad') && e.key.length === 1) return [e.key.charCodeAt(0), scan];
    return scan ? [0, scan] : null;
  }
  if (e.key === 'Enter') return [e.ctrlKey ? 0x0A : 0x0D, 0x1C];
  if (e.key === 'Backspace') return [e.ctrlKey ? 0x7F : 0x08, 0x0E];
  if (e.key === 'Escape') return [0x1B, 0x01];
  if (e.key === 'Tab') return e.shiftKey ? [0, 0x0F] : [0x09, 0x0F];
  if (e.ctrlKey && e.key.length === 1) {
    const c = e.key.toUpperCase().charCodeAt(0);
    if (c >= 0x40 && c <= 0x5F) return [c - 0x40, scan];
    return null;
  }
  if (e.key.length === 1) {
    const c = e.key.charCodeAt(0);
    if (c < 128) return [c, scan];
  }
  return null;
}
