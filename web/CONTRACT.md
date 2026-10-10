# Compiler ↔ runtime contract (browser port)

The generated program modules (`loader.js`, `game.js`, both produced by `tools/pas2js.py`) are ES modules.
Each one exports `async function main(R)`. `R` is the runtime instance created by `runtime.js`.
All integers are JS numbers. Strings are JS strings whose char codes are bytes 0..255 (Latin-1, not Unicode).

## Memory model

`R.mem` is a `Uint8Array` of 3 × 65536 bytes. An address is a single JS number:

| Segment | Base | Contents |
|---|---|---|
| DS | `0x00000` | Globals, laid out exactly as by the 1985 compiler (first variable at DS:0260). |
| CS | `0x10000` | Typed constants. |
| SS | `0x20000` | Procedure frames (locals and value parameters). |

Out-of-range array indexes are not checked. They simply address neighbouring memory, as on the original.

Accessors (no bounds checks):
- `R.rb(a)` / `R.wb(a, v)`: byte; `v & 255` is stored.
- `R.rw(a)` / `R.ww(a, v)`: integer, 16-bit signed, little endian. `R.rw` returns −32768..32767.
- `R.rs(a)`: returns the string stored at `a` (length byte followed by characters).
- `R.ws(a, s, max)`: stores `s` truncated to `max`.
- `R.rr(a)` / `R.wr(a, x)`: 6-byte Turbo real.
- `R.move(dst, src, n)`: byte copy.

Frames:
- `R.enter(n)` returns `fp`: allocates `n` bytes on the SS stack, growing downward.
- `R.leave(n)` releases them.

## Console / CRT (Turbo Pascal 3 semantics, 1985 runtime)

Text mode, window and cursor:
- `R.textMode(m)`, `R.window(x1, y1, x2, y2)`, `R.clrScr()`, `R.clrEol()`, `R.gotoXY(x, y)`, `R.whereX()`, `R.whereY()`.
- `R.textColor(c)`, `R.textBackground(c)`, `R.lowVideo()`, `R.highVideo()`.

Output to standard output:
- `R.wrStr(s, w)`: string; `w` is the field width, `0` means none.
- `R.wrChar(code, w)`: char.
- `R.wrInt(v, w)`: integer.
- `R.wrBool(b, w)`: boolean.
- `R.wrReal(x, w, d)`: real; `w = -1` means default format, `d = -1` means no decimals given.
- `R.wrLn()`: new line.

Input:
- `await R.readKbd()`: `Read(Kbd, ch)`; returns a char code.
- `await R.keyPressed()`: returns `true`/`false` and always yields to the event loop.
- `await R.rdStr(max)`: `Read(s)` from standard input.
- `await R.rdLn()`: end of `ReadLn` (skips to end of line). `ReadLn(s)` compiles to `await R.rdBeginLn(); s = await R.rdStr(max); await R.rdLn()`.

Timing, sound and random numbers:
- `await R.delay(ms)`, `R.sound(hz)`, `R.noSound()`.
- `R.random(n)`, `R.randomize()`.

## Files (typed and untyped)

A file variable lives in program memory. The runtime stores its own state keyed by the variable's address.

Operations:
- `R.assign(fa, name)`.
- `R.reset(fa, recSize)`, `R.rewrite(fa, recSize)`.
- `R.readRec(fa, addr)`, `R.writeRec(fa, addr)`.
- `R.close(fa)`, `R.chain(fa)`.

Error handling:
- After each I/O call compiled under `{$I+}`, the code calls `R.ioCheck()`. It throws a runtime error if `IOResult <> 0`.
- `R.ioResult()` returns the error code and clears it.

## Graphics (GRAPH.P externals)

`R.graphColorMode()`, `R.palette(n)`, `R.getPic(addr, x1, y1, x2, y2)`, `R.putPic(addr, x, y)`.

## Program control

- `R.halt()` throws `HaltSignal`.
- `R.chain(fa)` throws `ChainSignal(name)`. The shell then runs the chained program's `main` with the runtime state kept: screen, window, colours.
