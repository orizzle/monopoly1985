"""Annotated listings of the original program: chn.lst, ovl.lst, com.lst"""
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp3cmp, tp3dis, procs
O = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'original') + os.sep
OUT = os.environ.get('LISTINGS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'an'))
os.makedirs(OUT, exist_ok=True)
names = tp3dis.ORIGNAMES
ob, od = tp3cmp.load_chn(O + 'MONOCODE.CHN', 0x2d7c)
B = 0x2d7c
ps = procs.find_procs(ob, B, 0x4c33 - B)
pstart = {p['addr']: p for p in ps}
desc_after = od[0][0]
def fmt_insn(a, b, op, t, dat, base_desc=None):
    if t is not None:
        if t < 0x2d7c:
            nm = names.get(t, 'RT_%04x' % t)
            s = '%s %s' % (op, nm)
            if dat is not None: s += ' %r' % dat.decode('latin1')
            return s
        if t in pstart: return '%s P_%04x' % (op, t)
        if base_desc and t == base_desc: return '%s OVERLAY_DISPATCH' % op
        return '%s L_%04x' % (op, t)
    return op
def listing(buf, base, start, end, out, desc=None):
    for a, b, (op, t, dat) in tp3cmp.program_insns(buf, base, 0x2d7c, tp3cmp.INL_O, start, end):
        if a in pstart:
            p = pstart[a]
            out.write('\n;==== PROC P_%04x  args=%d locals=%d end=%04x\n' % (a, p['argbytes'], p['locals'], p['end']))
        out.write('%04x: %-22s %s\n' % (a, b.hex()[:22], fmt_insn(a, b, op, t, dat, desc)))
with open(os.path.join(OUT, 'chn.lst'), 'w') as f:
    # tconst regions dumped as hex
    listing(ob, B, 0x4c33 - B, 0xaacd - B, f, 0xaacd)
    f.write('\n;==== OVERLAY DESCRIPTOR aacd: %s\n;==== overlay area aae3..%04x (expanded)\n' % (ob[0xaacd-B:0xaae3-B].hex(), desc_after + od[0][1]))
    st = desc_after + od[0][1]
    # procs after area until tconst block
    listing(ob, B, st - B, 0xab1d + 0xbfc - B, f, 0xaacd)
    f.write('\n;==== TYPED CONST BLOCK %04x..%04x (cards)\n' % (0xab1d + 0xbfc, 0xc23d + 0xbfc))
    listing(ob, B, 0xc23d + 0xbfc - B, len(ob), f, 0xaacd)
ov = open(O + 'MONOCODE.000', 'rb').read()
with open(os.path.join(OUT, 'ovl.lst'), 'w') as f:
    k = 0
    while k < len(ov):
        sz, ad = struct.unpack("<HH", ov[k+3:k+7]); base = ad - 7
        f.write('\n;######## OVERLAY RECORD @%05x size=%d load=%04x\n' % (k, sz, base))
        rec = ov[k:k+7+sz]
        sub = procs.find_procs(rec, base, 7)
        for p in sub: pstart[p['addr']] = p
        listing(rec, base, 7, 7 + sz, f, 0xaacd)
        for p in sub: del pstart[p['addr']]
        k += ((sz + 7 + 255) // 256) * 256
com = open(O + 'monopoly.com', 'rb').read()[0x2c7c:]
cps = procs.find_procs(com, B, 0x20)
saved = dict(pstart); pstart.clear(); pstart.update({p['addr']: p for p in cps})
with open(os.path.join(OUT, 'com.lst'), 'w') as f:
    listing(com, B, 0x1e, len(com), f)
print('ok', len(ps))
