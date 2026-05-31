"""Helper: find your Telegram chat_id and write it into secrets.local.yaml.

How to use:
  1. In Telegram, open @BotFather, send /newbot, copy the token.
  2. Put token+chat_id into secrets.local.yaml  (bot_token: "..."), chat_id can stay empty.
  3. Open a chat with YOUR new bot and send it any message (e.g. "hi").
  4. Run:  python setup_telegram.py   -> finds chat_id and saves it.
"""
import truststore; truststore.inject_into_ssl()
import requests, sys, os
import yaml
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SECRETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets.local.yaml")


def main():
    if not os.path.exists(SECRETS):
        print("✗ secrets.local.yaml fehlt. Lege sie an mit:  bot_token: \"<token>\"")
        sys.exit(1)
    with open(SECRETS, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    token = str(data.get("bot_token", "")).strip()
    if not token:
        print("✗ Kein bot_token in secrets.local.yaml.")
        sys.exit(1)
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
    if not r.get("ok"):
        print("✗ Telegram-Fehler:", r)
        sys.exit(1)
    updates = r.get("result", [])
    if not updates:
        print("✗ Keine Nachrichten. Schreibe deinem Bot in Telegram zuerst eine Nachricht, "
              "dann dieses Skript erneut starten.")
        sys.exit(1)
    chat = updates[-1]["message"]["chat"]
    chat_id = str(chat["id"])
    name = chat.get("first_name") or chat.get("title") or "?"
    print(f"✓ chat_id gefunden: {chat_id}  (Chat mit: {name})")

    data["chat_id"] = chat_id
    with open(SECRETS, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    print("✓ In secrets.local.yaml gespeichert.")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat_id, "text": "✅ BMW Deal Scanner ist verbunden!"})


if __name__ == "__main__":
    main()
