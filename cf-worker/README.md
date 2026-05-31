# BMW Deal Scanner — Cloudflare Worker

Interaktiver Telegram-Bot **und** Markt-Scanner in einem Cloudflare Worker.
Läuft 24/7 gratis, ohne eigenen Server. Quelle: AutoScout24.ch (interne JSON-API).

**Live:** https://bmw-deal-scanner.giankp007.workers.dev

## Funktionen
- Telegram-Befehle mit Menüs: `/addcar`, `/deletecar`, `/list`, `/deals`,
  `/block`, `/blocklist`, `/help`
- Scan alle 30 Min (Cron) → Telegram-Alarm bei neuen Treffern
- Deal-Bewertung vs. Markt-Median (🔥/👍/🆕)
- Stichwort-Filter: Inserate mit gesperrten Wörtern (z. B. „Motorschaden") im
  Titel werden ausgeblendet
- Dedup über KV → kein Spam

## Aufbau
```
src/index.js       Einstieg: Webhook (fetch) + Cron (scheduled)
src/bot.js         Befehle & Menü-Logik
src/scan.js        Scan, Deal-Scoring, Sperrwort-Filter, Nachrichten
src/autoscout24.js AutoScout24-API-Client
src/store.js       KV: searches / seen / blockwords / pending
src/telegram.js    Telegram-API-Helfer
wrangler.toml      Worker-Konfig + Cron + KV-Binding
```

## Daten (Cloudflare KV, Namespace `BMW_KV`)
- `searches` – aktive Suchen (JSON-Array)
- `seen` – gesehene Inserate (uid → Zeitstempel), Dedup
- `blockwords` – gesperrte Stichwörter (JSON-Array)
- `pending:<chatId>` – Gesprächszustand (TTL)

## Deployen / Aktualisieren
```bash
cd cf-worker
npm install
# Token mit "Edit Cloudflare Workers"-Rechten:
export CLOUDFLARE_API_TOKEN=...
NODE_OPTIONS=--use-system-ca npx wrangler deploy
```

## Secrets (im Worker, via `wrangler secret put`)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`   (privat: nur dieser Chat darf Befehle geben)
- `WEBHOOK_SECRET`     (verifiziert Telegram-Webhook-Aufrufe)

Webhook registrieren: `GET /init?key=<WEBHOOK_SECRET>` aufrufen, oder per
Telegram-API `setWebhook` mit `secret_token=<WEBHOOK_SECRET>`.

> Hinweis: Diese Maschine hat einen TLS-Intercept → npm/wrangler mit
> `NODE_OPTIONS=--use-system-ca` ausführen.
