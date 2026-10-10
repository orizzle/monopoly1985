#!/usr/bin/env python3
"""Ground-truth comparison of the JS runtime against the original 1985 TP3 runtime under DOSBox.

Each test is an op list.  It is turned into (1) a Turbo Pascal probe program, compiled with TP 3.02
(tools/tpc.py), relocated onto the 1985 runtime (tools/relocate.py com) and run under DOSBox, and
(2) the same calls on the headless JS runtime (runops.mjs).  The dumps (video memory, BIOS mode /
cursor / colour register, WhereX/WhereY, GetPic buffers) are compared byte-for-byte.

usage: dosbox_compare.py [testname ...]      (needs dosbox, node, ../../verify with TP 3.02 + emu2)"""
import json, os, subprocess, sys, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
import tempfile
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(REPO, 'verify')
TP302 = os.environ.get('TP302', os.path.join(TOOLS, 'tp302'))
WORK = os.environ.get('MONO_WORK', os.path.join(tempfile.gettempdir(), 'monopoly-webtest')); os.makedirs(WORK, exist_ok=True)
DBXCONF = """[sdl]\noutput=surface\n[dosbox]\nmachine=cga\nmemsize=4\n[cpu]\ncycles=max\n[mixer]\nnosound=true\n[speaker]\npcspeaker=false\n"""

def pstr(s):
    return "'" + s.replace("'", "''") + "'" if s else "''"

def to_pascal(ops):
    body = []; pics = {}; strs = {}
    for op in ops:
        k, a = op[0], op[1:]
        if k == 'tm': body.append('TextMode(%d);' % a[0])
        elif k == 'win': body.append('Window(%d,%d,%d,%d);' % tuple(a))
        elif k == 'clr': body.append('ClrScr;')
        elif k == 'eol': body.append('ClrEol;')
        elif k == 'gxy': body.append('GotoXY(%d,%d);' % tuple(a))
        elif k == 'tc': body.append('TextColor(%d);' % a[0])
        elif k == 'tb': body.append('TextBackground(%d);' % a[0])
        elif k == 'lv': body.append('LowVideo;')
        elif k == 'hv': body.append('HighVideo;')
        elif k == 'wr': body.append('Write(%s);' % pstr(a[0]))
        elif k == 'wrs': body.append('Write(%s:%d);' % (pstr(a[0]), a[1]))
        elif k == 'wri': body.append('Write(%d:%d);' % (a[0], a[1]))
        elif k == 'wrc': body.append('Write(Chr(%d):%d);' % (a[0], a[1]))
        elif k == 'ln': body.append('WriteLn;')
        elif k == 'gcm': body.append('GraphColorMode;')
        elif k == 'pal': body.append('Palette(%d);' % a[0])
        elif k == 'pic':
            pics.setdefault(a[0], len(pics))
            for i, b in enumerate(a[1]): body.append('PB[%d,%d]:=%d;' % (pics[a[0]], i, b))
        elif k == 'put': body.append('PutPic(PB[%d],%d,%d);' % (pics[a[0]], a[1], a[2]))
        elif k == 'get':
            body.append('GetPic(PB[%d],%d,%d,%d,%d);' % (pics[a[0]], a[1], a[2], a[3], a[4]))
            body.append('for DI:=0 to %d do begin DB:=PB[%d,DI]; Write(DF,DB) end;' % (a[5] - 1, pics[a[0]]))
        elif k == 'keys':
            for c, s in a[0]:
                body.append('KT:=MemW[$40:$1C]; Mem[$40:KT]:=%d; Mem[$40:KT+1]:=%d; KT:=KT+2; if KT=$3E then KT:=$1E; MemW[$40:$1C]:=KT;' % (c, s))
        elif k in ('rdln', 'rd'):
            v = 'S%d' % a[0]; strs[a[1]] = v
            body.append(('ReadLn(%s);' if k == 'rdln' else 'Read(%s);') % v)
        elif k == 'wrv': body.append('Write(%s);' % strs[a[0]])
        elif k == 'dump': body.append('Dump;')
        else: raise SystemExit('op ' + k)
    sdecl = ''.join('  S%d: string[%d];\n' % (n, n) for n in sorted({int(v[1:]) for v in strs.values()}))
    src = ("program probe;\n{$I GRAPH.P}\nvar DF: file of byte; DB: byte; DI, KT: integer;\n"
           "  PB: array[0..3,0..8191] of byte;\n" + sdecl +
           "procedure Dump;\nbegin\n  for DI := 0 to 16383 do begin DB := Mem[$B800:DI]; Write(DF, DB) end;\n"
           "  DB := Mem[$40:$49]; Write(DF, DB); DB := Mem[$40:$50]; Write(DF, DB);\n"
           "  DB := Mem[$40:$51]; Write(DF, DB); DB := Mem[$40:$66]; Write(DF, DB);\n"
           "  DB := WhereX; Write(DF, DB); DB := WhereY; Write(DF, DB);\nend;\n"
           "begin\n  Assign(DF, 'DUMP.BIN'); Rewrite(DF);\n" + ''.join('  %s\n' % l for l in body) +
           "  Close(DF);\nend.\n")
    return src

def run_dosbox(ops, name):
    d = os.path.join(WORK, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    open(os.path.join(d, 'PROBE.PAS'), 'w').write(to_pascal(ops))
    for f in ('GRAPH.P', 'GRAPH.BIN'): shutil.copy(os.path.join(TP302, f), d)
    r = subprocess.run(['python3', '-I', os.path.join(TOOLS, 'tpc.py'), 'PROBE.PAS', 'out', '--inc', 'GRAPH.P',
                        '--raw', 'GRAPH.BIN', '--timeout', '90'], cwd=d, capture_output=True, text=True)
    if 'FAILED' in r.stdout: raise SystemExit(name + ': compile failed: ' + r.stdout[-300:])
    subprocess.run(['python3', '-I', os.path.join(TOOLS, 'relocate.py'), 'com', 'out/PROBE.COM', 'P85.COM'], cwd=d, check=True)
    open(os.path.join(d, 'dbx.conf'), 'w').write(DBXCONF)
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    subprocess.run(['timeout', '60', 'dosbox', '-conf', 'dbx.conf', '-c', 'mount c ' + d, '-c', 'c:',
                    '-c', 'P85.COM', '-c', 'exit'], cwd=d, env=env, capture_output=True)
    return open(os.path.join(d, 'DUMP.BIN'), 'rb').read()

def run_js(ops, name, font=None):
    d = os.path.join(WORK, name)
    open(os.path.join(d, 'ops.json'), 'w').write(json.dumps(ops))
    cmd = ['node', os.path.join(HERE, 'runops.mjs'), os.path.join(d, 'ops.json'), os.path.join(d, 'JS.BIN')]
    if font: cmd.append(font)
    subprocess.run(cmd, check=True)
    return open(os.path.join(d, 'JS.BIN'), 'rb').read()

def extract_font():
    """Test-only: glyphs as drawn by the DOSBox BIOS in graphics mode, so graphics-mode text can be
    compared pixel-exactly.  Written to the scratch work dir only; never shipped."""
    path = os.path.join(WORK, 'testfont.bin')
    if os.path.exists(path): return path
    ops = [['gcm'], ['tc', 3]]
    for c in range(256):
        ops += [['gxy', c % 32 + 1, c // 32 + 1], ['wrc', c, 0]] if c not in (7, 8, 10, 13) else []
    ops.append(['dump'])
    v = run_dosbox(ops, 'font')
    font = bytearray(2048)
    for c in range(256):
        cx, cy = c % 32, c // 32
        for y in range(8):
            py = cy * 8 + y; off = (py & 1) * 0x2000 + (py >> 1) * 80 + cx * 2
            w = (v[off] << 8) | v[off + 1]; b = 0
            for x in range(8):
                if (w >> (14 - 2 * x)) & 3: b |= 0x80 >> x
            font[c * 8 + y] = b
    open(path, 'wb').write(font)
    return path

def describe(o, n):
    if len(o) != len(n): return 'length %d vs %d' % (len(o), len(n))
    d = [i for i in range(len(o)) if o[i] != n[i]]
    return '%d bytes differ, first at %d: dosbox %s js %s' % (len(d), d[0], o[d[0]:d[0]+8].hex(), n[d[0]:d[0]+8].hex()) if d else 'IDENTICAL'

sys.path.insert(0, HERE)
from probe_tests import TESTS

if __name__ == '__main__':
    names = sys.argv[1:] or list(TESTS)
    font = extract_font()
    bad = 0
    for nm in names:
        ops = TESTS[nm]
        o = run_dosbox(ops, nm); n = run_js(ops, nm, font)
        r = describe(o, n); bad += r != 'IDENTICAL'
        print('%-22s %s' % (nm, r))
    sys.exit(1 if bad else 0)
