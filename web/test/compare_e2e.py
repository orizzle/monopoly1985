#!/usr/bin/env python3
"""Compare port snapshots (Pnnnn.BIN, normal font and inverted font runs) with DOSBox snapshots of
the ORIGINAL program (Dnnnn.BIN from KEYFEED.COM).

Text modes: the whole 16 KB of video memory (characters + attributes), BIOS mode, cursor and colour
register must be identical.
Graphics mode: pixels that are the same in both port runs (i.e. not produced by the font) must equal
the original's pixels.  Pixels that differ between the two port runs are text pixels; for those, every
8x8 text cell must contain, in the original, the same bitmap wherever the same character was drawn in
the same colours (font-independent comparison: no PC ROM font is used anywhere).
usage: compare_e2e.py DOSDIR PORTDIR_A PORTDIR_B"""
import sys, os, glob

def pixels(v):
    P = bytearray(320 * 200)
    for y in range(200):
        base = (y & 1) * 0x2000 + (y >> 1) * 80
        for xb in range(80):
            b = v[base + xb]
            o = y * 320 + xb * 4
            P[o] = b >> 6; P[o + 1] = (b >> 4) & 3; P[o + 2] = (b >> 2) & 3; P[o + 3] = b & 3
    return P

def main():
    dd, pa, pb = sys.argv[1:4]
    D = sorted(glob.glob(dd + '/D*.BIN')); A = sorted(glob.glob(pa + '/P*.BIN')); B = sorted(glob.glob(pb + '/P*.BIN'))
    print('snapshots: original %d, port %d/%d' % (len(D), len(A), len(B)))
    glyph_map = {}            # (cell bitmap in port font A, port colours) -> original cell bitmap
    total_bad = 0
    for k in range(max(len(D), len(A))):
        if k >= len(D) or k >= len(A) or k >= len(B):
            print('#%d: missing snapshot (original %s, port %s)' % (k, k < len(D), k < len(A))); total_bad += 1; continue
        d = open(D[k], 'rb').read(); a = open(A[k], 'rb').read(); b = open(B[k], 'rb').read()
        dv, bios = d[:16384], d[16384:]
        state_o = (bios[0x49], bios[0x50], bios[0x51], bios[0x66])
        state_p = (a[16384], a[16385], a[16386], a[16387])
        msgs = []
        if state_o != state_p: msgs.append('state orig mode/col/row/reg %s port %s' % (state_o, state_p))
        mode = bios[0x49]
        if mode in (4, 5):
            Pd, Pa, Pb = pixels(dv), pixels(a[:16384]), pixels(b[:16384])
            bad_px = 0; first = None
            text_cells = set()
            for i in range(320 * 200):
                if Pa[i] != Pb[i]:
                    text_cells.add(((i % 320) // 8, (i // 320) // 8))
                elif Pa[i] != Pd[i]:
                    bad_px += 1
                    if first is None: first = (i % 320, i // 320, Pd[i], Pa[i])
            if bad_px: msgs.append('%d non-text pixels differ, first at x=%d y=%d orig %d port %d' % ((bad_px,) + first))
            incons = 0
            for (cx, cy) in text_cells:
                cell = [Pa[(cy * 8 + y) * 320 + cx * 8 + x] for y in range(8) for x in range(8)]
                # decode the character from the test font (row 0 = code) and the colours used
                fg = max(cell); code = sum(1 << (7 - x) for x in range(8) if cell[x] == fg and fg)
                key = bytes([code]) + bytes(sorted(set(cell)))
                orig = bytes(Pd[(cy * 8 + y) * 320 + cx * 8 + x] for y in range(8) for x in range(8))
                # colours used must agree as sets (glyph colour + background)
                bad = (not set(orig) <= set(key[1:])) or (key in glyph_map and glyph_map[key] != orig)
                if bad:
                    incons += 1
                    if os.environ.get('VERBOSE'):
                        pb_ = bytes(Pb[(cy * 8 + y) * 320 + cx * 8 + x] for y in range(8) for x in range(8))
                        print('   cell col %d row %d' % (cx, cy))
                        for y in range(8):
                            row = lambda bb: ''.join('.123'[c] for c in bb[y * 8:y * 8 + 8])
                            prev = glyph_map.get(key)
                            print('     char %3d  orig %s  mapped %s' % (key[0], row(orig), row(prev) if prev else '-'))
                    continue
                glyph_map.setdefault(key, orig)
            if incons: msgs.append('%d text cells inconsistent with the original glyphs' % incons)
            what = 'graphics, %d text cells' % len(text_cells)
        else:
            nd = sum(1 for i in range(16384) if dv[i] != a[i])
            if nd:
                i = next(i for i in range(16384) if dv[i] != a[i])
                msgs.append('%d video bytes differ, first at offset %d (row %d col %d %s): orig %02x port %02x' % (
                    nd, i, (i // 2) // 80, (i // 2) % 80, 'attr' if i & 1 else 'char', dv[i], a[i]))
            what = 'text'
        print('#%d %-26s %s' % (k, what, 'IDENTICAL' if not msgs else 'DIFFERS: ' + '; '.join(msgs)))
        total_bad += bool(msgs)
    print('RESULT: %s' % ('ALL IDENTICAL' if total_bad == 0 else '%d snapshots differ' % total_bad))
    return 1 if total_bad else 0

if __name__ == '__main__':
    sys.exit(main())
