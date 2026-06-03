# 🚗 BMW Deal Scanner

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Cloudflare Workers](https://img.shields.io/badge/Cloudflare-Workers-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Alerts-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)

Durchsucht automatisch den Schweizer Occasionen-Markt nach deinen Wunsch-Autos
(Standard: BMW 335i / 330i / 130i / 135i, Reihensechszylinder ≥ 3.0 L, ≤ 20'000 CHF)
und schickt dir per **Telegram** eine Nachricht, sobald ein **neues Inserat** oder
ein **guter Deal** auftaucht.

Du musst nicht mehr jeden Tag selber auf den Marktplätzen suchen. ✅

---

## Zwei Betriebsarten

Das Repo enthält **zwei vollwertige Implementierungen** desselben Scanners – wähl die, die zu dir passt:

| | ☁️ **Cloudflare Worker** *(empfohlen)* | 🖥️ **Python-CLI** |
|---|---|---|
| Läuft | 24/7 in der Cloud, **gratis**, ohne eigenen PC | lokal auf deinem Rechner |
| Steuerung | **interaktiver Telegram-Bot** (`/addcar`, `/deals`, …) | `config.yaml` + Kommandozeile |
| Ordner | [`cf-worker/`](cf-worker/) | Projekt-Wurzel |
| Scan-Takt | Cron alle 30 Min | `--loop` oder Aufgabenplanung |

> Die Cloud-Variante läuft live unter `https://bmw-deal-scanner.<account>.workers.dev`. Details + Deployment siehe **[`cf-worker/README.md`](cf-worker/README.md)**.

---

## Was es kann

- **Profil-basiert** – such nach beliebigen Fahrzeugen (Marke, Modell, Preis, Jahr, km, **Hubraum**, PS, Treibstoff).
- **Deal-Bewertung** – jedes Inserat wird mit dem aktuellen Markt-Median verglichen
  (🔥 TOP-DEAL ≥ 25 % unter Median, 👍 Guter Deal ≥ 15 %, 🆕 Neu).
- **Stichwort-Filter** – Inserate mit gesperrten Wörtern im Titel (z. B. „Motorschaden", „Bastler") werden ausgeblendet.
- **Kein Spam** – gesehene Inserate werden gemerkt (SQLite bzw. Cloudflare KV), gemeldet wird nur wirklich Neues.
- **Telegram-Push** – Alarm aufs Handy mit Preis, Jahr, km, PS, Ort und Link.

## Datenquellen

| Quelle               | Status        | Technik |
|----------------------|---------------|---------|
| **AutoScout24.ch**   | ✅ **aktiv**  | offizielle interne JSON-API, präzise Filter |
| tutti.ch / ricardo.ch | 🔬 experimentell | Browser-Scraper ([`browser-scraper/`](browser-scraper/), Playwright) |
| Facebook Marketplace | 🔜 geplant    | Browser + Login |

> AutoScout24 ist die mit Abstand grösste CH-Autobörse und deckt den Grossteil des
> Markts ab – damit funktioniert der Scanner schon vollwertig. Der `browser-scraper/`
> ist ein Erweiterungs-Experiment für Quellen ohne öffentliche API.

---

## 🖥️ Python-CLI – Einrichtung

### 1. Abhängigkeiten
```powershell
pip install -r requirements.txt
```

### 2. Telegram-Bot einrichten
1. In Telegram **@BotFather** öffnen → `/newbot` → Namen vergeben → **Token kopieren**.
2. Token in `config.yaml` eintragen:
   ```yaml
   telegram:
     bot_token: "123456:ABC-dein-token"
   ```
3. Deinem neuen Bot in Telegram **irgendeine Nachricht** schreiben (z. B. „hi").
4. chat_id automatisch holen + speichern:
   ```powershell
   python setup_telegram.py
   ```
   → Du bekommst eine Bestätigungsnachricht im Chat. Fertig.

> Ohne Telegram läuft alles trotzdem – Alarme erscheinen dann in der Konsole.

### 3. Benutzung
```powershell
python scanner.py --once     # einmal scannen
python scanner.py --loop     # dauerhaft scannen (alle 30 Min, einstellbar)
python scanner.py --seed     # Bestand still einlesen, ohne Alarme
```

Beim **allerersten** Scan eines Profils wird der Bestand nur stillschweigend gemerkt
(kein Spam). Ab dem zweiten Scan kommen Alarme nur für **neue** Inserate.

**Im Hintergrund (empfohlen):** `run.bat` per Windows-Aufgabenplanung *bei Anmeldung*
oder *alle 30 Min* mit `python scanner.py --once`, „Starten in" = Projektordner.

---

## ☁️ Cloudflare Worker – Kurzfassung

```bash
cd cf-worker
npm install
export CLOUDFLARE_API_TOKEN=...          # "Edit Cloudflare Workers"-Rechte
NODE_OPTIONS=--use-system-ca npx wrangler deploy
```

Steuerung danach komplett per Telegram: `/addcar`, `/deletecar`, `/list`, `/deals`,
`/block`, `/blocklist`, `/help`. Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`WEBHOOK_SECRET`) via `wrangler secret put`. Volle Anleitung in [`cf-worker/README.md`](cf-worker/README.md).

---

## Eigene Fahrzeuge hinzufügen (CLI)

In `config.yaml` ein neues Profil anhängen:

```yaml
  - name: "Audi RS3 8V"
    enabled: true
    sources: [autoscout24]
    price_max: 45000
    year_min: 2015
    cubic_capacity_min: 2400      # 2.5 L Fünfzylinder
    fuel_types: [petrol]
    autoscout24_models:
      - {makeKey: audi, modelKey: "rs3"}
    keywords_any: ["RS3"]
```

`makeKey`/`modelKey` sind die AutoScout24-Schlüssel (klein, z. B. `bmw`/`335`,
`audi`/`rs3`, `mercedes-benz`/`c63`). Modelle einer Marke findest du via:
`https://api.autoscout24.ch/v1/makes/key/<marke>/models?vehicleCategory=car`

### Kriterien-Felder
| Feld | Bedeutung |
|------|-----------|
| `price_min` / `price_max` | Preisspanne CHF |
| `year_min` / `year_max` | Erstzulassungs-Jahr |
| `mileage_max` | max. Kilometer |
| `cubic_capacity_min` | min. Hubraum in ccm (2900 ≈ 3.0 L) |
| `horsepower_min` | min. PS |
| `fuel_types` | `petrol`, `diesel`, `electric`, `hybrid`, `gas` |
| `deal_threshold` | ab wie viel % unter Median = „guter Deal" (0.15 = 15 %) |

---

## Projektstruktur
```
scanner.py          CLI-Orchestrierung (--once / --loop / --seed)
config.yaml         Such-Profile + Telegram + Einstellungen
core.py             Listing-/Profil-Datenmodelle
sources/
  autoscout24.py    ✅ aktive Quelle (JSON-API)
  tutti.py          🔜 Scaffold
store.py            SQLite, merkt gesehene Inserate (seen.db)
scoring.py          Deal-Bewertung (Median-Vergleich)
notify.py           Telegram-Versand
setup_telegram.py   Helfer für chat_id
browser-scraper/    🔬 Playwright-Scraper für API-lose Quellen
cf-worker/          ☁️ Cloudflare-Worker-Variante (24/7, Telegram-Bot)
```

## Hinweise
- Diese Maschine hat einen TLS-Intercept → alle HTTP-Module nutzen `truststore`
  (Windows-Zertifikatsspeicher) bzw. npm/wrangler mit `NODE_OPTIONS=--use-system-ca`. Nicht entfernen.
- AutoScout24 begrenzt die API-Seitengrösse auf 20 (intern bereits berücksichtigt).
- Respektvoll bleiben: Scan-Intervall nicht zu klein wählen (30 Min ist gut).

---

*Entwickelt von Gian Kappeler*
