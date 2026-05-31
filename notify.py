"""Telegram notifications (with console fallback when not configured)."""
from __future__ import annotations
import truststore; truststore.inject_into_ssl()
import requests
from core import Listing


def _fmt_price(p):
    return f"CHF {p:,}".replace(",", "'") if p else "Preis k.A."


def build_message(listing: Listing, profile_name: str, score: dict) -> str:
    median_note = ""
    if score.get("discount"):
        median_note = f"  ({score['discount']*100:+.0f}% vs. Median)"
    parts = [
        f"{score['label']}{median_note}",
        f"*{listing.title}*",
        f"💰 {_fmt_price(listing.price)}",
    ]
    spec = []
    if listing.year: spec.append(f"📅 {listing.year}")
    if listing.mileage is not None: spec.append(f"🛣 {listing.mileage:,}".replace(",", "'") + " km")
    if listing.horsepower: spec.append(f"⚙ {listing.horsepower} PS")
    if spec: parts.append("  ".join(spec))
    if listing.location: parts.append(f"📍 {listing.location}")
    parts.append(f"🔎 _{profile_name}_ · {listing.source}")
    parts.append(listing.url)
    return "\n".join(parts)


class Notifier:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

    def send(self, listing: Listing, profile_name: str, score: dict) -> bool:
        text = build_message(listing, profile_name, score)
        if not self.enabled:
            print("\n[ALERT — Telegram nicht konfiguriert, Konsolen-Ausgabe]\n" + text)
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            r = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=20)
            if r.status_code != 200:
                print(f"[Telegram-Fehler {r.status_code}] {r.text[:200]}")
                return False
            return True
        except Exception as e:
            print(f"[Telegram-Ausnahme] {e!r}")
            return False
