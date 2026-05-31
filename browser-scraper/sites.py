"""Browser scrapers for tutti.ch, ricardo.ch, kleinanzeigen.de, mobile.de."""
import re
from urllib.parse import quote, quote_plus

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_BADGES = {"beliebt", "boost", "neu", "gesponsert", "sponsored", "popular", "top",
           "sofort kaufen", "oder preis vorschlagen", "bmw", "audi", "mercedes-benz"}


def accept_cookies(pg):
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Akzeptieren')",
                "button:has-text('Alle akzeptieren')", "button:has-text('Zustimmen')",
                "button:has-text('Accept')"]:
        try:
            if pg.locator(sel).count():
                pg.locator(sel).first.click(timeout=3000)
                return
        except Exception:
            pass


def _money(s):
    """Integer part of a Swiss amount: "7'500.00" -> 7500, "CHF 15'900.–" -> 15900."""
    m = re.search(r"(\d[\d'’]{0,9})(?:[.,]\d{1,2})?", s or "")
    return int(re.sub(r"[^\d]", "", m.group(1))) if m else None


def _is_money_line(s):
    return bool(re.search(r"\d[\d'’]{2,}", s or ""))


def _pick_title(lines):
    for l in lines:
        s = l.strip()
        if (len(s) >= 6 and re.search(r"[A-Za-zÄÖÜäöü]", s)
                and s.lower() not in _BADGES
                and "gebot" not in s.lower() and "kaufen" not in s.lower()
                and not re.fullmatch(r"[\d'’.,\s–\-CHFchf]+", s)):
            return s[:80]
    return (lines[0].strip()[:80] if lines else "Inserat")


def _extract_rows(pg, sel):
    return pg.eval_on_selector_all(sel, """els => {
        const seen = new Set(); const out = [];
        for (const e of els) {
            const href = e.getAttribute('href'); if (!href || seen.has(href)) continue;
            seen.add(href);
            const img = e.querySelector('img');
            out.push({ href,
                lines: (e.innerText || '').split('\\n').map(s=>s.trim()).filter(Boolean),
                img: img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '' });
        }
        return out;
    }""")


def keyword(search):
    extra = search.get("modelName") or search.get("groupName") or ""
    return (search.get("makeName", "") + " " + extra).strip()


# ---------------------------------------------------------------- ricardo
def scrape_ricardo(pg, search, limit=40):
    pg.goto("https://www.ricardo.ch/de/s/" + quote(keyword(search)) + "/?sort=newest",
            wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2500); accept_cookies(pg); pg.wait_for_timeout(2500)
    for _ in range(4):
        pg.mouse.wheel(0, 4000); pg.wait_for_timeout(1200)
    try:
        pg.wait_for_selector("a[href*='/de/a/']", timeout=8000)
    except Exception:
        pass
    n_links = pg.locator("a[href*='/de/a/']").count()
    title = pg.title()
    print(f"     [ricardo] title={title[:50]!r} links={n_links}", flush=True)
    # Cloudflare challenge / block → signal "unavailable" (None), so we don't
    # mistake it for "0 results" and later spam when it recovers.
    blocked_markers = ("moment", "forbidden", "attention", "captcha", "blocked", "zugriff")
    if n_links == 0 or any(m in title.lower() for m in blocked_markers):
        return None
    out = []
    for r in _extract_rows(pg, "a[href*='/de/a/']")[:limit]:
        lines = r["lines"]
        # buy-now amount = line right before "Sofort kaufen"; else largest plausible bid
        price = None
        for i, l in enumerate(lines):
            if "sofort kaufen" in l.lower() and i > 0 and _is_money_line(lines[i - 1]):
                price = _money(lines[i - 1]); break
        if price is None:
            vals = [_money(l) for l in lines if _is_money_line(l)]
            vals = [v for v in vals if v and 200 <= v <= 300000]
            price = max(vals) if vals else None
        date = ""
        for l in lines:
            if re.match(r"(Mo|Di|Mi|Do|Fr|Sa|So),", l):
                date = l; break
        mid = re.search(r"(\d+)/?$", r["href"])
        out.append({"source": "ricardo",
                    "id": mid.group(1) if mid else r["href"],
                    "url": "https://www.ricardo.ch" + r["href"],
                    "title": _pick_title(lines), "price": price, "image": r["img"],
                    "date": date, "location": "", "text": " | ".join(lines)})
    return out


# ---------------------------------------------------------------- tutti
def scrape_tutti(pg, search, limit=40):
    pg.goto("https://www.tutti.ch/de", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2000); accept_cookies(pg); pg.wait_for_timeout(1200)
    inp = None
    for sel in ["input[placeholder*=Was]", "input[type=search]", "input[name=query]"]:
        if pg.locator(sel).count(): inp = sel; break
    if not inp:
        return []
    box = pg.locator(inp).first
    box.click(); box.fill(keyword(search)); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    for _ in range(3):
        pg.mouse.wheel(0, 4000); pg.wait_for_timeout(900)
    # tutti: title/price live in the card CONTAINER, not inside the <a>. Climb up.
    rows = pg.eval_on_selector_all("a[href*='/de/vi/']", """els => {
        const seen = new Set(); const out = [];
        for (const a of els) {
            const href = a.getAttribute('href'); if (!href || seen.has(href)) continue;
            seen.add(href);
            let card = a;
            for (let i=0;i<4 && card.parentElement;i++){ card = card.parentElement;
                if ((card.innerText||'').length > 25) break; }
            const img = card.querySelector('img');
            out.push({ href,
                lines: (card.innerText||'').split('\\n').map(s=>s.trim()).filter(Boolean),
                img: img ? (img.getAttribute('src')||img.getAttribute('data-src')||'') : '' });
        }
        return out;
    }""")
    out = []
    for r in rows:
        href = r["href"]
        if "/autos/" not in href:        # only real cars, not accessories
            continue
        lines = r["lines"]
        price = next((_money(l) for l in lines if "chf" in l.lower()), None)
        if price is None:
            vals = [_money(l) for l in lines if _is_money_line(l)]
            vals = [v for v in vals if v and 200 <= v <= 300000]
            price = max(vals) if vals else None
        loc = next((l for l in lines if re.search(r"\d{4}\s+\w", l)), "")
        mid = re.search(r"/(\d+)$", href)
        out.append({"source": "tutti",
                    "id": mid.group(1) if mid else href,
                    "url": "https://www.tutti.ch" + href,
                    "title": _pick_title(lines), "price": price, "image": r["img"],
                    "date": "", "location": loc, "text": " | ".join(lines)})
        if len(out) >= limit:
            break
    return out


SCRAPERS = {"ricardo": scrape_ricardo, "tutti": scrape_tutti}


# ---------------------------------------------------------------- helpers
def _kw_for_de(search):
    """Combine make/model/keyword into a free-text query for kleinanzeigen/mobile."""
    parts = [search.get("makeName") or "",
             search.get("modelName") or "",
             search.get("keyword") or ""]
    s = " ".join(p for p in parts if p).strip()
    return s


def _slug(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9äöüß]+", "-", s).strip("-")
    return s or "auto"


def _accept_kleinanzeigen_cookies(pg):
    """Kleinanzeigen has its own consent flow (gdpr-banner-accept)."""
    for sel in [
        "#gdpr-banner-accept", "button[data-testid='gdpr-banner-accept']",
        "button:has-text('Alle akzeptieren')", "button:has-text('Akzeptieren')",
        "button:has-text('Zustimmen')",
    ]:
        try:
            if pg.locator(sel).count():
                pg.locator(sel).first.click(timeout=3000)
                return
        except Exception:
            pass


# ---------------------------------------------------------------- kleinanzeigen.de

# Tuning-Suffixe, die als zusätzliche Suchanfragen an kleinanzeigen geschickt
# werden, wenn der User KEIN eigenes Stichwort gesetzt hat. So zwingen wir den
# Volltext-Index serverseitig auf Tuning-Verdacht, statt 90 % Standard-Inserate
# durchzunehmen und clientseitig wegzuwerfen.
_KLEIN_TUNING_SUFFIXES = ["tuning", "stage", "umbau", "kompressor"]


def _klein_build_url(search, suffix=None):
    """URL zu einer kleinanzeigen-Suche mit optionalem Tuning-Suffix im Slug.

    Wichtig: das funktionierende Format ist `/s-{slug}/k0c216` (nicht
    `/s-autos/{slug}/k0c216`). Mit `/s-autos/` ignoriert kleinanzeigen Such-
    Suffixe wie `-tuning` und liefert nur eine Vorschlagsseite ohne Treffer.
    Der `k0c216`-Suffix beschränkt die Kategorie weiterhin auf "Autos".

    Kein Preisfilter in der URL: das `/s-{slug}/preis:0:MAX/k0c216`-Segment
    bringt kleinanzeigen aus der Spur (0 Treffer). Stattdessen filtert
    `matches_de` clientseitig nach `search.maxPrice`.
    """
    kw_base = _kw_for_de(search) or "BMW"
    kw = (kw_base + " " + suffix).strip() if suffix else kw_base
    slug = _slug(kw)
    return f"https://www.kleinanzeigen.de/s-{slug}/k0c216"


def _klein_load(pg, url):
    """URL laden + Cookies + Scrollen. Liefert True wenn ok, False/None bei Block."""
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return None
    pg.wait_for_timeout(2200)
    _accept_kleinanzeigen_cookies(pg)
    pg.wait_for_timeout(1500)
    for _ in range(3):
        pg.mouse.wheel(0, 4000)
        pg.wait_for_timeout(700)
    title = (pg.title() or "").lower()
    if any(m in title for m in ("captcha", "blocked", "forbidden",
                                 "attention required", "zugriff", "akamai", "robot")):
        return None
    return True


def scrape_kleinanzeigen(pg, search, limit=40):
    """Suche auf kleinanzeigen.de/s-autos. Filtert via URL nach Preis + Keyword.

    Wenn der User KEIN eigenes Stichwort gesetzt hat, schiessen wir mehrere
    Tuning-orientierte Anfragen ab (`… tuning`, `… stage`, `… umbau`, …) und
    mergen die Resultate — sonst dominieren Standard-Inserate die Trefferliste.

    Returns:
        list[dict] mit den gefundenen Inseraten (noch ungefiltert nach Tuning),
        oder None bei Block / Challenge der ERSTEN Anfrage.
    """
    user_kw = (search.get("keyword") or "").strip()
    # User-Stichwort = explizit, keine Erweiterung. Sonst: Basis + Tuning-Pool.
    suffixes = [None] if user_kw else [None] + _KLEIN_TUNING_SUFFIXES

    merged = []
    seen_ids = set()
    first_blocked = False
    per_query_cap = max(20, limit)

    for i, suf in enumerate(suffixes):
        url = _klein_build_url(search, suf)
        ok = _klein_load(pg, url)
        if ok is None:
            if i == 0:
                first_blocked = True
            continue
        rows = _klein_extract_rows(pg, per_query_cap)
        for r in rows:
            rid = str(r.get("id") or r.get("href") or "")
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            merged.append(r)
        if len(merged) >= limit * 3:
            break

    if not merged and first_blocked:
        return None

    return _klein_parse(merged, limit)


def _klein_extract_rows(pg, limit):
    """Rohe Card-Rows von der aktuell geladenen Listen-Page abgreifen."""

    rows = pg.eval_on_selector_all("article.aditem", """els => els.map(e => {
        const a = e.querySelector('a.ellipsis') || e.querySelector('a');
        const href = a ? a.getAttribute('href') : '';
        const id = e.getAttribute('data-adid') || (href ? (href.match(/\\/(\\d+)-/) || [])[1] : '') || '';
        // Titel-Quellen, in Reihenfolge der Verlässlichkeit:
        //   1) JSON-LD (immer der saubere Anzeigentitel)
        //   2) h2.text-module-begin / a.ellipsis
        //   3) <img alt="..."> (kleinanzeigen schreibt den Titel ins alt-Attribut)
        // Das primitive `e.querySelector('a')` ist NICHT zuverlässig — es trifft
        // oft den Galerie-Link, dessen innerText nur die Bilder-Anzahl ("14") ist.
        let ldJson = null;
        const ld = e.querySelector('script[type=\"application/ld+json\"]');
        if (ld) { try { ldJson = JSON.parse(ld.textContent || '{}'); } catch (_) {} }
        let title = '';
        if (ldJson && ldJson.title) title = String(ldJson.title).trim();
        if (!title) {
            const tEl = e.querySelector('h2.text-module-begin a, h2.text-module-begin, a.ellipsis');
            if (tEl) title = (tEl.innerText || tEl.textContent || '').trim();
        }
        if (!title) {
            const imgEl0 = e.querySelector('.imagebox img, img');
            const alt = imgEl0 ? (imgEl0.getAttribute('alt') || '') : '';
            // alt-Attribut endet typischerweise auf " <Region> Vorschau" — abschneiden.
            title = alt.replace(/\\s+Vorschau\\s*$/i, '').replace(/\\s+[A-ZÄÖÜ][\\wäöüß\\-]+\\s*-\\s*[A-ZÄÖÜ][\\wäöüß\\-]+\\s*$/, '').trim();
        }
        // Bild-Zähler-Artefakte ("14", "9", "20") rausfiltern.
        if (/^\\d{1,3}$/.test(title)) title = '';
        const priceEl = e.querySelector('.aditem-main--middle--price-shipping--price, .aditem-main--middle--price, p.aditem-main--middle--price-shipping--price');
        const price = priceEl ? (priceEl.innerText || '').trim() : '';
        const teaserEl = e.querySelector('.aditem-main--middle--description, p.text-module-begin');
        const teaser = teaserEl ? (teaserEl.innerText || '').trim() : '';
        const locEl = e.querySelector('.aditem-main--top--left');
        const loc = locEl ? (locEl.innerText || '').trim() : '';
        const dateEl = e.querySelector('.aditem-main--top--right');
        const date = dateEl ? (dateEl.innerText || '').trim() : '';
        const imgEl = e.querySelector('.imagebox img, img');
        const img = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || imgEl.getAttribute('data-imgsrc') || '') : '';
        // JSON-LD: längere description als der sichtbare Mini-Teaser (200-500 Zeichen)
        const descLong = (ldJson && ldJson.description) ? String(ldJson.description).trim() : '';
        // Tag-Zeile am Card-Ende: "85.770 km · EZ 01/2010"
        const tagEls = Array.from(e.querySelectorAll('.simpletag, .simpletag-list li, .aditem-main--bottom span, span.simpletag'));
        let tagBlob = tagEls.map(t => (t.innerText || '').trim()).filter(Boolean).join(' | ');
        if (!tagBlob) {
            const text = (e.innerText || '');
            const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
            tagBlob = lines.filter(l => /km|EZ\\s*\\d/.test(l)).join(' | ');
        }
        return { id, href, title, price, teaser, teaser_full: descLong, loc, date, img, tag_blob: tagBlob };
    })""")
    if not rows:
        # Fallback: Layout geändert → mit a-Liste arbeiten
        rows = pg.eval_on_selector_all("a[href*='/s-anzeige/']", """els => {
            const seen = new Set(); const out = [];
            for (const a of els) {
                const href = a.getAttribute('href'); if (!href || seen.has(href)) continue;
                seen.add(href);
                let card = a; for (let i=0;i<5 && card.parentElement;i++){ card = card.parentElement;
                    if ((card.innerText||'').length > 30) break; }
                const img = card.querySelector('img');
                out.push({ id: (href.match(/\\/(\\d+)-/)||[])[1] || href,
                    href, title: (a.innerText||'').trim().slice(0,120),
                    price: (card.innerText||'').match(/\\d[\\d\\.\\s]*\\s*€/)?.[0] || '',
                    teaser: (card.innerText||'').slice(0,300),
                    teaser_full: '',
                    loc: '', date: '', tag_blob: '',
                    img: img ? (img.getAttribute('src')||img.getAttribute('data-src')||'') : ''});
            }
            return out;
        }""")
    return rows[:limit]


def _klein_parse(rows, limit):
    """Rohe Card-Rows (aus 1+ Anfragen, schon dedupliziert) → unsere Listing-Shape."""
    year_rx = re.compile(r"EZ\s*\d{1,2}/(\d{4})", re.I)
    km_rx = re.compile(r"(\d[\d\.\s]{0,9})\s*km", re.I)
    ps_rx = re.compile(r"(\d{2,4})\s*PS\b", re.I)
    kw_rx = re.compile(r"(\d{2,4})\s*kW\b", re.I)

    out = []
    for r in rows[:limit]:
        if not r.get("href") or not r.get("title"):
            continue
        href = r["href"]
        if href.startswith("/"):
            href = "https://www.kleinanzeigen.de" + href
        # Preis aus "1.500 €" → 1500 (EUR)
        price = None
        m = re.search(r"(\d[\d\.\s]{0,9})\s*€", r.get("price") or "")
        if m:
            price = int(re.sub(r"[^\d]", "", m.group(1)))

        tag_blob = r.get("tag_blob") or ""
        teaser_short = r.get("teaser") or ""
        teaser_full = r.get("teaser_full") or ""

        # Jahr aus "EZ MM/YYYY"
        year = None
        m = year_rx.search(tag_blob + " " + teaser_short + " " + teaser_full)
        if m:
            y = int(m.group(1))
            if 1980 <= y <= 2030:
                year = y

        # km aus Tag-Zeile bevorzugt (rauschärmer als Teaser)
        mileage = None
        m = km_rx.search(tag_blob)
        if m:
            v = int(re.sub(r"[^\d]", "", m.group(1)))
            if 100 <= v <= 1_500_000:
                mileage = v

        # PS aus dem ganzen verfügbaren Text (Titel + Teaser + langer Description)
        hp_blob = (r["title"] + " " + teaser_short + " " + teaser_full)
        hp = None
        cands = []
        for m in ps_rx.finditer(hp_blob):
            v = int(m.group(1))
            if 60 <= v <= 1500:
                cands.append(v)
        for m in kw_rx.finditer(hp_blob):
            v = int(round(int(m.group(1)) * 1.35962))
            if 60 <= v <= 1500:
                cands.append(v)
        if cands:
            hp = max(cands)

        # Längeren Teaser an matches_de / Telegram-Karte weitergeben.
        # is_tuning_candidate liest hier den vollen Kontext (description), nicht
        # nur die 1-Zeilen-Vorschau.
        teaser_out = (teaser_full or teaser_short)[:800]

        out.append({
            "source": "kleinanzeigen",
            "id": str(r.get("id") or href),
            "url": href,
            "title": r["title"][:120],
            "price": price,                # EUR
            "image": r.get("img") or "",
            "date": r.get("date") or "",
            "location": r.get("loc") or "",
            "teaser": teaser_out,
            "year": year, "mileage": mileage, "horsepower": hp, "fuel": None,
        })
    return out


# ---------------------------------------------------------------- mobile.de
def scrape_mobile(pg, search, limit=30):
    """mobile.de Freitext-Suche. Liefert eine Liste (oder None bei Block)."""
    kw = _kw_for_de(search) or "BMW"
    # mobile.de hat eine Freitext-Box; einfachster Weg ist die URL mit dem
    # Quicksearch-Param. PriceTo + JahrFrom als Standard-Params.
    url = "https://suchen.mobile.de/fahrzeuge/search.html?vc=Car&dam=false&isSearchRequest=true"
    url += "&s=Car&searchFreeText=" + quote_plus(kw)
    max_price = search.get("maxPrice")
    if max_price:
        url += "&pe=" + str(int(max_price))
    min_year = search.get("minYear")
    if min_year:
        url += "&fr=" + str(int(min_year))
    url += "&sb=rel"  # nach Relevanz; für "neuste" wäre sb=lu
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return None
    pg.wait_for_timeout(2500)
    accept_cookies(pg)
    pg.wait_for_timeout(1500)
    for _ in range(3):
        pg.mouse.wheel(0, 4000)
        pg.wait_for_timeout(700)

    title = pg.title()
    if any(m in title.lower() for m in ("captcha", "blocked", "robot", "akamai", "forbidden")):
        return None

    rows = pg.eval_on_selector_all(
        "a[href*='/fahrzeuge/details.html'], article a[data-testid]",
        """els => {
            const seen = new Set(); const out = [];
            for (const a of els) {
                let href = a.getAttribute('href'); if (!href) continue;
                if (href.startsWith('/')) href = 'https://suchen.mobile.de' + href;
                if (seen.has(href)) continue; seen.add(href);
                let card = a; for (let i=0;i<6 && card.parentElement;i++){ card = card.parentElement;
                    if ((card.innerText||'').length > 30) break; }
                const txt = (card.innerText||'').trim();
                const img = card.querySelector('img');
                const m = href.match(/id=(\\d+)/) || href.match(/\\/(\\d+)\\./);
                out.push({ id: m ? m[1] : href, href, text: txt,
                    img: img ? (img.getAttribute('src')||img.getAttribute('data-src')||'') : '' });
            }
            return out;
        }""")

    out = []
    seen_ids = set()
    for r in rows:
        rid = str(r.get("id") or r["href"])
        if rid in seen_ids: continue
        seen_ids.add(rid)
        lines = [l for l in (r.get("text") or "").splitlines() if l.strip()]
        if not lines: continue
        title_line = next((l for l in lines if len(l) >= 8 and any(c.isalpha() for c in l)
                           and "€" not in l and "km" not in l.lower()),
                          lines[0])
        # Preis aus erstem "12.345 €"
        price = None
        for l in lines:
            m = re.search(r"(\d[\d\.\s]{1,9})\s*€", l)
            if m:
                price = int(re.sub(r"[^\d]", "", m.group(1)))
                break
        # km
        mileage = None
        for l in lines:
            m = re.search(r"(\d[\d\.\s]{1,9})\s*km", l, re.I)
            if m:
                mileage = int(re.sub(r"[^\d]", "", m.group(1)))
                break
        # PS
        hp = None
        for l in lines:
            m = re.search(r"(\d{2,4})\s*kW\s*\((\d{2,4})\s*PS", l)
            if m:
                hp = int(m.group(2))
                break
            m = re.search(r"(\d{2,4})\s*PS", l)
            if m:
                hp = int(m.group(1)); break
        # Jahr
        year = None
        for l in lines:
            m = re.search(r"\b(19|20)\d{2}\b", l)
            if m:
                year = int(m.group(0)); break
        out.append({
            "source": "mobile",
            "id": rid,
            "url": r["href"],
            "title": title_line.strip()[:120],
            "price": price,
            "image": r.get("img") or "",
            "date": "", "location": "",
            "teaser": " | ".join(lines[:4])[:300],
            "year": year, "mileage": mileage, "horsepower": hp, "fuel": None,
        })
        if len(out) >= limit: break
    return out


SCRAPERS["kleinanzeigen"] = scrape_kleinanzeigen
SCRAPERS["mobile"] = scrape_mobile
