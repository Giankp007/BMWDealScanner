# 🚗 BMW Deal Scanner

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Alerts-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Scraping](https://img.shields.io/badge/Web-Scraping-43853D?style=for-the-badge)

Durchsucht automatisch den Schweizer Occasionen-Markt nach deinen Wunsch-Autos
(Standard: BMW 335i / 330i / 130i / 135i, Reihensechszylinder ≥ 3.0 L, ≤ 20'000 CHF)
und schickt dir per **Telegram** eine Nachricht, sobald ein **neues Inserat** oder
ein **guter Deal** auftaucht.

Du musst nicht mehr jeden Tag selber auf den Marktplätzen suchen. ✅

---

## Was es kann

- **Profil-basiert** – such nach beliebigen Fahrzeugen, einfach Profile in `config.yaml`
  anlegen (Marke, Modell, Preis, Jahr, km, **Hubraum**, PS, Treibstoff).
- **Deal-Bewertung** – jedes Inserat wird mit dem aktuellen Markt-Median verglichen
  (🔥 TOP-DEAL ≥ 25 % unter Median, 👍 Guter Deal ≥ 15 %, 🆕 Neu).
- **Kein Spam** – merkt sich gesehene Inserate (SQLite), meldet nur wirklich neue.
- **Telegram-Push** – Alarm aufs Handy mit Preis, Jahr, km, PS, Ort und Link.

## Datenquellen

| Quelle           | Status        | Technik |
|------------------|---------------|---------|
| **AutoScout24.ch** | ✅ **aktiv**  | offizielle interne JSON-API, präzise Filter |
| tutti.ch         | 🔜 geplant    | Browser (Playwright) |
| ricardo.ch       | 🔜 geplant    | Browser (Playwright) |
| Facebook Marketplace | 🔜 geplant | Browser + Login |
| comparis.ch      | 🔜 evtl.      | starker Anti-Bot; aggregiert ohnehin grösstenteils AutoScout24 |

> AutoScout24 ist die mit Abstand grösste CH-Autobörse und deckt den Grossteil des
> Markts ab – damit funktioniert der Scanner schon vollwertig. Die weiteren Quellen
> sind als Erweiterung vorbereitet (gleiche Schnittstelle, siehe `sources/`).

---

## Einrichtung (einmalig)

### 1. Abhängigkeiten
```powershell
cd "C:\Users\giank\Desktop\BMWDealScanner"
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

---

## Benutzung

```powershell
python scanner.py --once     # einmal scannen
python scanner.py --loop     # dauerhaft scannen (alle 30 Min, einstellbar)
python scanner.py --seed     # Bestand still einlesen, ohne Alarme
```

Beim **allerersten** Scan eines Profils wird der Bestand nur stillschweigend gemerkt
(kein Spam). Ab dem zweiten Scan kommen Alarme nur für **neue** Inserate.

### Im Hintergrund laufen lassen (empfohlen)
**Variante A – einfach:** Doppelklick auf `run.bat` (Fenster offen lassen).

**Variante B – Windows-Aufgabenplanung** (läuft auch ohne offenes Fenster):
1. „Aufgabenplanung" öffnen → *Aufgabe erstellen*.
2. Trigger: *Bei Anmeldung* (oder *täglich, alle 30 Min wiederholen*).
3. Aktion: Programm `python`, Argumente `scanner.py --once`,
   „Starten in" = `C:\Users\giank\Desktop\BMWDealScanner`.

---

## Eigene Fahrzeuge hinzufügen

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

`makeKey`/`modelKey` sind die AutoScout24-Schlüssel (klein geschrieben, z. B.
`bmw`/`335`, `audi`/`rs3`, `mercedes-benz`/`c63`). Modelle einer Marke findest du via:
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
scanner.py        Orchestrierung (--once / --loop / --seed)
config.yaml       Such-Profile + Telegram + Einstellungen
core.py           Listing / Profile Datenmodelle
sources/
  autoscout24.py  ✅ aktive Quelle (JSON-API)
  tutti.py        🔜 Scaffold (Browser)
store.py          SQLite, merkt gesehene Inserate (seen.db)
scoring.py        Deal-Bewertung (Median-Vergleich)
notify.py         Telegram-Versand
setup_telegram.py Helfer für chat_id
```

## Hinweise
- Die Maschine hat einen TLS-Intercept → alle HTTP-Module nutzen `truststore`
  (Windows-Zertifikatsspeicher). Nicht entfernen.
- AutoScout24 begrenzt die API-Seitengrösse auf 20 (intern bereits berücksichtigt).
- Respektvoll bleiben: Scan-Intervall nicht zu klein wählen (30 Min ist gut).
