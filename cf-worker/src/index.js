// Cloudflare Worker entry: Telegram webhook (fetch) + 30-min scan (scheduled).
import { tg } from "./telegram.js";
import { handleMessage, handleCallback, COMMANDS } from "./bot.js";
import { scanAndAlert } from "./scan.js";
import { getSearches, getBlockwords, saveRicache, saveKleinCache, saveMobileCache } from "./store.js";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/" ) {
      return new Response("BMW Deal Scanner Worker läuft.", { status: 200 });
    }

    // One-time setup: register webhook + bot commands. Protected by WEBHOOK_SECRET.
    if (url.pathname === "/init") {
      if (url.searchParams.get("key") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const token = env.TELEGRAM_BOT_TOKEN;
      const hookUrl = url.origin + "/webhook";
      const set = await fetch(
        "https://api.telegram.org/bot" + token + "/setWebhook",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: hookUrl,
            secret_token: env.WEBHOOK_SECRET,
            allowed_updates: ["message", "callback_query"],
          }),
        }
      ).then((r) => r.json());
      await tg(token).setMyCommands(COMMANDS);
      return new Response(JSON.stringify({ webhook: hookUrl, result: set }, null, 2), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Read endpoint for the browser-scraper companion (active searches + blockwords).
    if (url.pathname === "/searches") {
      if (url.searchParams.get("key") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const [searches, blockwords] = await Promise.all([getSearches(env), getBlockwords(env)]);
      return new Response(JSON.stringify({ searches, blockwords }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // The browser-scraper posts its latest ricardo results here for /ricardo.
    if (url.pathname === "/ricache" && request.method === "POST") {
      if (url.searchParams.get("key") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      await saveRicache(env, { updated: Date.now(), groups: body.groups || [] });
      return new Response("ok");
    }

    // kleinanzeigen-Treffer einer Suche (Browser-Scraper → Worker, gefiltert
    // auf Tuning). Body: { searchId, listings:[...] }
    if (url.pathname === "/kleincache" && request.method === "POST") {
      if (url.searchParams.get("key") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      const sid = (body.searchId || "").toString();
      if (!sid) return new Response("missing searchId", { status: 400 });
      await saveKleinCache(env, sid, {
        updated: Date.now(),
        listings: body.listings || [],
      });
      return new Response("ok");
    }

    // mobile.de — kuratierter Pool für /mobile, keine Alerts.
    // Body: { groups:[{label, listings:[...]}] }
    if (url.pathname === "/mobilecache" && request.method === "POST") {
      if (url.searchParams.get("key") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const body = await request.json();
      await saveMobileCache(env, { updated: Date.now(), groups: body.groups || [] });
      return new Response("ok");
    }

    // Telegram webhook
    if (url.pathname === "/webhook" && request.method === "POST") {
      if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
      const update = await request.json();
      const tgApi = tg(env.TELEGRAM_BOT_TOKEN);
      const allowed = String(env.TELEGRAM_CHAT_ID || "");

      try {
        if (update.message) {
          if (allowed && String(update.message.chat.id) !== allowed) {
            // private bot: ignore strangers
            return new Response("ok");
          }
          ctx.waitUntil(handleMessage(env, tgApi, update.message));
        } else if (update.callback_query) {
          if (allowed && String(update.callback_query.message.chat.id) !== allowed) {
            return new Response("ok");
          }
          ctx.waitUntil(handleCallback(env, tgApi, update.callback_query));
        }
      } catch (e) {
        // never fail the webhook (Telegram would retry)
      }
      return new Response("ok");
    }

    return new Response("not found", { status: 404 });
  },

  async scheduled(event, env, ctx) {
    const tgApi = tg(env.TELEGRAM_BOT_TOKEN);
    ctx.waitUntil(scanAndAlert(env, tgApi, env.TELEGRAM_CHAT_ID));
  },
};
