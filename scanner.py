"""BMW Deal Scanner — main orchestrator.

Usage:
    python scanner.py --once     # one scan and exit
    python scanner.py --loop     # scan forever, every settings.scan_interval_minutes
    python scanner.py --seed     # populate the store quietly (no alerts), e.g. first setup
"""
from __future__ import annotations
import argparse, sys, time, datetime, os
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import yaml

from core import Profile
from store import Store
from scoring import market_median, score as score_listing
from notify import Notifier
import sources


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_secrets(cfg: dict) -> tuple[str, str]:
    """Telegram token/chat_id from (1) env vars, (2) secrets.local.yaml, (3) config.yaml.

    The token must NEVER live in a committed file. In GitHub Actions it comes from
    env vars (repo secrets); locally from the gitignored secrets.local.yaml.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        here = os.path.dirname(os.path.abspath(__file__))
        local = os.path.join(here, "secrets.local.yaml")
        if os.path.exists(local):
            with open(local, "r", encoding="utf-8") as f:
                s = yaml.safe_load(f) or {}
            token = token or str(s.get("bot_token", "")).strip()
            chat_id = chat_id or str(s.get("chat_id", "")).strip()
    tg = cfg.get("telegram", {}) or {}
    token = token or str(tg.get("bot_token", "")).strip()
    chat_id = chat_id or str(tg.get("chat_id", "")).strip()
    return token, chat_id


def scan_profile(profile: Profile, settings: dict, store: Store, notifier: Notifier,
                 seed: bool = False):
    quiet_first = settings.get("quiet_first_run", True) and store.profile_count(profile.name) == 0
    if seed:
        quiet_first = True
    max_listings = int(settings.get("max_listings", 250))

    all_listings = []
    for src_name in profile.sources:
        fetch = sources.get(src_name)
        if not fetch:
            log(f"  ⚠ Quelle '{src_name}' noch nicht implementiert — übersprungen")
            continue
        try:
            listings = fetch(profile, max_listings)
            log(f"  {src_name}: {len(listings)} Inserate")
            all_listings.extend(listings)
        except Exception as e:
            log(f"  ✗ {src_name} Fehler: {e!r}")

    median = market_median(all_listings)
    median_txt = f"{int(median):,}".replace(",", "'") if median else "—"
    log(f"  Markt-Median: CHF {median_txt}  ({len(all_listings)} Inserate gesamt)")

    new_count = alert_count = 0
    for listing in all_listings:
        is_new = store.upsert(listing, profile.name, alerted=quiet_first)
        if not is_new:
            continue
        new_count += 1
        if quiet_first:
            continue
        sc = score_listing(listing, median)
        ok = notifier.send(listing, profile.name, sc)
        if ok:
            store.mark_alerted(listing.uid)
        alert_count += 1

    if quiet_first:
        log(f"  Erststart: {new_count} Inserate gemerkt (keine Alarme).")
    else:
        log(f"  {new_count} neu · {alert_count} Alarme gesendet")


def run_once(cfg: dict, store: Store, notifier: Notifier, seed: bool = False):
    profiles = [Profile.from_dict(p) for p in cfg.get("profiles", [])]
    settings = cfg.get("settings", {})
    active = [p for p in profiles if p.enabled]
    log(f"=== Scan startet · {len(active)} aktive Profile ===")
    for p in active:
        log(f"▶ {p.name}")
        scan_profile(p, settings, store, notifier, seed=seed)
    log("=== Scan fertig ===")


def main():
    ap = argparse.ArgumentParser(description="BMW Deal Scanner")
    ap.add_argument("--once", action="store_true", help="ein Scan und beenden")
    ap.add_argument("--loop", action="store_true", help="endlos scannen")
    ap.add_argument("--seed", action="store_true", help="Bestand still einlesen, keine Alarme")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    token, chat_id = resolve_secrets(cfg)
    notifier = Notifier(token, chat_id)
    if not notifier.enabled:
        log("⚠ Telegram nicht konfiguriert — Alarme erscheinen nur in der Konsole. "
            "Siehe README, Schritt 2.")
    store = Store()

    try:
        if args.loop:
            interval = int(cfg.get("settings", {}).get("scan_interval_minutes", 30)) * 60
            while True:
                run_once(cfg, store, notifier, seed=args.seed)
                log(f"⏳ nächster Scan in {interval // 60} Min …\n")
                time.sleep(interval)
        else:
            run_once(cfg, store, notifier, seed=args.seed)
    except KeyboardInterrupt:
        log("Abgebrochen.")
    finally:
        store.close()


if __name__ == "__main__":
    main()
