"""Schickt SOFORT eine Übersicht der aktuell besten passenden Inserate je Profil.
Einmaliger Versand (kein Dedup, kein Speichern) — für 'zeig mir was gerade online ist'.
"""
import truststore; truststore.inject_into_ssl()
import sys, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import yaml
from core import Profile
from scoring import market_median, score
import sources
from scanner import resolve_secrets, load_config

TOP_N = 6


def fmt_price(p): return f"CHF {p:,}".replace(",", "'") if p else "k.A."


def main():
    cfg = load_config("config.yaml")
    token, chat_id = resolve_secrets(cfg)
    profiles = [Profile.from_dict(p) for p in cfg.get("profiles", []) if p.get("enabled", True)]
    for prof in profiles:
        listings = []
        for s in prof.sources:
            fetch = sources.get(s)
            if fetch:
                try: listings += fetch(prof, 250)
                except Exception as e: print("err", s, e)
        if not listings:
            continue
        med = market_median(listings)
        best = sorted(listings, key=lambda l: (l.price or 1e9))[:TOP_N]
        head = f"📋 *Aktuell online · {prof.name}*\n" \
               f"{len(listings)} Treffer · Median {fmt_price(int(med)) if med else '—'}\n" \
               f"Die {len(best)} günstigsten gerade:\n"
        lines = [head]
        for l in best:
            sc = score(l, med)
            tag = "🔥" if sc["tier"] == "hot" else ("👍" if sc["tier"] == "good" else "•")
            spec = " · ".join(filter(None, [
                str(l.year) if l.year else "",
                (f"{l.mileage:,}".replace(",", "'") + " km") if l.mileage is not None else "",
                (f"{l.horsepower} PS") if l.horsepower else "",
            ]))
            lines.append(f"{tag} *{fmt_price(l.price)}* · {spec}\n{l.title[:50]}\n{l.url}")
        text = "\n\n".join(lines)
        if token and chat_id:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat_id, "text": text,
                                    "parse_mode": "Markdown", "disable_web_page_preview": True},
                              timeout=20)
            print(prof.name, "->", r.status_code)
        else:
            print(text)


if __name__ == "__main__":
    main()
