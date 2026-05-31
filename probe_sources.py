"""Find JSON search APIs for ricardo / tutti / comparis (Worker-compatible = plain HTTP)."""
import truststore; truststore.inject_into_ssl()
from playwright.sync_api import sync_playwright
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

TARGETS = {
    "ricardo": "https://www.ricardo.ch/de/s/bmw/",
    "tutti": "https://www.tutti.ch/de/li/ganze-schweiz/autos-fahrzeuge-boote/autos?query=bmw",
    "comparis": "https://en.comparis.ch/carfinder/marktplatz/occasion",
}

def run(name, url):
    print("\n" + "=" * 70 + f"\n{name}: {url}\n" + "=" * 70)
    api_hits = []
    def on_resp(resp):
        ct = resp.headers.get("content-type", "")
        rt = resp.request.resource_type
        if "json" in ct and rt in ("xhr", "fetch"):
            u = resp.url
            try: body = resp.text()
            except Exception: body = ""
            # heuristic: looks like it carries listings
            score = sum(k in body.lower() for k in ["price", "preis", "title", "titel", "mileage", "listing", "article", "offer"])
            api_hits.append((score, resp.request.method, u, len(body), body[:150]))
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, locale="de-CH", ignore_https_errors=True)
        pg = ctx.new_page(); pg.on("response", on_resp)
        try:
            r = pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            print("page status:", r.status if r else "?")
            pg.wait_for_timeout(2500)
            for sel in ["#onetrust-accept-btn-handler", "button:has-text('Akzeptieren')",
                        "button:has-text('Alle akzeptieren')", "button:has-text('Accept')", "button:has-text('Zustimmen')"]:
                try:
                    if pg.locator(sel).count(): pg.locator(sel).first.click(timeout=2500); break
                except Exception: pass
            pg.wait_for_timeout(2500)
            pg.mouse.wheel(0, 4000); pg.wait_for_timeout(2500)
        except Exception as e:
            print("nav err:", repr(e)[:150])
        b.close()
    api_hits.sort(reverse=True)
    print(f"top JSON API calls (by listing-likeness):")
    for score, m, u, ln, prev in api_hits[:6]:
        print(f"  [score {score}] {m} len={ln} {u[:110]}")
        if score >= 3: print(f"      {prev}")

for n, u in TARGETS.items():
    try: run(n, u)
    except Exception as e: print(n, "FATAL", repr(e)[:150])
