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

## Online play

Every player's browser runs its own copy of the game, compiled from the same source. A small PHP backend (`web/api.php`) does not run the game and sends no pictures. It keeps a shared log of keys, and the copies stay identical because the program is deterministic.

### Keys at the same point in every copy

- **Poll points:** the runtime numbers every point where the program can receive a key:
  - every `KeyPressed`;
  - every wait for a key (`Read(Kbd)`, `ReadLn`, the Ctrl-S pause);
  - the end of every `Delay` and CPU-timed loop. Those are where keys typed during the dice animation reach the keyboard buffer in a single-player game.
- **Delivery:** with `Runtime.keyGate` set (`web/online.js`), keys reach the program only at those points.
- **The log:** the player whose turn it is decides each point: a key, or no key. Each decision goes into the log. The other copies follow the log, and when they catch up with it they wait at the next point.
- **Dice:** the dice come from `Random`, which advances on every poll while the dice shake. Because a key arrives at the same numbered poll in every copy, every copy rolls the same dice. Pressing a key two or three times is also the same everywhere. Extra keys pressed while the token moves are swallowed by the game's own check while drawing, exactly as in the single-player game.
- **Checking:** each logged key carries an FNV hash of the game's data segment and random seed. A copy whose state differs notices at the next key and rebuilds itself from the log. A rebuilt copy is right by construction, so it trusts the log up to the point where it was rebuilt; the copy that was out of step is then the one that rebuilds.
- **Catching up:** a copy far behind the log, such as one that just rejoined, runs without waiting for `Delay` and without sound until it has caught up.

### Whose turn

Ownership comes from the game's own data, which is the same in every copy:
- **Setting up:** the host types while the players are entered or a saved game is loaded. For a new game, the host's copy types the players' names into the game's own name entry.
- **During the game:** the player whose name is `Player[CurPlayer]` types. That covers everything on their turn, including business, auctions and paying.
- **Everyone else:** keys and taps are ignored, and the status line says whose turn it is.
- **Absent players:** if a player is offline for 20 seconds, the host may play for them ("Play for …"). Those keys are applied only once the backend has accepted them, and the player gets the seat back on rejoining.

### Files

The host's saved games are sent to everyone at the start, so loading a saved game works the same in every copy. Games saved during play are written by every copy, and each player keeps one in their own browser.

### Backend (`web/api.php`)

- **Requests:** POSTed JSON: `create`, `join`, `leave`, `start`, `control` and `sync`.
- **`sync`:** sends the poster's decisions and chat, and returns new log entries, events and the players' status.
- **Storage:** each game is a directory under `MONOPOLY_DATA` holding `meta.json`, an append-only `keys.log` and `events.log`.
- **Locking and checks:** requests on a game are serialized with `flock`. The backend accepts decisions only in order, and only from the player entitled to make them.
- **Expiry:** idle games are removed after 6 hours.
- **The live site:** the file runs on its own PHP-FPM pool (`monopoly`, `MONOPOLY_DATA=/var/lib/monopoly-online`).

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
| `web/test/online/online_sync.py` | Online games of 2 to 4 players in separate browsers, one on a phone with the on-screen keyboard. Every copy must agree at every recorded point (data, dice, seed, screen). Out-of-turn presses must be ignored. Runs against `api.php` through `devserver.py` or the live site (`MONOPOLY_URL`) |
| `web/test/online/online_rejoin.py`, `online_repair.py` | Reload and rejoin, playing for an absent player and their return, and repair of a deliberately corrupted copy |

## Differences that remain

- **Fonts:** IBM's ROM fonts (8×8 and VGA 8×16) are not included (see the README for `extract_pcfont.sh`).
- **Drawing speed:** on a 4.77 MHz PC the screen drew visibly slowly. The port draws instantly, as DOSBox does at full speed. Only the CPU-dependent *sound* loops are timed.
