"""Browser-scraper companion (runs on GitHub Actions, every ~30 min).

Reads the active searches from the Cloudflare Worker, scrapes ricardo.ch with a
real browser, and sends NEW matching listings to the same Telegram bot.
Dedup state lives in seen_browser.json (committed back by the workflow).
"""
import truststore; truststore.inject_into_ssl()
import os, sys, json, re, time
import requests
from playwright.sync_api import sync_playwright
from sites import scrape_ricardo, scrape_kleinanzeigen, scrape_mobile, scrape_facebook, UA
from tuning import is_tuned, is_tuning_candidate
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

WORKER_URL = os.environ.get("WORKER_URL", "https://bmw-deal-scanner.giankp007.workers.dev")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")
BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_browser.json")
HEALTH_FILE = os.path.join(os.path.dirname(__file__), "health_browser.json")
FB_COOKIE = os.environ.get("FB_COOKIE", "").strip()   # best-effort Facebook-Login
ACTIVE_SOURCES = ["ricardo"]      # tutti deferred (overlaps AutoScout24 + fragile)
EUR_TO_CHF = 0.95                 # rough — update every few months
BLOCK_NOTIFY_HOURS = 6            # erst nach X h Dauerblock EINE Telegram-Notiz


def log(m): print(m, flush=True)


def get_config(attempts=3):
    """Aktive Suchen vom Worker holen — mit Retry + Backoff. Wirft erst nach
    `attempts` Fehlversuchen weiter; der __main__-Wrapper fängt das ab und
    beendet den Job grün (kein Fehlermail-Spam)."""
    last = None
    for i in range(attempts):
        try:
            r = requests.get(f"{WORKER_URL}/searches", params={"key": WORKER_SECRET}, timeout=30)
            r.raise_for_status()
            d = r.json()
            return d.get("searches", []), [w.lower() for w in d.get("blockwords", [])]
        except Exception as e:
            last = e
            log(f"  get_config Versuch {i + 1}/{attempts} fehlgeschlagen: {e!r}")
            time.sleep(3 * (i + 1))
    raise last


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_seen(seen):
    cutoff = time.time() - 60 * 86400
    seen = {k: v for k, v in seen.items() if v > cutoff}
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f)


# ---------------------------------------------------------------- status / health
def tg_notify(text):
    """Reine Status-Notiz an den Owner-Chat (kein Inserat). Schluckt alle Fehler."""
    if not BOT or not CHAT:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                      json={"chat_id": CHAT, "text": text, "parse_mode": "Markdown",
                            "disable_web_page_preview": True}, timeout=20)
    except Exception:
        pass


def load_health():
    try:
        with open(HEALTH_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_health(health):
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(health, f, indent=0)
    except Exception as e:
        log(f"  health speichern fehlgeschlagen: {e!r}")


SOURCE_LABELS = {"ricardo": "ricardo.ch", "kleinanzeigen": "kleinanzeigen.de",
                 "mobile": "mobile.de", "facebook": "Facebook Marketplace"}


def mark_ok(health, now, src):
    """Quelle war erreichbar. War sie vorher als blockiert gemeldet → Entwarnung."""
    h = health.setdefault(src, {"ok": now, "notified": 0})
    if h.get("notified"):
        down_h = (now - h.get("ok", now)) / 3600.0
        tg_notify(f"✅ *{SOURCE_LABELS.get(src, src)}* wieder erreichbar "
                  f"(war ~{down_h:.0f} h blockiert).")
        h["notified"] = 0
    h["ok"] = now


def mark_blocked(health, now, src):
    """Quelle blockiert. EINE Notiz nach BLOCK_NOTIFY_HOURS Dauerblock, danach
    frühestens wieder nach einem weiteren BLOCK_NOTIFY_HOURS-Fenster."""
    h = health.setdefault(src, {"ok": now, "notified": 0})
    down_h = (now - h.get("ok", now)) / 3600.0
    last_note_h = (now - h["notified"]) / 3600.0 if h.get("notified") else 1e9
    if down_h >= BLOCK_NOTIFY_HOURS and last_note_h >= BLOCK_NOTIFY_HOURS:
        tg_notify(f"⚠️ *{SOURCE_LABELS.get(src, src)}* seit ~{down_h:.0f} h "
                  f"durchgehend blockiert — wird weiter automatisch versucht.")
        h["notified"] = now


def _fb_cookies(raw):
    """'c_user=123; xs=abc; …' → Playwright-Cookie-Liste für .facebook.com."""
    out = []
    for part in raw.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip():
            out.append({"name": k.strip(), "value": v.strip(),
                        "domain": ".facebook.com", "path": "/"})
    return out


def fmt_price(p):
    return f"CHF {p:,}".replace(",", "'") if p else "Preis k.A."


def fmt_eur_chf(p):
    if p is None: return "Preis k.A."
    eur = f"€ {p:,}".replace(",", "'")
    chf = int(round((p * EUR_TO_CHF) / 100) * 100)
    return f"{eur}  (≈ CHF {chf:,})".replace(",", "'")


def matches(listing, search, blockwords):
    if listing["price"] is None:
        return False
    if search.get("maxPrice") and listing["price"] > search["maxPrice"] * 1.02:
        return False
    model = (search.get("modelName") or "").lower()
    if model and model not in listing["title"].lower():
        return False
    text = listing["title"].lower()
    if any(w in text for w in blockwords):
        return False
    return True


def send_card(listing, label):
    src = listing["source"]
    cap = [f"🆕 *Neuer Treffer* · {src}",
           f"*{listing['title']}*",
           f"💰 {fmt_price(listing['price'])}"]
    if listing.get("date"): cap.append(f"🕐 {listing['date']}")
    if listing.get("location"): cap.append(f"📍 {listing['location']}")
    cap.append(f"🔎 _{label}_")
    cap.append(f"[➜ Inserat ansehen]({listing['url']})")
    text = "\n".join(cap)
    api = f"https://api.telegram.org/bot{BOT}/"
    if listing.get("image"):
        r = requests.post(api + "sendPhoto",
                          json={"chat_id": CHAT, "photo": listing["image"], "caption": text,
                                "parse_mode": "Markdown"}, timeout=30)
        if r.json().get("ok"): return
    requests.post(api + "sendMessage",
                  json={"chat_id": CHAT, "text": text, "parse_mode": "Markdown",
                        "disable_web_page_preview": True}, timeout=30)


def send_de_card(listing, label):
    """DE-Variante mit 🇩🇪 prominent + EUR/CHF + 🔧 Tuning-Label."""
    src = "kleinanzeigen.de" if listing["source"] == "kleinanzeigen" else "mobile.de"
    cap = [f"🇩🇪 *{src}* · 🔧 Tuning-Fund",
           f"*{listing['title']}*",
           f"💰 {fmt_eur_chf(listing.get('price'))}"]
    spec = []
    if listing.get("year"): spec.append(f"📅 {listing['year']}")
    if listing.get("mileage") is not None:
        spec.append(f"🛣 {int(listing['mileage']):,}".replace(",", "'") + " km")
    if listing.get("horsepower"): spec.append(f"⚙ {listing['horsepower']} PS")
    if spec: cap.append("  ".join(spec))
    if listing.get("date"): cap.append(f"🕐 {listing['date']}")
    if listing.get("location"): cap.append(f"📍 {listing['location']}")
    cap.append(f"🔎 _{label}_")
    cap.append(f"[➜ Inserat ansehen]({listing['url']})")
    text = "\n".join(cap)
    api = f"https://api.telegram.org/bot{BOT}/"
    if listing.get("image"):
        r = requests.post(api + "sendPhoto",
                          json={"chat_id": CHAT, "photo": listing["image"], "caption": text,
                                "parse_mode": "Markdown"}, timeout=30)
        if r.json().get("ok"): return
    requests.post(api + "sendMessage",
                  json={"chat_id": CHAT, "text": text, "parse_mode": "Markdown",
                        "disable_web_page_preview": True}, timeout=30)


def matches_de(listing, search, blockwords):
    """DE-Filterung: "Tuning-Verdacht reicht" + Preis/Jahr/PS-Cap + Blockwords.

    Reihenfolge so gewählt, dass die billigsten Checks (Blockword/Tuning) zuerst
    laufen. minHp ist NUR hart, wenn der Scraper im Inserat überhaupt eine
    PS-Zahl gefunden hat — sonst durchwinken (sonst hätten 90 % der Cards
    bei kleinanzeigen keine Chance).
    """
    title = listing.get("title", "")
    teaser = listing.get("teaser", "") or ""
    blob = (title + " " + teaser).lower()

    if any(w in blob for w in blockwords):
        return False

    min_hp = search.get("minHp") or 0
    # PS-Schwelle für "Tuning-Verdacht reicht": user-minHp bzw. 320 (BMW Reihen-6er Serie).
    if not is_tuning_candidate(title, teaser, min_hp or 320):
        return False

    if search.get("maxPrice") and listing.get("price") is not None:
        if listing["price"] > search["maxPrice"] * 1.02:
            return False
    if search.get("minYear") and listing.get("year"):
        if listing["year"] < search["minYear"]:
            return False
    # Hartes minHp nur, wenn der Inserat-Text wirklich eine PS-Zahl preisgibt
    # UND die niedriger als der Wunsch ist. Sonst (None) durchlassen.
    if min_hp and listing.get("horsepower") and listing["horsepower"] < min_hp:
        return False
    return True


def post_klein_cache(search_id, listings):
    """Worker-Cache für /zeig auf kleinanzeigen-Suchen aktualisieren."""
    if not WORKER_SECRET: return
    payload = {"searchId": search_id, "listings": listings}
    try:
        requests.post(f"{WORKER_URL}/kleincache", params={"key": WORKER_SECRET},
                      json=payload, timeout=30)
    except Exception as e:
        log(f"  kleincache-Fehler: {e!r}")


def post_mobile_cache(groups):
    """Worker-Cache für /mobile aktualisieren (kuratierter Pool, keine Alerts)."""
    if not WORKER_SECRET: return
    try:
        requests.post(f"{WORKER_URL}/mobilecache", params={"key": WORKER_SECRET},
                      json={"groups": groups}, timeout=30)
    except Exception as e:
        log(f"  mobilecache-Fehler: {e!r}")


def main():
    searches, blockwords = get_config()
    ch_searches = [s for s in searches if s.get("source") in (None, "autoscout24")]
    de_searches = [s for s in searches if s.get("source") == "kleinanzeigen"]
    log(f"{len(searches)} Suchen ({len(ch_searches)} 🇨🇭, {len(de_searches)} 🇩🇪), "
        f"{len(blockwords)} Sperrwörter")
    seen = load_seen()
    health = load_health()
    now = time.time()
    new_count = alert_count = blocked = 0
    de_new = de_alerts = 0
    fb_new = fb_alerts = 0
    attempted, reachable = set(), set()
    ricardo_groups = []
    mobile_groups = []

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(
            user_agent=UA, locale="de-CH", timezone_id="Europe/Zurich",
            viewport={"width": 1366, "height": 900}, ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "de-CH,de;q=0.9,en;q=0.8"})
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'languages',{get:()=>['de-CH','de','en']});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});")

        # Best-effort Facebook-Login: Cookie-String "k=v; k=v" → Context-Cookies.
        if FB_COOKIE:
            try:
                ctx.add_cookies(_fb_cookies(FB_COOKIE))
                log("  Facebook-Cookie geladen.")
            except Exception as e:
                log(f"  Facebook-Cookie ungültig: {e!r}")

        # ---------------- 🇨🇭 ricardo (CH) — pro AS24-Suche ----------------
        for search in ch_searches:
            label = search.get("label") or search.get("makeName", "Suche")
            for src in ACTIVE_SOURCES:
                attempted.add(src)
                try:
                    pg = ctx.new_page()
                    listings = scrape_ricardo(pg, search, 40) if src == "ricardo" else None
                    pg.close()
                except Exception as e:
                    log(f"  ✗ {src} '{label}': {e!r}"); continue
                if listings is None:
                    log(f"  ⤬ {src} · {label}: blockiert/nicht erreichbar — übersprungen")
                    blocked += 1; continue
                reachable.add(src)
                hits = [l for l in listings if matches(l, search, blockwords)]
                if src == "ricardo" and hits:
                    ricardo_groups.append({"label": label, "listings": [
                        {k: l.get(k) for k in ("title", "price", "url", "image", "date", "location")}
                        for l in hits[:8]]})
                skey = f"__seeded__:{src}:{search.get('id', label)}"
                seeded = skey in seen
                log(f"  {src} · {label}: {len(listings)} gescrapt, {len(hits)} passend"
                    + ("" if seeded else " (Erstaufnahme – kein Alarm)"))
                for l in hits:
                    uid = f"{l['source']}:{l['id']}"
                    if uid in seen:
                        seen[uid] = now; continue
                    seen[uid] = now; new_count += 1
                    if not seeded: continue
                    send_card(l, label); alert_count += 1
                    time.sleep(0.2)
                if not seeded:
                    seen[skey] = now

        # ---------------- 🇩🇪 kleinanzeigen.de (DE) — pro DE-Suche ----------------
        for search in de_searches:
            label = search.get("label") or search.get("makeName", "DE-Suche")
            sid = search.get("id") or label
            attempted.add("kleinanzeigen")
            try:
                pg = ctx.new_page()
                raw = scrape_kleinanzeigen(pg, search, 40)
                pg.close()
            except Exception as e:
                log(f"  ✗ kleinanzeigen '{label}': {e!r}"); continue
            if raw is None:
                log(f"  ⤬ kleinanzeigen · {label}: blockiert — übersprungen")
                blocked += 1; continue
            reachable.add("kleinanzeigen")
            hits = [l for l in raw if matches_de(l, search, blockwords)]
            log(f"  🇩🇪 kleinanzeigen · {label}: {len(raw)} gescrapt, "
                f"{len(hits)} Tuning-passend")
            # Worker-Cache füllen — slim shape für /zeig (uid für ⭐-Button)
            slim = []
            for l in hits[:30]:
                slim.append({
                    "source": "kleinanzeigen",
                    "uid": f"kleinanzeigen:{l['id']}",
                    "url": l.get("url"), "title": l.get("title"),
                    "price": l.get("price"), "image": l.get("image"),
                    "teaser": l.get("teaser") or "",
                    "year": l.get("year"), "mileage": l.get("mileage"),
                    "horsepower": l.get("horsepower"),
                    "location": l.get("location") or "",
                    "date": l.get("date") or "",
                })
            post_klein_cache(sid, slim)
            # Alerts (mit Per-Suche-Seeden)
            skey = f"__seeded__:kleinanzeigen:{sid}"
            seeded = skey in seen
            if not seeded: log(f"     (Erstaufnahme – kein Alarm)")
            for l in hits:
                uid = f"kleinanzeigen:{l['id']}"
                if uid in seen:
                    seen[uid] = now; continue
                seen[uid] = now; de_new += 1
                if not seeded: continue
                send_de_card(l, label); de_alerts += 1
                time.sleep(0.25)
            if not seeded:
                seen[skey] = now

        # ---------------- 🇩🇪 mobile.de (DE, kuratierter Pool) ----------------
        # Pro DE-Suche scrapen → tuning-gefilterte Gruppe → /mobilecache. KEINE Alerts.
        for search in de_searches:
            label = search.get("label") or search.get("makeName", "DE-Suche")
            attempted.add("mobile")
            try:
                pg = ctx.new_page()
                raw = scrape_mobile(pg, search, 25)
                pg.close()
            except Exception as e:
                log(f"  ✗ mobile.de '{label}': {e!r}"); continue
            if raw is None:
                log(f"  ⤬ mobile.de · {label}: blockiert — übersprungen")
                blocked += 1; continue
            reachable.add("mobile")
            hits = [l for l in raw if matches_de(l, search, blockwords)]
            log(f"  🇩🇪 mobile.de · {label}: {len(raw)} gescrapt, "
                f"{len(hits)} Tuning-passend (nur Cache)")
            if hits:
                mobile_groups.append({"label": label, "listings": [
                    {k: l.get(k) for k in (
                        "title", "price", "url", "image", "year", "mileage",
                        "horsepower", "location")} for l in hits[:8]]})

        # ---------------- 📘 Facebook Marketplace (best-effort, CH-Suchen) ----------------
        if FB_COOKIE:
            for search in ch_searches:
                label = search.get("label") or search.get("makeName", "Suche")
                attempted.add("facebook")
                try:
                    pg = ctx.new_page()
                    listings = scrape_facebook(pg, search, 30)
                    pg.close()
                except Exception as e:
                    log(f"  ✗ facebook '{label}': {e!r}"); continue
                if listings is None:
                    log(f"  ⤬ facebook · {label}: Login-Wall/blockiert — übersprungen")
                    blocked += 1; continue
                reachable.add("facebook")
                hits = [l for l in listings if matches(l, search, blockwords)]
                skey = f"__seeded__:facebook:{search.get('id', label)}"
                seeded = skey in seen
                log(f"  📘 facebook · {label}: {len(listings)} gescrapt, {len(hits)} passend"
                    + ("" if seeded else " (Erstaufnahme – kein Alarm)"))
                for l in hits:
                    uid = f"facebook:{l['id']}"
                    if uid in seen:
                        seen[uid] = now; continue
                    seen[uid] = now; fb_new += 1
                    if not seeded: continue
                    send_card(l, label); fb_alerts += 1
                    time.sleep(0.25)
                if not seeded:
                    seen[skey] = now
        else:
            log("  📘 facebook: kein FB_COOKIE gesetzt — übersprungen.")

        b.close()

    # Health/Block-Status pro Quelle aktualisieren (EINE Notiz nach Dauerblock).
    for src in attempted:
        if src in reachable:
            mark_ok(health, now, src)
        else:
            mark_blocked(health, now, src)
    save_seen(seen)
    save_health(health)
    # ricardo-Cache
    if ricardo_groups and WORKER_SECRET:
        try:
            requests.post(f"{WORKER_URL}/ricache", params={"key": WORKER_SECRET},
                          json={"groups": ricardo_groups}, timeout=30)
            log(f"ricardo-Cache aktualisiert "
                f"({sum(len(g['listings']) for g in ricardo_groups)} Inserate).")
        except Exception as e:
            log(f"ricache-Fehler: {e!r}")
    # mobile.de-Cache
    if mobile_groups:
        post_mobile_cache(mobile_groups)
        log(f"mobile.de-Cache aktualisiert "
            f"({sum(len(g['listings']) for g in mobile_groups)} Inserate, "
            f"{len(mobile_groups)} Gruppen).")
    log(f"Fertig: 🇨🇭 {new_count} neu / {alert_count} Alarme, "
        f"🇩🇪 {de_new} neu / {de_alerts} Alarme, "
        f"📘 {fb_new} neu / {fb_alerts} Alarme, {blocked} Quellen-Läufe blockiert.")


if __name__ == "__main__":
    # Oberste Schutzschicht: ein unerwarteter Fehler darf den Job NICHT rot
    # färben (sonst Fehlermail-Spam). Wir loggen, versuchen eine Telegram-Notiz
    # und beenden mit Exit 0 — der nächste 30-Min-Lauf probiert es erneut.
    try:
        main()
    except Exception as e:
        import traceback
        log("‼️ Unerwarteter Fehler — Lauf abgebrochen, aber Job bleibt grün:")
        log(traceback.format_exc())
        tg_notify(f"‼️ Browser-Scan-Lauf abgebrochen: `{e!r}`\nNächster Versuch in ~30 Min.")
        sys.exit(0)
