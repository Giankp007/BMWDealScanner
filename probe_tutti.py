import truststore; truststore.inject_into_ssl()
from playwright.sync_api import sync_playwright
import sys, json, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
URL = "https://www.tutti.ch/de/q/bmw-335i/Su4uAQ"
captured = []

def on_req(req):
    u = req.url
    if ("graphql" in u or "api.tutti" in u or "/api/" in u) and req.resource_type in ("xhr", "fetch"):
        pd = None
        try: pd = req.post_data
        except Exception: pass
        captured.append((req.method, u, dict(req.headers), pd))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, locale="de-CH", ignore_https_errors=True)
    pg = ctx.new_page(); pg.on("request", on_req)
    r = pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
    print("page status:", r.status if r else "?")
    pg.wait_for_timeout(2500)
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Akzeptieren')", "button:has-text('Zustimmen')"]:
        try:
            if pg.locator(sel).count(): pg.locator(sel).first.click(timeout=2500); break
        except Exception: pass
    pg.wait_for_timeout(3000); pg.mouse.wheel(0, 3000); pg.wait_for_timeout(2000)
    b.close()

print(f"\ncaptured {len(captured)} api/graphql calls")
seen=set()
target=None
for m,u,h,pd in captured:
    base=u.split('?')[0]
    if base in seen: continue
    seen.add(base)
    print(f"\n[{m}] {u[:130]}")
    if pd: print("  POST body:", pd[:250])
    if "graphql" in u and m=="POST" and not target:
        target=(m,u,h,pd)

# Try to replay the graphql call via PLAIN requests (= Worker-compatible test)
if target:
    m,u,h,pd = target
    print("\n=== REPLAY via plain requests ===")
    hdrs={k:v for k,v in h.items() if k.lower() in ("content-type","accept","accept-language","user-agent","origin","referer","x-tutti-hash","x-tutti-source","apollographql-client-name","apollographql-client-version")}
    hdrs.setdefault("User-Agent",UA)
    try:
        rr=requests.post(u,data=pd,headers=hdrs,timeout=20)
        print("status",rr.status_code,"len",len(rr.text))
        print("body[:300]:",rr.text[:300])
    except Exception as e:
        print("replay err",repr(e)[:150])
    print("\nheaders that were sent by browser:")
    for k,v in h.items():
        if k.lower().startswith(("x-","apollo","content-type","origin","referer")):
            print(f"   {k}: {v[:80]}")
