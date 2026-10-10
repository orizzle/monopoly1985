# Plays an online game in 2-4 browsers (Playwright/Chromium; player 2 on a phone with the on-screen
# keyboard). The player whose turn it is presses random keys, sometimes 2-3 times; the others press
# keys too, which must be ignored. Every copy records its state every 128 keyboard polls; all
# copies must agree at every recorded point, and when they all wait for a key their data, dice,
# random seed and screen must be identical.
# usage: online_sync.py PLAYERS STEPS SEED [simple]     (MONOPOLY_URL, default http://127.0.0.1:8771/)
import asyncio, os, sys, json, random, time
from playwright.async_api import async_playwright
URL = os.environ.get('MONOPOLY_URL', 'http://127.0.0.1:8771/')
NPL = int(sys.argv[1]) if len(sys.argv) > 1 else 2
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 120
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1
random.seed(SEED)
SIMPLE = len(sys.argv) > 4
STATE = """() => { const {R, online} = window.monopolyState(); if (!online) return null;
  const fnv = (a, n) => { let h = 0x811C9DC5; for (let i = 0; i < n; i++) h = Math.imul(h ^ a[i], 0x01000193); return h >>> 0; };
  return {p: online.gate.p, H: online.s.H, by: online.gate.by, owner: online.gate.owner, hash: fnv(R.mem, 0x10000),
          vram: fnv(R.vram, 0x4000), mode: R.bios.mode, dice: [R.rw(0x264), R.rw(0x266)], cur: R.rw(0x262), seed: R.seed >>> 0,
          ff: R.ff, status: document.getElementById('olstatus').textContent}; }"""
KEYS = ['Enter'] * 6 + ['g', 'G', 'p', 'a', 'b', 'n', 'l', 'c', 'r', 'y', 'f', 'Escape', 'Space', '1', '5', '0', '2', 's', 'd', 'o', 'u', 'h', 't', 'm', 'F1']
def code_of(k):
    if k in ('Enter', 'Escape', 'Space', 'F1', 'F2', 'Backspace'): return k
    if k.isdigit(): return 'Digit' + k
    return 'Key' + k.upper()
async def press(p, k):
    if p.touch:
        if len(k) == 1 and k.isupper(): await p.tap('#kbd .key[data-code="Shift"]')
        await p.tap(f'#kbd .key[data-code="{code_of(k)}"]')
    else: await p.keyboard.press(k)
async def typ(p, text, delay=60):
    for ch in text:
        await press(p, ch if ch != '\n' else 'Enter'); await p.wait_for_timeout(delay)
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pages, navs, errs = [], [0] * NPL, []
        for i in range(NPL):
            ctx = await (b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True) if i == 1
                         else b.new_context(viewport={'width': 1000, 'height': 900}))
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e, i=i: errs.append((i, str(e))))
            pg.on('framenavigated', lambda f, i=i: navs.__setitem__(i, navs[i] + 1) if f.parent_frame is None else None)
            await pg.goto(URL); await pg.evaluate("window.monopolyTraceEvery = 128"); await pg.click('#overlay'); await pg.wait_for_timeout(400)
            pg.touch = i == 1
            pages.append(pg)
        names = ['Al', 'Bo', 'Cy', 'Di'][:NPL]
        await typ(pages[0], 'c'); await typ(pages[0], names[0] + '\n'); await pages[0].wait_for_timeout(1200)
        code = json.loads(await pages[0].evaluate("localStorage.getItem('monopoly.online')"))['code']
        for i in range(1, NPL):
            await typ(pages[i], 'j'); await typ(pages[i], code + '\n'); await typ(pages[i], names[i] + '\n')
        await pages[0].wait_for_timeout(1500)
        await typ(pages[0], 's'); await pages[0].wait_for_timeout(5000)
        checks = mism = rejected = ignored = 0; dice_seen = []; turns = {}
        for step in range(STEPS):
            st = [await pg.evaluate(STATE) for pg in pages]
            if None in st: print('not started', st); break
            by = st[0]['by']; turns[by] = turns.get(by, 0) + 1
            k = random.choice(['Enter', 'g', 'g', 'Enter', 'Space']) if SIMPLE else random.choice(KEYS)
            n = 1 if random.random() < 0.7 else random.choice([2, 3])
            for _ in range(n):
                await press(pages[by], k); await pages[by].wait_for_timeout(random.choice([20, 60, 150]))
            if NPL > 1 and random.random() < 0.25:
                other = random.choice([i for i in range(NPL) if i != by])
                await press(pages[other], random.choice(KEYS))
            await pages[0].wait_for_timeout(random.choice([100, 300, 700, 1500, 2500]))
            if step % 4 == 3:
                # wait until every copy sits at the same keyboard poll (a wait for a key), then compare
                for _ in range(60):
                    st = [await pg.evaluate(STATE) for pg in pages]
                    if len({s['p'] for s in st}) == 1:
                        await pages[0].wait_for_timeout(300)
                        st2 = [await pg.evaluate(STATE) for pg in pages]
                        if len({s['p'] for s in st2}) == 1 and st2[0]['p'] == st[0]['p']: st = st2; break
                    await pages[0].wait_for_timeout(250)
                else:
                    print('step', step, 'no common wait', [s['p'] for s in st]); continue
                checks += 1
                keys = ['hash', 'vram', 'mode', 'dice', 'cur', 'seed']
                same = all(all(s[k] == st[0][k] for k in keys) for s in st)
                if not same: mism += 1; print('MISMATCH step', step, st)
                # players whose turn it is not try to roll / answer: nothing may change, nothing logged
                by = st[0]['by']; nlog0 = await pages[0].evaluate("window.monopolyState().online.s.keys.size")
                for o in [i for i in range(NPL) if i != by]:
                    for k in ['Enter', 'g', 'Enter']: await press(pages[o], k); await pages[o].wait_for_timeout(80)
                await pages[0].wait_for_timeout(1200)
                st3 = [await pg.evaluate(STATE) for pg in pages]
                nlog1 = await pages[0].evaluate("window.monopolyState().online.s.keys.size")
                intr = any(s['p'] != st[0]['p'] or s['hash'] != st[0]['hash'] or s['vram'] != st[0]['vram'] for s in st3) or nlog1 != nlog0
                ignored += 0 if intr else 1
                if intr: print('INTRUSION ACCEPTED step', step, 'by', by, st[0]['p'], [s['p'] for s in st3], nlog0, nlog1)
                if st[0]['dice'] not in dice_seen: dice_seen.append(st[0]['dice'])
        print(f'players={NPL} steps={STEPS} checks={checks} mismatches={mism} reloads={[n - 1 for n in navs]} errors={errs[:3]}')
        print('turns', turns, 'other players ignored', ignored, 'of', checks); print('dice seen', dice_seen[:12], 'final p', [s['p'] for s in st], 'status', st[0]['status'])
        await pages[0].wait_for_timeout(4000)
        traces = [await pg.evaluate("window.monopolyState().online.gate.trace") for pg in pages]
        common = set(traces[0]).intersection(*map(set, traces[1:]))
        bad = [p for p in common if any(t[p] != traces[0][p] for t in traces[1:])]
        rolls = sorted({tuple(traces[0][p][1:3]) for p in common})
        print(f'trace points compared {len(common)}, different {len(bad)}; distinct dice states {len(rolls)}')
        for i, pg in enumerate(pages): await pg.screenshot(path=f'/tmp/ol2_{i}.png')
        await b.close()
asyncio.run(main())
