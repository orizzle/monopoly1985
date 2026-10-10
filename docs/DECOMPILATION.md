# How the source was recovered and verified

## The originals

`monopoly.com` (12,223 bytes) is a Turbo Pascal 3 program. It starts with Borland's runtime library, about 11 KB, marked `Copyright (C) 1985 BORLAND Inc`. Its own code is a short loader:
- it checks that the other files can be opened;
- if one is missing, it shows a "Monopoly Problem" box;
- otherwise it `Chain`s to the game.

The game itself consists of:
- **`MONOCODE.CHN`** (47,899 bytes): a TP3 *chain file*, which holds program code without a runtime;
- **`MONOCODE.000`** (10,496 bytes): its *overlay file*, holding four overlay procedures;
- **`MONOGRAF.GRA`**: the pictures, a single 13,774-byte record read in one piece.

The programs were built with **Turbo Pascal 3.0/3.01**. The only freely available version is **3.02** (1986, released free by Borland), and its runtime library differs:

| Difference | 3.02 compared with the 1985 runtime |
|---|---|
| Runtime size | `0x2F` bytes shorter, so all program code addresses differ by `0x2F` |
| User data | starts at DS:`0262` instead of DS:`0260`, so all global addresses differ by 2 |
| Routine entry points | different addresses for the same runtime routines; `TextMode` has an extra prefix |
| Header words 2 and 3 | constants of the compiler version |
| `Kbd` file variable | DS:`014C` instead of DS:`014A` |

## Method

1. **Runtime map.**
   - The 1985 runtime was aligned with 3.02's (`verify/rtmap.py`).
   - Each runtime routine was named by compiling probe programs that use every Turbo Pascal builtin (`verify/rtnames.py`).
   - Two routines are followed by inline data: string literals and 6-byte real constants. The disassemblers handle both.
2. **Structure.** The chain file contains, in order:
   - a header;
   - Borland's `GRAPH.BIN`, unchanged (the source includes `GRAPH.P`);
   - typed constants: colour groups, squares, token offsets and deeds;
   - procedures, four `forward` declarations and the overlay group;
   - two wrappers that call overlays;
   - the card texts;
   - more procedures and the main program.

   TP3 does not store the overlay area in the file. It compiles the code that follows as if the area were present and reserves the space at load time. The area here is `0xBFC` bytes: 12 × 256 bytes for the largest overlay, minus 4.
3. **Declarations.**
   - The typed constants were generated straight from the binary's bytes.
   - The global variables were recovered from how the code uses them:
     - string lengths from the `StrStore`/`RdStr` length arguments;
     - element sizes from index arithmetic;
     - booleans from `not`/`xor al,1` patterns.
   - The skeleton with every procedure stubbed reports exactly the data size the original header records (`$05CE` paragraphs).
4. **Procedures.** Every procedure was decompiled, compiled with TP 3.02 and compared with the original by a per-procedure structural comparator (`verify/tp3pcmp.py`). The comparator lines up procedures, forward jumps, overlay descriptors and data blocks by position. It translates:
   - runtime call targets, through the runtime map;
   - code and data addresses, by the fixed differences above;
   - overlay calls, by overlay number.

   Each procedure was iterated until it compared identical. Some original forms had to be kept exactly, for example `goto`s into the middle of loops, the order of operands, and `exit` against falling through to the end.
5. **Whole-program check.**
   - `verify/relocate.py` rewrites a 3.02 build onto the 1985 runtime, using only the fixed differences listed above. It never reads the original program code.
   - The result is compared with the originals using `cmp`.
   - `verify/verify.sh` runs the whole check, and all three files come out **byte-identical**.

## Settings recovered from the binaries

- **Game:** compiled as a chain file with the work file typed as lower-case `monocode`. The overlay file name is stored as `monocode.000`.
- **Loader:**
  - Compiled with minimum code segment `$0C72` and minimum data segment `$05CE` paragraphs. Those are the game's sizes, which a chaining program must reserve.
  - Installed for "Color display 80x25" (text mode 3).
- **Compiler directives:** defaults throughout ({$I+}, {$K+}, {$C+}), with `{$I-}` only around the file checks and the save/load code.

## What cannot be recovered

- **Identifiers, comments and layout.** The names in `src/` are ours, and each carries its original address.
- **Where the source was split into include files.** The size of TP3's editor forces some split.
- **Forms that compile to identical machine code**, such as `TextMode(C80)` against `TextMode(3)`. The simplest form was chosen.
- **Three regions of the data segment that nothing references** (`Unused…`): their sizes are known, their types are not.
