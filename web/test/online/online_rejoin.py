# Online game recovery: a player reloads and rejoins (the copy is rebuilt from the log), leaves (the
# host may then play for them), and comes back. The copies must agree throughout.
# usage: online_rejoin.py                                (MONOPOLY_URL, default http://127.0.0.1:8771/)
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
        # 1. the guest reloads the page and joins again: the copy is rebuilt from the log
        await guest.close(); guest = await newpage(gctx)
        await typ(guest, 'j'); await typ(guest, code + '\n'); await typ(guest, 'Bo\n')
        for i in range(30):
            await host.wait_for_timeout(1000)
            g = await guest.evaluate(ST); h = await host.evaluate(ST)
            if g and g['p'] >= h['p'] - 5: break
        print('rejoined after', i + 1, 's: host p', h['p'], 'guest p', g['p'], 'ff', g['ff'], '|', g['status'])
        await compare([host, guest], 'after rejoin')
        await play([host, guest], 20)
        await compare([host, guest], 'after more play')
        # 2. the guest leaves; on Bo's turn the host may play for Bo after 20 s
        await guest.close(); guest = None
        st = await play([host, None], 60)
        print('waiting on', st['by'], st['status'])
        await host.wait_for_timeout(23000)
        st = await host.evaluate(ST); print('host sees:', st['status'], '| takeover button', st['take'], st['takeText'])
        if st['take']:
            await host.click('#takeover'); await host.wait_for_timeout(1500)
            p0 = (await host.evaluate(ST))['p']
            for _ in range(8):
                await host.keyboard.press(random.choice(['Enter', 'g'])); await host.wait_for_timeout(1200)
            st = await host.evaluate(ST); print('host playing for Bo: p', p0, '->', st['p'], '|', st['status'])
        # 3. Bo comes back and takes the seat over again
        guest = await newpage(gctx)
        await typ(guest, 'j'); await typ(guest, code + '\n'); await typ(guest, 'Bo\n')
        for i in range(40):
            await host.wait_for_timeout(1000)
            g = await guest.evaluate(ST); h = await host.evaluate(ST)
            if g and g['p'] >= h['p'] - 5: break
        print('Bo back after', i + 1, 's:', g['status'], '| host:', h['status'])
        await play([host, guest], 15)
        await compare([host, guest], 'after return')
        await b.close()
asyncio.run(main())
