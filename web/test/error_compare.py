#!/usr/bin/env python3
"""I/O error output: the 1985 runtime's message vs the JS runtime (DOSBox ground truth).
P85.COM writes some text, then Reset()s a missing file under {$I+} and aborts; D85.COM (a second
relocated probe, run from a batch file with echo off) dumps the screen the abort left behind."""
import os, re, subprocess, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosbox_compare as dc
W = os.path.join(dc.WORK, 'ioerror'); shutil.rmtree(W, ignore_errors=True); os.makedirs(W)
pre = [['win', 1, 1, 80, 25], ['clr'], ['win', 10, 5, 50, 12], ['tc', 14], ['tb', 1], ['clr'], ['wr', 'about to fail']]
src = dc.to_pascal(pre).replace("  Close(DF);\nend.", "  Close(DF);\n  Assign(DF, 'NOFILE.XYZ'); Reset(DF);\nend.")
def build(name, source):
    open(os.path.join(W, name + '.PAS'), 'w').write(source)
    for f in ('GRAPH.P', 'GRAPH.BIN'): shutil.copy(os.path.join(dc.S, 'tp302', f), W)
    r = subprocess.run(['python3', '-I', os.path.join(dc.TOOLS, 'tpc.py'), name + '.PAS', 'out', '--inc', 'GRAPH.P',
                        '--raw', 'GRAPH.BIN', '--timeout', '90'], cwd=W, capture_output=True, text=True)
    assert 'FAILED' not in r.stdout, r.stdout
    subprocess.run(['python3', '-I', os.path.join(dc.TOOLS, 'relocate.py'), 'com', 'out/%s.COM' % name, name[0] + '85.COM'], cwd=W, check=True)
build('PERR', src)
build('DUMPER', dc.to_pascal([['dump']]))
open(os.path.join(W, 'RUN.BAT'), 'w').write('@echo off\r\nP85.COM\r\nD85.COM\r\n')
open(os.path.join(W, 'dbx.conf'), 'w').write(dc.DBXCONF)
env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
subprocess.run(['timeout', '60', 'dosbox', '-conf', 'dbx.conf', '-c', 'mount c ' + W, '-c', 'c:', '-c', 'RUN.BAT', '-c', 'exit'],
               cwd=W, env=env, capture_output=True)
o = open(os.path.join(W, 'DUMP.BIN'), 'rb').read()
text = bytes(o[0:16384:2]).decode('latin1')
m = re.search(r'I/O error ([0-9A-F]{2}), PC=([0-9A-F]{4})', text)
print('DOSBox message:', m.group(0) if m else None)
ops = pre + [['dump']][:0] + [['ioerr', int(m.group(1), 16), int(m.group(2), 16)], ['dump']]
import json
open(os.path.join(W, 'ops.json'), 'w').write(json.dumps(ops))
subprocess.run(['node', os.path.join(dc.HERE, 'runops.mjs'), os.path.join(W, 'ops.json'), os.path.join(W, 'JS.BIN')], check=True)
n = open(os.path.join(W, 'JS.BIN'), 'rb').read()
for r in range(4, 13): print(repr(bytes(o[r*160:(r+1)*160:2]).decode('latin1').rstrip()))
print('ioerror', dc.describe(o, n))
