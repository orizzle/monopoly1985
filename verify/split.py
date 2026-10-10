#!/usr/bin/env python3
"""Split a merged MONOCODE.PAS into MONOCODE.PAS (program header + declarations + {$I} lines)
and include files MONOCOD1.INC ... each below LIMIT bytes, breaking only between sections."""
import re, sys, os
src, outdir = sys.argv[1], sys.argv[2]
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 40000
t = open(src).read()
secs = list(re.finditer(r'\{@@BEGIN (\w+)\}.*?\{@@END \1\}\n?', t, re.S))
head = t[:secs[0].start()]
decl = secs[0].group(0); assert secs[0].group(1) == 'DECL'
rest = secs[1:]
mainsec = rest[-1]; assert mainsec.group(1) == 'MAIN'
chunks, cur = [], ''
for m in rest[:-1]:
    s = m.group(0)
    if cur and len(cur) + len(s) > LIMIT:
        chunks.append(cur); cur = ''
    cur += s + '\n'
if cur: chunks.append(cur)
os.makedirs(outdir, exist_ok=True)
names = []
for i, c in enumerate(chunks, 1):
    n = 'MONOCOD%d.INC' % i; names.append(n)
    open(os.path.join(outdir, n), 'w').write(c)
main = head + decl + '\n' + ''.join('{$I %s}\n' % n for n in names) + '\n' + mainsec.group(0)
open(os.path.join(outdir, 'MONOCODE.PAS'), 'w').write(main)
print(' '.join(names), [len(c) for c in chunks], len(main))
