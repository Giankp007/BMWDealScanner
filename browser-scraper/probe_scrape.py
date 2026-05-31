"""Verify we can extract car listings from tutti + ricardo with a real browser."""
import truststore; truststore.inject_into_ssl()
from playwright.sync_api import sync_playwright
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def accept_cookies(pg):
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Akzeptieren')",
                "button:has-text('Alle akzeptieren')", "button:has-text('Zustimmen')",
                "button:has-text('Accept')"]:
        try:
            if pg.locator(sel).count():
                pg.locator(sel).first.click(timeout=3000); return True
        except Exception: pass
    return False

def scrape(name, fn):
    print("\n" + "=" * 60 + f"\n{name}\n" + "=" * 60)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, locale="de-CH", ignore_https_errors=True)
        pg = ctx.new_page()
        try:
            fn(pg)
        except Exception as e:
            print("ERR", repr(e)[:200])
        b.close()

def tutti(pg):
    pg.goto("https://www.tutti.ch/de/q/bmw%20335i", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2500); accept_cookies(pg); pg.wait_for_timeout(3000)
    pg.mouse.wheel(0, 3000); pg.wait_for_timeout(2000)
    print("url:", pg.url, "| title:", pg.title()[:60])
    # listing anchors
    for sel in ["a[href*='/vi/']", "a[href*='/li/']", "article a", "[data-testid*='listing'] a"]:
        try:
            n = pg.locator(sel).count()
            if n: print(f"  sel {sel!r}: {n}")
        except Exception: pass
    cards = pg.eval_on_selector_all("a[href*='/vi/']",
        "els=>els.slice(0,5).map(e=>({href:e.getAttribute('href'),txt:e.innerText.slice(0,80).replace(/\\n/g,' | ')}))")
    for c in cards: print("  ", c)

def ricardo(pg):
    pg.goto("https://www.ricardo.ch/de/s/bmw%20335i/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2500); accept_cookies(pg); pg.wait_for_timeout(3000)
    pg.mouse.wheel(0, 3000); pg.wait_for_timeout(2000)
    print("url:", pg.url, "| title:", pg.title()[:60])
    for sel in ["a[href*='/a/']", "article", "[class*='article']", "[class*='Article']", "a[href*='/de/a/']"]:
        try:
            n = pg.locator(sel).count()
            if n: print(f"  sel {sel!r}: {n}")
        except Exception: pass
    cards = pg.eval_on_selector_all("a[href*='/a/']",
        "els=>els.slice(0,5).map(e=>({href:e.getAttribute('href'),txt:e.innerText.slice(0,90).replace(/\\n/g,' | ')}))")
    for c in cards: print("  ", c)

scrape("TUTTI", tutti)
scrape("RICARDO", ricardo)
