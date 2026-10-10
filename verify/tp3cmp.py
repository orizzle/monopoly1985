#!/usr/bin/env python3
"""Compare a TP 3.02-compiled program image against the original 1985 image.
Normalises: runtime call targets (via rtmap), program base (0x2D7C vs 0x2D4D),
overlay-area expansion after each overlay-group descriptor.
usage: tp3cmp.py ORIG NEW [--kind chn|com|ovl] [--max N] [--ctx N] [--from ADDR] [--to ADDR]"""
import sys, os, struct, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
import rtmap, rtnames, tp3dis
md = Cs(CS_ARCH_X86, CS_MODE_16)
OBASE, NBASE = 0x2D7C, 0x2D4D
INL_O = tp3dis.INLINE_ORIG; INL_N = set(rtnames.INLINE302)
FIX_N = dict(rtnames.INLINE_FIXED302)
FIX_O = {rtmap.n2o_near(a): n for a, n in FIX_N.items()}
DSDELTA = 2   # TP 3.02 starts user globals at DS:0262, the 1985 compiler at DS:0260
def is_ds_ref(op):
    if 'cs:' in op or 'es:' in op or 'ss:' in op: return False
    if '[' in op: return 'bp' not in op.split('[', 1)[1]
    return re.match(r'(mov|lea|add) (di|si|bx), 0x', op) is not None

def find_desc(buf, base):
    """overlay group descriptors: E8 rel16 FF FF name[13] w1 w2  -> list of (addr_after_desc, shift)"""
    out = []
    for m in re.finditer(rb'\xe8..\xff\xff[\x20-\x7e]{1,12}', buf, re.S):
        i = m.start()
        w1, w2 = struct.unpack('<HH', buf[i+18:i+22])
        after = base + i + 22
        sh = w2 - after - sum(s for _, s in out)
        if 0 < sh < 0x8000 and sh % 256 == 0xFC:
            out.append((after, sh))
    return out

def expand(buf, base, descs):
    """Insert overlay areas: returns expanded bytes (filled with None marker 0x00)."""
    res = bytearray(); last = 0
    for after, sh in descs:
        i = after - base
        res += buf[last:i] + bytes(sh); last = i
    res += buf[last:]
    return bytes(res)

def program_insns(buf, base, rtend, inline, start=0, end=None):
    end = len(buf) if end is None else end
    i = start
    while i < end:
        a = base + i
        b0 = buf[i]
        if b0 in (0xe8, 0xe9) and i + 3 <= len(buf):
            t = (a + 3 + struct.unpack('<h', buf[i+1:i+3])[0]) & 0xffff
            fx = (FIX_N if rtend == 0x2D4D else FIX_O).get(t) if t < rtend else None
            if fx:
                yield a, buf[i:i+3+fx], ('call', t, buf[i+3:i+3+fx]); i += 3 + fx; continue
            if t < rtend and t in inline:
                n = buf[i+3]
                yield a, buf[i:i+4+n], ('call', t, buf[i+4:i+4+n]); i += 4 + n; continue
            yield a, buf[i:i+3], ('call' if b0 == 0xe8 else 'jmp', t, None); i += 3; continue
        ins = next(md.disasm(buf[i:i+8], a), None)
        if ins is None:
            yield a, buf[i:i+1], ('db', None, None); i += 1; continue
        yield a, bytes(ins.bytes), (ins.mnemonic + ' ' + ins.op_str, None, None)
        i += ins.size

def compare(ob, nb, obase=OBASE, nbase=NBASE, maxerr=10, ctx=3, lo=None, hi=None, quiet=False):
    """ob/nb are expanded images. Returns list of mismatches."""
    delta = obase - nbase
    oend = obase + len(ob); nend = nbase + len(nb)
    oi = list(program_insns(ob, obase, OBASE, INL_O, 32))
    ni = list(program_insns(nb, nbase, NBASE, INL_N, 32))
    errs = []
    fo = ob.find(b'\x55\x8b\xec\x55\xe9', 32); fn = nb.find(b'\x55\x8b\xec\x55\xe9', 32)
    if ob[32+3:fo] != nb[32+3:fn] and (hi is None or hi > obase + 35):
        d = next((x for x in range(min(fo, fn) - 35) if ob[35+x] != nb[35+x]), None)
        errs.append((obase+35, nbase+35, 'raw prefix (externals/typed consts) differs at +%s; sizes %d vs %d' % (hex(35+d) if d is not None else '?', fo, fn), [], None, None))
        if not quiet: print('MISMATCH:', errs[-1][2])
    oi = [x for x in oi if x[0] - obase >= fo or x[0] - obase < 35]
    ni = [x for x in ni if x[0] - nbase >= fn or x[0] - nbase < 35]
    k = 0
    hist = []
    j = 0
    while k < len(oi) and j < len(ni):
        (oa, obytes, (oop, ot, odat)), (na, nbytes, (nop, nt, ndat)) = oi[k], ni[j]
        if oa - obase < 32: k += 1; j += 1; continue
        if lo is not None and oa < lo: k += 1; j += 1; continue
        if hi is not None and oa >= hi: break
        ok = True; why = ''
        if oa - obase != na - nbase:
            ok = False; why = 'misaligned'
        elif ot is not None or nt is not None:
            if ot is None or nt is None or oop != nop or (odat != ndat):
                ok = False; why = 'call/jmp shape'
            else:
                if ot < OBASE or nt < NBASE:
                    m = rtmap.n2o_near(nt) if nt < NBASE else None
                    if ot >= OBASE or nt >= NBASE or m != ot:
                        ok = False; why = 'runtime target %04x vs new %04x(->%s)' % (ot, nt, hex(m) if m else None)
                elif ot - obase != nt - nbase:
                    ok = False; why = 'program target %04x vs %04x' % (ot, nt + delta)
        elif obytes != nbytes:
            if len(obytes) != len(nbytes): ok = False; why = 'length'
            else:
                # allow 16-bit fields differing by exactly delta pointing into program
                p = 0; ok2 = True
                while p < len(obytes):
                    if obytes[p] != nbytes[p]:
                        if p + 1 < len(obytes) + 1 and p + 2 <= len(obytes):
                            ov = struct.unpack('<H', obytes[p:p+2])[0]; nv = struct.unpack('<H', nbytes[p:p+2])[0]
                            if ov - nv == delta and nbase <= nv <= nend: p += 2; continue
                        if p >= 1:
                            ov = struct.unpack('<H', obytes[p-1:p+1])[0]; nv = struct.unpack('<H', nbytes[p-1:p+1])[0]
                            if ov - nv == delta and nbase <= nv <= nend: p += 1; continue
                        if p + 2 <= len(obytes):
                            ov = struct.unpack('<H', obytes[p:p+2])[0]; nv = struct.unpack('<H', nbytes[p:p+2])[0]
                            if nv - ov == DSDELTA and ov >= 0x260 and is_ds_ref(oop): p += 2; continue
                        if p >= 1:
                            ov = struct.unpack('<H', obytes[p-1:p+1])[0]; nv = struct.unpack('<H', nbytes[p-1:p+1])[0]
                            if nv - ov == DSDELTA and ov >= 0x260 and is_ds_ref(oop): p += 1; continue
                        ok2 = False; break
                    p += 1
                if not ok2: ok = False; why = 'bytes'
        if not ok:
            errs.append((oa, na, why, hist[-ctx:], (oa, obytes, oop), (na, nbytes, nop)))
            if not quiet:
                print('MISMATCH at orig %04x / new %04x (+%04x): %s' % (oa, na, oa - obase, why))
                for h in hist[-ctx:]: print('      %04x: %-20s %s' % h)
                print('  O > %04x: %-20s %s' % (oa, obytes.hex()[:20], oop if ot is None else '%s %04x' % (oop, ot)))
                print('  N > %04x: %-20s %s' % (na, nbytes.hex()[:20], nop if nt is None else '%s %04x' % (nop, nt)))
            if len(errs) >= maxerr: break
            # resync: advance both by bytes
            k += 1; j += 1
            while k < len(oi) and j < len(ni) and (oi[k][0] - obase) != (ni[j][0] - nbase):
                if oi[k][0] - obase < ni[j][0] - nbase: k += 1
                else: j += 1
            continue
        hist.append((oa, obytes.hex()[:20], oop if ot is None else '%s %04x' % (oop, ot)))
        k += 1; j += 1
    if len(ob) != len(nb) and not quiet and (hi is None):
        print('LENGTH: orig %d new %d (expanded)' % (len(ob), len(nb)))
    return errs

def load_chn(path, base):
    b = open(path, 'rb').read()
    d = find_desc(b, base)
    return expand(b, base, d), d

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('orig'); ap.add_argument('new')
    ap.add_argument('--com', action='store_true', help='inputs are .COM files; compare program part')
    ap.add_argument('--max', type=int, default=10); ap.add_argument('--ctx', type=int, default=4)
    ap.add_argument('--lo', type=lambda x: int(x, 16)); ap.add_argument('--hi', type=lambda x: int(x, 16))
    a = ap.parse_args()
    if a.com:
        ob = open(a.orig, 'rb').read()[OBASE - 0x100:]; nb = open(a.new, 'rb').read()[NBASE - 0x100:]
        od = find_desc(ob, OBASE); nd = find_desc(nb, NBASE)
        ob = expand(ob, OBASE, od); nb = expand(nb, NBASE, nd)
    else:
        ob, od = load_chn(a.orig, OBASE); nb, nd = load_chn(a.new, NBASE)
    print('descs orig', [(hex(x), hex(y)) for x, y in od], 'new', [(hex(x), hex(y)) for x, y in nd])
    oh = struct.unpack('<8H', ob[3:19]); nh = struct.unpack('<8H', nb[3:19])
    hdr_ok = (oh[0] == nh[0] and oh[3] - 0x2D8 == nh[3] - 0x2D5 and oh[4:] == nh[4:]
              and ob[19:25] == nb[19:25] and ob[28:30] == nb[28:30]
              and struct.unpack('<H', ob[30:32])[0] - struct.unpack('<H', nb[30:32])[0] == OBASE - NBASE)
    print('header orig', [hex(x) for x in oh], 'new', [hex(x) for x in nh], 'semantic match' if hdr_ok else 'HEADER DIFFERS')
    e = compare(ob, nb, maxerr=a.max, ctx=a.ctx, lo=a.lo, hi=a.hi)
    print('RESULT:', 'IDENTICAL (normalised)' if not e else '%d mismatches shown' % len(e))
