"""TP3-aware disassembler for the original (1985-runtime) program images."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
import rtmap, rtnames
md = Cs(CS_ARCH_X86, CS_MODE_16)
RT_END_ORIG = 0x2D7C
ORIGNAMES = {}
for a, n in rtnames.N302.items():
    o = rtmap.n2o_near(a)
    if o is not None: ORIGNAMES[o] = n
INLINE_ORIG = {rtmap.n2o(a) for a in rtnames.INLINE302}

def rel(buf, i, base):
    return (base + i + 3 + struct.unpack('<h', buf[i+1:i+3])[0]) & 0xffff

def disasm(buf, base, start=0, end=None, rtend=RT_END_ORIG, names=ORIGNAMES, inline=INLINE_ORIG, labels=None):
    """Yield (addr, bytes, text). Handles inline strings after WrStrLit/StrLit."""
    end = len(buf) if end is None else end
    i = start
    labels = labels or {}
    while i < end:
        a = base + i
        ins = next(md.disasm(buf[i:i+8], a), None)
        if ins is None:
            yield a, buf[i:i+1], 'db 0x%02x' % buf[i]; i += 1; continue
        txt = ins.mnemonic + ' ' + ins.op_str
        if ins.mnemonic in ('call', 'jmp') and buf[i] in (0xe8, 0xe9):
            t = rel(buf, i, base)
            if t < rtend:
                nm = names.get(t, 'RT_%04x' % t)
                txt = '%s %s' % (ins.mnemonic, nm)
                if t in inline:
                    n = buf[i+3]
                    s = buf[i+4:i+4+n]
                    yield a, buf[i:i+4+n], "%s %r" % (txt, s.decode('latin1'))
                    i += 4 + n; continue
            else:
                txt = '%s %s' % (ins.mnemonic, labels.get(t, 'L_%04x' % t))
        yield a, bytes(ins.bytes), txt
        i += ins.size
