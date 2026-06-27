<div align="center">

# 🚗 BMW Deal Scanner

**Dein persönlicher Auto-Spürhund.** Er durchsucht rund um die Uhr die grössten Occasionen-Börsen der Schweiz und Deutschlands nach *deinen* Wunsch-Autos – und schickt dir neue Treffer und gute Deals sofort per **Telegram** aufs Handy.

Kein tägliches Durchklicken mehr. Du sagst einmal, was du suchst – der Bot macht den Rest. Für immer. Gratis.

![Cloudflare Workers](https://img.shields.io/badge/Cloudflare-Workers-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub-Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)

</div>

---

## 📑 Inhalt

- [Was es macht](#-was-es-macht)
- [So sieht ein Alarm aus](#-so-sieht-ein-alarm-aus)
- [Datenquellen](#-datenquellen)
- [Architektur](#-architektur)
- [Telegram-Befehle](#-telegram-befehle)
- [Selbst betreiben (Schritt für Schritt)](#-selbst-betreiben-schritt-für-schritt)
- [Eigene Suchen anlegen](#-eigene-suchen-anlegen)
- [Warum es gratis bleibt](#-warum-es-gratis-bleibt)
- [Grenzen & Ehrlichkeit](#-grenzen--ehrlichkeit)
- [Projektstruktur](#-projektstruktur)
- [Lokale Python-Variante](#-lokale-python-variante-optional)
- [Hinweise & Disclaimer](#-hinweise--disclaimer)

---

## ✨ Was es macht

- 🔎 **Multi-Börsen-Suche** – AutoScout24.ch, ricardo.ch, kleinanzeigen.de & mobile.de in einem Tool (Facebook Marketplace optional).
- 🎯 **Punktgenaue Filter** – Marke, Modell, Preis, Jahr, Kilometer, **Hubraum**, **PS (bis ≥ 500)** und Treibstoff. Alles per Knopfdruck im Telegram-Bot, kein Tippen nötig.
- 🔥 **Deal-Bewertung** – jedes CH-Inserat wird mit dem aktuellen Markt-Median verglichen: **🔥 TOP-DEAL** (≥ 25 % unter Median), **👍 Guter Deal** (≥ 15 %), **🆕 Neu**.
- 📉 **Preissenkungs-Alarm** – der Scanner merkt sich jeden Preis. Fällt er später, bekommst du automatisch eine **„Preis gesenkt"-Karte** (alt → neu, −%). Übersicht mit `/preis`.
- 📋 **Komplettes Inserat im Chat** – mit `/mehrinfo` *als Antwort* auf eine Karte holst du das **ganze** Inserat: Hubraum, Zylinder, Verbrauch, CO₂, Getriebe, Farben, Zustand, kompletter Text – **und alle Bilder als Galerie**. Kein Wechsel zur Plattform nötig.
- 🔧 **Tuning-Radar für DE** – die deutschen Quellen werden auf getunte Autos gefiltert (~80 Keywords wie *Stage 2, Kompressor, JB4, Eisenmann* + PS-Schwelle).
- 🚫 **Stichwort-Sperre** – Inserate mit „Motorschaden", „Bastler", „Export" & Co. fliegen automatisch raus.
- 🔕 **Kein Spam** – gesehene Inserate werden gemerkt; gemeldet wird nur wirklich Neues. Der allererste Lauf einer Suche merkt sich still den Bestand. Die „nichts Neues"-Statusmeldung **räumt sich selbst auf** (immer nur eine, mit Zähler) – kein endloses Scrollen.
- ✏️ **Suchen verwalten** – bestehende Suche per `/edit` anpassen (Preis/PS/Jahr/…) oder **pausieren/fortsetzen**, ohne sie zu löschen. `/stats` zeigt dir den Gesamtüberblick.
- ⭐ **Favoriten** – jedes Auto per Knopfdruck merken und später mit `/favoriten` wieder aufrufen.
- 🛡️ **Läuft konstant** – ein blockierter Anbieter bringt nie das ganze System zum Absturz; nach längerem Ausfall einer Quelle bekommst du *eine* dezente Telegram-Notiz statt Fehler-Spam.
- ☁️ **24/7 & gratis** – kein eigener Server, kein Strom, kein PC, der laufen muss.

---

## 📱 So sieht ein Alarm aus

> 🆕 **Neuer Treffer** · ricardo
> **BMW M5 E60 V10 SMG – frisch ab MFK**
> 💰 CHF 18'900   🔥 TOP-DEAL (−27 % vs. Median)
> 📅 2008   🛣 142'000 km   ⚙ 507 PS
> 📍 8000 Zürich
> 🔎 *🇨🇭 BMW M5 · Benzin · ≥350 PS*
> [➜ Inserat ansehen](#)  ⭐ Merken

Jede Karte kommt mit Bild, Preis, Eckdaten, Deal-Einschätzung und Direktlink – DE-Karten zusätzlich mit 🇩🇪-Flagge und EUR→CHF-Umrechnung.

---

## 🌐 Datenquellen

| Quelle | Land | Status | Technik |
|---|---|---|---|
| **AutoScout24.ch** | 🇨🇭 | ✅ **Hauptquelle, sehr stabil** | interne JSON-API (kein Browser nötig) |
| **ricardo.ch** | 🇨🇭 | 🟡 Best-effort | echter Browser (Playwright); Cloudflare blockt zeitweise |
| **kleinanzeigen.de** | 🇩🇪 | 🟡 Best-effort, Tuning-gefiltert | echter Browser (Playwright) |
| **mobile.de** | 🇩🇪 | 🟡 Best-effort (Pool für `/mobile`) | echter Browser (Playwright) |
| **Facebook Marketplace** | 🌍 | ⚪ Optional, eingebaut | Browser + Login-Cookie |

> **Warum „Best-effort"?** ricardo/kleinanzeigen/mobile schützen sich gegen Bots und blockieren Rechenzentrums-IPs zeitweise. Der Scanner erkennt das, **überspringt** die Quelle sauber und versucht es beim nächsten Lauf erneut – ohne Absturz, ohne Falschmeldung. AutoScout24 läuft über eine saubere API und ist praktisch immer erreichbar.

---

## 🏗 Architektur

Drei Bausteine, die zusammenspielen – alle im Gratis-Kontingent:

```
                          ┌──────────────────────────────┐
                          │        TELEGRAM (du)         │
                          │  /addcar · Alarme · ⭐ · /deals │
                          └───────────────┬──────────────┘
                                          │  Webhook
                                          ▼
   ┌───────────────────────────────────────────────────────────────┐
   │              ☁️  CLOUDFLARE WORKER  (das Gehirn)               │
   │  • Telegram-Bot (alle Befehle & Menüs)                        │
   │  • AS24-Scan per API · Deal-Scoring · Preissenkung · Filter   │
   │  • KV: Suchen · gesehen · Preise · Favoriten · Heartbeat      │
   │            Cron: alle 30 Min                                  │
   └───────────────▲───────────────────────────────┬──────────────┘
                   │  /searches (Suchen abholen)    │  Cache füllen
                   │                                ▼
   ┌───────────────┴───────────────────────────────────────────────┐
   │        🤖  GITHUB ACTIONS  ·  Browser-Scraper (Playwright)      │
   │  ricardo.ch · kleinanzeigen.de · mobile.de · (Facebook)       │
   │            alle 30 Min  →  neue Treffer direkt per Telegram     │
   └───────────────────────────────────────────────────────────────┘
```

- **Cloudflare Worker** (`cf-worker/`) – das Herz: betreibt den Telegram-Bot, scannt AutoScout24 selbst per API und speichert alles in Cloudflare KV.
- **GitHub Actions** (`browser-scraper/`) – der „Browser-Arm" für die Seiten, die einen echten Browser brauchen. Holt sich die aktiven Suchen vom Worker und schickt neue Treffer direkt an denselben Telegram-Bot.
- **Telegram** – deine komplette Fernsteuerung und dein Briefkasten.

---

## 💬 Telegram-Befehle

| Befehl | Was es tut |
|---|---|
| `/addcar` | Neue Auto-Suche anlegen – 🇨🇭 oder 🇩🇪, **alles per Buttons** (Marke → Modell → Treibstoff → Preis → PS → Karosserie) |
| `/kleinanzeigen` | 🇩🇪 Direkt eine kleinanzeigen.de-Suche (nur Tuning) anlegen |
| `/mobile` | 🇩🇪 Heisse mobile.de-Inserate ansehen |
| `/list` | Alle aktiven Suchen anzeigen |
| `/edit` | ✏️ Bestehende Suche bearbeiten (Preis/PS/Jahr/Treibstoff/Karosserie) oder **pausieren / fortsetzen** |
| `/deletecar` | Eine Suche löschen |
| `/stats` | 📊 Übersicht & Status (Suchen, beobachtete Inserate, Senkungen, letzter Treffer) |
| `/deals` | Beste Treffer aller 🇨🇭-Suchen |
| `/preis` | 📉 Jüngste Preissenkungen |
| `/mehrinfo` | 📋 **Als Antwort auf eine Inserat-Karte:** komplettes Inserat (alle Daten + alle Bilder) in den Chat |
| `/zeig` | Eine Suche auswählen & Top-Treffer zeigen (auch `/zeig BMW 335`) |
| `/ricardo` | Neueste ricardo-Treffer |
| `/favoriten` | ⭐ Gemerkte Autos |
| `/block` · `/blocklist` | Stichwörter sperren / verwalten (z. B. „Motorschaden") |
| `/scrape` | 🤖 Den Browser-Scraper sofort manuell starten (~2 Min) |
| `/clear` | Chat aufräumen |
| `/help` | Hilfe |

> **💡 Tipp – `/mehrinfo`:** Antworte (Telegram-„Reply") auf eine beliebige Inserat-Karte mit `/mehrinfo`. Der Bot liest die Inserat-ID aus der Karte und holt dir bei 🇨🇭 AutoScout24 das **komplette** Inserat samt Bildergalerie direkt in den Chat. (🇩🇪-Inserate eingeschränkt – ohne Detail-API.)

> Der Bot antwortet **ausschliesslich** auf deine eigene Chat-ID. Schreibt ein Fremder dem Bot, wird er ignoriert – auch wenn das Repo öffentlich ist.

---

## 🚀 Selbst betreiben (Schritt für Schritt)

Du willst denselben Bot für dich? In ~20 Minuten steht er. Du brauchst nur kostenlose Accounts: **Telegram**, **Cloudflare** und **GitHub**.

### Voraussetzungen
- [Node.js](https://nodejs.org/) (für `wrangler`, das Cloudflare-CLI)
- Ein Telegram-Konto, ein (kostenloses) Cloudflare-Konto, ein GitHub-Konto

### 1️⃣ Telegram-Bot erstellen
1. In Telegram **[@BotFather](https://t.me/BotFather)** öffnen → `/newbot` → Namen vergeben → **Bot-Token** kopieren.
2. Schreibe deinem neuen Bot **irgendeine Nachricht** (z. B. „hi").
3. Deine **Chat-ID** holen: Öffne `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` im Browser und such nach `"chat":{"id":...}`.

### 2️⃣ Cloudflare Worker deployen (das Gehirn)
```bash
git clone https://github.com/Giankp007/BMWDealScanner.git
cd BMWDealScanner/cf-worker
npm install

# Bei Cloudflare anmelden:
npx wrangler login

# KV-Speicher anlegen und die ausgegebene id in wrangler.toml eintragen:
npx wrangler kv namespace create BMW_KV

# Drei Secrets setzen (jeweils nach Aufforderung den Wert einfügen):
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler secret put WEBHOOK_SECRET      # frei wählbares, langes Passwort

# Deployen:
npx wrangler deploy
```
Danach **einmal den Telegram-Webhook registrieren** – im Browser aufrufen:
```
https://<dein-worker>.workers.dev/init?key=<DEIN_WEBHOOK_SECRET>
```
✅ Ab jetzt läuft der Telegram-Bot und scannt AutoScout24 alle 30 Min.

### 3️⃣ GitHub Actions für die Browser-Quellen (ricardo & DE)
1. **Forke** dieses Repo in deinen GitHub-Account.
2. Im Fork → **Settings → Secrets and variables → Actions** → diese Secrets anlegen:
   | Secret | Wert |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | dein Bot-Token |
   | `TELEGRAM_CHAT_ID` | deine Chat-ID |
   | `WORKER_SECRET` | **derselbe** Wert wie `WEBHOOK_SECRET` oben |
   | `FB_COOKIE` | *(optional)* dein Facebook-Login-Cookie |
3. **Empfohlen: Repo öffentlich stellen** (*Settings → General → Visibility*). Öffentliche Repos haben **unbegrenzte** Actions-Minuten → garantiert gratis. *(Deine Secrets bleiben verschlüsselt und sind nie im Code.)*
4. Fertig – `.github/workflows/browser-scan.yml` läuft automatisch alle 30 Min.

### 4️⃣ Loslegen
Im Telegram-Bot **`/addcar`** tippen und deine erste Suche zusammenklicken. 🎉

---

## 🔧 Eigene Suchen anlegen

Am einfachsten **komplett im Bot** über `/addcar` – dort wählst du Marke, Modell, Preis, **PS (egal · ≥150 · ≥200 · ≥250 · ≥300 · ≥350 · ≥400 · ≥450 · ≥500)**, Treibstoff und Karosserie per Knopfdruck. Nichts ist vorgegeben – **du** entscheidest, wonach gesucht wird.

Für die lokale Python-Variante trägst du Profile stattdessen in `config.yaml` ein (Beispiel ist auskommentiert enthalten).

---

## 💸 Warum es gratis bleibt

| Baustein | Gratis-Grundlage |
|---|---|
| Cloudflare Worker | Free-Tier: 100'000 Requests/Tag – weit mehr als genug |
| Cloudflare KV | Free-Tier-Speicher für Suchen & Dedup |
| GitHub Actions | **Öffentliches** Repo = unbegrenzte Minuten |
| Telegram Bot API | komplett kostenlos |

Zusammen: **0 CHF/Monat**, 24/7, ohne eigenen Server.

---

## ⚖️ Grenzen & Ehrlichkeit

- **ricardo / kleinanzeigen / mobile** werden aus der Gratis-Rechenzentrums-IP zeitweise blockiert. Das ist normal und eingeplant: Die Quelle wird übersprungen und beim nächsten Lauf neu versucht. Ist eine Quelle **länger als 6 h** am Stück blockiert, bekommst du *eine* Telegram-Notiz.
- **Facebook Marketplace** ist der heikelste Fall (Login-Walls, Account-Checks). Eingebaut, aber wirklich nur „best-effort" – der Cookie kann ablaufen und muss dann erneuert werden.
- **AutoScout24** ist die verlässliche Hauptquelle und deckt den CH-Markt breit ab.

---

## 📂 Projektstruktur

```
cf-worker/              ☁️ Cloudflare Worker – das Gehirn (empfohlen)
  src/index.js          Einstieg: Telegram-Webhook + 30-Min-Cron
  src/bot.js            Alle Befehle & Menüs (/addcar, /edit, /stats, /preis, /mehrinfo …)
  src/scan.js           AutoScout24-Scan, Deal-Scoring, Stichwortfilter, Preissenkung, Heartbeat
  src/autoscout24.js    AutoScout24-API-Client (Suche · Detail · Bilder)
  src/store.js          KV: Suchen · gesehen · Preise · Senkungen · Sperrwörter · Favoriten · Heartbeat
  src/telegram.js       Telegram-API-Helfer (inkl. Bildergalerie)
  wrangler.toml         Worker-Konfig, Cron, KV-Binding

browser-scraper/        🤖 GitHub-Actions-Scraper (Playwright)
  scrape.py             Orchestrierung: Quellen, Alarme, Block-Notify
  sites.py              ricardo · kleinanzeigen · mobile · facebook
  tuning.py             Tuning-Verdacht-Filter (~80 Keywords + PS-Schwelle)

.github/workflows/
  browser-scan.yml      Cron alle 30 Min für den Browser-Arm

config.yaml             Profile für die lokale Python-Variante (startet leer)
scanner.py / sources/   🖥️ eigenständige lokale CLI-Variante (nur AutoScout24)
```

---

## 🖥️ Lokale Python-Variante (optional)

Wer lieber alles lokal laufen lässt (nur AutoScout24, ohne Bot):
```bash
pip install -r requirements.txt
python scanner.py --once     # einmal scannen
python scanner.py --loop     # dauerhaft (alle 30 Min)
python scanner.py --seed     # Bestand still einlesen, ohne Alarme
```
Suchen werden in `config.yaml` definiert. Telegram optional via `setup_telegram.py`.

---

## 📝 Hinweise & Disclaimer

- **Privater Gebrauch.** Dieses Projekt ist ein persönlicher Helfer, um nicht ständig manuell suchen zu müssen. Bitte respektiere die Nutzungsbedingungen der jeweiligen Plattformen und halte das Scan-Intervall fair (30 Min ist bewusst entspannt).
- **Keine Garantie.** Marktplätze ändern ihr Layout; Browser-Quellen können zeitweise ausfallen. AutoScout24 ist die stabile Basis.
- **Deine Daten bleiben deine.** Alle Zugangsdaten liegen in verschlüsselten Secrets, nie im Code. Der Bot kommuniziert nur mit deiner eigenen Chat-ID.

---

## 📄 Lizenz

[MIT](LICENSE) – mach damit, was du willst.

<div align="center">

*Gebaut mit ❤️ und zu viel Liebe für Reihensechszylinder von **Gian Kappeler***

</div>
