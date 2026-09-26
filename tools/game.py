# The main case in File 07, played to the verdict at 1440 and 375 (one wrong answer on purpose, so 5 of 6).
# Usage: python3 game.py [root]
import asyncio, sys, json, http.server, socketserver, threading
from playwright.async_api import async_playwright
ROOT=sys.argv[1] if len(sys.argv)>1 else '.'; PORT=8787
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(s,*a): pass
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),Q); threading.Thread(target=srv.serve_forever,daemon=True).start()
async def play(pg):
    async def opt(t): await pg.locator('.gm-opt',has_text=t).first.click(); await pg.wait_for_timeout(80)
    async def nxt(t): await pg.locator('button',has_text=t).last.click(); await pg.wait_for_timeout(150)
    tops=[]
    async def head(): tops.append(await pg.evaluate("(()=>{const h=document.querySelector('.gm-h');return [h.textContent,Math.round(h.getBoundingClientRect().top),document.activeElement===h]})()"))
    await pg.click('.masthead .cta a[href="#main-case"]'); await pg.wait_for_timeout(300); await head()
    await opt('Book the training'); await opt('Ask what made this urgent now'); await nxt('Next: Clarify'); await head()
    await opt('Each team hears the update'); await nxt('Next: Look'); await head()
    for i in [0,1,3,5]: await pg.locator('.gm-src').nth(i).click(); await pg.wait_for_timeout(60)
    await nxt('Name the cause'); await head()
    await opt('Managers are briefed last'); await nxt('Build the fix'); await head()
    for i in [0,2,4,6]: await pg.locator('.gm-fix').nth(i).click()
    await nxt('Check the fix'); await nxt('Write the hypothesis'); await head()
    await opt('One business unit'); await pg.wait_for_timeout(150); await opt('80% of teams'); await nxt('Close the case'); await head()
    res=await pg.evaluate("(()=>({rank:document.querySelector('.gm-rank').textContent,file:[...document.querySelectorAll('.gm-file dd')].map(d=>d.textContent),best:localStorage.getItem('ldd-case'),solvedOpen:!document.querySelector('#closed .tl-wrap').closest('[hidden]')}))()")
    return tops,res
async def main():
    out={}
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for w in [1440,375]:
            errs=[]; pg=await b.new_page(viewport={'width':w,'height':850},reduced_motion='reduce')
            pg.on('pageerror',lambda e: errs.append(str(e))); pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
            await pg.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
            tops,res=await play(pg); out[w]={'screens':tops,'result':res,'errors':errs}; await pg.close()
        await b.close()
    print(json.dumps(out,indent=1,ensure_ascii=False))
asyncio.run(main())
