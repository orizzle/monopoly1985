"""Map 1985-runtime addresses (memory offsets, CS:0100-based) to TP 3.02 runtime addresses."""
import difflib, os, pickle
S = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(os.path.dirname(S), 'original', 'monopoly.com')
TP302 = os.environ.get('TP302', os.path.join(S, 'tp302'))
RT_ORIG_END = 0x2C7C   # file offsets
RT_302_END = 0x2C4D
_cache = os.path.join(S, '.rtruns.pkl')
def runs():
    if os.path.exists(_cache): return pickle.load(open(_cache, 'rb'))
    a = open(ORIG, 'rb').read()[:RT_ORIG_END]
    b = open(os.path.join(TP302, 'TURBO.COM'), 'rb').read()[:RT_302_END]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    r = [(i1 + 0x100, i2 + 0x100, i1 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t == 'equal' and i2 - i1 >= 4]
    pickle.dump(r, open(_cache, 'wb')); return r
def o2n(addr):
    for s, e, d in runs():
        if s <= addr < e: return addr - d
    return None
def n2o(addr):
    for s, e, d in runs():
        if s - d <= addr < e - d: return addr + d
    return None
# Same builtin, different entry: 3.02 TextMode has an extra prefix before the 1985 body
OVERRIDE_N2O = {0x0295: 0x02d9}
def n2o_near(addr):
    if addr in OVERRIDE_N2O: return OVERRIDE_N2O[addr]
    r = n2o(addr)
    if r is not None: return r
    best = None
    for s, e, d in runs():
        if s - d <= addr: best = addr + d
    return best
