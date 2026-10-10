# Monopoly (1985): reconstructed source and browser port

This repository contains a 1985 freeware Monopoly game for MS-DOS (IBM PC with CGA). The game is credited to Don Phillip Gibson (MS-DOS adaptation, version 5.1) and was distributed as freeware by John Capers. The included `MONOFREE.TXT` invites anyone to "distribute, copy, or decompile and change" it.

The repository holds three things built from the game:

1. **The reconstructed Turbo Pascal source** (`src/`). It was decompiled from the original binaries and is proven to compile back to them byte for byte.
2. **A browser port** (`web/`). The reconstructed source is compiled to JavaScript and runs on an emulation of the PC and of the original Turbo Pascal runtime. It reproduces the original screen for screen and plays the same sounds.
3. **The tools and tests** that prove both of the above.

| Path | Contents |
|---|---|
| `src/` | `MONOPOLY.PAS` (loader), `MONOCODE.PAS` + `MONOCOD1.INC` + `MONOCOD2.INC` (game and overlays) |
| `original/` | The original freeware files: `monopoly.com`, `MONOCODE.CHN`, `MONOCODE.000`, `MONOGRAF.GRA`, `MONOFREE.TXT` |
| `docs/SOURCE.md` | Guide to the source: structure, data model, turn flow, every procedure |
| `docs/DECOMPILATION.md` | How the source was recovered and how it is verified |
| `docs/WEBPORT.md` | How the browser port works and how it was verified, including sound |
| `verify/` | Rebuild the originals from `src/` and compare (`verify.sh`) |
| `web/` | The browser port, its Pascal-to-JavaScript compiler (`web/tools/pas2js.py`) and its tests |

## Play it in a browser

    cd web && python3 -m http.server 8000      # then open http://localhost:8000/

Click the screen to start; sound needs a user action in the browser. During the dice roll, F1 toggles sound and F2 saves the game; on the "Who are the players?" screen, F2 loads a saved game. Saved games are kept in the browser's localStorage. On phones and tablets an on-screen PC keyboard appears below the screen (the "Keyboard" button shows or hides it).

**Speed.** The "Speed" control below the screen sets how fast the sound effects that depended on the PC's speed run (token steps, sirens, house sweeps, cash counters): **Fast PC (DOSBox)**, the default, as on the faster PCs of the early 1990s and DOSBox's default setting, or **IBM PC 4.77 MHz**, the machine the game was written for (see `docs/WEBPORT.md`).

**Online play.** After the click, a menu in the game's own style offers **L** (play on this computer, the original game), **C** (create an online game), **J** (join one) or **S** (sound test: every sound of the game, one letter each, Esc to go back).
- **Creating a game:** the creator, the host, gets a four-letter game code to give to the others, up to four players in all, and starts the game when everyone has joined. **S** starts a new game and **F2** starts the original "load a saved game" screen.
- **Taking turns:** every player sees the game exactly as in the original. Only the player whose turn it is can type or tap; anyone else's keys are ignored.
- **Talking:** a chat line under the screen is there for what the game expects players to say aloud, such as auction bids and trade prices.
- **Reloads and absences:** a player who reloads rejoins with the same code and name. If a player is gone for 20 seconds on their turn, the host can play for them.
- **Requirements:** online play needs `web/api.php` on a PHP 8 server (see `docs/WEBPORT.md`).

**Display and font.** The port can show the screen as a VGA (the default) or a CGA would.
- **VGA:** text screens use an 8×16 font in 9×16 character cells at 720×400; the board stays in 320×200 CGA graphics, as on a VGA PC.
- **CGA:** everything uses the 8×8 font, as on the game's original 1985 target.

The real IBM fonts are not included; the port has its own. To get the original look, run `web/tools/extract_pcfont.sh` once. It takes the 8×8 and VGA 8×16 fonts from the BIOS of your own DOSBox and writes `web/pcfont.bin` and `web/pcfont16.bin`, which the port then uses automatically. Without both files, you can also load any 2048-byte (8×8) or 4096-byte (8×16) font file with the control below the screen; when both are present, they are always used and that control is hidden.

## Build the original programs from the source

You need Turbo Pascal 3 and Borland's `GRAPH.P` and `GRAPH.BIN`, which are not included.

1. **Compile the game:**
   - Work file `monocode`, typed in lower case. The overlay file name `monocode.000` is stored inside the `.CHN` exactly as typed.
   - Compiler options → **cHn-file**.
   - Output: `MONOCODE.CHN` and `MONOCODE.000`.
2. **Compile the loader:**
   - Work file `MONOPOLY`.
   - Compiler options → **Com-file**, minimum cOde segment size `0C72`, minimum Data segment size `05CE`.
   - Output: `MONOPOLY.COM`.

`verify/verify.sh` does all of this headless and checks the result:
- It compiles both programs with Turbo Pascal 3.02 under the emu2 DOS emulator.
- It relocates the output onto the 1985 runtime the originals were built with, which differs slightly from the 3.02 runtime.
- It compares the result with `original/` using `cmp`.

The result: `MONOCODE.CHN`, `MONOCODE.000` and `MONOPOLY.COM` are all byte-identical to the originals.

## Notes

- **Names.** Compiled code keeps no identifiers or comments, so all names in `src/` were chosen during the reconstruction. Each procedure and global carries its original address in a comment.
- **Not included:** Borland's Turbo Pascal compiler and `GRAPH.P`/`GRAPH.BIN`, and IBM's PC font.
- **Trademark.** Monopoly is a trademark of its owner; the game's title screen carries the original 1985 notice.
