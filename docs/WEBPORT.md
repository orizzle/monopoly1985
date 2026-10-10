# The browser port

The port runs the reconstructed program itself; none of the game logic was rewritten by hand. It has three parts:

| Part | What it does |
|---|---|
| `web/tools/pas2js.py` | Compiles the Turbo Pascal 3 source to an async ES module (`loader.js`, `game.js`). |
| `web/runtime.js` | Emulates the machine and the 1985 Turbo Pascal runtime. |
| `web/pasrt.js` | Language-level helpers: strings, `Val`/`Str`, and Turbo Pascal's 6-byte real arithmetic. |

`web/shell.js` runs the loader. When the loader calls `Chain`, it runs the game on the same runtime, as DOS would.

## Compiler (`pas2js.py`)

### Memory

Every variable lives at the address the 1985 compiler gave it, in byte-addressed memory:
- **DS:** globals start at DS:0260, in declaration order.
- **CS:** typed constants. Their bytes are built from the source and are identical to the original's.
- **SS:** stack frames.

Integers wrap at 16 bits, strings are length-prefixed and booleans are bytes. Out-of-range indexes therefore read the same neighbouring memory as on the PC. The game's `Random(8)` index into a 1..7 array relies on this.

### Control flow

- Procedures without labels compile to ordinary structured code.
- Procedures with labels compile to a `switch` state machine, so every `goto` behaves as in the original.
- `for` loops evaluate their bounds once and run a fixed count, as TP3 does.

### Faithful details

- **Run-time errors:** messages print the original program's PC. The compiler attaches to each operation that can fail (`Copy`, string `+`, string→char, file I/O) the address of the corresponding call in the original binary (`tools/pcmap.json`).
- **CPU-timed loops:** see "Sound" below.

## Runtime (`runtime.js`)

### Video

- CGA video memory (B800) with BIOS INT 10h behaviour for text modes 2/3 and graphics mode 4: mode set, cursor, scroll, write-character, teletype and palette.
- The Turbo Pascal console on top, as in the 1985 runtime:
  - windows and attributes;
  - `ClrScr` switching back to the program's text mode;
  - wrapping and scrolling.
- `GRAPH.BIN`'s `GraphColorMode`, `Palette`, `GetPic` and `PutPic`.
- The canvas is drawn from video memory every frame.

### Display: VGA or CGA

Video memory and all game behaviour are the same in both; only the way text modes are drawn differs.

**VGA (the default):**
- Text modes are drawn at 720×400: 8×16 glyphs in 9-pixel cells. For characters C0h–DFh the 9th column repeats the 8th, so line-drawing characters join.
- The cursor covers scan lines 13–14, and blinking follows 70 Hz frames.
- Graphics mode 4 is 320×200, line-doubled, with the 8×8 font.

**CGA:** text modes are 640×200 with the 8×8 font, line-doubled.

**In both modes:**
- The screen is shown at a monitor's 4:3 aspect.
- The fonts come from `pcfont.bin`/`pcfont16.bin` when present (made by `tools/extract_pcfont.sh` from your own DOSBox BIOS), or from a font file loaded in the page; when both `.bin` files are present they are always used and the font controls are hidden. Otherwise the port's own font is used; its 8×16 version is the 8×8 one with each row doubled.

### Keyboard

- The 15-key BIOS buffer.
- `Read(Kbd)`: extended keys arrive as `#27` followed by the scan code.
- **The `{$C+}` check after every character written:** a key typed while the screen is being drawn is read and thrown away; Ctrl-S pauses, Ctrl-C breaks. The original game behaves this way.
- `ReadLn`: the runtime's own line editor.
- **On-screen keyboard** (`web/touchkbd.js`), for touch screens:
  - It is a US PC layout with Esc, F1, F2, Backspace, Shift, Caps Lock, Space and Enter. Every key goes through the same mapping as a physical key, so the program receives the same character and scan code.
  - It is shown by default when touch is the main input, and the "Keyboard" button toggles it.
  - In landscape, the screen and keyboard sit side by side.

### Other behaviour

- **Random numbers:** the original generator (`S = S·129 + 361962E9h`) with the original start seed. The game never calls `Randomize`, so its dice depend only on when keys are pressed.
- **Files:** typed and untyped files with the 1985 runtime's IOResult codes. Save games go to localStorage.
- **Errors:** messages formatted exactly as the 1985 runtime prints them (`Run-time error 11, PC=xxxx` / `Program aborted`).

### Real arithmetic

Real arithmetic matches the 1985 runtime exactly, and was measured against it:
- **Multiplication and division:** truncate the exact result to a 40-bit significand.
- **Addition and subtraction:** shift the smaller operand right, truncating, before adding.
- **Decimal literals:** truncated. The game's `0.1` is `7D CC CC CC CC 4C`, slightly below 0.1.
- **`Round`:** rounds half away from zero.

So mortgage interest on a $150 property comes to $7, as on the original.

## Sound

- **Pitch:** the PC speaker is a Web Audio square wave. `Sound(Hz)` uses the same timer divisor as the runtime (`1234DDh / Hz`, frequencies of 18 Hz and below ignored), so pitches are exact.
- **`Delay`:** a real millisecond, as it was on the PC, where the runtime calibrated it at start-up. Browser timers are coarse, so the port keeps a virtual clock and schedules every speaker change on the audio clock at its exact virtual time.

### CPU-timed effects

Several effects are loops of `Sound` calls with no `Delay`: the house-building sweeps, the jail siren, the three-doubles siren and the cash counters. How long they last depended on the speed of the PC, and some compute real arithmetic in software on every step.

The port reproduces the IBM PC (8088 at 4.77 MHz) the game was written for:
1. `web/tools/cycles8088.py` is an 8086 interpreter with an 8088 timing model. It uses the data-sheet clock counts, the 8-bit bus and the 4-byte prefetch queue.
2. `web/tools/measure_sound_loops.py` runs the **original machine code** of each such loop through it, including the 1985 runtime's `Sound` and real-arithmetic routines, and records the clocks per iteration (`tools/soundloops.json`).
3. The compiled loops charge that CPU time to the virtual clock.

The model is a first-order 8088 estimate, typically within about 10% of real hardware.

### Sound test

The game's effects, copied into `web/test/sound/SNDPROBE.PAS`, were recorded on a Linux machine through PulseAudio from two sources:
- the original 1985 runtime in DOSBox (fixed cycles, so that `Delay` calibration is correct);
- the port in Firefox.

| Effect | Original (DOSBox) | Port (Firefox) |
|---|---|---|
| Reference tones 440 / 1000 / 100 Hz | 0.46 / 0.48 / 0.48 s | 0.50 / 0.51 / 0.51 s, same pitch |
| Pass GO sweep (1600→1900 Hz) | 0.66 s | 0.72 s |
| Dice rattle | 5 bursts of 3.3 ms, 42 ms apart | 5 bursts of 3.6 ms, 44 ms apart |
| Not-enough-cash beeps | 1.74 s | 1.81 s |
| Three-doubles siren | 4.00 s | 3.85 s |
| House sweeps | 0.55 s | 0.81 s |
| Jail siren | 6.29 s | 6.15 s |
| Bankruptcy | 4.01 s | 4.25 s |

The CPU-timed effects follow the 8088 model. DOSBox's fixed-cycle mode is a rough speed approximation, which accounts for the differences there.

## Verification

### End-to-end screens

`web/test/e2e_session.sh` and `web/test/fuzz.py` compare the port against the original programs.
- **Setup:** the originals run in DOSBox with a resident key feeder (`test/dos/keyfeed.asm`). The port runs headless in Node. Both get the same key script.
- **Determinism:** a key becomes available after exactly the same number of keyboard polls on both sides, so even the dice are identical.
- **Snapshots:** taken at every key.
  - Text screens must be byte-identical: characters, attributes, mode, cursor and colour register.
  - Graphics screens must be pixel-identical apart from glyph shapes, and every text cell must be consistent with the original's glyph for that character.
- **Results:** 40 random sessions of about 90 keys each matched the original at all 3,512 snapshots. More seeds and a scripted session have been run since, all identical.

### Other tests

| Test | What it checks |
|---|---|
| `web/test/dosbox_compare.py` | Individual runtime behaviours against the original runtime in DOSBox: text and windows, scrolling, graphics text, palettes, `GetPic`/`PutPic` at every alignment, the line editor, key swallowing, error messages |
| `web/test/real48.test.mjs` | 6,260 real-arithmetic results recorded from the original runtime (`test/data/`) |
| `web/test/unit.mjs` | Unit tests |

## Differences that remain

- **Fonts:** IBM's ROM fonts (8×8 and VGA 8×16) are not included (see the README for `extract_pcfont.sh`).
- **Drawing speed:** on a 4.77 MHz PC the screen drew visibly slowly. The port draws instantly, as DOSBox does at full speed. Only the CPU-dependent *sound* loops are timed.
