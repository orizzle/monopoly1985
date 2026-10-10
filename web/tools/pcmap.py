#!/usr/bin/env python3
"""Build pcmap.json: for every procedure of the original programs, the addresses of the runtime calls
that can raise a run-time or I/O error, in code order.  The 1985 runtime reports these addresses as
'PC=xxxx' in its error messages; pas2js.py attaches them to the corresponding operations.
input: annotated listings of the original binaries (chn.lst, ovl.lst, com.lst)."""
import re, sys, json
ERR = {'Copy': 'copy', 'Concat': 'cat', 'StrToChar': 'strchar'}
FILEOPS = {'ResetTyped', 'RewriteTyped', 'ResetUntyped', 'RewriteUntyped', 'ReadTyped', 'WriteTyped',
           'CloseF', 'Chain', 'BlockRead', 'BlockWrite', 'Erase', 'Rename', 'Seek'}
def scan(path, out, prog, ovl=False, first=None):
    cur = first; ovn = 0; end = None
    if first: out.setdefault(first, {})
    for line in open(path):
        m = re.match(r';==== PROC (P_[0-9a-f]{4}).*end=([0-9a-f]{4})', line)
        if m:
            if not ovl and cur != '$main' or (not ovl and cur == '$main' and False):
                cur = m.group(1).lower(); out.setdefault(cur, {}); end = int(m.group(2), 16)
            continue
        if ovl and line.startswith(';######## OVERLAY RECORD'):
            ovn += 1; cur = 'ov%d' % ovn; out.setdefault(cur, {}); continue
        m = re.match(r'([0-9a-f]{4}): \S+\s+call (\w+)', line)
        if not m: continue
        a, r = int(m.group(1), 16), m.group(2)
        if not ovl and end is not None and a >= end and cur != '$main':
            nxt = None
        if not ovl and end is not None and a >= end:
            cur = '$main'; out.setdefault(cur, {})
        if cur is None: continue
        if r in ERR: out[cur].setdefault(ERR[r], []).append(a)
        elif r in FILEOPS: out[cur].setdefault('io', []).append(a)
    return out
def main():
    an = sys.argv[1]
    game = {}
    scan(an + '/chn.lst', game, 'game')
    # code after the last procedure's end is the main program: P_ebab is the last; listing marks
    # procedures only, so split main off from the last procedure by its end address
    scan(an + '/ovl.lst', game, 'game', ovl=True)
    loader = {}
    scan(an + '/com.lst', loader, 'loader', first='startgame')
    json.dump({'game': game, 'loader': loader}, open(sys.argv[2], 'w'), indent=0)
if __name__ == '__main__': main()
