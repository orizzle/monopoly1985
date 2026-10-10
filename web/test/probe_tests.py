"""Probe op lists for dosbox_compare.py."""
def keys(s, extra=()):
    SC = {c: s for s, cs in {0x10: 'qQ', 0x11: 'wW', 0x12: 'eE', 0x13: 'rR', 0x14: 'tT', 0x15: 'yY', 0x16: 'uU',
                             0x17: 'iI', 0x18: 'oO', 0x19: 'pP', 0x1E: 'aA', 0x1F: 'sS', 0x20: 'dD', 0x21: 'fF',
                             0x22: 'gG', 0x23: 'hH', 0x24: 'jJ', 0x25: 'kK', 0x26: 'lL', 0x2C: 'zZ', 0x2D: 'xX',
                             0x2E: 'cC', 0x2F: 'vV', 0x30: 'bB', 0x31: 'nN', 0x32: 'mM', 0x39: ' ',
                             0x02: '1', 0x03: '2', 0x04: '3', 0x05: '4', 0x06: '5', 0x07: '6', 0x08: '7',
                             0x09: '8', 0x0A: '9', 0x0B: '0', 0x34: '.'}.items() for c in cs}
    out = []
    for ch in s:
        if ch == '\r': out.append([13, 0x1C])
        elif ch == '\b': out.append([8, 0x0E])
        elif ch == '\x1b': out.append([27, 0x01])
        elif ch == '\x18': out.append([0x18, 0x2D])
        elif ch == '\x04': out.append([4, 0x20])
        elif ch == '\x12': out.append([0x12, 0x13])
        else: out.append([ord(ch), SC.get(ch, 0)])
    return [['keys', out]]

TESTS = {}
TESTS['text_basic'] = [
    ['tm', 3], ['win', 1, 1, 80, 25], ['clr'], ['wr', 'Hello world'], ['ln'],
    ['tc', 12], ['tb', 1], ['wr', 'colour'], ['tc', 16 + 14], ['wr', 'blink'], ['lv'], ['wr', 'low'], ['hv'], ['wr', 'high'],
    ['gxy', 70, 3], ['wr', 'wrap-around-the-right-edge'], ['wri', -1234, 8], ['wrs', 'ab', 5], ['wrc', 65, 3],
    ['win', 10, 5, 30, 9], ['tb', 4], ['tc', 15], ['clr'], ['wr', 'window text that is long enough to wrap twice in here'],
    ['ln'], ['wr', 'more'], ['ln'], ['wr', 'and more'], ['ln'], ['wr', 'scrolls'], ['ln'], ['wr', 'up'],
    ['gxy', 3, 2], ['eol'], ['gxy', 40, 2], ['wr', 'X'], ['gxy', 1, 9], ['wr', 'Y'], ['gxy', 0, 0], ['wr', 'Z'],
    ['dump'],
]
TESTS['text_modes'] = [
    ['win', 1, 1, 80, 25], ['clr'], ['wr', 'before'], ['tm', 3], ['wr', 'same mode keeps screen'],
    ['win', 5, 5, 60, 20], ['tm', 3], ['gxy', 1, 24], ['wr', 'bottom limit kept'], ['dump'],
    ['win', 90, 30, 100, 40], ['wr', 'clamped'], ['win', 50, 3, 20, 2], ['wr', '!'], ['dump'],
]
TESTS['gfx_text'] = [
    ['gcm'], ['pal', 3], ['tc', 1], ['gxy', 1, 1], ['wr', 'Hello'], ['tc', 2], ['gxy', 37, 2], ['wr', 'ABCDEF'],
    ['tc', 3], ['gxy', 1, 3], ['wr', 'XYZ'], ['gxy', 2, 3], ['eol'], ['tc', 19], ['gxy', 1, 5], ['wr', '##'],
    ['gxy', 1, 5], ['wr', '#'], ['tc', 2], ['tb', 1], ['gxy', 1, 7], ['wr', 'bg'],
    ['win', 5, 20, 15, 22], ['tc', 1], ['gxy', 1, 3], ['wr', 'line1'], ['ln'], ['wr', 'line2'], ['ln'], ['wr', 'l3'],
    ['dump'], ['pal', 0], ['dump'], ['pal', 1], ['pal', 2], ['dump'], ['clr'], ['wr', 'back to text'], ['dump'],
]
PIC = [2, 0, 6, 0, 3, 0, 0x1B, 0xE0, 0xFF, 0xF0, 0x55, 0x50]
BIG = [2, 0, 13, 0, 4, 0] + [((i * 37) & 255) for i in range(16)]
TESTS['pics'] = [
    ['gcm'], ['pal', 3], ['pic', 'a', PIC], ['pic', 'b', BIG], ['pic', 'c', [0] * 64],
    ['put', 'a', 10, 20], ['put', 'a', 33, 40], ['put', 'a', 0, 2], ['put', 'a', 317, 60],
    ['put', 'a', 100, 199], ['put', 'a', 120, 201], ['put', 'a', 140, 1],  # left-edge clipping (x<0) not used by the game: see runtime notes
] + [['put', 'b', 40 + 17 * i + i, 100 + i] for i in range(8)] + [
    ['put', 'a', 320, 50], ['put', 'a', -6, 50],
    ['get', 'c', 8, 18, 20, 22, 30], ['get', 'c', 41, 99, 60, 106, 60], ['get', 'c', 0, 0, 3, 0, 8],
    ['pic', 'd', [1, 0, 6, 0, 3, 0, 255, 255, 255, 255, 255, 255]], ['put', 'd', 200, 150],
    ['dump'],
]
# The runtime checks the keyboard after every character it echoes through console output
# (Backspace/erase echo "BS space BS"), consuming one waiting key each time: filler keys
# after an erase are swallowed exactly as on the original.
TESTS['readln'] = (
    [['win', 1, 1, 80, 25], ['tb', 0], ['clr'], ['win', 5, 3, 40, 10], ['tc', 10], ['tb', 1], ['clr'], ['wr', 'Name? ']]
    + keys('AB\bxyzCD\r') + [['rdln', 10, 'a'], ['wr', '['], ['wrv', 'a'], ['wr', ']'], ['ln'], ['wr', 'Again? ']]
    + keys('pq\x1babcdefQ\r') + [['rdln', 10, 'b'], ['wrv', 'b'], ['ln'], ['wr', 'Recall? ']]
    + keys('\x04\x12\r') + [['rdln', 10, 'c'], ['wrv', 'c'], ['ln'], ['wr', 'Long? ']]
    + keys('abcdefgh\r') + [['rdln', 5, 'd'], ['wrv', 'd'], ['wr', '|']]
    + keys('pq\r') + [['rd', 10, 'e'], ['wr', '<'], ['wrv', 'e'], ['wr', '>'], ['dump']]
)
TESTS['swallow'] = (
    [['win', 1, 1, 80, 25], ['clr']] + keys('XYZ\r') + [['wr', 'AB'], ['rdln', 10, 'a'], ['wr', '='], ['wrv', 'a'], ['dump']]
)
