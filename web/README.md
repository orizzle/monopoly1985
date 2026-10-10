# Monopoly (1985): browser port

This is the 1985 freeware Monopoly (`MONOPOLY.COM`, `MONOCODE.CHN`, `MONOCODE.000`, `MONOGRAF.GRA`) running in a web browser.

The game logic is not rewritten by hand:

- `loader.js` and `game.js` are compiled by `tools/pas2js.py` from the reconstructed Turbo Pascal source in `../src`. That source is verified to compile to code identical to the original binaries.
- `runtime.js` reimplements the PC (CGA video, BIOS keyboard, PC speaker, DOS files) and the Turbo Pascal 3.0 (1985) runtime the game was built with.
- `pasrt.js` holds the language helpers. These include Turbo Pascal's exact 6-byte real arithmetic, which is measured against the original runtime.

## Running

ES modules do not load from `file://`, so serve the folder:

    cd web && python3 -m http.server 8000      # then open http://localhost:8000/

Click the screen, or press a key, to start; browsers only allow sound after a user action.

The keyboard works as on the PC. During the dice roll, F1 toggles sound and F2 saves the game. On the "Who are the players?" screen, F2 loads a saved game.

Saved games are stored in the browser's localStorage under the file name you type.

## What is identical, and what is not

**Identical to the original:**
- every screen: characters, colours, cursor, windows and graphics;
- the dice and other random numbers, given the same key timing;
- sounds: the same frequencies and lengths, as a square wave;
- timing of delays;
- keyboard behaviour, including keys typed while the screen is being drawn being swallowed exactly as in the original;
- the save-file format;
- error messages.

**Not identical: the text font.** The PC's character ROM font is IBM's and is not included. The built-in font is an original 8×8 design covering every character the game can display. To get the original look, load a 2048-byte 8×8 PC font file of your own (256 glyphs × 8 rows, top row first, leftmost pixel = most significant bit) with the control under the screen. The browser remembers it. Glyph positions and colours are identical either way.

## Verification (`test/`)

- **`e2e_session.sh` and `fuzz.py`:** run the original programs in DOSBox with a resident key feeder (`test/dos/keyfeed.asm`) and the port headless in Node, with the same key script. A key becomes available after exactly the same number of keyboard polls, so even the random numbers are identical. Video memory, BIOS mode, cursor and colour register are compared at every key with `compare_e2e.py`:
  - text screens must match byte-for-byte;
  - graphics screens must match on every pixel not drawn by the font, and their text cells are checked for consistency with the original's glyphs without using any PC font.
- **`dosbox_compare.py`:** compares individual runtime behaviours (text output, windows, scrolling, graphics text, palettes, GetPic/PutPic, the line editor, keyboard swallowing, error messages) with the original 1985 runtime running in DOSBox.
- **`real48.test.mjs`:** 6,260 real-arithmetic results compared with the original runtime.
- **`unit.mjs`:** unit tests.

Requirements:
- The DOSBox-based tests need `dosbox` and `node`. `KEYFEED.COM` is prebuilt; `nasm` is only needed to rebuild it.
- `dosbox_compare.py` also needs `../verify` with Turbo Pascal 3.02 and emu2 (see `../verify/verify.sh`).

Commands:

    node test/unit.mjs
    node test/real48.test.mjs
    test/e2e_session.sh demo "0x41:0x1e:1000 0x4c:0x26:2 13:0x1c:2 0x42:0x30:700 0x4f:0x18:2 13:0x1c:2 13:0x1c:900"
    python3 test/fuzz.py 1 80

The sound probe page is `test/sound/sound.html`. See `../docs/WEBPORT.md` for how it was recorded and compared.
