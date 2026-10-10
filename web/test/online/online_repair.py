# A copy whose data is corrupted on purpose must be noticed (the hash in the key log) and rebuilt,
# without the copies reloading in a loop, and agree again afterwards.
# usage: online_repair.py                                (MONOPOLY_URL, default http://127.0.0.1:8771/)
import asyncio, os, json, random
from playwright.async_api import async_playwright
URL = os.environ.get('MONOPOLY_URL', 'http://127.0.0.1:8771/')
random.seed(11)
ST = """() => { const o = window.monopolyState(); if (!o || !o.online) return null; const g = o.online.gate;
  return {p: g.p, H: o.online.s.H, by: g.by, owner: g.owner, ff: o.R.ff, status: document.getElementById('olstatus').textContent,
          take: !document.getElementById('takeover').hidden, takeText: document.getElementById('takeover').textContent}; }"""
async def typ(p, text, delay=60):
    for ch in text:
        await p.keyboard.press(ch if ch != '\n' else 'Enter'); await p.wait_for_timeout(delay)
async def newpage(ctx):
    pg = await ctx.new_page(); pg.on('pageerror', lambda e: print('ERR', e))
    await pg.goto(URL); await pg.evaluate("window.monopolyTraceEvery = 128"); await pg.click('#overlay'); await pg.wait_for_timeout(400)
    return pg
async def compare(pages, label):
    await pages[0].wait_for_timeout(3000)
    tr = [await pg.evaluate("window.monopolyState().online.gate.trace") for pg in pages]
    common = set(tr[0]) & set(tr[1])
    bad = [p for p in common if tr[0][p] != tr[1][p]]
    print(f'{label}: compared {len(common)} trace points, different {len(bad)}')
async def play(pages, steps):
    for _ in range(steps):
        st = await pages[0].evaluate(ST); by = st['by']
        if by >= len(pages) or pages[by] is None: return st
        await pages[by].keyboard.press(random.choice(['Enter', 'g', 'g', 'Enter']))
        await pages[0].wait_for_timeout(random.choice([300, 800, 1500]))
    return await pages[0].evaluate(ST)
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        hctx, gctx = await b.new_context(), await b.new_context()
        host, guest = await newpage(hctx), await newpage(gctx)
        await typ(host, 'c'); await typ(host, 'Al\n'); await host.wait_for_timeout(1200)
        code = json.loads(await host.evaluate("localStorage.getItem('monopoly.online')"))['code']
        await typ(guest, 'j'); await typ(guest, code + '\n'); await typ(guest, 'Bo\n'); await host.wait_for_timeout(1500)
        await typ(host, 's'); await host.wait_for_timeout(4000)
        await play([host, guest], 30)
        # corrupt Bo's copy (Al's cash) and let the game go on: the difference must be found and repaired
        await guest.evaluate("window.monopolyState().R.mem[0x3897 + 13] ^= 1")
        pages = [host, guest]; reloads = [0, 0]
        for k, pg in enumerate(pages):
            pg.on('framenavigated', lambda f, k=k: reloads.__setitem__(k, reloads[k] + 1) if f.parent_frame is None else None)
        for step in range(40):
            for k, pg in enumerate(pages):          # a page that reloaded asks for a click to rejoin
                if await pg.evaluate("document.getElementById('overlay').style.display !== 'none'"):
                    await pg.wait_for_timeout(300); await pg.evaluate("window.monopolyTraceEvery = 128"); await pg.click("#overlay")
            st = [await pg.evaluate(ST) for pg in pages]
            if None not in st:
                await pages[st[0]['by']].keyboard.press(random.choice(['g', 'Enter']))
            await host.wait_for_timeout(1200)
            if step > 15 and sum(reloads) and None not in st: break
        print('reloads (host, guest):', reloads)
        for i in range(30):
            await host.wait_for_timeout(1000)
            g = await guest.evaluate(ST); h = await host.evaluate(ST)
            if g and h and abs(g['p'] - h['p']) < 6: break
        await play([host, guest], 25)
        await compare([host, guest], 'after repair')
        cash = [await pg.evaluate("window.monopolyState().R.rw(0x3897 + 13)") for pg in pages]
        print('Al cash in both copies:', cash)
        await b.close()
asyncio.run(main())
