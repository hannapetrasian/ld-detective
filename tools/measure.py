import sys, json, asyncio, re, http.server, threading, socketserver, os
from playwright.async_api import async_playwright

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8731
SHOTS = sys.argv[3] if len(sys.argv) > 3 else None

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def serve():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Q) as httpd:
        httpd.serve_forever()
threading.Thread(target=serve, daemon=True).start()

WIDTHS = [1440,1300,1200,1160,1120,1080,1024,960,900,834,768,700,640,540,430,375]

async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':1440,'height':900})
        page = await ctx.new_page()
        errors = []; ext = []
        page.on('console', lambda m: errors.append(m.text) if m.type in ('error','warning') else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: ext.append(r.url) if not r.url.startswith(f'http://localhost:{PORT}') else None)
        await page.goto(f'http://localhost:{PORT}/index.html', wait_until='networkidle')
        await page.wait_for_timeout(500)
        out['height_1440'] = await page.evaluate('document.documentElement.scrollHeight')
        out['screens_1440'] = round(out['height_1440']/900,1)
        out['words'] = await page.evaluate("""() => {
          const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const e=n.parentElement;if(!e)return 2;const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return 2;if(['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName))return 2;return 1}});
          let t='';while(w.nextNode())t+=' '+w.currentNode.data;return t.trim().split(/\\s+/).filter(Boolean).length}""")
        out['console'] = errors
        out['external_requests'] = ext
        out['fonts'] = await page.evaluate("""async()=>{await document.fonts.ready;const l=[];document.fonts.forEach(f=>l.push(f.family+' '+f.weight+' '+f.style+' '+f.status));return l}""")
        out['broken_anchors'] = await page.evaluate("""()=>{const ids=new Set([...document.querySelectorAll('[id]')].map(e=>e.id));return [...document.querySelectorAll('a[href^="#"]')].map(a=>a.getAttribute('href')).filter(h=>h.length>1&&!ids.has(h.slice(1)))}""")
        out['ids'] = await page.evaluate("document.querySelectorAll('[id]').length")
        out['hash_links'] = await page.evaluate("document.querySelectorAll('a[href^=\"#\"]').length")
        out['data_l'] = await page.evaluate("document.querySelectorAll('[data-l]').length")
        out['tables'] = await page.evaluate("document.querySelectorAll('table').length")
        out['headings'] = await page.evaluate("""()=>{const hs=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')];let skips=0,prev=0;for(const h of hs){const n=+h.tagName[1];if(prev&&n>prev+1)skips++;prev=n}return {count:hs.length,skips}}""")
        out['dup_ids'] = await page.evaluate("""()=>{const m={};document.querySelectorAll('[id]').forEach(e=>m[e.id]=(m[e.id]||0)+1);return Object.keys(m).filter(k=>m[k]>1)}""")
        # contrast check of visible text nodes (approx, solid backgrounds)
        out['contrast_fails'] = await page.evaluate("""()=>{
          function parse(c){const m=c.match(/[\\d.]+/g).map(Number);return m}
          function lum(r,g,b){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)}
          function bg(el){while(el){const c=getComputedStyle(el).backgroundColor;const m=parse(c);if(m.length<4||m[3]>0.9)return m;el=el.parentElement}return [255,255,255,1]}
          const fails=[];const seen=new Set();
          const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
          while(w.nextNode()){const n=w.currentNode;if(!n.data.trim())continue;const e=n.parentElement;const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden'||+s.opacity===0)continue;const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;
            const fg=parse(s.color);const b=bg(e);const l1=lum(...fg),l2=lum(...b);const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);const big=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&+s.fontWeight>=700);const need=big?3:4.5;
            if(ratio<need){const k=e.tagName+'.'+e.className+'|'+ratio.toFixed(2);if(!seen.has(k)){seen.add(k);fails.push({el:k,text:n.data.trim().slice(0,40)})}}}
          return fails}""")
        # widths: h-scroll and overflow cells
        hs = {}
        for wdt in WIDTHS:
            await page.set_viewport_size({'width':wdt,'height':900})
            await page.wait_for_timeout(150)
            r = await page.evaluate("""()=>{const de=document.documentElement;const hsc=de.scrollWidth>de.clientWidth+1;let over=0;document.querySelectorAll('td,th,li,p,h1,h2,h3,h4').forEach(c=>{if(c.scrollWidth>c.clientWidth+2)over++});return {h:de.scrollHeight,hscroll:hsc,overflow:over}}""")
            hs[wdt] = r
        out['widths'] = hs
        await page.set_viewport_size({'width':1440,'height':900})
        # downloads
        for path in ['files/pocket-guide.pdf','files/case-file-template.docx','og-image.png','404.html']:
            resp = await page.request.get(f'http://localhost:{PORT}/{path}')
            out['file_'+path] = resp.status
        # print pages
        await page.emulate_media(media='print')
        await page.pdf(path='/tmp/ld-print.pdf', format='A4', print_background=True)
        await page.emulate_media(media='screen')
        # screenshots
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            for wdt in [1440, 1024, 375]:
                await page.set_viewport_size({'width':wdt,'height':900})
                await page.wait_for_timeout(200)
                await page.screenshot(path=f'{SHOTS}/full-{wdt}.png', full_page=True)
        await b.close()
    try:
        from pypdf import PdfReader
        out['print_pages'] = len(PdfReader('/tmp/ld-print.pdf').pages)
    except Exception as e:
        out['print_pages'] = str(e)
    print(json.dumps(out, indent=1, ensure_ascii=False))

asyncio.run(main())
