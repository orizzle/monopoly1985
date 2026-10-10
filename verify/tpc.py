#!/usr/bin/env python3
"""Compile a Turbo Pascal 3.02 program headlessly under emu2.
usage: tpc.py SRC.PAS OUTDIR [--chn] [--code HEX] [--data HEX] [--minheap HEX] [--maxheap HEX] [--inc FILE...]
Leaves outputs (.COM/.CHN/.0xx) and compile.log in OUTDIR."""
import os, pty, sys, time, select, shutil, re, tempfile, argparse
S = os.path.dirname(os.path.abspath(__file__))
# Turbo Pascal 3.02 (TURBO.COM, TURBO.MSG) and the emu2 DOS emulator are not part of this repository
EMU = os.environ.get('EMU2', os.path.join(S, 'emu2', 'emu2')); TP = os.environ.get('TP302', os.path.join(S, 'tp302'))
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('outdir')
ap.add_argument('--chn', action='store_true')
ap.add_argument('--code'); ap.add_argument('--data'); ap.add_argument('--minheap'); ap.add_argument('--maxheap')
ap.add_argument('--inc', nargs='*', default=[])
ap.add_argument('--raw', nargs='*', default=[])
ap.add_argument('--timeout', type=float, default=120)
ap.add_argument('--wname', help='work file name exactly as typed at the prompt')
a = ap.parse_args()
wd = tempfile.mkdtemp(dir=os.path.join(S, 'tmp')) if os.path.isdir(os.path.join(S,'tmp')) else tempfile.mkdtemp()
for f in ('TURBO.COM', 'TURBO.MSG'): shutil.copy(os.path.join(TP, f), wd)
name = os.path.basename(a.src).upper()
def todos(p, dst):
    d = open(p, 'rb').read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    if not d.endswith(b'\x1a'): d += b'\x1a'
    open(dst, 'wb').write(d)
todos(a.src, os.path.join(wd, name))
for f in a.inc: todos(f, os.path.join(wd, os.path.basename(f).upper()))
for f in a.raw: shutil.copy(f, os.path.join(wd, os.path.basename(f).upper()))
pid, fd = pty.fork()
if pid == 0:
    os.chdir(wd); os.environ['TERM'] = 'xterm'
    os.execv(EMU, [EMU, 'TURBO.COM'])
out = bytearray()
def plain(): return re.sub(r'\s+', ' ', re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', ' ', out.decode('latin1')))
def pump(t):
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.02)
        if r:
            try: d = os.read(fd, 65536)
            except OSError: return
            if not d: return
            out.extend(d)
def expect(pat, t=10):
    end = time.time() + t
    start = len(out)
    while time.time() < end:
        pump(0.05)
        if re.search(pat, plain()[-400:]): return True
    return False
def send(s, delay=0.05):
    for ch in s.encode('latin1'):
        os.write(fd, bytes([ch])); pump(delay)
expect(r'error messages', 10); send('Y'); expect(r'>', 10); pump(0.3)
send('W'); expect(r'Work file name', 5); send((a.wname or name.rsplit('.', 1)[0]) + '\r'); pump(0.5)
send('O'); pump(0.4)
if a.chn: send('H'); pump(0.3)
else:
    send('C'); pump(0.3)
    for key, val in (('O', a.code), ('D', a.data), ('I', a.minheap), ('A', a.maxheap)):
        if val is not None:
            send(key); pump(0.3); send(val + '\r'); pump(0.3)
send('Q'); pump(0.4)
mark = len(out)
send('C')
ok = expect(r'\(maximum\) >|paragraphs free >|Error \d+|ERROR|Press <ESC>|\(minimum\) >|bytes free\) >', a.timeout)
pump(0.5)
log = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', ' ', out[mark:].decode('latin1'))
try: os.kill(pid, 9)
except Exception: pass
os.makedirs(a.outdir, exist_ok=True)
open(os.path.join(a.outdir, 'compile.log'), 'w').write(log)
for f in os.listdir(wd):
    if re.search(r'\.(COM|CHN|\d\d\d)$', f, re.I) and f.upper() != 'TURBO.COM':
        shutil.copy(os.path.join(wd, f), os.path.join(a.outdir, f.upper()))
shutil.rmtree(wd, ignore_errors=True)
m = re.search(r'Error \d+[^\n]*', log)
if m or not ok:
    print('COMPILE FAILED:', re.sub(r'\s+', ' ', log)[-600:]); sys.exit(1)
print(re.sub(r'\s+', ' ', log).strip()[-400:])
