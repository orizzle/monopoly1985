#!/usr/bin/env python3
"""Small 8086 interpreter with an Intel 8088 timing model, used to measure how long the ORIGINAL
machine code of the game's sound loops takes on an IBM PC (8088 at 4.77 MHz).

Timing model
  * execution-unit (EU) clocks per instruction from Intel's 8086/8088 data sheet, including the
    effective-address (EA) calculation clocks and +4 clocks per 16-bit memory transfer on the
    8-bit 8088 bus;
  * bus-interface unit: 4-byte prefetch queue, one byte fetched per 4 clocks while the bus is not
    used by the EU; the EU waits when the queue does not hold the next instruction's bytes;
    jumps, calls and returns flush the queue.
This is the standard first-order 8088 model; it is an estimate (typically within ~10% of real
hardware), not a cycle-exact simulation of the bus.
"""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM

MD = Cs(CS_ARCH_X86, CS_MODE_16); MD.detail = True

REG16 = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']
REG8 = {'al': (0, 0), 'cl': (1, 0), 'dl': (2, 0), 'bl': (3, 0), 'ah': (0, 8), 'ch': (1, 8), 'dh': (2, 8), 'bh': (3, 8)}
SEGS = ['es', 'cs', 'ss', 'ds']

class Halt(Exception): pass

class CPU:
    def __init__(self):
        self.mem = bytearray(1 << 20)
        self.r = {n: 0 for n in REG16}
        self.s = {n: 0 for n in SEGS}
        self.ip = 0
        self.cf = self.zf = self.sf = self.of = self.df = 0
        self.clock = 0          # 8088 clocks
        self.queue = 0          # bytes in the prefetch queue
        self.port_log = []      # (clock, port, value)
        self.skip = {}          # near-call targets to skip (address -> cycles charged, e.g. Delay = 0)
        self.decode_cache = {}

    # -------------------------------------------------------------- registers / memory
    def get(self, name):
        if name in self.r: return self.r[name]
        if name in REG8:
            i, sh = REG8[name]; return (self.r[REG16[i]] >> sh) & 0xff
        if name in self.s: return self.s[name]
        raise KeyError(name)
    def put(self, name, v):
        if name in self.r: self.r[name] = v & 0xffff; return
        if name in REG8:
            i, sh = REG8[name]; n = REG16[i]
            self.r[n] = (self.r[n] & (0xff00 >> sh)) | ((v & 0xff) << sh); return
        if name in self.s: self.s[name] = v & 0xffff; return
        raise KeyError(name)
    def lin(self, seg, off): return ((self.s[seg] << 4) + (off & 0xffff)) & 0xfffff
    def rb(self, seg, off): return self.mem[self.lin(seg, off)]
    def rw(self, seg, off): return self.rb(seg, off) | (self.rb(seg, off + 1) << 8)
    def wb(self, seg, off, v): self.mem[self.lin(seg, off)] = v & 0xff
    def ww(self, seg, off, v): self.wb(seg, off, v); self.wb(seg, off + 1, v >> 8)
    def push(self, v): self.r['sp'] = (self.r['sp'] - 2) & 0xffff; self.ww('ss', self.r['sp'], v)
    def pop(self):
        v = self.rw('ss', self.r['sp']); self.r['sp'] = (self.r['sp'] + 2) & 0xffff; return v

    # -------------------------------------------------------------- operands
    def ea(self, op, ins):
        m = op.mem
        base = ins.reg_name(m.base) if m.base else None
        idx = ins.reg_name(m.index) if m.index else None
        off = m.disp
        if base: off += self.get(base)
        if idx: off += self.get(idx)
        seg = ins.reg_name(m.segment) if m.segment else ('ss' if base == 'bp' else 'ds')
        # EA clocks
        if base and idx:
            c = 7 if (base, idx) in (('bp', 'di'), ('bx', 'si')) else 8
            if m.disp: c += 4
        elif base or idx:
            c = 9 if m.disp else 5
        else:
            c = 6
        if m.segment: c += 2
        return seg, off & 0xffff, c
    def rd(self, op, ins, size):
        if op.type == X86_OP_REG: return self.get(ins.reg_name(op.reg))
        if op.type == X86_OP_IMM: return op.imm & (0xffff if size == 2 else 0xff)
        seg, off, _ = self.ea(op, ins)
        return self.rw(seg, off) if size == 2 else self.rb(seg, off)
    def wr(self, op, ins, size, v):
        if op.type == X86_OP_REG: self.put(ins.reg_name(op.reg), v); return
        seg, off, _ = self.ea(op, ins)
        if size == 2: self.ww(seg, off, v)
        else: self.wb(seg, off, v)

    # -------------------------------------------------------------- flags
    def szp(self, v, size):
        m = 0xffff if size == 2 else 0xff
        v &= m
        self.zf = int(v == 0); self.sf = int(bool(v & (0x8000 if size == 2 else 0x80)))
        return v
    def flags_word(self):
        return (self.cf | (self.zf << 6) | (self.sf << 7) | (self.df << 10) | (self.of << 11) | 0xf002)
    def set_flags_word(self, w):
        self.cf = w & 1; self.zf = (w >> 6) & 1; self.sf = (w >> 7) & 1; self.df = (w >> 10) & 1; self.of = (w >> 11) & 1

    # -------------------------------------------------------------- timing helpers
    def account(self, eu, length, mem_bytes, flush):
        """advance the clock for one instruction: EU clocks + waits for code bytes"""
        need = max(0, length - self.queue)          # bytes the BIU still has to fetch
        wait = need * 4
        self.clock += wait + eu
        # while the EU executes, the BIU refills the queue in clocks not used for memory transfers
        free = max(0, eu - mem_bytes * 4)
        self.queue = max(0, self.queue - length + need)
        self.queue = min(4, self.queue + free // 4)
        if flush: self.queue = 0

    # -------------------------------------------------------------- execution
    def step(self):
        a = self.lin('cs', self.ip)
        key = a
        ins = self.decode_cache.get(key)
        if ins is None:
            ins = next(MD.disasm(bytes(self.mem[a:a + 8]), self.ip))
            self.decode_cache[key] = ins
        m = ins.mnemonic; ops = ins.operands; L = ins.size
        nxt = (self.ip + L) & 0xffff
        size = 2
        if ops and ops[0].size == 1: size = 1
        memop = any(o.type == X86_OP_MEM for o in ops)
        eac = 0
        if memop:
            for o in ops:
                if o.type == X86_OP_MEM: eac = self.ea(o, ins)[2]
        wpen = 4 if size == 2 else 0                # extra 8088 clocks for a 16-bit memory transfer
        flush = False; mem_bytes = 0
        prefix_rep = ins.prefix[0] in (0xf2, 0xf3)
        self.ip = nxt

        def alu_time(dst, src):
            if dst.type == X86_OP_REG and src.type == X86_OP_REG: return 3, 0
            if dst.type == X86_OP_REG and src.type == X86_OP_MEM: return 9 + eac + wpen, size
            if dst.type == X86_OP_MEM and src.type == X86_OP_REG: return 16 + eac + 2 * wpen, 2 * size
            if dst.type == X86_OP_REG and src.type == X86_OP_IMM: return 4, 0
            return 17 + eac + 2 * wpen, 2 * size
        if m in ('add', 'adc', 'sub', 'sbb', 'cmp', 'and', 'or', 'xor', 'test'):
            d, s = ops
            x = self.rd(d, ins, size); y = self.rd(s, ins, size)
            if s.type == X86_OP_IMM and s.size != d.size: y &= 0xffff if size == 2 else 0xff
            mask = 0xffff if size == 2 else 0xff; top = 0x8000 if size == 2 else 0x80
            if m in ('add', 'adc'):
                c = self.cf if m == 'adc' else 0
                r = x + y + c; self.cf = int(r > mask)
                self.of = int(bool((~(x ^ y) & (x ^ r)) & top))
            elif m in ('sub', 'sbb', 'cmp'):
                c = self.cf if m == 'sbb' else 0
                r = x - y - c; self.cf = int(r < 0)
                self.of = int(bool(((x ^ y) & (x ^ r)) & top))
            else:
                r = {'and': x & y, 'test': x & y, 'or': x | y, 'xor': x ^ y}[m]; self.cf = self.of = 0
            r = self.szp(r, size)
            if m not in ('cmp', 'test'): self.wr(d, ins, size, r)
            eu, mb = alu_time(d, s)
            if m in ('cmp', 'test') and d.type == X86_OP_MEM: eu -= 7 + wpen; mb = size
            if d.type == X86_OP_REG and s.type == X86_OP_IMM and ins.reg_name(d.reg) in ('ax', 'al'): eu = 4
        elif m == 'mov':
            d, s = ops
            v = self.rd(s, ins, size); self.wr(d, ins, size, v)
            if d.type == X86_OP_REG and s.type == X86_OP_REG: eu, mb = 2, 0
            elif d.type == X86_OP_REG and s.type == X86_OP_IMM: eu, mb = 4, 0
            elif d.type == X86_OP_REG and s.type == X86_OP_MEM:
                eu = (10 + wpen) if (ins.reg_name(d.reg) in ('ax', 'al') and not ops[1].mem.base and not ops[1].mem.index) else 8 + eac + wpen; mb = size
            elif d.type == X86_OP_MEM and s.type == X86_OP_REG:
                eu = (10 + wpen) if (ins.reg_name(s.reg) in ('ax', 'al') and not d.mem.base and not d.mem.index) else 9 + eac + wpen; mb = size
            else: eu, mb = 10 + eac + wpen, size
            if d.type == X86_OP_REG and ins.reg_name(d.reg) in SEGS or s.type == X86_OP_REG and ins.reg_name(s.reg) in SEGS:
                eu = 2 if (d.type == X86_OP_REG and s.type == X86_OP_REG) else 8 + eac + 4
        elif m in ('inc', 'dec'):
            d = ops[0]; x = self.rd(d, ins, size)
            r = x + (1 if m == 'inc' else -1); top = 0x8000 if size == 2 else 0x80
            self.of = int((m == 'inc' and (x & (top * 2 - 1)) == top - 1) or (m == 'dec' and (x & (top * 2 - 1)) == top))
            self.wr(d, ins, size, self.szp(r, size))
            eu, mb = (2 if size == 2 else 3, 0) if d.type == X86_OP_REG else (15 + eac + 2 * wpen, 2 * size)
        elif m in ('neg', 'not'):
            d = ops[0]; x = self.rd(d, ins, size); mask = 0xffff if size == 2 else 0xff
            if m == 'neg':
                r = (-x) & mask; self.cf = int(x != 0); self.of = int(x == (mask + 1) >> 1); self.szp(r, size)
            else: r = (~x) & mask
            self.wr(d, ins, size, r)
            eu, mb = (3, 0) if d.type == X86_OP_REG else (16 + eac + 2 * wpen, 2 * size)
        elif m in ('shl', 'sal', 'shr', 'sar', 'rol', 'ror', 'rcl', 'rcr'):
            d = ops[0]
            n = 1 if len(ops) == 1 or (ops[1].type == X86_OP_IMM and ops[1].imm == 1) else (self.get('cl') if ops[1].type == X86_OP_REG else ops[1].imm)
            x = self.rd(d, ins, size); bits = 16 if size == 2 else 8; mask = (1 << bits) - 1
            for _ in range(n & 0x1f):
                if m in ('shl', 'sal'): self.cf = (x >> (bits - 1)) & 1; x = (x << 1) & mask
                elif m == 'shr': self.cf = x & 1; x >>= 1
                elif m == 'sar': self.cf = x & 1; x = (x >> 1) | (x & (1 << (bits - 1)))
                elif m == 'rol': self.cf = (x >> (bits - 1)) & 1; x = ((x << 1) | self.cf) & mask
                elif m == 'ror': self.cf = x & 1; x = (x >> 1) | (self.cf << (bits - 1))
                elif m == 'rcl': c = (x >> (bits - 1)) & 1; x = ((x << 1) | self.cf) & mask; self.cf = c
                elif m == 'rcr': c = x & 1; x = (x >> 1) | (self.cf << (bits - 1)); self.cf = c
            if m in ('shl', 'sal', 'shr', 'sar') and n: self.szp(x, size)
            self.wr(d, ins, size, x)
            if len(ops) == 1 or (ops[1].type == X86_OP_IMM and ops[1].imm == 1):
                eu, mb = (2, 0) if d.type == X86_OP_REG else (15 + eac + 2 * wpen, 2 * size)
            else:
                eu, mb = (8 + 4 * n, 0) if d.type == X86_OP_REG else (20 + eac + 2 * wpen + 4 * n, 2 * size)
        elif m in ('mul', 'imul', 'div', 'idiv'):
            s = ops[0]; v = self.rd(s, ins, size)
            if size == 1:
                al = self.get('al'); ax = self.get('ax')
                if m == 'mul': r = al * v; self.put('ax', r); self.cf = self.of = int(r > 0xff); eu = 74
                elif m == 'imul':
                    sa = al - 256 if al & 0x80 else al; sv = v - 256 if v & 0x80 else v
                    r = sa * sv; self.put('ax', r); self.cf = self.of = int(not -128 <= r <= 127); eu = 89
                elif m == 'div':
                    if v == 0: raise Halt('divide by zero')
                    q, rr = divmod(ax, v); self.put('al', q); self.put('ah', rr); eu = 85
                else:
                    sa = ax - 65536 if ax & 0x8000 else ax; sv = v - 256 if v & 0x80 else v
                    q = int(sa / sv); rr = sa - q * sv; self.put('al', q); self.put('ah', rr); eu = 106
            else:
                ax = self.get('ax'); dx = self.get('dx')
                if m == 'mul': r = ax * v; self.put('ax', r); self.put('dx', r >> 16); self.cf = self.of = int((r >> 16) != 0); eu = 126
                elif m == 'imul':
                    sa = ax - 65536 if ax & 0x8000 else ax; sv = v - 65536 if v & 0x8000 else v
                    r = sa * sv; self.put('ax', r); self.put('dx', r >> 16); self.cf = self.of = int(not -32768 <= r <= 32767); eu = 141
                elif m == 'div':
                    if v == 0: raise Halt('divide by zero')
                    n_ = (dx << 16) | ax; q, rr = divmod(n_, v)
                    if q > 0xffff: raise Halt('divide overflow')
                    self.put('ax', q); self.put('dx', rr); eu = 153
                else:
                    n_ = (dx << 16) | ax; n_ = n_ - (1 << 32) if n_ & 0x80000000 else n_
                    sv = v - 65536 if v & 0x8000 else v
                    q = int(n_ / sv); rr = n_ - q * sv; self.put('ax', q); self.put('dx', rr); eu = 174
            mb = 0
            if s.type == X86_OP_MEM: eu += 6 + eac + wpen; mb = size
        elif m in ('cbw', 'cwd', 'cdq', 'cwde'):
            if m in ('cbw', 'cwde') and ins.bytes[0] == 0x98:
                al = self.get('al'); self.put('ax', al | (0xff00 if al & 0x80 else 0)); eu = 2
            else:
                ax = self.get('ax'); self.put('dx', 0xffff if ax & 0x8000 else 0); eu = 5
            mb = 0
        elif m == 'xchg':
            d, s = ops; x = self.rd(d, ins, size); y = self.rd(s, ins, size)
            self.wr(d, ins, size, y); self.wr(s, ins, size, x)
            if d.type == X86_OP_REG and s.type == X86_OP_REG:
                eu = 3 if 'ax' in (ins.reg_name(d.reg), ins.reg_name(s.reg)) else 4; mb = 0
            else: eu, mb = 17 + eac + 2 * wpen, 2 * size
        elif m == 'lea':
            d, s = ops; self.put(ins.reg_name(d.reg), self.ea(s, ins)[1]); eu, mb = 2 + eac, 0
        elif m in ('les', 'lds'):
            d, s = ops; seg, off, _ = self.ea(s, ins)
            self.put(ins.reg_name(d.reg), self.rw(seg, off)); self.s['es' if m == 'les' else 'ds'] = self.rw(seg, off + 2)
            eu, mb = 16 + eac + 8, 4
        elif m == 'push':
            o = ops[0]
            v = self.rd(o, ins, 2); self.push(v)
            eu, mb = (15, 2) if o.type == X86_OP_REG else (24 + eac + 4, 4)
        elif m == 'pop':
            o = ops[0]; v = self.pop(); self.wr(o, ins, 2, v)
            eu, mb = (12, 2) if o.type == X86_OP_REG else (25 + eac + 4, 4)
        elif m == 'pushf': self.push(self.flags_word()); eu, mb = 14, 2
        elif m == 'popf': self.set_flags_word(self.pop()); eu, mb = 12, 2
        elif m == 'lahf': self.put('ah', self.flags_word() & 0xff); eu, mb = 4, 0
        elif m == 'sahf':
            ah = self.get('ah'); self.cf = ah & 1; self.zf = (ah >> 6) & 1; self.sf = (ah >> 7) & 1; eu, mb = 4, 0
        elif m in ('clc', 'stc', 'cmc', 'cld', 'std', 'cli', 'sti', 'nop'):
            if m == 'clc': self.cf = 0
            elif m == 'stc': self.cf = 1
            elif m == 'cmc': self.cf ^= 1
            elif m == 'cld': self.df = 0
            elif m == 'std': self.df = 1
            eu, mb = (3 if m == 'nop' else 2), 0
        elif m == 'call':
            o = ops[0]
            if o.type == X86_OP_IMM:
                t = o.imm & 0xffff
                if t in self.skip:
                    self.clock += self.skip[t]; eu, mb = 0, 0
                else:
                    self.push(nxt); self.ip = t; eu, mb, flush = 23, 2, True
            else:
                t = self.rd(o, ins, 2); self.push(nxt); self.ip = t; eu, mb, flush = 29 + eac + 4, 4, True
        elif m in ('ret', 'retf'):
            if m == 'retf':
                self.ip = self.pop(); self.s['cs'] = self.pop(); eu = 34; mb = 4
            else:
                self.ip = self.pop(); eu = 20; mb = 2
            if ops: self.r['sp'] = (self.r['sp'] + ops[0].imm) & 0xffff; eu += 4
            flush = True
        elif m == 'jmp':
            o = ops[0]
            if o.type == X86_OP_IMM: self.ip = o.imm & 0xffff; eu, mb, flush = 15, 0, True
            elif o.type == X86_OP_REG: self.ip = self.get(ins.reg_name(o.reg)); eu, mb, flush = 11, 0, True
            else: self.ip = self.rd(o, ins, 2); eu, mb, flush = 18 + eac + 4, 2, True
        elif m.startswith('j') or m.startswith('loop'):
            t = ops[0].imm & 0xffff
            cond = {'je': self.zf, 'jne': not self.zf, 'jb': self.cf, 'jae': not self.cf, 'jbe': self.cf or self.zf,
                    'ja': not (self.cf or self.zf), 'js': self.sf, 'jns': not self.sf, 'jl': self.sf != self.of,
                    'jge': self.sf == self.of, 'jle': self.zf or self.sf != self.of, 'jg': not self.zf and self.sf == self.of,
                    'jo': self.of, 'jno': not self.of}.get(m)
            if m == 'jcxz':
                cond = self.r['cx'] == 0; tk, nt = 18, 6
            elif m.startswith('loop'):
                self.r['cx'] = (self.r['cx'] - 1) & 0xffff
                cond = self.r['cx'] != 0
                if m in ('loope', 'loopz'): cond = cond and self.zf
                if m in ('loopne', 'loopnz'): cond = cond and not self.zf
                tk, nt = 17, 5
            else: tk, nt = 16, 4
            if cond is None: raise Halt('unknown jump ' + m)
            if cond: self.ip = t; eu, mb, flush = tk, 0, True
            else: eu, mb = nt, 0
        elif m in ('in', 'out'):
            if m == 'out':
                port = ops[0].imm if ops[0].type == X86_OP_IMM else self.get('dx')
                self.port_log.append((self.clock, port, self.get(ins.reg_name(ops[1].reg))))
            else:
                port = ops[1].imm if ops[1].type == X86_OP_IMM else self.get('dx')
                self.put(ins.reg_name(ops[0].reg), 0 if port != 0x61 else 0x4c)
            eu, mb = (10 if ops[0].type == X86_OP_IMM or ops[1].type == X86_OP_IMM else 8), 1
        elif m in ('lodsb', 'lodsw', 'stosb', 'stosw', 'movsb', 'movsw', 'cmpsb', 'cmpsw', 'scasb', 'scasw'):
            sz = 1 if m.endswith('b') else 2; step = -sz if self.df else sz
            count = self.r['cx'] if prefix_rep else 1
            per = {'lods': 12, 'stos': 11, 'movs': 18, 'cmps': 22, 'scas': 15}[m[:4]] + (4 if sz == 2 else 0) * (2 if m[:4] in ('movs', 'cmps') else 1)
            n_done = 0
            while count:
                if m.startswith('lods'):
                    self.put('al' if sz == 1 else 'ax', self.rb('ds', self.r['si']) if sz == 1 else self.rw('ds', self.r['si'])); self.r['si'] = (self.r['si'] + step) & 0xffff
                elif m.startswith('stos'):
                    (self.wb if sz == 1 else self.ww)('es', self.r['di'], self.get('al' if sz == 1 else 'ax')); self.r['di'] = (self.r['di'] + step) & 0xffff
                elif m.startswith('movs'):
                    v = self.rb('ds', self.r['si']) if sz == 1 else self.rw('ds', self.r['si'])
                    (self.wb if sz == 1 else self.ww)('es', self.r['di'], v)
                    self.r['si'] = (self.r['si'] + step) & 0xffff; self.r['di'] = (self.r['di'] + step) & 0xffff
                else:
                    x = self.rb('ds', self.r['si']) if m.startswith('cmps') and sz == 1 else (self.rw('ds', self.r['si']) if m.startswith('cmps') else self.get('al' if sz == 1 else 'ax'))
                    y = self.rb('es', self.r['di']) if sz == 1 else self.rw('es', self.r['di'])
                    r = x - y; self.cf = int(r < 0); self.szp(r, sz)
                    if m.startswith('cmps'): self.r['si'] = (self.r['si'] + step) & 0xffff
                    self.r['di'] = (self.r['di'] + step) & 0xffff
                n_done += 1
                if not prefix_rep: break
                count -= 1; self.r['cx'] = count
                if m[:4] in ('cmps', 'scas'):
                    if ins.prefix[0] == 0xf3 and not self.zf: break
                    if ins.prefix[0] == 0xf2 and self.zf: break
            eu = (9 + (per - 2) * n_done) if prefix_rep else per; mb = n_done * sz * (2 if m[:4] in ('movs', 'cmps') else 1)
        elif m == 'xlatb':
            self.put('al', self.rb('ds', (self.r['bx'] + self.get('al')) & 0xffff)); eu, mb = 11, 1
        elif m == 'int':
            raise Halt('int %x' % ops[0].imm)
        else:
            raise Halt('unimplemented %s %s at %04x' % (m, ins.op_str, ins.address))
        self.account(eu, L, mb, flush)

    def run(self, until_ip, max_steps=50_000_000):
        n = 0
        while self.ip != until_ip:
            self.step(); n += 1
            if n > max_steps: raise Halt('step limit')
        return n
