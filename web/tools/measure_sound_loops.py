#!/usr/bin/env python3
"""Measure, on the 8088 timing model, how long each iteration of the game's sound loops takes in the
ORIGINAL program (MONOCODE.CHN + the 1985 runtime of MONOPOLY.COM), excluding Delay calls.
Writes tools/soundloops.json: {procedure: [clocks per iteration for each for-loop that calls Sound
directly, in source order]}, used by pas2js.py to reproduce the CPU-paced sweeps and sirens.
usage: measure_sound_loops.py MONOCODE.PAS ORIGDIR OUT.json
       measure_sound_loops.py PROBE.PAS --com PROBE85.COM OUT.json   (a program relocated onto the
       1985 runtime with relocate.py; its procedures are located in source order)"""
import sys, os, re, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pas2js
from cycles8088 import CPU, Halt

DOSBOX_OUT = None
if '--dosbox' in sys.argv:      # also write the loops' timing at DOSBox's default speed
    i = sys.argv.index('--dosbox'); DOSBOX_OUT = sys.argv[i + 1]; del sys.argv[i:i + 2]
DOSBOX_IPMS = 3000      # DOSBox cycles=auto runs a real-mode program at 3000 instructions per ms
SRC, ORIG, OUT = sys.argv[1], sys.argv[2], sys.argv[-1]
COM = sys.argv[3] if ORIG == '--com' else None
CHN_BASE = 0x2D7C
DELAY = 0x0213          # 1985 runtime Delay (skipped: the port waits for delays in real time)

def expand_chn(raw):
    """insert the overlay area after the overlay descriptor (same as the comparison tools)"""
    for m in re.finditer(rb'\xe8..\xff\xff[\x20-\x7e]{1,12}', raw, re.S):
        i = m.start(); w2 = struct.unpack('<H', raw[i + 20:i + 22])[0]
        after = CHN_BASE + i + 22; sh = w2 - after
        if 0 < sh < 0x8000 and sh % 256 == 0xFC:
            return raw[:i + 22] + bytes(sh) + raw[i + 22:]
    return raw

has_sound, for_loops = pas2js.has_sound, pas2js.for_loops

def const(e):
    if e.k == 'num': return e.v
    if e.k == 'neg': return -const(e.a)
    return None

def main():
    toks = pas2js.lex(SRC, [])
    prog = pas2js.Parser(toks).program()
    if COM:
        img = open(COM, 'rb').read()
        rt, chn, ovl, gra = img, img[0x2C7C:], b'', b''
        heads = [m.start() for m in re.finditer(rb'\x55\x8b\xec\x55\xe9', chn)]
        procaddr = {d.name: CHN_BASE + h for d, h in zip([d for d in prog.decls if d.k == 'proc'], heads)}
    else:
        rt = open(os.path.join(ORIG, 'monopoly.com'), 'rb').read()
        chn = expand_chn(open(os.path.join(ORIG, 'MONOCODE.CHN'), 'rb').read())
        ovl = open(os.path.join(ORIG, 'MONOCODE.000'), 'rb').read()
        gra = open(os.path.join(ORIG, 'MONOGRAF.GRA'), 'rb').read()
        procaddr = {}
    # overlay records: list of (record bytes, load base)
    ovrecs = []; k = 0
    while k + 7 <= len(ovl):
        sz, ad = struct.unpack('<HH', ovl[k + 3:k + 7]); ovrecs.append((ovl[k:k + 7 + sz], ad - 7))
        k += ((sz + 7 + 255) // 256) * 256
    # where each procedure is in the original: the comment before it gives its address
    # ('{ P_4DA4 -- ...}') or its overlay ('{ overlay 2 -- ...}')
    where = {}
    if not COM:
        srcdir = os.path.dirname(os.path.abspath(SRC))
        text = ''.join(open(os.path.join(srcdir, f), encoding='latin-1').read()
                       for f in sorted(os.listdir(srcdir)) if f.upper().endswith(('.PAS', '.INC')))
        for m in re.finditer(r'\{ (P_([0-9A-Fa-f]{4})|overlay (\d+)) --[^}]*\}\s*(?:overlay\s+)?procedure\s+(\w+)', text, re.I):
            where[m.group(4).lower()] = ('ov', int(m.group(3))) if m.group(3) else ('addr', int(m.group(2), 16))
    def overlay_of(name):
        w = where.get(name.lower())
        if w and w[0] == 'ov': return w[1]
        return int(name[2:]) if name.startswith('ov') and name[2:].isdigit() else None
    def addr_of(name):
        w = where.get(name.lower())
        return procaddr.get(name) or (w[1] if w else int(name[2:], 16))
    result = {}; dosbox = {}
    for d in prog.decls:
        if d.k != 'proc': continue
        name = d.name
        ovn = overlay_of(name)
        loops = []
        for_loops(d.body, loops)
        sound_loops = [(i, l) for i, l in enumerate(loops) if has_sound(l.body)]
        if not sound_loops: continue
        # code of this procedure in the original
        def fresh():
            cpu = CPU()
            CS, DS, SS = 0x1000, 0x2000, 0x3000
            cpu.s.update(cs=CS, ds=DS, es=DS, ss=SS)
            base = CS << 4
            cpu.mem[base + 0x100:base + 0x100 + 0x2C7C] = rt[:0x2C7C]
            cpu.mem[base + CHN_BASE:base + CHN_BASE + len(chn)] = chn
            if ovn:
                rec, lb = ovrecs[ovn - 1]
                cpu.mem[base + lb:base + lb + len(rec)] = rec
            dbase = DS << 4
            cpu.mem[dbase + 0x2C9:dbase + 0x2C9 + len(gra)] = gra       # graphics record G02C9
            cpu.mem[dbase + 0x3B79] = 1                                 # sound on (G3B79)
            cpu.mem[dbase + 0x0262] = 1                                 # current player 1
            cpu.r['sp'] = 0xFFF0; cpu.r['bp'] = 0xFFF0
            cpu.skip = {DELAY: 0}
            return cpu
        if ovn:
            rec, lb = ovrecs[ovn - 1]
            code, cbase = rec, lb
        else:
            addr = addr_of(name)
            code, cbase = chn[addr - CHN_BASE:], addr
        # loop heads: 'pop cx; xchg cx,ax; sub cx,ax' in code order (TP3 for-loop prologue)
        heads = [m.start() for m in re.finditer(rb'\x59\x91\x2b\xc8', code)]
        per = []; fast = []
        for idx, lp in sound_loops:
            h = heads[idx]
            # TP3: [start expr] push ax; [end expr -> ax]; pop cx; xchg; sub; jge/jle +3; jmp EXIT; ...
            jop = code[h + 4]; assert code[h + 5] == 3 and code[h + 6] == 0xE9, (name, idx)
            exit_ = (cbase + h + 9 + struct.unpack('<h', code[h + 7:h + 9])[0]) & 0xffff
            s, e = const(lp.start), const(lp.stop)
            if s is not None and e is not None:
                assert code[h - 3] == 0xB8 and struct.unpack('<h', code[h - 2:h])[0] == e, (name, idx, 'end bound mismatch')
            else:
                # bounds computed at run time: the cost per iteration does not depend on them;
                # measure 10 iterations
                s = s if s is not None else 1
                e = s - 9 if lp.down else s + 9
            cpu = fresh()
            cpu.push(s & 0xffff); cpu.r['ax'] = e & 0xffff
            cpu.ip = (cbase + h) & 0xffff
            n_iter = abs(e - s) + 1
            t0 = cpu.clock
            try:
                steps = cpu.run(exit_)
            except Halt as ex:
                # the loop does BIOS/DOS I/O (screen output, keyboard): its sounds are all paced by
                # Delay, so no CPU time is modelled for it
                print('%-8s loop %d: not measured (%s); sounds in it are paced by Delay' % (name, idx, ex))
                per.append(0); fast.append(0); continue
            cyc = (cpu.clock - t0) / n_iter
            outs = [p for p in cpu.port_log if p[1] == 0x42]
            per.append(round(cyc))
            # the same time at DOSBox's speed, in 4.77 MHz clocks (what the runtime's cpu() takes)
            fast.append(max(1, round(steps / n_iter / DOSBOX_IPMS * 4772.727)))
            print('%-8s loop %d (%d..%d, %d iterations): %.0f clocks/iteration = %.3f ms; speaker writes %d' % (
                name, idx, s, e, n_iter, cyc, cyc / 4772.727, len(outs) // 2))
        key = '#%d' % [x.name for x in prog.decls if x.k == 'proc'].index(name)
        result[key] = per; dosbox[key] = fast
    json.dump(result, open(OUT, 'w'), indent=1)
    if DOSBOX_OUT: json.dump(dosbox, open(DOSBOX_OUT, 'w'), indent=1)

if __name__ == '__main__':
    main()
