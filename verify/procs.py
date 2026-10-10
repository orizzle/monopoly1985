"""Find TP3 procedures in a program image: prologue 55 8B EC 55 E9 rel16."""
import struct, re
def find_procs(buf, base, start):
    out = []
    for m in re.finditer(re.escape(b'\x55\x8b\xec\x55\xe9'), buf[start:]):
        i = start + m.start()
        body = (base + i + 7 + struct.unpack('<h', buf[i+5:i+7])[0]) & 0xffff
        out.append({'addr': base + i, 'body': body})
    # end: next 'mov sp,bp; pop bp; ret[ n]' after body
    for p in out:
        j = p['body'] - base
        k = buf.find(b'\x8b\xe5\x5d', j)
        while k >= 0 and buf[k+3] not in (0xc3, 0xc2):
            k = buf.find(b'\x8b\xe5\x5d', k + 1)
        p['ret'] = base + k
        p['end'] = base + k + (4 if buf[k+3] == 0xc3 else 6)
        p['argbytes'] = 0 if buf[k+3] == 0xc3 else struct.unpack('<H', buf[k+4:k+6])[0]
        sub = buf[j:j+3]
        p['locals'] = sub[2] if sub[:2] == b'\x83\xec' else (struct.unpack('<H', buf[j+2:j+4])[0] if sub[:2] == b'\x81\xec' else 0)
    # nesting
    for p in out:
        p['parent'] = None
        for q in out:
            if q['addr'] < p['addr'] < q['body']:
                if p['parent'] is None or q['addr'] > p['parent']: p['parent'] = q['addr']
    return out
