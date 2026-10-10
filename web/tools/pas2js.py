#!/usr/bin/env python3
"""pas2js — compile the Turbo Pascal 3 subset used by MONOPOLY.PAS / MONOCODE.PAS to an async ES module.

Memory model (see ../CONTRACT.md): every Pascal variable lives in the runtime's byte memory at the
address the 1985 compiler gave it (globals from DS:0260 in declaration order), typed constants in a
separate CS area, locals and value parameters in stack frames.  Integers wrap at 16 bits, strings are
length-prefixed, booleans are bytes.  Procedures with labels are compiled to a flat switch state
machine so that every goto of the original is reproduced exactly.

usage: pas2js.py SOURCE.PAS OUT.js
"""
import os, re, sys, base64, struct

# ---------------------------------------------------------------------------------------------- lexer

class Tok:
    __slots__ = ('k', 'v', 'pos')
    def __init__(self, k, v, pos): self.k, self.v, self.pos = k, v, pos
    def __repr__(self): return '%s:%r@%s' % (self.k, self.v, self.pos)

SYMS = [':=', '..', '<=', '>=', '<>', '(', ')', '[', ']', ',', ';', ':', '.', '+', '-', '*', '/', '=', '<', '>', '^', '@']


def lex(path, out):
    text = open(path, encoding='latin1').read().replace('\r\n', '\n').replace('\x1a', '')
    fname = os.path.basename(path)
    i, n, line = 0, len(text), 1
    while i < n:
        c = text[i]
        if c == '\n': line += 1; i += 1; continue
        if c in ' \t\r\f': i += 1; continue
        pos = '%s:%d' % (fname, line)
        if c == '{' or text.startswith('(*', i):
            close = '}' if c == '{' else '*)'
            j = text.index(close, i + 1)
            body = text[i + (1 if c == '{' else 2):j]
            line += body.count('\n')
            i = j + len(close)
            if body.startswith('$'):
                d = body[1:].strip()
                m = re.match(r'[Ii]\s+(\S+)$', d)
                if m:
                    inc = m.group(1)
                    if inc.upper() == 'GRAPH.P': out.append(Tok('graphinc', None, pos))
                    else:
                        p = os.path.join(os.path.dirname(path), inc)
                        if not os.path.exists(p):
                            for f in os.listdir(os.path.dirname(path) or '.'):
                                if f.upper() == inc.upper(): p = os.path.join(os.path.dirname(path), f)
                        lex(p, out)
                else:
                    for part in d.split(','):
                        part = part.strip()
                        if re.match(r'[A-Za-z][+-]$', part): out.append(Tok('dir', part.upper(), pos))
            continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'): j += 1
            out.append(Tok('id', text[i:j].lower(), pos)); i = j; continue
        if c.isdigit():
            j = i
            while j < n and text[j].isdigit(): j += 1
            if j < n and text[j] == '.' and j + 1 < n and text[j + 1].isdigit():
                j += 1
                while j < n and text[j].isdigit(): j += 1
                if j < n and text[j] in 'eE':
                    j += 1
                    if text[j] in '+-': j += 1
                    while j < n and text[j].isdigit(): j += 1
                out.append(Tok('real', text[i:j], pos))
            else:
                out.append(Tok('int', int(text[i:j]), pos))
            i = j; continue
        if c == '$':
            j = i + 1
            while j < n and text[j] in '0123456789abcdefABCDEF': j += 1
            out.append(Tok('int', int(text[i + 1:j], 16), pos)); i = j; continue
        if c == "'" or c == '#' or (c == '^' and i + 1 < n and text[i + 1].isalpha() and out and out[-1].k in ('sym',) and out[-1].v in ('=', ':=', '(', ',', '+', '<>', '[')):
            s = ''
            while i < n:
                if text[i] == "'":
                    j = i + 1
                    while True:
                        k = text.index("'", j)
                        s += text[j:k]
                        if k + 1 < n and text[k + 1] == "'": s += "'"; j = k + 2; continue
                        i = k + 1; break
                elif text[i] == '#':
                    j = i + 1
                    if text[j] == '$':
                        j += 1
                        while text[j] in '0123456789abcdefABCDEF': j += 1
                        s += chr(int(text[i + 2:j], 16))
                    else:
                        while text[j].isdigit(): j += 1
                        s += chr(int(text[i + 1:j]))
                    i = j
                elif text[i] == '^' and i + 1 < n and text[i + 1].isalpha():
                    s += chr(ord(text[i + 1].upper()) - 64); i += 2
                else: break
            out.append(Tok('str', s, pos)); continue
        for s in SYMS:
            if text.startswith(s, i):
                out.append(Tok('sym', s, pos)); i += len(s); break
        else:
            raise SyntaxError('%s: bad char %r' % (pos, c))
    return out

# ---------------------------------------------------------------------------------------------- types

class T:
    def __init__(self, kind, size, **kw):
        self.kind, self.size = kind, size
        self.__dict__.update(kw)
    def __repr__(self): return '<%s %d>' % (self.kind, self.size)

INT = T('int', 2); BYTE = T('byte', 1); CHAR = T('char', 1); BOOL = T('bool', 1); REAL = T('real', 6)
def STR(n): return T('str', n + 1, max=n)
FILESIZE = 76            # size of a TP3 file variable

def is_ord(t): return t.kind in ('int', 'byte', 'char', 'bool')

# ---------------------------------------------------------------------------------------------- AST

class N:
    def __init__(self, k, **kw): self.k = k; self.__dict__.update(kw)
    def __repr__(self): return 'N(%s)' % self.k

class Parser:
    def __init__(self, toks):
        self.t = toks; self.i = 0
        self.ioc = True           # {$I+}
        self.graph = False
    def peek(self, off=0):
        j = self.i
        cnt = -1
        while True:
            t = self.t[j] if j < len(self.t) else Tok('eof', None, 'eof')
            if t.k == 'dir':
                j += 1; continue
            if t.k == 'graphinc':
                j += 1; continue
            cnt += 1
            if cnt == off: return t
            j += 1
    def next(self):
        while self.i < len(self.t) and self.t[self.i].k in ('dir', 'graphinc'):
            t = self.t[self.i]
            if t.k == 'dir':
                if t.v[0] == 'I': self.ioc = t.v[1] == '+'
            else: self.graph = True
            self.i += 1
        t = self.t[self.i] if self.i < len(self.t) else Tok('eof', None, 'eof')
        self.i += 1
        return t
    def sync(self):
        """consume pending directives (so ioc is current before a statement)"""
        while self.i < len(self.t) and self.t[self.i].k in ('dir', 'graphinc'):
            t = self.t[self.i]
            if t.k == 'dir':
                if t.v[0] == 'I': self.ioc = t.v[1] == '+'
            else: self.graph = True
            self.i += 1
    def isid(self, v, off=0): t = self.peek(off); return t.k == 'id' and t.v == v
    def issym(self, v, off=0): t = self.peek(off); return t.k == 'sym' and t.v == v
    def expect_sym(self, v):
        t = self.next()
        if t.k != 'sym' or t.v != v: raise SyntaxError('%s: expected %r got %r' % (t.pos, v, t))
    def expect_id(self, v=None):
        t = self.next()
        if t.k != 'id' or (v and t.v != v): raise SyntaxError('%s: expected %s got %r' % (t.pos, v or 'identifier', t))
        return t.v
    def accept_sym(self, v):
        if self.issym(v): self.next(); return True
        return False
    def accept_id(self, v):
        if self.isid(v): self.next(); return True
        return False

    # program ----------------------------------------------------------------------------------
    def program(self):
        self.expect_id('program'); name = self.expect_id()
        if self.accept_sym('('):
            while not self.accept_sym(')'): self.next()
        self.expect_sym(';')
        decls, body = self.block()
        self.expect_sym('.')
        return N('program', name=name, decls=decls, body=body, graph=self.graph)

    def block(self):
        decls = []
        while True:
            self.sync()
            if self.isid('label'):
                self.next(); labs = []
                while True:
                    t = self.next(); labs.append(str(t.v))
                    if not self.accept_sym(','): break
                self.expect_sym(';'); decls.append(N('label', labels=labs))
            elif self.isid('const'): self.next(); decls += self.const_section()
            elif self.isid('type'): self.next(); decls += self.type_section()
            elif self.isid('var'): self.next(); decls += self.var_section()
            elif self.isid('procedure') or self.isid('overlay') or self.isid('function'):
                decls.append(self.proc_decl())
            else: break
        self.sync()
        body = self.compound()
        return decls, body

    def const_section(self):
        out = []
        while self.peek().k == 'id' and not self.peek().v in ('const', 'type', 'var', 'procedure', 'overlay', 'function', 'begin', 'label'):
            name = self.expect_id()
            if self.accept_sym(':'):
                ty = self.type_()
                self.expect_sym('=')
                val = self.const_value()
                self.expect_sym(';')
                out.append(N('tconst', name=name, type=ty, value=val))
            else:
                self.expect_sym('=')
                e = self.expr(); self.expect_sym(';')
                out.append(N('const', name=name, expr=e))
        return out

    def const_value(self):
        if self.issym('('):
            # record constant  (id: val; ...)  or array constant (v, v, ...)
            if self.peek(1).k == 'id' and self.issym(':', 2):
                self.next(); fields = []
                while True:
                    f = self.expect_id(); self.expect_sym(':'); fields.append((f, self.const_value()))
                    if self.accept_sym(';'):
                        if self.issym(')'): break
                        continue
                    break
                self.expect_sym(')')
                return ('rec', fields)
            self.next(); items = [self.const_value()]
            while self.accept_sym(','): items.append(self.const_value())
            self.expect_sym(')')
            return ('arr', items)
        return ('expr', self.expr())

    def type_section(self):
        out = []
        while self.peek().k == 'id' and self.issym('=', 1):
            name = self.expect_id(); self.expect_sym('='); ty = self.type_(); self.expect_sym(';')
            out.append(N('type', name=name, type=ty))
        return out

    def var_section(self):
        out = []
        while self.peek().k == 'id' and not self.peek().v in ('const', 'type', 'var', 'procedure', 'overlay', 'function', 'begin', 'label'):
            names = [self.expect_id()]
            while self.accept_sym(','): names.append(self.expect_id())
            self.expect_sym(':'); ty = self.type_()
            absolute = None
            self.expect_sym(';')
            out.append(N('var', names=names, type=ty))
        return out

    def type_(self):
        if self.accept_id('string'):
            self.expect_sym('['); e = self.expr(); self.expect_sym(']')
            return ('string', e)
        if self.accept_id('array'):
            self.expect_sym('['); ranges = [self.range_()]
            while self.accept_sym(','): ranges.append(self.range_())
            self.expect_sym(']'); self.expect_id('of'); el = self.type_()
            return ('array', ranges, el)
        if self.accept_id('record'):
            fields = []
            while not self.isid('end'):
                names = [self.expect_id()]
                while self.accept_sym(','): names.append(self.expect_id())
                self.expect_sym(':'); ty = self.type_()
                fields.append((names, ty))
                if not self.accept_sym(';'): break
            self.expect_id('end')
            return ('record', fields)
        if self.accept_id('file'):
            if self.accept_id('of'): return ('file', self.type_())
            return ('file', None)
        if self.peek().k == 'id' and not self.issym('..', 1):
            return ('named', self.expect_id())
        lo = self.expr(); self.expect_sym('..'); hi = self.expr()
        return ('subrange', lo, hi)

    def range_(self):
        lo = self.expr(); self.expect_sym('..'); hi = self.expr()
        return (lo, hi)

    def proc_decl(self):
        overlay = self.accept_id('overlay')
        kind = self.expect_id()
        if kind == 'function': raise SyntaxError('functions are not used by this program')
        name = self.expect_id()
        params = []
        if self.accept_sym('('):
            while True:
                isvar = self.accept_id('var')
                names = [self.expect_id()]
                while self.accept_sym(','): names.append(self.expect_id())
                self.expect_sym(':'); ty = self.type_()
                params.append((names, ty, isvar))
                if not self.accept_sym(';'): break
            self.expect_sym(')')
        self.expect_sym(';')
        if self.accept_id('forward'):
            self.expect_sym(';')
            return N('forward', name=name, params=params)
        decls, body = self.block()
        self.expect_sym(';')
        return N('proc', name=name, params=params, decls=decls, body=body, overlay=overlay)

    # statements -------------------------------------------------------------------------------
    def compound(self):
        self.expect_id('begin')
        stmts = self.stmt_list(('end',))
        self.expect_id('end')
        return N('compound', stmts=stmts)

    def stmt_list(self, enders):
        stmts = [self.statement()]
        while self.accept_sym(';'):
            stmts.append(self.statement())
        return stmts

    def statement(self):
        self.sync()
        t = self.peek()
        if t.k in ('int', 'id') and self.issym(':', 1):
            self.next(); self.next()
            return N('labeled', label=str(t.v), stmt=self.statement())
        if t.k == 'id':
            v = t.v
            if v == 'begin': return self.compound()
            if v == 'if':
                self.next(); c = self.expr(); self.expect_id('then')
                th = self.statement() if not self.isid('else') else N('empty')
                el = None
                if self.accept_id('else'): el = self.statement()
                return N('if', cond=c, then=th, els=el)
            if v == 'case':
                self.next(); sel = self.expr(); self.expect_id('of')
                arms = []; els = None
                while True:
                    self.sync()
                    if self.isid('end'): break
                    if self.accept_id('else'):
                        els = self.stmt_list(('end',)); break
                    labels = []
                    while True:
                        a = self.expr()
                        if self.accept_sym('..'): labels.append((a, self.expr()))
                        else: labels.append((a, None))
                        if not self.accept_sym(','): break
                    self.expect_sym(':')
                    st = self.statement()
                    arms.append((labels, st))
                    if not self.accept_sym(';'): break
                self.expect_id('end')
                return N('case', sel=sel, arms=arms, els=els)
            if v == 'for':
                self.next(); var = self.designator(); self.expect_sym(':=')
                a = self.expr()
                down = self.accept_id('downto')
                if not down: self.expect_id('to')
                b = self.expr(); self.expect_id('do')
                return N('for', var=var, start=a, stop=b, down=down, body=self.statement())
            if v == 'while':
                self.next(); c = self.expr(); self.expect_id('do')
                return N('while', cond=c, body=self.statement())
            if v == 'repeat':
                self.next(); body = self.stmt_list(('until',)); self.expect_id('until')
                return N('repeat', body=body, cond=self.expr())
            if v == 'with':
                self.next(); recs = [self.designator()]
                while self.accept_sym(','): recs.append(self.designator())
                self.expect_id('do')
                return N('with', recs=recs, body=self.statement())
            if v == 'goto':
                self.next(); t2 = self.next()
                return N('goto', label=str(t2.v))
            if v in ('end', 'until', 'else'):
                return N('empty')
            # assignment or procedure call
            d = self.designator()
            if self.accept_sym(':='):
                return N('assign', target=d, expr=self.expr(), pos=t.pos)
            args = []
            if d.k == 'call': return N('pcall', name=d.name, args=d.args, ioc=self.ioc, pos=t.pos)
            if d.k == 'id': return N('pcall', name=d.name, args=[], ioc=self.ioc, pos=t.pos)
            raise SyntaxError('%s: bad statement' % t.pos)
        return N('empty')

    # expressions ------------------------------------------------------------------------------
    def designator(self):
        t = self.next()
        if t.k != 'id': raise SyntaxError('%s: identifier expected, got %r' % (t.pos, t))
        d = N('id', name=t.v, pos=t.pos)
        if self.issym('('):
            # call with args (procedures / builtin functions)
            self.next(); args = []
            if not self.issym(')'):
                while True:
                    e = self.expr()
                    if self.accept_sym(':'):
                        w = self.expr(); dd = None
                        if self.accept_sym(':'): dd = self.expr()
                        e = N('fmt', e=e, w=w, d=dd)
                    args.append(e)
                    if not self.accept_sym(','): break
            self.expect_sym(')')
            return N('call', name=t.v, args=args, pos=t.pos)
        while True:
            if self.accept_sym('['):
                idx = [self.expr()]
                while self.accept_sym(','): idx.append(self.expr())
                self.expect_sym(']')
                for e in idx: d = N('index', base=d, idx=e)
            elif self.issym('.') and self.peek(1).k == 'id':
                self.next(); d = N('field', base=d, name=self.expect_id())
            else: break
        return d

    RELOPS = ('=', '<>', '<', '>', '<=', '>=')
    def expr(self):
        a = self.simple()
        t = self.peek()
        if t.k == 'sym' and t.v in self.RELOPS:
            self.next(); return N('bin', op=t.v, a=a, b=self.simple())
        if t.k == 'id' and t.v == 'in':
            self.next(); return N('in', a=a, b=self.simple())
        return a
    def simple(self):
        neg = False
        if self.accept_sym('-'): neg = True
        elif self.accept_sym('+'): pass
        a = self.term()
        if neg: a = N('neg', a=a)
        while True:
            t = self.peek()
            if (t.k == 'sym' and t.v in ('+', '-')) or (t.k == 'id' and t.v in ('or', 'xor')):
                self.next(); a = N('bin', op=t.v, a=a, b=self.term())
            else: return a
    def term(self):
        a = self.factor()
        while True:
            t = self.peek()
            if (t.k == 'sym' and t.v in ('*', '/')) or (t.k == 'id' and t.v in ('div', 'mod', 'and', 'shl', 'shr')):
                self.next(); a = N('bin', op=t.v, a=a, b=self.factor())
            else: return a
    def factor(self):
        t = self.peek()
        if t.k == 'int': self.next(); return N('num', v=t.v)
        if t.k == 'real': self.next(); return N('real', v=t.v)
        if t.k == 'str': self.next(); return N('str', v=t.v)
        if t.k == 'sym' and t.v == '(':
            self.next(); e = self.expr(); self.expect_sym(')'); return e
        if t.k == 'sym' and t.v == '[':
            self.next(); items = []
            if not self.issym(']'):
                while True:
                    a = self.expr()
                    if self.accept_sym('..'): items.append((a, self.expr()))
                    else: items.append((a, None))
                    if not self.accept_sym(','): break
            self.expect_sym(']')
            return N('set', items=items)
        if t.k == 'id' and t.v == 'not':
            self.next(); return N('not', a=self.factor())
        if t.k == 'id':
            return self.designator()
        raise SyntaxError('%s: unexpected %r' % (t.pos, t))

# ---------------------------------------------------------------------------------------------- Real48

def real48_from_decimal(s):
    """Convert a decimal literal to a 6-byte real the way the 1985 compiler does (truncation of the
    40-bit significand).  Returns (exponent byte, 5 mantissa bytes incl. sign)"""
    from fractions import Fraction
    v = Fraction(s)
    if v == 0: return bytes(6)
    neg = v < 0; v = abs(v)
    e = 0
    while v >= 1: v /= 2; e += 1
    while v < Fraction(1, 2): v *= 2; e -= 1
    m = v * (1 << 40)                  # 0.5 <= v < 1  ->  m in [2^39, 2^40)
    mi = int(m)                        # the 1985 compiler truncates (0.1 -> 7D CC CC CC CC 4C)
    mi &= (1 << 39) - 1
    if neg: mi |= 1 << 39
    return bytes([e + 128]) + mi.to_bytes(5, 'little')

# ---------------------------------------------------------------------------------------------- sound loops

def has_sound(st, direct=True):
    """does statement st call Sound (not counting nested for-loops when direct)"""
    k = st.k
    if k == 'pcall': return st.name == 'sound'
    if k == 'compound': return any(has_sound(x, direct) for x in st.stmts)
    if k == 'if': return has_sound(st.then, direct) or (st.els is not None and has_sound(st.els, direct))
    if k == 'while': return has_sound(st.body, direct)
    if k == 'repeat': return any(has_sound(x, direct) for x in st.body)
    if k == 'case': return any(has_sound(s, direct) for _, s in st.arms) or bool(st.els and any(has_sound(x, direct) for x in st.els))
    if k == 'with': return has_sound(st.body, direct)
    if k == 'labeled': return has_sound(st.stmt, direct)
    if k == 'for': return False if direct else has_sound(st.body, direct)
    return False

def for_loops(st, out):
    """all for statements of a statement tree in source order"""
    if st.k == 'for':
        out.append(st); for_loops(st.body, out); return
    for attr in ('stmts', 'body', 'then', 'els', 'stmt'):
        v = getattr(st, attr, None)
        if isinstance(v, list):
            for x in v: for_loops(x, out)
        elif v is not None and hasattr(v, 'k'): for_loops(v, out)
    if st.k == 'case':
        for _, x in st.arms: for_loops(x, out)

# ---------------------------------------------------------------------------------------------- compiler

BUILTIN_CONSTS = {'c80': 3, 'bw80': 2, 'c40': 1, 'bw40': 0, 'maxint': 32767, 'true': 1, 'false': 0}

class Sym:
    def __init__(self, kind, **kw): self.kind = kind; self.__dict__.update(kw)

class E:
    """expression result: cat in int|char|bool|real|str|set ; code is JS; const optional"""
    def __init__(self, cat, code, const=None, t=None, addr=None):
        self.cat, self.code, self.const, self.t, self.addr = cat, code, const, t, addr


class Compiler:
    def __init__(self, prog, name, pcmap=None, cpu=None, speed=None, like=None):
        self.pcmap = pcmap
        self.cpumap = cpu or {}       # procedure -> 8088 clocks per iteration of its sound loops
        self.speedmap = speed or {}   # procedure -> the same at DOSBox's default speed (the speed switch)
        self.loopcost = {}
        self.like = like              # procedure names of the program the cpu/speed tables belong to
        self.prog = prog; self.name = name
        self.types = {'integer': INT, 'byte': BYTE, 'char': CHAR, 'boolean': BOOL, 'real': REAL}
        self.globals = {}       # name -> Sym
        self.consts = {}
        self.procs = {}
        self.ds = 0x260         # 1985 compiler: user data starts at DS:0260
        self.cs = bytearray()   # typed constants
        self.out = []
        self.tmp = 0
        self.graph = prog.graph

    # ---- types
    def resolve_type(self, ty):
        k = ty[0]
        if k == 'named':
            if ty[1] not in self.types: raise SyntaxError('unknown type %s' % ty[1])
            return self.types[ty[1]]
        if k == 'string': return STR(self.const_int(ty[1]))
        if k == 'array':
            el = self.resolve_type(ty[2])
            for lo, hi in reversed(ty[1]):
                l, lt = self.const_val(lo); h, _ = self.const_val(hi)
                if isinstance(l, str): l, h, idx = ord(l), ord(h), 'char'
                else: idx = 'int'
                el = T('array', (h - l + 1) * el.size, lo=l, hi=h, el=el, idx=idx)
            return el
        if k == 'record':
            off = 0; fields = {}; order = []
            for names, fty in ty[1]:
                ft = self.resolve_type(fty)
                for nm in names:
                    fields[nm] = (off, ft); order.append(nm); off += ft.size
            return T('record', off, fields=fields, order=order)
        if k == 'file':
            el = self.resolve_type(ty[1]) if ty[1] else None
            return T('file', FILESIZE, el=el)
        if k == 'subrange':
            l, _ = self.const_val(ty[1]); h, _ = self.const_val(ty[2])
            if isinstance(l, str): return CHAR
            return BYTE if 0 <= l and h <= 255 else INT
        raise SyntaxError('type %r' % (ty,))

    def const_val(self, e):
        if e.k == 'num': return e.v, INT
        if e.k == 'str': return (e.v, CHAR) if len(e.v) == 1 else (e.v, STR(len(e.v)))
        if e.k == 'neg': v, t = self.const_val(e.a); return -v, t
        if e.k == 'id':
            if e.name in self.consts: return self.consts[e.name]
            if e.name in BUILTIN_CONSTS: return BUILTIN_CONSTS[e.name], INT
        if e.k == 'real': return float(e.v), REAL
        if e.k == 'bin':
            a, _ = self.const_val(e.a); b, _ = self.const_val(e.b)
            return {'+': a + b, '-': a - b, '*': a * b}[e.op], INT
        raise SyntaxError('constant expected: %r' % e)
    def const_int(self, e):
        v, _ = self.const_val(e); return v

    # ---- typed constant bytes
    def tconst_bytes(self, t, val):
        if t.kind == 'record':
            assert val[0] == 'rec'
            b = bytearray(t.size)
            given = dict(val[1])
            for nm in t.order:
                off, ft = t.fields[nm]
                if nm in given: b[off:off + ft.size] = self.tconst_bytes(ft, given[nm])
            return bytes(b)
        if t.kind == 'array':
            assert val[0] == 'arr' and len(val[1]) == t.hi - t.lo + 1, (t, len(val[1]))
            return b''.join(self.tconst_bytes(t.el, v) for v in val[1])
        v, _ = self.const_val(val[1])
        if t.kind == 'str':
            s = v.encode('latin1') if isinstance(v, str) else bytes([v])
            return bytes([len(s)]) + s + bytes(t.max - len(s))
        if t.kind == 'int': return struct.pack('<h', v)
        if t.kind in ('byte', 'bool'): return bytes([v & 255])
        if t.kind == 'char': return bytes([ord(v) if isinstance(v, str) else v])
        if t.kind == 'real': return real48_from_decimal(str(v))
        raise SyntaxError('tconst %r' % t)

    # ---- declarations
    def declare_globals(self, decls):
        for d in decls:
            if d.k == 'type': self.types[d.name] = self.resolve_type(d.type)
            elif d.k == 'const':
                self.consts[d.name] = self.const_val(d.expr)
            elif d.k == 'tconst':
                t = self.resolve_type(d.type)
                off = len(self.cs)
                self.cs += self.tconst_bytes(t, d.value)
                self.globals[d.name] = Sym('var', t=t, addr='0x%05x' % (0x10000 + off))
            elif d.k == 'var':
                t = self.resolve_type(d.type)
                for nm in d.names:
                    m = re.match(r'g([0-9a-f]{4})$', nm)
                    if m: assert int(m.group(1), 16) == self.ds, 'layout: %s placed at %04x' % (nm, self.ds)
                    self.globals[nm] = Sym('var', t=t, addr='0x%04x' % self.ds)
                    self.ds += t.size
            elif d.k in ('proc', 'forward'):
                if d.name not in self.procs:
                    self.procs[d.name] = Sym('proc', params=self.param_list(d.params), node=None)
                if d.k == 'proc': self.procs[d.name].node = d
            elif d.k == 'label': pass

    def param_list(self, params):
        out = []
        for names, ty, isvar in params:
            t = self.resolve_type(ty)
            for nm in names: out.append((nm, t, isvar))
        return out

    # ---- name lookup
    def lookup(self, name):
        for w in reversed(self.withs):
            if name in w[0].fields:
                off, ft = w[0].fields[name]
                return Sym('var', t=ft, addr='(%s + %d)' % (w[1], off))
        if name in self.locals: return self.locals[name]
        if name in self.globals: return self.globals[name]
        return None

    # ---- designators (addresses)
    def addr_of(self, d):
        """returns (js address expression, type)"""
        if d.k == 'id':
            s = self.lookup(d.name)
            if s is None or s.kind != 'var': raise SyntaxError('%s: unknown variable %s' % (getattr(d, 'pos', '?'), d.name))
            return s.addr, s.t
        if d.k == 'field':
            a, t = self.addr_of(d.base)
            off, ft = t.fields[d.name]
            return '(%s + %d)' % (a, off), ft
        if d.k == 'index':
            a, t = self.addr_of(d.base)
            if t.kind == 'str':
                i = self.expr(d.idx)
                return '(%s + (%s))' % (a, i.code), CHAR
            assert t.kind == 'array', (d, t)
            i = self.expr(d.idx)
            if i.const is not None:
                return '(%s + %d)' % (a, (i.const - t.lo) * t.el.size), t.el
            sub = '(%s)' % i.code if t.lo == 0 else '((%s) - %d)' % (i.code, t.lo)
            return '(%s + %s * %d)' % (a, sub, t.el.size), t.el
        raise SyntaxError('not a designator: %r' % d)

    def load(self, a, t):
        k = t.kind
        if k == 'int': return E('int', 'R.rw(%s)' % a, t=t, addr=a)
        if k == 'byte': return E('int', 'R.rb(%s)' % a, t=t, addr=a)
        if k == 'char': return E('char', 'R.rb(%s)' % a, t=t, addr=a)
        if k == 'bool': return E('bool', 'R.rb(%s)' % a, t=t, addr=a)
        if k == 'real': return E('real', 'R.rr(%s)' % a, t=t, addr=a)
        if k == 'str': return E('str', 'R.rs(%s)' % a, t=t, addr=a)
        return E('mem', a, t=t, addr=a)

    # ---- expressions
    def expr(self, e):
        k = e.k
        if k == 'num': return E('int', str(e.v), const=e.v)
        if k == 'real':
            return E('real', 'H.r48(%s)' % ','.join(str(x) for x in real48_from_decimal(e.v)))
        if k == 'str':
            if len(e.v) == 1: return E('char', str(ord(e.v[0])), const=ord(e.v[0]))
            return E('str', jsstr(e.v), const=e.v)
        if k == 'id':
            s = self.lookup(e.name)
            if s is None:
                if e.name in self.consts:
                    v, t = self.consts[e.name]
                    return self.expr(N('num', v=v) if isinstance(v, int) else N('str', v=v))
                if e.name in BUILTIN_CONSTS:
                    v = BUILTIN_CONSTS[e.name]
                    if e.name in ('true', 'false'): return E('bool', str(v), const=v)
                    return E('int', str(v), const=v)
                return self.func_call(e.name, [], e)
            a, t = self.addr_of(e)
            return self.load(a, t)
        if k in ('field', 'index'):
            a, t = self.addr_of(e)
            return self.load(a, t)
        if k == 'call': return self.func_call(e.name, e.args, e)
        if k == 'neg':
            a = self.expr(e.a)
            if a.cat == 'real': return E('real', 'H.rneg(%s)' % a.code)
            if a.const is not None: return E('int', str(-a.const), const=-a.const)
            return E('int', 'H.w(-(%s))' % a.code)
        if k == 'not':
            a = self.expr(e.a)
            if a.cat == 'bool': return E('bool', '((%s) ^ 1)' % a.code)
            return E('int', 'H.w(~(%s))' % a.code)
        if k == 'in':
            a = self.expr(e.a); assert e.b.k == 'set'
            parts = []
            for lo, hi in e.b.items:
                l = self.expr(lo);
                if hi is None: parts.append(l.code)
                else: parts.append('[%s,%s]' % (l.code, self.expr(hi).code))
            return E('bool', 'H.inset(%s, [%s])' % (a.code, ', '.join(parts)))
        if k == 'bin': return self.binop(e)
        if k == 'set': raise SyntaxError('set outside in')
        raise SyntaxError('expr %r' % e)

    def as_str(self, x):
        if x.cat == 'str': return x.code
        if x.cat == 'char': return 'String.fromCharCode(%s)' % x.code if x.const is None else jsstr(chr(x.const))
        raise SyntaxError('string expected, got %s' % x.cat)
    def as_real(self, x):
        if x.cat == 'real': return x.code
        if x.cat == 'int': return '(%s)' % x.code
        raise SyntaxError('real expected')

    def binop(self, e):
        op = e.op
        a = self.expr(e.a); b = self.expr(e.b)
        if op in ('=', '<>', '<', '>', '<=', '>='):
            jsop = {'=': '===', '<>': '!==', '<': '<', '>': '>', '<=': '<=', '>=': '>='}[op]
            if a.cat == 'str' or b.cat == 'str':
                return E('bool', '+(%s %s %s)' % (self.as_str(a), jsop, self.as_str(b)))
            if a.cat == 'real' or b.cat == 'real':
                return E('bool', '+H.rcmp(%s, %s, %r)' % (self.as_real(a), self.as_real(b), op))
            return E('bool', '+((%s) %s (%s))' % (a.code, jsop, b.code))
        if op == '+' and (a.cat == 'str' or b.cat == 'str'):
            sa, sb = self.as_str(a), self.as_str(b)
            return E('str', 'H.cat(%s, %s, %s)' % (sa, sb, self.pc('cat')))
        if op == '/':
            return E('real', 'H.rdiv(%s, %s)' % (self.as_real(a), self.as_real(b)))
        if a.cat == 'real' or b.cat == 'real':
            f = {'+': 'radd', '-': 'rsub', '*': 'rmul'}[op]
            return E('real', 'H.%s(%s, %s)' % (f, self.as_real(a), self.as_real(b)))
        if op in ('and', 'or', 'xor'):
            jsop = {'and': '&', 'or': '|', 'xor': '^'}[op]
            cat = 'bool' if a.cat == 'bool' and b.cat == 'bool' else 'int'
            return E(cat, '((%s) %s (%s))' % (a.code, jsop, b.code))
        if a.const is not None and b.const is not None and op in ('+', '-', '*'):
            v = {'+': a.const + b.const, '-': a.const - b.const, '*': a.const * b.const}[op]
            v = ((v + 0x8000) & 0xffff) - 0x8000
            return E('int', str(v), const=v)
        if op in ('+', '-', '*'):
            return E('int', 'H.w((%s) %s (%s))' % (a.code, op, b.code))
        if op == 'div': return E('int', 'H.idiv(%s, %s)' % (a.code, b.code))
        if op == 'mod': return E('int', 'H.imod(%s, %s)' % (a.code, b.code))
        if op == 'shl': return E('int', 'H.w((%s) << (%s))' % (a.code, b.code))
        if op == 'shr': return E('int', 'H.w(((%s) & 0xffff) >>> (%s))' % (a.code, b.code))
        raise SyntaxError('op %s' % op)

    def func_call(self, name, args, node):
        A = lambda i: self.expr(args[i])
        if name == 'length': return E('int', '(%s).length' % self.as_str(A(0)))
        if name == 'copy':
            a0, a1, a2 = self.as_str(A(0)), A(1).code, A(2).code
            return E('str', 'H.copy(%s, %s, %s, %s)' % (a0, a1, a2, self.pc('copy')))
        if name == 'concat':
            s = self.as_str(A(0))
            for i in range(1, len(args)): s = 'H.cat(%s, %s, %s)' % (s, self.as_str(A(i)), self.pc('cat'))
            return E('str', s)
        if name == 'pos': return E('int', 'H.pos(%s, %s)' % (self.as_str(A(0)), self.as_str(A(1))))
        if name == 'upcase': return E('char', 'H.upcase(%s)' % self.as_char(A(0)))
        if name == 'chr': return E('char', '((%s) & 255)' % A(0).code)
        if name == 'ord': return E('int', '(%s)' % A(0).code)
        if name == 'trunc': return E('int', 'H.trunc(%s)' % self.as_real(A(0)))
        if name == 'round': return E('int', 'H.round(%s)' % self.as_real(A(0)))
        if name == 'random': return E('int', 'R.random(%s)' % A(0).code)
        if name == 'keypressed': return E('bool', '(await R.keyPressed() ? 1 : 0)')
        if name == 'ioresult': return E('int', 'R.ioResult()')
        if name == 'wherex': return E('int', 'R.whereX()')
        if name == 'wherey': return E('int', 'R.whereY()')
        if name == 'abs': return E('int', 'H.w(Math.abs(%s))' % A(0).code)
        if name == 'odd': return E('bool', '((%s) & 1)' % A(0).code)
        if name == 'succ': return E(A(0).cat, '(%s + 1)' % A(0).code)
        if name == 'pred': return E(A(0).cat, '(%s - 1)' % A(0).code)
        raise SyntaxError('%s: unknown function %s' % (getattr(node, 'pos', '?'), name))

    def as_char(self, x):
        if x.cat == 'char': return x.code
        if x.cat == 'str': return 'H.strchar(%s, %s)' % (x.code, self.pc('strchar'))
        raise SyntaxError('char expected')

    # ---- statements (structured)
    def emit(self, s): self.out.append('  ' * self.ind + s)

    def store(self, a, t, v, pos=''):
        k = t.kind
        if k == 'int':
            if v.cat == 'real': raise SyntaxError('%s: real to integer' % pos)
            self.emit('R.ww(%s, %s);' % (a, v.code))
        elif k in ('byte', 'bool'):
            self.emit('R.wb(%s, %s);' % (a, v.code))
        elif k == 'char':
            self.emit('R.wb(%s, %s);' % (a, self.as_char(v)))
        elif k == 'real':
            self.emit('R.wr(%s, %s);' % (a, self.as_real(v)))
        elif k == 'str':
            self.emit('R.ws(%s, %s, %d);' % (a, self.as_str(v), t.max))
        elif k in ('record', 'array'):
            assert v.cat == 'mem' and v.t.size == t.size, (pos, t, v.t)
            self.emit('R.move(%s, %s, %d);' % (a, v.code, t.size))
        else: raise SyntaxError('%s: cannot assign %s' % (pos, k))

    def stmt(self, s):
        k = s.k
        if k == 'empty': return
        if k == 'compound':
            for x in s.stmts: self.stmt(x)
            return
        if k == 'assign':
            a, t = self.addr_of(s.target)
            v = self.expr(s.expr)
            self.store(a, t, v, s.pos)
            return
        if k == 'pcall': return self.pcall(s)
        if k == 'if':
            self.emit('if (%s) {' % self.cond(s.cond)); self.ind += 1
            self.stmt(s.then); self.ind -= 1
            if s.els is not None:
                self.emit('} else {'); self.ind += 1; self.stmt(s.els); self.ind -= 1
            self.emit('}')
            return
        if k == 'while':
            self.emit('while (%s) {' % self.cond(s.cond)); self.ind += 1; self.stmt(s.body); self.ind -= 1; self.emit('}')
            return
        if k == 'repeat':
            self.emit('do {'); self.ind += 1
            for x in s.body: self.stmt(x)
            self.ind -= 1; self.emit('} while (!(%s));' % self.cond(s.cond))
            return
        if k == 'for':
            a, t = self.addr_of(s.var)
            st = self.expr(s.start); en = self.expr(s.stop)
            n = self.newtmp()
            wr = 'R.ww' if t.kind == 'int' else 'R.wb'
            rd = 'R.rw' if t.kind == 'int' else 'R.rb'
            self.emit('{'); self.ind += 1
            self.emit('const s%d = %s, e%d = %s;' % (n, st.code, n, en.code))
            cmp = '>=' if not s.down else '<='
            self.emit('if (e%d %s s%d) {' % (n, cmp, n)); self.ind += 1
            self.emit('let c%d = %s;' % (n, ('e%d - s%d + 1' if not s.down else 's%d - e%d + 1') % (n, n)))
            self.emit('%s(%s, s%d);' % (wr, a, n))
            self.emit('for (;;) {'); self.ind += 1
            if id(s) in self.loopcost: self.emit(self.cpucall(s))
            self.stmt(s.body)
            self.emit('if (--c%d === 0) break;' % n)
            self.emit('%s(%s, %s(%s) %s 1);' % (wr, a, rd, a, '+' if not s.down else '-'))
            self.ind -= 1; self.emit('}')
            self.ind -= 1; self.emit('}')
            if self.loopcost.get(id(s)): self.emit('await R.catchUp();')
            self.ind -= 1; self.emit('}')
            return
        if k == 'case':
            sel = self.expr(s.sel); n = self.newtmp()
            self.emit('{'); self.ind += 1
            self.emit('const k%d = %s;' % (n, sel.code if sel.cat != 'str' else self.as_char(sel)))
            first = True
            for labels, st in s.arms:
                conds = []
                for lo, hi in labels:
                    l = self.expr(lo)
                    if hi is None: conds.append('k%d === %s' % (n, l.code))
                    else: conds.append('(k%d >= %s && k%d <= %s)' % (n, l.code, n, self.expr(hi).code))
                self.emit('%sif (%s) {' % ('' if first else '} else ', ' || '.join(conds))); first = False
                self.ind += 1; self.stmt(st); self.ind -= 1
            if s.els is not None:
                self.emit('} else {' if not first else '{'); self.ind += 1
                for x in s.els: self.stmt(x)
                self.ind -= 1
            if not first or s.els is not None: self.emit('}')
            self.ind -= 1; self.emit('}')
            return
        if k == 'with':
            saved = len(self.withs)
            self.emit('{'); self.ind += 1
            for r in s.recs:
                a, t = self.addr_of(r)
                n = self.newtmp()
                self.emit('const w%d = %s;' % (n, a))
                self.withs.append((t, 'w%d' % n))
            self.stmt(s.body)
            del self.withs[saved:]
            self.ind -= 1; self.emit('}')
            return
        if k == 'labeled' or k == 'goto':
            raise SyntaxError('goto/label in structured procedure')
        raise SyntaxError('stmt %r' % s)

    def cond(self, e):
        v = self.expr(e)
        return '%s' % v.code

    def pc(self, kind):
        """next original call-site address for an operation that can fail (see tools/pcmap.py)"""
        lst = self.pcs.get(kind)
        if lst is None: return '0'
        if not lst: raise SyntaxError('pcmap exhausted for %s in %s' % (kind, self.curproc))
        return '0x%04X' % lst.pop(0)

    def newtmp(self):
        self.tmp += 1; return self.tmp

    # ---- procedure calls & builtins
    def pcall(self, s):
        name, args = s.name, s.args
        A = lambda i: self.expr(args[i])
        def io():
            pc = self.pc('io')
            if s.ioc: self.emit('R.ioCheck(%s);' % pc)
        if name in self.procs:
            p = self.procs[name]
            cargs = []
            for (pn, pt, isvar), arg in zip(p.params, args):
                if isvar:
                    a, t = self.addr_of(arg); cargs.append(a)
                else:
                    v = self.expr(arg)
                    if pt.kind == 'str': cargs.append(self.as_str(v))
                    elif pt.kind == 'char': cargs.append(self.as_char(v))
                    elif pt.kind == 'real': cargs.append(self.as_real(v))
                    else: cargs.append(v.code)
            self.emit('await %s(%s);' % (name, ', '.join(cargs)))
            return
        if name in ('write', 'writeln'):
            if args and args[0].k == 'id' and args[0].name in ('lst', 'kbd', 'con', 'trm'):
                raise SyntaxError('write to device not supported')
            if args and args[0].k in ('id', 'field', 'index'):
                s0 = self.lookup(args[0].name) if args[0].k == 'id' else None
                if s0 is not None and s0.kind == 'var' and s0.t.kind == 'file':
                    fa, ft = self.addr_of(args[0])
                    for x in args[1:]:
                        a, t = self.addr_of(x); self.emit('R.writeRec(%s, %s);' % (fa, a)); io()
                    return
            for x in args:
                w = d = None
                if x.k == 'fmt': w, d, x = x.w, x.d, x.e
                v = self.expr(x)
                wc = self.expr(w).code if w is not None else '0'
                if v.cat == 'str': self.emit('R.wrStr(%s, %s);' % (v.code, wc))
                elif v.cat == 'char': self.emit('R.wrChar(%s, %s);' % (v.code, wc))
                elif v.cat == 'int': self.emit('R.wrInt(%s, %s);' % (v.code, wc))
                elif v.cat == 'bool': self.emit('R.wrBool(%s, %s);' % (v.code, wc))
                elif v.cat == 'real': self.emit('R.wrReal(%s, %s, %s);' % (v.code, wc if w is not None else '-1', self.expr(d).code if d is not None else '-1'))
                else: raise SyntaxError('%s: cannot write %s' % (s.pos, v.cat))
            if name == 'writeln': self.emit('R.wrLn();')
            return
        if name in ('read', 'readln'):
            if args and args[0].k == 'id' and args[0].name == 'kbd':
                for x in args[1:]:
                    a, t = self.addr_of(x); self.emit('R.wb(%s, await R.readKbd());' % a)
                return
            if args and args[0].k == 'id':
                s0 = self.lookup(args[0].name)
                if s0 is not None and s0.kind == 'var' and s0.t.kind == 'file':
                    fa, ft = self.addr_of(args[0])
                    for x in args[1:]:
                        a, t = self.addr_of(x); self.emit('R.readRec(%s, %s);' % (fa, a)); io()
                    return
            if name == 'readln': self.emit('await R.rdBeginLn();')
            else: self.emit('await R.rdBegin();')
            for x in args:
                a, t = self.addr_of(x)
                if t.kind == 'str': self.emit('R.ws(%s, await R.rdStr(%d), %d);' % (a, t.max, t.max))
                else: raise SyntaxError('%s: read of %s not supported' % (s.pos, t.kind))
            if name == 'readln': self.emit('await R.rdLn();')
            return
        simple = {'clrscr': 'R.clrScr()', 'clreol': 'R.clrEol()', 'nosound': 'R.noSound()', 'lowvideo': 'R.lowVideo()',
                  'highvideo': 'R.highVideo()', 'normvideo': 'R.highVideo()', 'halt': 'R.halt()', 'randomize': 'R.randomize()',
                  'graphcolormode': 'R.graphColorMode()'}
        if name in simple and not args: self.emit(simple[name] + ';'); return
        if name == 'exit': self.emit('return;'); return
        if name == 'gotoxy': self.emit('R.gotoXY(%s, %s);' % (A(0).code, A(1).code)); return
        if name == 'textcolor': self.emit('R.textColor(%s);' % A(0).code); return
        if name == 'textbackground': self.emit('R.textBackground(%s);' % A(0).code); return
        if name == 'window': self.emit('R.window(%s);' % ', '.join(A(i).code for i in range(4))); return
        if name == 'textmode': self.emit('R.textMode(%s);' % (A(0).code if args else '-1')); return
        if name == 'delay': self.emit('await R.delay(%s);' % A(0).code); return
        if name == 'sound': self.emit('R.sound(%s);' % A(0).code); return
        if name == 'palette': self.emit('R.palette(%s);' % A(0).code); return
        if name == 'getpic':
            a, t = self.addr_of(args[0])
            self.emit('R.getPic(%s, %s);' % (a, ', '.join(A(i).code for i in range(1, 5)))); return
        if name == 'putpic':
            a, t = self.addr_of(args[0])
            self.emit('R.putPic(%s, %s, %s);' % (a, A(1).code, A(2).code)); return
        if name == 'assign':
            fa, ft = self.addr_of(args[0]); self.emit('R.assign(%s, %s);' % (fa, self.as_str(A(1)))); return
        if name in ('reset', 'rewrite'):
            fa, ft = self.addr_of(args[0])
            rs = ft.el.size if ft.el is not None else 128
            self.emit('R.%s(%s, %d);' % (name, fa, rs)); io(); return
        if name == 'close':
            fa, ft = self.addr_of(args[0]); self.emit('R.close(%s);' % fa); io(); return
        if name == 'chain':
            fa, ft = self.addr_of(args[0]); self.emit('R.chain(%s);' % fa); io(); return
        if name == 'str':
            x = args[0]; w = None
            if x.k == 'fmt': w, x = x.w, x.e
            a, t = self.addr_of(args[1])
            self.emit('R.ws(%s, H.strInt(%s, %s), %d);' % (a, self.expr(x).code, self.expr(w).code if w else '0', t.max)); return
        if name == 'val':
            sv = self.as_str(A(0)); va, vt = self.addr_of(args[1]); ca, ct = self.addr_of(args[2])
            assert vt.kind == 'int'
            n = self.newtmp()
            self.emit('{ const v%d = H.valInt(%s, R.rw(%s)); R.ww(%s, v%d[0]); R.ww(%s, v%d[1]); }' % (n, sv, va, va, n, ca, n)); return
        if name == 'delete':
            a, t = self.addr_of(args[0])
            self.emit('R.ws(%s, H.del(R.rs(%s), %s, %s), %d);' % (a, a, A(1).code, A(2).code, t.max)); return
        if name == 'insert':
            a, t = self.addr_of(args[1])
            self.emit('R.ws(%s, H.ins(%s, R.rs(%s), %s), %d);' % (a, self.as_str(A(0)), a, A(2).code, t.max)); return
        if name == 'move':
            sa, _ = self.addr_of(args[0]); da, _ = self.addr_of(args[1])
            self.emit('R.move(%s, %s, %s);' % (da, sa, A(2).code)); return
        raise SyntaxError('%s: unknown procedure %s' % (s.pos, name))

    # ---- lowering for procedures with labels
    def lower(self, s, L):
        """append instructions to L: ('code', js) ('label', id) ('jmp', id) ('jf', cond, id)"""
        k = s.k
        if k == 'labeled':
            L.append(('label', 'u' + s.label)); self.lower(s.stmt, L); return
        if k == 'goto':
            L.append(('jmp', 'u' + s.label)); return
        if k == 'compound':
            for x in s.stmts: self.lower(x, L)
            return
        if k == 'if':
            n = self.newtmp(); Lelse, Lend = 'e%d' % n, 'x%d' % n
            L.append(('jf', self.cond(s.cond), Lelse))
            self.lower(s.then, L)
            if s.els is not None:
                L.append(('jmp', Lend)); L.append(('label', Lelse)); self.lower(s.els, L); L.append(('label', Lend))
            else:
                L.append(('label', Lelse))
            return
        if k == 'while':
            n = self.newtmp(); Ltop, Lend = 't%d' % n, 'x%d' % n
            L.append(('label', Ltop)); L.append(('jf', self.cond(s.cond), Lend)); self.lower(s.body, L)
            L.append(('jmp', Ltop)); L.append(('label', Lend)); return
        if k == 'repeat':
            n = self.newtmp(); Ltop = 't%d' % n
            L.append(('label', Ltop))
            for x in s.body: self.lower(x, L)
            L.append(('jf', self.cond(s.cond), Ltop)); return
        if k == 'for':
            a, t = self.addr_of(s.var)
            st = self.expr(s.start); en = self.expr(s.stop)
            n = self.newtmp(); self.fvars.append(n)
            wr = 'R.ww' if t.kind == 'int' else 'R.wb'
            rd = 'R.rw' if t.kind == 'int' else 'R.rb'
            Ltop, Lend = 't%d' % n, 'x%d' % n
            cmp = '>=' if not s.down else '<='
            L.append(('code', 's%d = %s; e%d = %s;' % (n, st.code, n, en.code)))
            L.append(('jf', 'e%d %s s%d' % (n, cmp, n), Lend))
            L.append(('code', 'c%d = %s; %s(%s, s%d);' % (n, ('e%d - s%d + 1' if not s.down else 's%d - e%d + 1') % (n, n), wr, a, n)))
            L.append(('label', Ltop))
            if id(s) in self.loopcost: L.append(('code', self.cpucall(s)))
            self.lower(s.body, L)
            L.append(('jf', '--c%d !== 0' % n, Lend))
            L.append(('code', '%s(%s, %s(%s) %s 1);' % (wr, a, rd, a, '+' if not s.down else '-')))
            L.append(('jmp', Ltop)); L.append(('label', Lend))
            if self.loopcost.get(id(s)): L.append(('code', 'await R.catchUp();'))
            return
        if k == 'case':
            sel = self.expr(s.sel); n = self.newtmp(); self.fvars.append(n)
            Lend = 'x%d' % n
            L.append(('code', 'k%d = %s;' % (n, sel.code if sel.cat != 'str' else self.as_char(sel))))
            for i, (labels, st) in enumerate(s.arms):
                conds = []
                for lo, hi in labels:
                    l = self.expr(lo)
                    if hi is None: conds.append('k%d === %s' % (n, l.code))
                    else: conds.append('(k%d >= %s && k%d <= %s)' % (n, l.code, n, self.expr(hi).code))
                Lnext = 'n%d_%d' % (n, i)
                L.append(('jf', ' || '.join(conds), Lnext))
                self.lower(st, L)
                L.append(('jmp', Lend)); L.append(('label', Lnext))
            if s.els is not None:
                for x in s.els: self.lower(x, L)
            L.append(('label', Lend)); return
        if k == 'with':
            saved = len(self.withs)
            for r in s.recs:
                a, t = self.addr_of(r); n = self.newtmp(); self.fvars.append(n)
                L.append(('code', 'w%d = %s;' % (n, a)))
                self.withs.append((t, 'w%d' % n))
            self.lower(s.body, L)
            del self.withs[saved:]
            return
        # simple statements -> code
        saved_out, saved_ind = self.out, self.ind
        self.out, self.ind = [], 0
        self.stmt(s)
        code = '\n'.join(self.out)
        self.out, self.ind = saved_out, saved_ind
        if code: L.append(('code', code))

    def emit_lowered(self, L):
        ids = {}
        def lid(x):
            if x not in ids: ids[x] = len(ids) + 1
            return ids[x]
        self.emit('let pc = 0;')
        self.emit('for (;;) switch (pc) {')
        self.emit('case 0:')
        self.ind += 1
        for ins in L:
            if ins[0] == 'label':
                self.ind -= 1; self.emit('case %d: // %s' % (lid(ins[1]), ins[1])); self.ind += 1
            elif ins[0] == 'jmp':
                self.emit('pc = %d; continue;' % lid(ins[1]))
            elif ins[0] == 'jf':
                self.emit('if (!(%s)) { pc = %d; continue; }' % (ins[1], lid(ins[2])))
            else:
                for line in ins[1].split('\n'): self.emit(line)
        self.emit('return;')
        self.ind -= 1
        self.emit('}')

    # ---- procedures
    def set_loop_costs(self, name, body):
        loops = []; for_loops(body, loops)
        sl = [l for l in loops if has_sound(l.body)]
        key = self.key(name)
        if self.like is not None:      # tables of another program: the procedure of the same name
            key = '#%d' % self.like.index(name) if name in self.like else None
        costs = self.cpumap.get(key, [])
        fast = self.speedmap.get(key, [])
        fast = list(fast) + [0] * (len(costs) - len(fast))
        self.loopcost = {id(l): (c, f) for l, c, f in zip(sl, costs, fast) if c}

    def cpucall(self, loop):
        c, f = self.loopcost[id(loop)]
        if f: return 'R.cpu(%d, %d);   // clocks per iteration: IBM PC (8088, 4.77 MHz), DOSBox default speed' % (c, f)
        return 'R.cpu(%d);   // 8088 clocks per iteration on the IBM PC' % c

    def compile_proc(self, d):
        p = self.procs[d.name]
        self.begin_pcs(d.name)
        self.set_loop_costs(d.name, d.body)
        self.locals = {}; self.withs = []; self.fvars = []
        # frame layout: locals first-declared highest (like TP3), then value params above them
        loc = []
        haslabels = False
        for x in d.decls:
            if x.k == 'var':
                t = self.resolve_type(x.type)
                for nm in x.names: loc.append((nm, t))
            elif x.k == 'label': haslabels = True
            elif x.k == 'type': self.types[x.name] = self.resolve_type(x.type)
            elif x.k in ('const', 'tconst'): raise SyntaxError('local consts unsupported')
        size = sum(t.size for _, t in loc) + sum(t.size for _, t, v in p.params if not v)
        off = size
        for nm, t in loc:
            off -= t.size
            self.locals[nm] = Sym('var', t=t, addr='(fp + %d)' % off)
        jsparams = []
        copies = []
        for nm, t, isvar in p.params:
            if isvar:
                jsparams.append('p_' + nm)
                self.locals[nm] = Sym('var', t=t, addr='p_' + nm)
            else:
                off -= t.size
                jsparams.append('a_' + nm)
                self.locals[nm] = Sym('var', t=t, addr='(fp + %d)' % off)
                if t.kind == 'str': copies.append('R.ws(fp + %d, a_%s, %d);' % (off, nm, t.max))
                elif t.kind == 'int': copies.append('R.ww(fp + %d, a_%s);' % (off, nm))
                elif t.kind in ('byte', 'char', 'bool'): copies.append('R.wb(fp + %d, a_%s);' % (off, nm))
                else: raise SyntaxError('value param kind %s' % t.kind)
        self.emit('async function %s(%s) {' % (d.name, ', '.join(jsparams))); self.ind += 1
        self.emit('const fp = R.enter(%d);' % size)
        self.emit('try {'); self.ind += 1
        for c in copies: self.emit(c)
        if haslabels:
            L = []
            self.lower(d.body, L)
            if self.fvars:
                self.emit('let ' + ', '.join('s%d, e%d, c%d, k%d, w%d' % (n, n, n, n, n) for n in self.fvars) + ';')
            self.emit_lowered(L)
        else:
            self.stmt(d.body)
        self.end_pcs()
        self.ind -= 1; self.emit('} finally { R.leave(%d); }' % size)
        self.ind -= 1; self.emit('}')
        self.emit('')

    def key(self, name):
        """tables (pcmap, sound loops) are keyed by procedure position, so renaming is safe"""
        if name == '$main': return name
        return '#%d' % self.proc_order.index(name)

    def begin_pcs(self, name):
        import copy as _copy
        self.curproc = name
        self.pcs = _copy.deepcopy(self.pcmap.get(self.key(name), {})) if self.pcmap is not None else {}
    def end_pcs(self):
        left = {k: v for k, v in self.pcs.items() if v}
        if self.pcmap is not None and left: raise SyntaxError('pcmap not fully used in %s: %r' % (self.curproc, left))

    def compile(self):
        self.locals = {}; self.withs = []; self.pcs = {}; self.curproc = None
        self.proc_order = [d.name for d in self.prog.decls if d.k == 'proc']
        self.declare_globals(self.prog.decls)
        self.ind = 0
        self.emit('// Generated by tools/pas2js.py from %s -- do not edit.' % self.name)
        self.emit("import * as H from './pasrt.js';")
        self.emit('let R;')
        self.emit('')
        for d in self.prog.decls:
            if d.k == 'proc': self.compile_proc(d)
        # main
        self.locals = {}; self.withs = []; self.fvars = []
        haslabels = any(d.k == 'label' for d in self.prog.decls)
        self.emit("export const CS_INIT = '%s';" % base64.b64encode(bytes(self.cs)).decode())
        self.emit('export const DS_END = 0x%04x;' % self.ds)
        self.emit('export async function main(rt) {'); self.ind += 1
        self.emit('R = rt;')
        self.emit('R.mem.set(H.b64(CS_INIT), 0x10000);')
        self.begin_pcs('$main')
        self.set_loop_costs('$main', self.prog.body)
        if haslabels:
            L = []
            self.lower(self.prog.body, L)
            if self.fvars:
                self.emit('let ' + ', '.join('s%d, e%d, c%d, k%d, w%d' % (n, n, n, n, n) for n in self.fvars) + ';')
            self.emit_lowered(L)
        else:
            self.stmt(self.prog.body)
        self.end_pcs()
        self.ind -= 1; self.emit('}')
        return '\n'.join(self.out) + '\n'


def jsstr(s):
    out = "'"
    for ch in s:
        o = ord(ch)
        if ch == "'" or ch == '\\': out += '\\' + ch
        elif 32 <= o < 127: out += ch
        else: out += '\\x%02x' % o
    return out + "'"


def main():
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--pcmap'); ap.add_argument('--prog'); ap.add_argument('--csout')
    ap.add_argument('--cpu', help='soundloops.json from measure_sound_loops.py')
    ap.add_argument('--speed', help='soundspeed.json from measure_sound_loops.py --dosbox: the same loops at '
                    'DOSBox\'s default speed; the runtime chooses between the two (Runtime.speed)')
    ap.add_argument('--like', help='the --cpu/--speed tables are those of this program (e.g. MONOCODE.PAS): '
                    'each procedure takes the timings of its namesake there (sound test copies)')
    a = ap.parse_args()
    src, dst = a.src, a.dst
    pcmap = json.load(open(a.pcmap))[a.prog] if a.pcmap else None
    toks = lex(src, [])
    prog = Parser(toks).program()
    cpu = json.load(open(a.cpu)) if a.cpu else None
    speed = json.load(open(a.speed)) if a.speed else None
    like = None
    if a.like:
        ref = Parser(lex(a.like, [])).program()
        like = [d.name for d in ref.decls if d.k == 'proc']
    c = Compiler(prog, os.path.basename(src), pcmap, cpu, speed, like)
    js = c.compile()
    open(dst, 'w').write(js)
    print('%s: %d procedures, data ends at DS:%04X, %d bytes of typed constants' % (
        os.path.basename(src), sum(1 for d in prog.decls if d.k == 'proc'), c.ds, len(c.cs)))
    if a.csout: open(a.csout, 'wb').write(bytes(c.cs))


if __name__ == '__main__':
    main()
