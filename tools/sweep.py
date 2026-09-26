import sys
ROOT=sys.argv[1] if len(sys.argv)>1 else '.'
import asyncio, os, http.server, socketserver, threading, json
from playwright.async_api import async_playwright
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(s,*a): pass
socketserver.TCPServer.allow_reuse_address=True
h=socketserver.TCPServer(("",8780),Q); threading.Thread(target=h.serve_forever,daemon=True).start()
U='http://localhost:8780/index.html'
async def main():
    r={}; errs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch()
        # the page scrolls smoothly: link and deep-link probes need reduced_motion='reduce' or they read mid-animation
        ctx=await b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce'); await ctx.grant_permissions(['clipboard-read','clipboard-write'])
        pg=await ctx.new_page()
        pg.on('pageerror',lambda e:errs.append('pageerror: '+str(e))); pg.on('console',lambda m: errs.append('console.'+m.type+': '+m.text) if m.type in('error','warning') else None)
        pg.on('requestfailed',lambda q: errs.append('requestfailed: '+q.url))
        await pg.goto(U,wait_until='networkidle'); await pg.wait_for_timeout(400)
        # 1. click every in-page link (nav, toc, strip, pills, captions, footer) and check the target lands under the sticky bar
        links=await pg.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(a=>a.getAttribute('href'))")
        bad=[]
        for hsh in sorted(set(links)):
            if hsh=='#': continue
            await pg.evaluate(f"document.querySelector('a[href=\"{hsh}\"]').click()"); await pg.wait_for_timeout(700)
            top=await pg.evaluate(f"(()=>{{const el=document.querySelector('{hsh}');if(!el)return 'MISSING';const r=el.getBoundingClientRect();return Math.round(r.top)}})()")
            if top=='MISSING' or not (0<=top<=140): bad.append((hsh,top))
        r['inpage_links']=len(set(links)); r['links_landing_off']=bad
        # 2. every file link resolves
        files=await pg.evaluate("[...document.querySelectorAll('a[href]:not([href^=\"#\"])')].map(a=>a.getAttribute('href'))")
        st={}
        for f in sorted(set(files)):
            if f.startswith('http'): st[f]='external'; continue
            resp=await pg.request.get('http://localhost:8780/'+f); st[f]=resp.status
        r['file_links']=st
        # 3. v8 cold cases: show-all toggle on a fresh page, then a verdict on every card, then keyboard on a fresh context
        await pg.goto(U,wait_until='networkidle'); await pg.evaluate("localStorage.removeItem('ldd-verdicts')"); await pg.reload(wait_until='networkidle')
        await pg.click('#showAllCases'); r['showall_opens_six']=await pg.evaluate("document.querySelectorAll('.cold .file.open').length")==6
        r['showall_label_open']=await pg.text_content('#showAllCases')
        r['showall_no_verdicts']=await pg.evaluate("[...document.querySelectorAll('.cold .back dd.vd')].every(d=>getComputedStyle(d).display==='none')")
        r['chips_hidden_when_shown']=await pg.evaluate("[...document.querySelectorAll('.cold .file .pick')].every(p=>getComputedStyle(p).display==='none')")
        await pg.click('#showAllCases'); r['closed_after_toggle']=await pg.evaluate("document.querySelectorAll('.cold .file.open').length")==0
        for i in range(1,7):
            await pg.click(f'#cold-0{i} .pick button.ch >> nth=0'); await pg.wait_for_timeout(80)
        r['all_six_open']=await pg.evaluate("document.querySelectorAll('.cold .file.open').length")==6
        r['chips_locked_when_guessed']=await pg.evaluate("[...document.querySelectorAll('.cold .file .pick button.ch')].every(b=>b.getAttribute('aria-disabled')==='true')")
        r['one_pressed_per_card']=await pg.evaluate("[...document.querySelectorAll('.cold .file')].every(c=>c.querySelectorAll('button.ch[aria-pressed=true]').length===1)")
        r['verdicts']=await pg.evaluate("[...document.querySelectorAll('.cold .back dd.vd')].map(d=>d.textContent)")
        r['tally']=await pg.text_content('#coldTally'); r['showall_hidden_when_all_guessed']=await pg.evaluate("getComputedStyle(document.getElementById('showAllCases')).display==='none'")
        await pg.reload(wait_until='networkidle'); r['verdicts_persist']=await pg.evaluate("document.querySelectorAll('.cold .file.guessed').length")==6
        await pg.evaluate("localStorage.removeItem('ldd-verdicts')"); await pg.reload(wait_until='networkidle')
        await pg.locator('#cold-04 .pick button.ch').first.focus()
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(80)
        r['keyboard_reveal']=await pg.evaluate("document.getElementById('cold-04').classList.contains('open')")
        r['focus_moved_to_answer']=await pg.evaluate("document.activeElement.closest('#cold-04 .back')!==null")
        await pg.evaluate("localStorage.removeItem('ldd-verdicts')")
        # 4. copy buttons
        await pg.click('#shareLink'); await pg.wait_for_timeout(100); r['copy_link']=await pg.evaluate("navigator.clipboard.readText()")
        r['copy_post_removed']=await pg.evaluate("document.getElementById('sharePost')===null")
        # 5. back-to-top button appears after scroll and returns to top, focus on h1
        await pg.evaluate("window.scrollTo({top:3000,behavior:'instant'})"); await pg.wait_for_timeout(300)
        r['totop_visible']=await pg.evaluate("document.getElementById('totop').classList.contains('show')")
        await pg.click('#totop'); await pg.wait_for_timeout(900)
        r['totop_scrollY']=await pg.evaluate("Math.round(scrollY)"); r['totop_focus_h1']=await pg.evaluate("document.activeElement.tagName")
        # 6. progress bar moves
        await pg.evaluate("window.scrollTo({top:document.body.scrollHeight,behavior:'instant'})"); await pg.wait_for_timeout(300)
        r['progress_at_end']=await pg.evaluate("document.getElementById('pbar').style.transform")
        # 7. welcome-back toast on revisit, its Continue link and dismiss
        pg2=await ctx.new_page(); pg2.on('pageerror',lambda e:errs.append('pageerror(p2): '+str(e)))
        await pg2.goto(U,wait_until='networkidle'); await pg2.wait_for_timeout(500)
        r['toast_shown']=await pg2.evaluate("!document.getElementById('toast').hidden")
        r['toast_text']=await pg2.evaluate("document.getElementById('toast').textContent.trim()")
        if r['toast_shown']:
            await pg2.click('#toast button'); await pg2.wait_for_timeout(400); r['toast_dismissed']=await pg2.evaluate("document.getElementById('toast').hidden")
        # 8. deep links to every section and cold case in fresh pages
        deep={}
        for hsh in ['#start','#mindset','#clue','#gadgets','#rules','#casefile','#closed','#cold-05','#push-back','#is-training']:
            p3=await ctx.new_page(); p3.on('pageerror',lambda e:errs.append('pageerror(deep): '+str(e)))
            await p3.goto(U+hsh,wait_until='networkidle'); await p3.wait_for_timeout(500)
            deep[hsh]=await p3.evaluate(f"Math.round(document.querySelector('{hsh}').getBoundingClientRect().top)")
            await p3.close()
        r['deep_links_top_px']=deep
        # 9. full keyboard tab through: count focusable, ensure every focused element is visible
        await pg.goto(U,wait_until='networkidle')
        hidden=[]; n=0
        for _ in range(140):
            await pg.keyboard.press('Tab'); n+=1
            info=await pg.evaluate("(()=>{const e=document.activeElement;const r=e.getBoundingClientRect();const s=getComputedStyle(e);return {t:e.tagName+'.'+e.className,vis:r.width>0&&r.height>0&&s.visibility!=='hidden',end:e===document.body}})()")
            if info['end']: break
            if not info['vis']: hidden.append(info['t'])
        r['tab_stops']=n; r['tab_hidden_focus']=hidden
        # 10. mobile: menu open/close via button, link click closes, outside click closes, pills scroll
        m=await b.new_context(viewport={'width':375,'height':800},reduced_motion='reduce'); mp=await m.new_page(); mp.on('pageerror',lambda e:errs.append('pageerror(m): '+str(e)))
        await mp.goto(U,wait_until='networkidle'); await mp.wait_for_timeout(400)
        await mp.click('#menuBtn'); await mp.wait_for_timeout(350); r['m_menu_open']=await mp.evaluate("document.getElementById('nav').classList.contains('open')")
        await mp.click('#nav a[href=\"#gadgets\"]'); await mp.wait_for_timeout(700)
        r['m_menu_closed_after_link']=await mp.evaluate("!document.getElementById('nav').classList.contains('open')")
        r['m_landed_gadgets']=await mp.evaluate("Math.round(document.getElementById('gadgets').getBoundingClientRect().top)")
        await mp.click('#menuBtn'); await mp.wait_for_timeout(350); await mp.mouse.click(360,400); await mp.wait_for_timeout(350)
        r['m_menu_closed_outside']=await mp.evaluate("!document.getElementById('nav').classList.contains('open')")
        r['m_body_scroll_restored']=await mp.evaluate("document.body.style.overflow===''")
        r['m_pills_scrollable']=await mp.evaluate("(()=>{const p=document.querySelector('#clue nav.pills');return p.scrollWidth>p.clientWidth})()")
        await mp.click('#cold-02 .pick button.ch >> nth=1'); r['m_reveal']=await mp.evaluate("document.getElementById('cold-02').classList.contains('open')")
        # 11. reduced motion honoured
        rm=await b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce'); rp=await rm.new_page()
        await rp.goto(U,wait_until='networkidle'); r['reduced_motion_scroll_behavior']=await rp.evaluate("getComputedStyle(document.documentElement).scrollBehavior")
        r['errors']=errs
        await b.close()
    print(json.dumps(r,indent=1,ensure_ascii=False))
asyncio.run(main())
