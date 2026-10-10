#!/usr/bin/env python3
"""Relocate a TP 3.02-compiled program onto the 1985 TP 3.0x runtime layout.

The two compilers differ only in their runtime library, so a TP 3.02 build of the same source
differs from the 1985 build in exactly these places:
  * the runtime library itself (copied verbatim from the 1985 file for .COM output),
  * calls/jumps into the runtime          -> remapped routine by routine (rtmap, rtnames),
  * program code addresses (CS)           -> +0x2F (1985 runtime is 0x2F bytes longer),
  * global data addresses (DS)            -> -2   (1985 compiler starts user data at DS:0260),
  * two compiler-version constants and the runtime-size paragraph count in the program header.
Nothing in this tool looks at the original program image; it only applies the rules above.
The result can then be compared byte-for-byte (cmp) with the original files.

usage: relocate.py com  NEW.COM  OUT.COM          (runtime taken from the 1985 loader)
       relocate.py chn  NEW.CHN  NEW.000 OUT.CHN OUT.000
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
import rtmap, rtnames, tp3cmp, procs

md = Cs(CS_ARCH_X86, CS_MODE_16)
OBASE, NBASE = 0x2D7C, 0x2D4D
CSD = OBASE - NBASE          # +0x2F
DSD = -2
RT1985 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'original', 'monopoly.com')
HDR_CONST_1985 = (0x30F4, 0x3AB4)   # header words 2,3 written by the 1985 compiler
RT_PARA_1985, RT_PARA_302 = 0x2D8, 0x2D5


def rt_map(t):
    m = rtmap.n2o_near(t)
    if m is None: raise SystemExit('no runtime mapping for %04x' % t)
    return m


def reloc_code(buf, nbase, start, end, code_lo, code_hi):
    """Relocate instructions in buf[start:end] (buf offsets; buf loaded at nbase). In place on a bytearray."""
    i = start
    out_base = nbase + CSD
    while i < end:
        a = nbase + i
        b0 = buf[i]
        if b0 in (0xe8, 0xe9) and i + 3 <= end:
            t = (a + 3 + struct.unpack('<h', buf[i+1:i+3])[0]) & 0xffff
            if t < NBASE:
                o = rt_map(t)
                rel = (o - (a + CSD + 3)) & 0xffff
                buf[i+1:i+3] = struct.pack('<H', rel)
                if t in rtnames.INLINE302:
                    i += 4 + buf[i+3]; continue
                if t in rtnames.INLINE_FIXED302:
                    i += 3 + rtnames.INLINE_FIXED302[t]; continue
            i += 3; continue
        ins = next(md.disasm(bytes(buf[i:i+8]), a), None)
        if ins is None: i += 1; continue
        op = ins.mnemonic + ' ' + ins.op_str
        n = ins.size
        # memory displacement (16-bit) fields
        m = re.search(r'(cs:|es:|ss:)?\[([a-z +]*?)(?:\s*\+\s*)?(0x[0-9a-f]+)\]', op)
        if m and n >= 3:
            seg, regs, disp = m.group(1), m.group(2), int(m.group(3), 16)
            if 'bp' not in regs and seg != 'es:' and seg != 'ss:' and disp >= 0x100:
                newv = disp + (CSD if seg == 'cs:' else DSD)
                p = bytes(buf[i:i+n]).find(struct.pack('<H', disp))
                if p > 0: buf[i+p:i+p+2] = struct.pack('<H', newv & 0xffff)
        mi = re.match(r'(mov|add) (di|si|bx), (0x[0-9a-f]+)$', op)
        # only 16-bit immediate encodings (mov r16,imm16 = B8+r; add r16,imm16 = 81 /0) carry addresses;
        # 'add di, imm8' (83 /0) after 'les di' is a field offset inside a var-parameter record
        if mi and not ((buf[i] in (0xbb, 0xbe, 0xbf) and n == 3) or (buf[i] == 0x81 and n == 4)):
            mi = None
        if mi:
            v = int(mi.group(3), 16)
            # look at the following 'push' (ds/cs/ss) to decide segment
            nxt = next(md.disasm(bytes(buf[i+n:i+n+1]), a + n), None)
            seg = nxt.op_str if nxt is not None and nxt.mnemonic == 'push' else None
            if seg == 'cs' or (seg is None and code_lo <= v < code_hi):
                newv = v + CSD
            else:
                newv = v + DSD
            buf[i+n-2:i+n] = struct.pack('<H', newv & 0xffff)
        i += n


def code_regions(buf, base):
    """(start,end) buffer ranges holding code: every procedure and the main program."""
    main = (base + 35 + struct.unpack('<h', buf[33:35])[0]) & 0xffff
    first = buf.find(b'\x55\x8b\xec\x55\xe9', 35)
    ps = procs.find_procs(buf, base, 35)
    regs = [(p['addr'] - base, p['end'] - base) for p in ps if p['addr'] < main]
    # forward jumps between procedures
    regs += [(main - base, len(buf))]
    return regs, first


def reloc_header(buf):
    h = list(struct.unpack('<8H', bytes(buf[3:19])))
    h[1], h[2] = HDR_CONST_1985
    h[3] = h[3] - RT_PARA_302 + RT_PARA_1985
    buf[3:19] = struct.pack('<8H', *h)
    # call RT_Init / RT_InitData
    for off in (0, 25):
        t = (NBASE + off + 3 + struct.unpack('<h', buf[off+1:off+3])[0]) & 0xffff
        buf[off+1:off+3] = struct.pack('<H', (rt_map(t) - (OBASE + off + 3)) & 0xffff)
    w = struct.unpack('<H', bytes(buf[30:32]))[0]
    buf[30:32] = struct.pack('<H', w + CSD)


def reloc_program(raw, descs_unused=None):
    """raw: program part (from runtime end) of a TP 3.02 image, unexpanded. Returns relocated bytes."""
    buf = bytearray(raw)
    descs = tp3cmp.find_desc(bytes(buf), NBASE)
    exp = bytearray(tp3cmp.expand(bytes(buf), NBASE, descs))
    reloc_header(exp)
    regs, first = code_regions(exp, NBASE)
    code_lo, code_hi = NBASE, NBASE + len(exp)
    for s, e in regs:
        reloc_code(exp, NBASE, s, e, code_lo, code_hi)
    # forward jmps and overlay descriptors live between procedures: rel16 program targets need no change;
    # descriptor: call to runtime + end-of-area address word
    for after, sh in descs:
        d = after - 22 - NBASE
        t = (NBASE + d + 3 + struct.unpack('<h', exp[d+1:d+3])[0]) & 0xffff
        exp[d+1:d+3] = struct.pack('<H', (rt_map(t) - (NBASE + d + CSD + 3)) & 0xffff)
        w2 = struct.unpack('<H', bytes(exp[d+20:d+22]))[0]
        exp[d+20:d+22] = struct.pack('<H', w2 + CSD)
    # collapse the overlay areas again
    out = bytearray(); last = 0; shift = 0
    for after, sh in descs:
        i = after - NBASE + shift
        out += exp[last:i]; last = i + sh; shift += sh
    out += exp[last:]
    return bytes(out)


def reloc_overlays(ov):
    buf = bytearray(ov); k = 0
    while k + 7 <= len(buf):
        sz, ad = struct.unpack('<HH', bytes(buf[k+3:k+7]))
        base = ad - 7
        t = (base + 3 + struct.unpack('<h', buf[k+1:k+3])[0]) & 0xffff
        buf[k+1:k+3] = struct.pack('<H', (rt_map(t) - (base + CSD + 3)) & 0xffff)
        buf[k+5:k+7] = struct.pack('<H', ad + CSD)
        rec = buf[k:k+7+sz]
        ps = procs.find_procs(bytes(rec), base, 7)
        reloc_code(rec, base, 7, 7 + sz, NBASE, 0xffff)
        buf[k:k+7+sz] = rec
        k += ((sz + 7 + 255) // 256) * 256
    return bytes(buf)


def main():
    mode = sys.argv[1]
    if mode == 'com':
        new = open(sys.argv[2], 'rb').read()
        rt = open(RT1985, 'rb').read()[:OBASE - 0x100]
        prog = reloc_program(new[NBASE - 0x100:])
        open(sys.argv[3], 'wb').write(rt + prog)
    elif mode == 'chn':
        new = open(sys.argv[2], 'rb').read()
        open(sys.argv[4], 'wb').write(reloc_program(new))
        if os.path.exists(sys.argv[3]):
            open(sys.argv[5], 'wb').write(reloc_overlays(open(sys.argv[3], 'rb').read()))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
