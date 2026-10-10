#!/usr/bin/env python3
"""Random key sessions: original (DOSBox + KEYFEED) vs port must stay identical at every key.
usage: fuzz.py SEED [NKEYS]"""
import random, subprocess, sys
seed = int(sys.argv[1]); nkeys = int(sys.argv[2]) if len(sys.argv) > 2 else 60
rnd = random.Random(seed)
KEYS = [(ord(c), s) for c, s in zip('PABGSHTMRUNLCDOYF', [0x19, 0x1e, 0x30, 0x22, 0x1f, 0x23, 0x14, 0x32, 0x13, 0x16, 0x31, 0x26, 0x2e, 0x20, 0x18, 0x15, 0x21])]
KEYS += [(c + 32, s) for c, s in KEYS[:6]]
KEYS += [(ord(str(d)), 0x02 + (d - 1) % 10 if d else 0x0b) for d in range(10)]
KEYS += [(13, 0x1c)] * 8 + [(27, 0x01), (8, 0x0e), (32, 0x39), (0, 0x3b), (0, 0x3c), (19, 0x1f)]
names = [rnd.choice(['AL', 'BO', 'CY', 'DEE', 'ED']) for _ in range(rnd.choice([2, 3]))]
script = []
for i, nm in enumerate(names):
    script.append('%d:%d:%d' % (ord(nm[0]), 0x1e, rnd.choice([50, 400, 1500])))
    for ch in nm[1:]: script.append('%d:%d:2' % (ord(ch), 0x1e))
    script.append('13:28:2')
script.append('13:28:%d' % rnd.choice([100, 900]))
for _ in range(nkeys):
    a, s = rnd.choice(KEYS)
    n = rnd.choice([0, 2, 2, 30, 30, 300, 3000])
    script.append('%d:%d:%d' % (a, s, n))
import os
r = subprocess.run([os.path.join(os.path.dirname(os.path.abspath(__file__)), 'e2e_session.sh'), 'fuzz%d' % seed] + script,
                   capture_output=True, text=True, env=dict(os.environ, TMO='150'))
print('seed', seed, ' '.join(script[:3]), '...')
print(r.stdout[-3000:]); print(r.stderr[-1500:])
