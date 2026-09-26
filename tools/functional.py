import asyncio, os, http.server, socketserver, threading, json
from playwright.async_api import async_playwright
import sys
ROOT=sys.argv[1] if len(sys.argv)>1 else '.'; PORT=8734
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
def serve():
    os.chdir(ROOT); socketserver.TCPServer.allow_reuse_address=True
    with socketserver.TCPServer(("",PORT),Q) as h: h.serve_forever()
threading.Thread(target=serve,daemon=True).start()
async def main():
    r={}
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce'); page=await ctx.new_page()
        errs=[]; page.on('pageerror',lambda e:errs.append(str(e))); page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
        await page.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
        # 1. scroll slowly through File 03 and record pill highlights
        seq=[]
        top=await page.evaluate("document.getElementById('clue').getBoundingClientRect().top+scrollY")
        end=await page.evaluate("document.getElementById('gadgets').getBoundingClientRect().top+scrollY")
        y=top
        while y<end:
            await page.evaluate(f"window.scrollTo({{top:{y},behavior:'instant'}})"); await page.wait_for_timeout(60)
            cur=await page.evaluate("(()=>{const a=document.querySelector('#clue nav.pills a[aria-current=true]');return a?a.textContent:null})()")
            if not seq or seq[-1]!=cur: seq.append(cur)
            y+=300
        r['pills03_sequence']=seq
        # 2. anchors land clear of sticky pills: target top >= 84
        lands={}
        for h in ['#clue-c','#push-back','#is-training','#clue']:
            await page.goto(f'http://localhost:{PORT}/index.html{h}',wait_until='networkidle'); await page.wait_for_timeout(300)
            lands[h]=await page.evaluate(f"document.querySelector('{h}').getBoundingClientRect().top")
        r['anchor_top_px']=lands
        # 3. reveal cards + show all
        await page.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
        r['open_default']=await page.evaluate("document.querySelectorAll('.cold .file.open').length")
        # v8: a verdict chip replaces 'Reveal the cause'; a guessed card stays open when the answers are hidden again
        await page.click('#cold-01 .pick button.ch[data-gap="Process"]'); r['open_after_click']=await page.evaluate("document.querySelectorAll('.cold .file.open').length")
        r['verdict_01']=await page.text_content('#cold-01 .back dd.vd'); r['tally']=await page.text_content('#coldTally')
        await page.click('#showAllCases'); r['open_after_showall']=await page.evaluate("document.querySelectorAll('.cold .file.open').length")
        r['showall_label']=await page.text_content('#showAllCases')
        r['verdict_lines_after_showall']=await page.evaluate("[...document.querySelectorAll('.cold .back dd.vd')].filter(d=>getComputedStyle(d).display!=='none').length")
        await page.click('#showAllCases'); r['open_after_hide_guessed_stays']=await page.evaluate("document.querySelectorAll('.cold .file.open').length")
        await page.evaluate("localStorage.removeItem('ldd-verdicts')")
        # 4. deep link opens a case
        await page.goto(f'http://localhost:{PORT}/index.html#cold-03',wait_until='networkidle'); await page.wait_for_timeout(200)
        r['deeplink_cold03_open']=await page.evaluate("document.getElementById('cold-03').classList.contains('open')")
        # 5. copy buttons
        await ctx.grant_permissions(['clipboard-read','clipboard-write'])
        # 'Copy a line to post' (#sharePost) was removed in v8; test the remaining copy button
        r['share_post_removed']=await page.evaluate("document.getElementById('sharePost')===null")
        await page.click('#shareLink'); await page.wait_for_timeout(100)
        r['share_link_text']=await page.evaluate("navigator.clipboard.readText()")
        r['share_link_label']=await page.text_content('#shareLink')
        await page.wait_for_timeout(2000); r['share_link_label_reset']=await page.text_content('#shareLink')
        # 6. keyboard: tab reaches skip link, ten-minute CTA is a link
        await page.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
        await page.keyboard.press('Tab'); r['first_tab']=await page.evaluate("document.activeElement.textContent")
        r['ten_min_href']=await page.get_attribute('.masthead .cta a[href="#clue"]','href')
        # 7. read ticks after scrolling to the end
        await page.evaluate("window.scrollTo(0,document.body.scrollHeight)"); await page.wait_for_timeout(500)
        r['read_store']=await page.evaluate("localStorage.getItem('ldd-read')")
        # 8. no-js: answers visible, buttons hidden
        ctx2=await b.new_context(viewport={'width':1440,'height':900},java_script_enabled=False); p2=await ctx2.new_page()
        await p2.goto(f'http://localhost:{PORT}/index.html',wait_until='load')
        r['nojs_back_visible']=await p2.evaluate("getComputedStyle(document.querySelector('#cold-01 .back')).display")
        r['nojs_pick_display']=await p2.evaluate("getComputedStyle(document.querySelector('#cold-01 .pick')).display")
        r['nojs_verdict_display']=await p2.evaluate("getComputedStyle(document.querySelector('#cold-01 .back dd.vd')).display")
        r['nojs_tally_hidden']=await p2.evaluate("document.getElementById('coldTally').hidden")
        # 9. mobile menu focus + scroll lock
        ctx3=await b.new_context(viewport={'width':375,'height':800}); p3=await ctx3.new_page()
        await p3.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
        await p3.click('#menuBtn'); await p3.wait_for_timeout(350)
        r['menu_open_focus']=await p3.evaluate("document.activeElement.textContent.trim().slice(0,30)")
        r['menu_body_overflow']=await p3.evaluate("document.body.style.overflow")
        await p3.keyboard.press('Escape'); await p3.wait_for_timeout(100)
        r['menu_closed']=await p3.evaluate("!document.getElementById('nav').classList.contains('open')")
        # 10. 200% zoom overflow (emulate with 2x font via CSS zoom)
        await page.goto(f'http://localhost:{PORT}/index.html',wait_until='networkidle')
        await page.add_style_tag(content='html{font-size:200%} body{font-size:34px}')
        await page.wait_for_timeout(300)
        r['zoom200_overflow']=await page.evaluate("(()=>{let n=0;document.querySelectorAll('td,th,li,p,h1,h2,h3,h4,.hyp,.pills a').forEach(c=>{if(c.scrollWidth>c.clientWidth+2)n++});return n})()")
        r['errors']=errs
        await b.close()
    print(json.dumps(r,indent=1,ensure_ascii=False))
asyncio.run(main())
