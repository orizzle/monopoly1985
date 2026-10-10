#!/usr/bin/env python3
"""Per-procedure structural comparison of a TP 3.02 build against the original MONOCODE.CHN/.000.

Both images are expanded (overlay area inserted) and split into an ordered list of items:
  hdr, raw (externals + typed consts before first proc), proc, fwd (forward jmp), desc (overlay
  descriptor + area), data (typed consts between procs), main.
Items are matched by position.  Inside procedures every code address (call/jmp target, cs:
displacement, immediate pointing into code) is mapped to (item index, offset) so a build whose
other procedures are stubs can still be checked.  DS addresses may differ by DSDELTA, runtime
targets are mapped with rtmap.  Overlay calls (mov ax,LEN / mov dx,REC / call desc) are checked
by overlay ordinal.

usage: tp3pcmp.py NEWDIR [--only P_xxxx,...|all] [--max N] [--list]
   NEWDIR contains MONOCODE.CHN and MONOCODE.000 built by tpc.py
   Procedure names are the ORIGINAL expanded addresses (P_4c33 ...), OV1..OV4 for overlays, MAIN.
"""
import sys, os, re, struct, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp3cmp, rtmap, procs
from tp3cmp import program_insns, is_ds_ref, DSDELTA, OBASE, NBASE, INL_O, INL_N

RTVARS = {(0x14a, 0x14c)}   # runtime file vars: Kbd
ORIGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'original') + os.sep


class Image:
    def __init__(self, chn_path, ovl_path, base, rtend, inline):
        raw = open(chn_path, 'rb').read()
        self.base, self.rtend, self.inline = base, rtend, inline
        self.descs = tp3cmp.find_desc(raw, base)
        self.buf = tp3cmp.expand(raw, base, self.descs)
        self.end = base + len(self.buf)
        b = self.buf
        self.main = (base + 35 + struct.unpack('<h', b[33:35])[0]) & 0xffff
        ps = procs.find_procs(b, base, 32)
        ps = [p for p in ps if p['addr'] < self.main]
        items = [('hdr', base, base + 35), ('raw', base + 35, ps[0]['addr'] if ps else self.main)]
        pos = items[-1][2]
        dstart = {a - 22: (a, s) for a, s in self.descs}
        for p in ps:
            while pos < p['addr']:
                if pos in dstart:
                    a, s = dstart[pos]
                    items.append(('desc', pos, a + s)); pos = a + s; continue
                if b[pos - base] == 0xe9 and pos + 3 <= p['addr']:
                    items.append(('fwd', pos, pos + 3)); pos += 3; continue
                nxt = min([p['addr']] + [d for d in dstart if d > pos])
                items.append(('data', pos, nxt)); pos = nxt
            items.append(('proc', p['addr'], p['end'])); pos = p['end']
        if pos < self.main: items.append(('data', pos, self.main))
        items.append(('main', self.main, self.end))
        self.items = items
        self.starts = [it[1] for it in items]
        # overlays
        self.ovl = []
        if ovl_path and os.path.exists(ovl_path):
            ov = open(ovl_path, 'rb').read(); k = 0
            while k + 7 <= len(ov):
                sz, ad = struct.unpack('<HH', ov[k+3:k+7])
                recs = ((sz + 7 + 255) // 256)
                self.ovl.append({'rec': k // 256, 'len': recs * 256, 'size': sz, 'load': ad,
                                 'bytes': ov[k:k+7+sz], 'base': ad - 7})
                k += recs * 256

    def locate(self, addr):
        """map a code address to (item index, offset) or None"""
        if not (self.base <= addr < self.end): return None
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= addr: lo = mid
            else: hi = mid - 1
        it = self.items[lo]
        if it[0] == 'desc':
            return (lo, addr - it[1]) if addr < it[1] + 22 else (lo, 'area')
        return (lo, addr - it[1])

    def ovl_ord(self, rec):
        for i, o in enumerate(self.ovl):
            if o['rec'] == rec: return i
        return None


def same_code_addr(O, N, ov, nv, oinitem=None, ninitem=None):
    lo, ln = O.locate(ov), N.locate(nv)
    if lo is None or ln is None: return False
    if lo[0] != ln[0]: return False
    it = O.items[lo[0]]
    if it[0] == 'raw':
        return ov - O.base == nv - N.base
    if it[0] in ('proc', 'main') and lo[1] == 0 and ln[1] == 0: return True
    return lo[1] == ln[1]


def cmp_code(O, N, obuf, obase, ostart, oend, nbuf, nbase, nstart, nend, maxerr=8, label='', out=print):
    oi = list(program_insns(obuf, obase, OBASE, INL_O, ostart - obase, oend - obase))
    ni = list(program_insns(nbuf, nbase, NBASE, INL_N, nstart - nbase, nend - nbase))
    errs = 0
    hist = []
    k = j = 0
    # overlay call context
    while k < len(oi) and j < len(ni):
        (oa, ob_, (oop, ot, od)), (na, nb_, (nop, nt, nd)) = oi[k], ni[j]
        ok, why = True, ''
        if oa - ostart != na - nstart:
            ok, why = False, 'misaligned (orig +%x, new +%x)' % (oa - ostart, na - nstart)
        elif ot is not None or nt is not None:
            if ot is None or nt is None or oop != nop or od != nd:
                ok, why = False, 'call/jmp shape'
            elif ot < OBASE or nt < NBASE:
                m = rtmap.n2o_near(nt) if nt < NBASE else None
                if not (ot < OBASE and nt < NBASE and m == ot):
                    ok, why = False, 'runtime target'
            elif ostart <= ot < oend or nstart <= nt < nend:
                if ot - ostart != nt - nstart:
                    ok, why = False, 'local target +%x vs +%x' % (ot - ostart, nt - nstart)
            else:
                if not same_code_addr(O, N, ot, nt):
                    # overlay-local jumps
                    if not (abs(ot - oa) < 0x4000 and ot - oa == nt - na):
                        ok, why = False, 'code target %s vs %s' % (O.locate(ot), N.locate(nt))
                # overlay dispatch check
                lo = O.locate(ot)
                if ok and lo and O.items[lo[0]][0] == 'desc' and lo[1] == 0 and k >= 2:
                    def imm(ins):
                        m = re.match(r'mov (ax|dx), (0x[0-9a-f]+|\d+)$', ins[2][0]); return int(m.group(2), 0) if m else None
                    oax, odx, nax, ndx = imm(oi[k-2]), imm(oi[k-1]), imm(ni[j-2]), imm(ni[j-1])
                    if None in (oax, odx, nax, ndx) or O.ovl_ord(odx) != N.ovl_ord(ndx) or O.ovl_ord(odx) is None:
                        ok, why = False, 'overlay call: orig ax=%s dx=%s new ax=%s dx=%s' % (oax, odx, nax, ndx)
                    else:
                        no = N.ovl[N.ovl_ord(ndx)]
                        if nax != no['len']: ok, why = False, 'overlay call length'
        elif ob_ != nb_:
            if len(ob_) != len(nb_): ok, why = False, 'length'
            else:
                p = 0
                while p < len(ob_):
                    if ob_[p] == nb_[p]: p += 1; continue
                    good = False
                    for st in (p, p - 1):
                        if st < 0 or st + 2 > len(ob_): continue
                        ov = struct.unpack('<H', ob_[st:st+2])[0]; nv = struct.unpack('<H', nb_[st:st+2])[0]
                        if nv - ov == DSDELTA and ov >= 0x260 and is_ds_ref(oop): good = True
                        elif (ov, nv) in RTVARS and is_ds_ref(oop): good = True
                        elif same_code_addr(O, N, ov, nv) and (('cs:' in oop) or re.match(r'(mov|add) (di|si|bx|ax), 0x', oop)): good = True
                        elif re.match(r'mov (ax|dx), ', oop) and k + 2 < len(oi):
                            # overlay dispatch immediates (checked at the call)
                            t = oi[k+1][2][1] if oop.startswith('mov dx') else (oi[k+2][2][1] if k + 2 < len(oi) else None)
                            lo = O.locate(t) if t else None
                            if lo and O.items[lo[0]][0] == 'desc': good = True
                        if good: p = st + 2; break
                    if not good: break
                if p < len(ob_): ok, why = False, 'bytes'
        if not ok:
            errs += 1
            out('  MISMATCH %s at orig %04x (+%x) / new %04x: %s' % (label, oa, oa - ostart, na, why))
            for h in hist[-4:]: out('        %s' % h)
            out('    O> %04x %-22s %s' % (oa, ob_.hex()[:22], oop if ot is None else '%s %04x' % (oop, ot)))
            out('    N> %04x %-22s %s' % (na, nb_.hex()[:22], nop if nt is None else '%s %04x' % (nop, nt)))
            if errs >= maxerr: return errs
            k += 1; j += 1
            while k < len(oi) and j < len(ni) and (oi[k][0] - ostart) != (ni[j][0] - nstart):
                if oi[k][0] - ostart < ni[j][0] - nstart: k += 1
                else: j += 1
            continue
        hist.append('%04x %-22s %s' % (oa, ob_.hex()[:22], oop if ot is None else '%s %04x' % (oop, ot)))
        k += 1; j += 1
    if (oend - ostart) != (nend - nstart):
        errs += 1
        out('  SIZE %s: orig %d bytes, new %d bytes' % (label, oend - ostart, nend - nstart))
    return errs


def item_name(img, idx):
    it = img.items[idx]
    if it[0] in ('proc', 'main', 'fwd', 'data', 'desc'):
        return ('P_%04x' % it[1]) if it[0] == 'proc' else ('%s_%04x' % (it[0].upper(), it[1]) if it[0] != 'main' else 'MAIN')
    return it[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('newdir')
    ap.add_argument('--only', default='all')
    ap.add_argument('--max', type=int, default=8)
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    O = Image(ORIGDIR + 'MONOCODE.CHN', ORIGDIR + 'MONOCODE.000', OBASE, OBASE, INL_O)
    N = Image(os.path.join(a.newdir, 'MONOCODE.CHN'), os.path.join(a.newdir, 'MONOCODE.000'), NBASE, NBASE, INL_N)
    if a.list:
        for i, it in enumerate(O.items):
            n = N.items[i] if i < len(N.items) else None
            print('%3d %-6s %04x-%04x  %s' % (i, it[0], it[1], it[2], ('new %s %04x-%04x' % (n[0], n[1], n[2])) if n else 'MISSING'))
        for i, o in enumerate(O.ovl):
            print('OV%d rec %02x len %04x size %d' % (i + 1, o['rec'], o['len'], o['size']))
        return
    if len(O.items) != len(N.items):
        print('ITEM COUNT DIFFERS: orig %d new %d' % (len(O.items), len(N.items)))
        for i in range(max(len(O.items), len(N.items))):
            oi = O.items[i] if i < len(O.items) else None; ni = N.items[i] if i < len(N.items) else None
            if not oi or not ni or oi[0] != ni[0]:
                print('  first difference at item %d: orig %s new %s' % (i, oi, ni)); break
        return 2
    want = None if a.only == 'all' else set(x.strip() for x in a.only.split(','))
    total = 0; checked = []
    for i, it in enumerate(O.items):
        nm = item_name(O, i)
        if want is not None and nm not in want: continue
        nt = N.items[i]
        if it[0] != nt[0]:
            print('%s: kind differs %s vs %s' % (nm, it[0], nt[0])); total += 1; continue
        if it[0] in ('proc', 'main'):
            e = cmp_code(O, N, O.buf, O.base, it[1], it[2], N.buf, N.base, nt[1], nt[2], a.max, nm)
        elif it[0] == 'fwd':
            ot = (it[1] + 3 + struct.unpack('<h', O.buf[it[1]-O.base+1:it[1]-O.base+3])[0]) & 0xffff
            ntt = (nt[1] + 3 + struct.unpack('<h', N.buf[nt[1]-N.base+1:nt[1]-N.base+3])[0]) & 0xffff
            e = 0 if same_code_addr(O, N, ot, ntt) else 1
            if e: print('  MISMATCH %s: forward target %s vs %s' % (nm, O.locate(ot), N.locate(ntt)))
        elif it[0] == 'data' or it[0] == 'raw':
            ob_ = O.buf[it[1]-O.base:it[2]-O.base]; nb_ = N.buf[nt[1]-N.base:nt[2]-N.base]
            e = 0 if ob_ == nb_ else 1
            if e:
                d = next((x for x in range(min(len(ob_), len(nb_))) if ob_[x] != nb_[x]), min(len(ob_), len(nb_)))
                print('  MISMATCH %s: data differs at +%x (orig %d bytes, new %d bytes): %s vs %s' % (nm, d, len(ob_), len(nb_), ob_[d:d+12].hex(), nb_[d:d+12].hex()))
        elif it[0] == 'desc':
            ob_ = O.buf[it[1]-O.base:it[1]-O.base+18]; nb_ = N.buf[nt[1]-N.base:nt[1]-N.base+18]
            e = 0 if ob_[3:] == nb_[3:] else 1
            if e: print('  MISMATCH %s: overlay descriptor %s vs %s' % (nm, ob_.hex(), nb_.hex()))
        else:
            e = 0
        total += e; checked.append((nm, e))
    # overlays
    for i, o in enumerate(O.ovl):
        nm = 'OV%d' % (i + 1)
        if want is not None and nm not in want: continue
        if i >= len(N.ovl):
            print('%s: missing in new build' % nm); total += 1; continue
        n = N.ovl[i]
        e = cmp_code(O, N, o['bytes'], o['base'], o['base'] + 7, o['base'] + 7 + o['size'],
                     n['bytes'], n['base'], n['base'] + 7, n['base'] + 7 + n['size'], a.max, nm)
        if o['rec'] != n['rec'] or o['load'] - O.base != n['load'] - N.base:
            print('  %s record/load differs: orig rec %x load %04x, new rec %x load %04x' % (nm, o['rec'], o['load'], n['rec'], n['load']))
            e += 1
        total += e; checked.append((nm, e))
    bad = [n for n, e in checked if e]
    print('CHECKED %d items, %d with mismatches%s' % (len(checked), len(bad), (': ' + ' '.join(bad)) if bad else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
