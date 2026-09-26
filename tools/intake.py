# The intake sheet in File 03: open from the hero, fill, save, reload, copy, clear, print only the notes,
# keyboard, no-JS, phone, old #open-case links. Usage: python3 intake.py [root] [screenshot dir]
import asyncio, os, sys, json, http.server, socketserver, threading
from playwright.async_api import async_playwright
ROOT=sys.argv[1] if len(sys.argv)>1 else '.'; SH=sys.argv[2] if len(sys.argv)>2 else '/tmp'; PORT=8766
os.makedirs(SH,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(s,*a): pass
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),Q); threading.Thread(target=srv.serve_forever,daemon=True).start()
U=f'http://localhost:{PORT}/index.html'
async def main():
  r={}; errs=[]
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce',permissions=['clipboard-read','clipboard-write'])
    pg=await ctx.new_page(); pg.on('console',lambda m: errs.append(m.text) if m.type in('error','warning') else None); pg.on('pageerror',lambda e: errs.append(str(e)))
    await pg.goto(U,wait_until='networkidle')
    r['form_hidden_initially']=await pg.evaluate("document.querySelector('.oc-form').hidden")
    r['fold_btn']=await pg.evaluate("document.querySelector('#openCase .fold-btn').textContent.trim()")
    # hero CTA opens the sheet and lands under the pills
    await pg.click('.masthead .cta a[href="#intake"]'); await pg.wait_for_timeout(300)
    r['form_open_after_hero']=not await pg.evaluate("document.querySelector('.oc-form').hidden")
    r['heading_top_after_hero']=await pg.evaluate("Math.round(document.getElementById('intake').getBoundingClientRect().top)")
    await pg.screenshot(path=SH+'/oc-empty-1440.png')
    await pg.evaluate("document.getElementById('openCase').scrollIntoView()")
    el=await pg.query_selector('#openCase'); await el.screenshot(path=SH+'/oc-empty-block-1440.png')
    # fill it
    await pg.check('input[name="oc-size"][value^="Quick"]',force=True)
    await pg.fill('#oc-asked','Communication training for all people managers')
    await pg.fill('#oc-c','Survey item "I understand where the company is going" at 41%, board asked why')
    await pg.fill('#oc-l','Managers hear it at the same moment as their teams')
    for g in ['Process','Expectations']: await pg.check(f'input[name="oc-gap"][value="{g}"]',force=True)
    await pg.fill('#oc-u','June pivot: three managers learned it in the all-hands.')
    vals={'hi':'pre-brief managers 48 hours ahead','ha':'one business unit','hm':'the share of teams hearing it from their own manager within a week','hb':'a third','ht':'80%','hw':'one quarter'}
    for k,v in vals.items(): await pg.fill('#oc-'+k,v)
    await pg.wait_for_timeout(400)
    r['sentence_partial']=await pg.text_content('.oc-sentence')
    await pg.fill('#oc-hs','a two-question pulse.')
    await pg.wait_for_timeout(400)
    r['sentence_full']=await pg.text_content('.oc-sentence')
    r['stored']=json.loads(await pg.evaluate("localStorage.getItem('ldd-open-case')"))
    await el.screenshot(path=SH+'/oc-filled-block-1440.png')
    await pg.click('#ocCopy'); await pg.wait_for_timeout(200)
    r['copy_label']=(await pg.text_content('#ocCopy')).strip()
    r['clipboard']=await pg.evaluate("navigator.clipboard.readText()")
    # reload: data returns, sheet opens itself
    await pg.reload(wait_until='networkidle'); await pg.wait_for_timeout(300)
    r['open_after_reload']=not await pg.evaluate("document.querySelector('.oc-form').hidden")
    r['asked_after_reload']=await pg.input_value('#oc-asked')
    r['gaps_after_reload']=await pg.evaluate("[...document.querySelectorAll('input[name=oc-gap]:checked')].map(i=>i.value)")
    # keyboard: tab into the chips, space toggles
    await pg.focus('input[name="oc-gap"][value="Tools"]'); await pg.keyboard.press('Space'); await pg.wait_for_timeout(100)
    r['kbd_toggle_tools']=await pg.is_checked('input[name="oc-gap"][value="Tools"]')
    r['chip_focus_outline']=await pg.evaluate("getComputedStyle(document.querySelector('input[name=oc-gap][value=Tools] + span')).outlineStyle")
    await pg.keyboard.press('Space')
    # print the case: only the case prints
    await pg.evaluate("""()=>{const d=document.documentElement;window.print=()=>{};document.getElementById('ocPrint').click();}""")
    r['print_class']=await pg.evaluate("document.documentElement.classList.contains('print-case')")
    await pg.emulate_media(media='print')
    r['print_visible_blocks']=await pg.evaluate("""()=>[...document.querySelectorAll('main .wrap > *, #clue .body > *')].filter(e=>getComputedStyle(e).display!=='none').map(e=>e.id||e.className).slice(0,10)""")
    pdf=await pg.pdf(path=SH+'/oc-print.pdf',format='A4',print_background=True)
    await pg.emulate_media(media='screen')
    await pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
    r['print_class_after']=await pg.evaluate("document.documentElement.classList.contains('print-case')")
    # whole-page print hides the sheet
    await pg.emulate_media(media='print')
    r['fullprint_oc_display']=await pg.evaluate("getComputedStyle(document.getElementById('openCase')).display")
    await pg.emulate_media(media='screen')
    # clear: needs two presses
    await pg.click('#ocClear'); r['clear_armed']=(await pg.text_content('#ocClear')).strip()
    r['asked_after_one_press']=await pg.input_value('#oc-asked')
    await pg.click('#ocClear'); await pg.wait_for_timeout(400)
    r['asked_after_clear']=await pg.input_value('#oc-asked')
    r['store_after_clear']=await pg.evaluate("localStorage.getItem('ldd-open-case')")
    r['focus_after_clear']=await pg.evaluate("document.activeElement.id")
    # copy when empty says so and focuses the first field
    await pg.click('#ocCopy'); await pg.wait_for_timeout(100)
    r['empty_copy_focus']=await pg.evaluate("document.activeElement.id")
    # E: the map table
    r['fixmap_rows']=await pg.evaluate("document.querySelectorAll('#fix-map tbody tr').length")
    fm=await pg.query_selector('#clue-e'); await pg.evaluate("document.getElementById('clue-e').scrollIntoView()"); await fm.screenshot(path=SH+'/e-1440.png')
    # watch-out and do callouts
    r['wo_label_color']=await pg.evaluate("getComputedStyle(document.querySelector('.wo:not(.do) b')).color")
    r['do_bg']=await pg.evaluate("getComputedStyle(document.querySelector('.wo.do')).backgroundColor")
    await ctx.close()
    # no-JS
    c2=await b.new_context(viewport={'width':1440,'height':900},java_script_enabled=False); p2=await c2.new_page()
    await p2.goto(U,wait_until='load')
    r['nojs_form_visible']=await p2.evaluate("getComputedStyle(document.querySelector('.oc-form')).display")
    r['nojs_acts']=await p2.evaluate("getComputedStyle(document.querySelector('.oc-acts')).display")
    r['nojs_sentence']=await p2.evaluate("getComputedStyle(document.querySelector('.oc-sentence')).display")
    await p2.fill('#oc-asked','x'); await p2.press('#oc-asked','Enter'); await p2.wait_for_timeout(200)
    r['nojs_enter_url']=p2.url
    await c2.close()
    # phone
    c3=await b.new_context(viewport={'width':375,'height':812},reduced_motion='reduce',is_mobile=True,has_touch=True); p3=await c3.new_page()
    p3.on('pageerror',lambda e: errs.append(str(e)))
    await p3.goto(U+'#open-case',wait_until='networkidle'); await p3.wait_for_timeout(400)
    r['m_form_open_via_hash']=not await p3.evaluate("document.querySelector('.oc-form').hidden")
    r['m_old_hash_now']=await p3.evaluate('location.hash'); r['m_old_hash_heading_top']=await p3.evaluate("Math.round(document.getElementById('intake').getBoundingClientRect().top)")
    r['m_hscroll']=await p3.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth")
    await p3.tap('input[name="oc-gap"][value="Skill"] + span'); r['m_tap_chip']=await p3.is_checked('input[name="oc-gap"][value="Skill"]')
    e3=await p3.query_selector('#openCase'); await e3.screenshot(path=SH+'/oc-375.png')
    await p3.evaluate("document.getElementById('fix-map').scrollIntoView()"); await p3.wait_for_timeout(100)
    e4=await p3.query_selector('#fix-map'); await e4.screenshot(path=SH+'/fixmap-375.png')
    await p3.goto(U,wait_until='networkidle'); await p3.wait_for_timeout(200)
    await p3.screenshot(path=SH+'/hero-375.png')
    await c3.close()
    await b.close()
  r['errors']=errs
  print(json.dumps(r,indent=1,ensure_ascii=False))
asyncio.run(main())
