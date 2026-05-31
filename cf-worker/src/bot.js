// Telegram command + callback handling (interactive menus).
import { keyboard, chunk } from "./telegram.js";
import { fetchModels, fetchMakes } from "./autoscout24.js";
import {
  getSearches, addSearch, removeSearch,
  getBlockwords, addBlockword, removeBlockword,
  getRicache, getMobileCache, setZeigCtx, getZeigCtx,
  setPending, getPending, clearPending,
  getFavorites, addFavorite, removeFavorite, isFavorite, getCachedListing,
} from "./store.js";
import { fmtPrice, sendListingsPage, sendFavoriteCard } from "./scan.js";

const PAGE = 8; // wie viele pro /zeig-Seite
import { sendSnapshot, seedSearch } from "./scan.js";

const POPULAR_BRANDS = [
  ["BMW", "bmw"], ["Audi", "audi"], ["Mercedes", "mercedes-benz"],
  ["VW", "volkswagen"], ["Porsche", "porsche"], ["Toyota", "toyota"],
  ["Ford", "ford"], ["Opel", "opel"], ["Škoda", "skoda"],
  ["Seat", "seat"], ["Volvo", "volvo"], ["Mini", "mini"],
  ["Tesla", "tesla"], ["Mazda", "mazda"], ["Honda", "honda"],
];

const HP_OPTIONS = [
  ["egal", 0], ["≥150 PS", 150], ["≥200 PS", 200],
  ["≥250 PS", 250], ["≥300 PS", 300], ["≥350 PS", 350],
];

// Karosserie (AutoScout24 bodyType-Keys)
const BODY_OPTIONS = [
  ["egal", ""], ["Limousine", "saloon"], ["Kombi", "estate"],
  ["Coupé", "coupe"], ["Cabrio", "cabriolet"], ["SUV", "suv"], ["Kleinwagen", "small-car"],
];
const BODY_NAME = Object.fromEntries(BODY_OPTIONS.map(([n, k]) => [k, n]));

// Treibstoff — AutoScout24 fuelType-Keys (verifiziert gegen die Such-API).
const FUEL_OPTIONS = [
  ["egal", "egal"], ["⛽ Benzin", "petrol"], ["🛢 Diesel", "diesel"],
  ["🔌 Elektro", "electric"], ["🔋 Hybrid", "hybrid"],
];
const FUEL_KEYS = {
  egal: [],
  petrol: ["petrol"],
  diesel: ["diesel"],
  electric: ["electric"],
  hybrid: ["phev-petrol", "mhev-petrol", "hev-petrol", "phev-diesel", "mhev-diesel"],
};
const FUEL_NAME = { petrol: "Benzin", diesel: "Diesel", electric: "Elektro", hybrid: "Hybrid" };

// Max-Preis (CHF)
const PRICE_OPTIONS = [
  ["egal", 0], ["≤ 5'000", 5000], ["≤ 10'000", 10000], ["≤ 15'000", 15000],
  ["≤ 20'000", 20000], ["≤ 30'000", 30000], ["≤ 50'000", 50000],
];

// Max-Preis (EUR, für kleinanzeigen — DE-Markt hat mehr High-End-Tuning)
const PRICE_EUR_OPTIONS = [
  ["egal", 0], ["≤ 10'000 €", 10000], ["≤ 15'000 €", 15000], ["≤ 25'000 €", 25000],
  ["≤ 40'000 €", 40000], ["≤ 60'000 €", 60000], ["≤ 100'000 €", 100000],
];

// Erstzulassung ab (Min-Jahr)
const YEAR_OPTIONS = [
  ["egal", 0], ["ab 2000", 2000], ["ab 2005", 2005],
  ["ab 2010", 2010], ["ab 2015", 2015], ["ab 2020", 2020],
];

const DEFAULT_MAX_PRICE = 20000;

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

function brandKeyboard() {
  const btns = POPULAR_BRANDS.map(([name, key]) => ({ text: name, data: "b:" + key }));
  const rows = chunk(btns, 3);
  rows.push([{ text: "✏️ Andere Marke (tippen)", data: "bx" }]);
  return keyboard(rows);
}

function hpKeyboard() {
  const btns = HP_OPTIONS.map(([t, v]) => ({ text: t, data: "h:" + v }));
  return keyboard(chunk(btns, 3));
}

function bodyKeyboard() {
  const btns = BODY_OPTIONS.map(([t, k]) => ({ text: t, data: "cb:" + k }));
  return keyboard(chunk(btns, 3));
}

function fuelKeyboard() {
  const btns = FUEL_OPTIONS.map(([t, k]) => ({ text: t, data: "f:" + k }));
  return keyboard(chunk(btns, 3));
}

function priceKeyboard() {
  const btns = PRICE_OPTIONS.map(([t, v]) => ({ text: t, data: "p:" + v }));
  return keyboard(chunk(btns, 3));
}

function priceEurKeyboard() {
  const btns = PRICE_EUR_OPTIONS.map(([t, v]) => ({ text: t, data: "p:" + v }));
  return keyboard(chunk(btns, 3));
}

function yearKeyboard() {
  const btns = YEAR_OPTIONS.map(([t, v]) => ({ text: t, data: "ky:" + v }));
  return keyboard(chunk(btns, 3));
}

function sourceKeyboard() {
  return keyboard([
    [{ text: "🇨🇭 AutoScout24 (CH)", data: "src:a" }],
    [{ text: "🇩🇪 kleinanzeigen.de (DE, nur Tuning)", data: "src:k" }],
  ]);
}

function searchLabel(s) {
  const flag = s.source === "kleinanzeigen" ? "🇩🇪 " : "🇨🇭 ";
  let label = flag + s.makeName;
  if (s.modelName) label += " " + s.modelName;
  else if (s.modelGroupKey) label += " " + (s.groupName || "");
  else if (!s.source || s.source === "autoscout24") label += " (alle Modelle)";
  if (s.keyword) label += " „" + s.keyword + "”";
  const tags = [];
  if (s.bodyKey && BODY_NAME[s.bodyKey]) tags.push(BODY_NAME[s.bodyKey]);
  if (s.fuelChoice && FUEL_NAME[s.fuelChoice]) tags.push(FUEL_NAME[s.fuelChoice]);
  if (s.minHp) tags.push("≥" + s.minHp + " PS");
  if (s.minYear) tags.push("ab " + s.minYear);
  if (s.maxPrice) {
    const unit = s.source === "kleinanzeigen" ? "k €" : "k";
    tags.push("≤ " + Math.round(s.maxPrice / 1000) + unit);
  }
  if (tags.length) label += " · " + tags.join(" · ");
  return label;
}

// Modelle in Baureihen-Gruppen + ungruppierte aufteilen.
function modelGroups(models) {
  const groups = new Map(); // key -> { key, name, models:[] }
  const ungrouped = [];
  for (const m of models) {
    const g = m.group;
    if (g && g.key) {
      if (!groups.has(g.key)) groups.set(g.key, { key: g.key, name: g.name, models: [] });
      groups.get(g.key).models.push(m);
    } else {
      ungrouped.push(m);
    }
  }
  return { groups, ungrouped };
}

// Modell-/Baureihen-Menü (Buttons). Mit msgId wird die Nachricht editiert, sonst neu gesendet.
async function showModelMenu(env, tgApi, chatId, makeKey, makeName, msgId) {
  let models = [];
  try { models = await fetchModels(makeKey); } catch (e) {}
  const { groups, ungrouped } = modelGroups(models);
  const rows = [];
  if (groups.size) {
    const btns = [...groups.values()].map((g) => ({ text: groupLabel(g.key, g.name), data: "g:" + g.key }));
    for (const r of chunk(btns, 3)) rows.push(r);
    if (ungrouped.length) rows.push([{ text: "➕ Weitere Modelle", data: "g:_none" }]);
  } else {
    const btns = models.slice(0, 30).map((m) => ({ text: m.name, data: "m:" + m.key }));
    for (const r of chunk(btns, 3)) rows.push(r);
  }
  rows.push([{ text: "🚙 Ganze Marke", data: "gall" }, { text: "✏️ Tippen", data: "gtype" }]);
  const text = "Marke: *" + makeName + "*\nWähle *Baureihe* oder *Modell* (wie auf AutoScout):";
  return msgId
    ? tgApi.editMessageText(chatId, msgId, text, keyboard(rows))
    : tgApi.sendMessage(chatId, text, keyboard(rows));
}

// Untermenü einer Baureihe: ganze Reihe oder ein einzelnes Modell.
async function showGroupModelMenu(env, tgApi, chatId, msgId, groupKey) {
  const pending = await getPending(env, chatId);
  if (!pending) return;
  let models = [];
  try { models = await fetchModels(pending.makeKey); } catch (e) {}
  const { groups, ungrouped } = modelGroups(models);
  const rows = [];
  let headLabel, list;
  if (groupKey === "_none") {
    headLabel = "Weitere Modelle";
    list = ungrouped;
  } else {
    const g = groups.get(groupKey);
    headLabel = groupLabel(groupKey, g ? g.name : groupKey);
    list = g ? g.models : [];
    rows.push([{ text: "✅ Ganze " + headLabel, data: "gw:" + groupKey }]);
  }
  const btns = list.map((m) => ({ text: m.name, data: "m:" + m.key }));
  for (const r of chunk(btns, 3)) rows.push(r);
  rows.push([{ text: "« Zurück", data: "gback" }, { text: "✏️ Tippen", data: "gtype" }]);
  const text = "*" + headLabel + "*\nGanze Reihe – oder ein bestimmtes Modell?";
  return tgApi.editMessageText(chatId, msgId, text, keyboard(rows));
}

// Modell-Auswahl übernehmen und nach dem Treibstoff fragen.
async function askFuel(env, tgApi, chatId, msgId, draft) {
  const pending = (await getPending(env, chatId)) || {};
  await setPending(env, chatId, {
    ...pending,
    modelKey: draft.modelKey || null, modelName: draft.modelName || null,
    modelGroupKey: draft.modelGroupKey || null, groupName: draft.groupName || null,
    step: "awaitFuel",
  });
  const name = draft.modelName || draft.groupName || "alle Modelle";
  const text = "Auswahl: *" + name + "*\nTreibstoff?";
  return msgId
    ? tgApi.editMessageText(chatId, msgId, text, fuelKeyboard())
    : tgApi.sendMessage(chatId, text, fuelKeyboard());
}

function norm(s) {
  return (s || "").toLowerCase().replace(/[\s\-]/g, "");
}

// Friendly name for a model group: "3-series" -> "3er", "m-series" -> "M-Reihe".
function groupLabel(key, name) {
  const m = key.match(/^(\d)-series$/);
  if (m) return m[1] + "er";
  if (key === "m-series") return "M-Reihe";
  if (key === "x-series") return "X-Reihe";
  if (key === "z-series") return "Z-Reihe";
  return name || key;
}

// Match typed text against a make's models OR a whole series (group).
// Returns { all } | { group:{key,name} } | { model:{key,name} } | null.
function matchModel(models, text) {
  const raw = (text || "").trim().toLowerCase();
  if (["-", "", "alle", "alles", "all", "egal", "*", "keins", "keine"].includes(raw)) {
    return { all: true };
  }
  const groups = {};
  for (const x of models) { const g = x.group; if (g && g.key) groups[g.key] = { key: g.key, name: g.name }; }
  const compact = raw.replace(/[\s\-.]/g, "");           // "3er", "3erreihe"
  const dm = compact.match(/^([1-8])er/);                 // 1er … 8er
  if (dm && groups[dm[1] + "-series"]) return { group: groups[dm[1] + "-series"] };
  if (groups[raw]) return { group: groups[raw] };          // exakt "3-series"
  if (["m", "mreihe"].includes(compact) && groups["m-series"]) return { group: groups["m-series"] };
  if (["x", "xreihe"].includes(compact) && groups["x-series"]) return { group: groups["x-series"] };
  if (["z", "zreihe"].includes(compact) && groups["z-series"]) return { group: groups["z-series"] };
  const t = norm(text);
  let m = models.find((x) => norm(x.key) === t || norm(x.name) === t);
  if (!m) m = models.find((x) => norm(x.key).startsWith(t) || norm(x.name).startsWith(t));
  if (!m) m = models.find((x) => norm(x.name).includes(t) || norm(x.key).includes(t));
  return m ? { model: m } : null;
}

export const COMMANDS = [
  { command: "addcar", description: "Neue Auto-Suche (CH oder DE, alles per Buttons)" },
  { command: "kleinanzeigen", description: "🇩🇪 Neue kleinanzeigen.de-Suche (nur Tuning)" },
  { command: "mobile", description: "🇩🇪 Heisse mobile.de-Inserate ansehen" },
  { command: "scrape", description: "🤖 DE-Scraper sofort manuell laufen lassen (~2 Min)" },
  { command: "deletecar", description: "Eine Auto-Suche löschen" },
  { command: "list", description: "Aktive Suchen anzeigen" },
  { command: "deals", description: "Beste Treffer aller CH-Suchen" },
  { command: "favoriten", description: "⭐ Gemerkte Autos anzeigen" },
  { command: "zeig", description: "Suche auswählen & beste zeigen (oder /zeig BMW 335)" },
  { command: "ricardo", description: "Neueste ricardo-Treffer zeigen" },
  { command: "block", description: "Stichwort sperren (z. B. Motorschaden)" },
  { command: "blocklist", description: "Gesperrte Stichwörter verwalten" },
  { command: "clear", description: "Chat aufräumen (leeren)" },
  { command: "help", description: "Hilfe" },
];

// GitHub-Repo, in dem der Browser-Scraper-Workflow liegt.
const GH_OWNER = "Giankp007";
const GH_REPO = "BmwFinder";
const GH_WORKFLOW = "browser-scan.yml";
// Cooldown zwischen manuellen /scrape-Triggern (GitHub limitiert sonst eh).
const SCRAPE_COOLDOWN_MS = 90_000;

async function triggerScrape(env, tgApi, chatId) {
  const token = env.GITHUB_TOKEN;
  if (!token) {
    return tgApi.sendMessage(chatId,
      "🤖 *Scraper-Trigger ist noch nicht konfiguriert.*\n\n" +
      "Einmaliger Setup (lokal):\n" +
      "1. github.com/settings/tokens → *Generate new token (classic)* → " +
      "Scope `repo` (oder fine-grained mit *Actions: Write* auf `BmwFinder`).\n" +
      "2. `cd cf-worker && wrangler secret put GITHUB_TOKEN` → Token einfügen.\n" +
      "3. `npm run deploy`.\n\n" +
      "Danach läuft /scrape.");
  }
  const lastKey = "scrape:last";
  const last = parseInt((await env.BMW_KV.get(lastKey)) || "0", 10);
  const now = Date.now();
  if (now - last < SCRAPE_COOLDOWN_MS) {
    const wait = Math.ceil((SCRAPE_COOLDOWN_MS - (now - last)) / 1000);
    return tgApi.sendMessage(chatId,
      `⏳ Der letzte manuelle Lauf ist erst ${Math.round((now - last) / 1000)} Sek her — ` +
      `noch ${wait} Sek warten. (Cooldown gegen versehentliches Spammen.)`);
  }
  const url = `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/dispatches`;
  let r;
  try {
    r = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bmw-deal-scanner-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    });
  } catch (e) {
    return tgApi.sendMessage(chatId,
      "❌ Netzwerkfehler beim Trigger: " + String(e).slice(0, 200));
  }
  if (r.status !== 204) {
    const txt = await r.text().catch(() => "");
    const hint = r.status === 401
      ? "\n→ Token ungültig/abgelaufen? Neuen PAT erstellen und `wrangler secret put GITHUB_TOKEN`."
      : r.status === 404
        ? "\n→ Repo/Workflow nicht gefunden — Token hat keinen Zugriff auf BmwFinder?"
        : "";
    return tgApi.sendMessage(chatId,
      `❌ GitHub gab \`${r.status}\` zurück.${hint}\n${txt.slice(0, 200)}`);
  }
  await env.BMW_KV.put(lastKey, String(now));
  const actionsUrl = `https://github.com/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}`;
  return tgApi.sendMessage(chatId,
    "🤖 *Scraper läuft jetzt manuell.*\n\n" +
    "In ~2-3 Min hast Du die neuen Treffer im Chat (falls welche dazugekommen sind).\n" +
    "Bei einer frischen kleinanzeigen-Suche siehst Du gleich nach dem Lauf alles via /zeig.\n\n" +
    `[Live-Log auf GitHub](${actionsUrl})`);
}

const HELP =
  "🚗 *BMW Deal Scanner*\n\n" +
  "Ich überwache den Markt und melde neue Treffer automatisch.\n" +
  "🇨🇭 *AutoScout24* (CH) — alle Suchen, alle 30 Min Alerts.\n" +
  "🇩🇪 *kleinanzeigen.de* (DE) — nur Inserate mit Tuning, alle 30 Min Alerts.\n" +
  "🇩🇪 *mobile.de* (DE) — kuratierter Tuning-Pool, nur per /mobile sichtbar.\n\n" +
  "*Befehle:*\n" +
  "/addcar – neue Suche anlegen (Quelle → Marke → Modell → … alles per Buttons)\n" +
  "/kleinanzeigen – Shortcut für 🇩🇪 kleinanzeigen.de-Suche anlegen\n" +
  "/mobile – 🇩🇪 mobile.de-Inserate ansehen (kein Auto-Alarm)\n" +
  "/scrape – DE-Scraper sofort manuell laufen lassen (~2 Min)\n" +
  "/deletecar – eine Suche löschen\n" +
  "/list – aktive Suchen (CH + DE)\n" +
  "/deals – beste 🇨🇭 Treffer aller aktiven CH-Suchen\n" +
  "/favoriten – ⭐ deine gemerkten Autos\n" +
  "/zeig – Suche auswählen & Treffer zeigen (oder `/zeig BMW 335`)\n" +
  "/ricardo – neueste ricardo-Treffer\n" +
  "/block <wort> – Stichwort sperren (gilt für alle Quellen)\n" +
  "/blocklist – gesperrte Stichwörter ansehen/entfernen\n" +
  "/clear – Chat aufräumen\n\n" +
  "🔧 Auf 🇩🇪-Inseraten zeigt der Bot nur Autos mit Tuning-Hinweisen " +
  "(Stage 2, Eisenmann, KW, Kompressor, Akrapovic, etc.).";

// ---------------- message (text / command) handling ----------------
export async function handleMessage(env, tgApi, msg) {
  const chatId = msg.chat.id;
  const text = (msg.text || "").trim();

  if (text.startsWith("/start") || text.startsWith("/help")) {
    return tgApi.sendMessage(chatId, HELP);
  }
  if (text.startsWith("/addcar")) {
    await clearPending(env, chatId);
    await setPending(env, chatId, { step: "awaitSource" });
    return tgApi.sendMessage(chatId,
      "🚗 *Neue Suche* — *Quelle* wählen:\n" +
      "🇨🇭 *AutoScout24* — alle Inserate, 30-Min-Alarme.\n" +
      "🇩🇪 *kleinanzeigen.de* — nur Tuning, 30-Min-Alarme.",
      sourceKeyboard());
  }
  if (text.startsWith("/kleinanzeigen") || text.startsWith("/kleinanzeige")) {
    await clearPending(env, chatId);
    await setPending(env, chatId, { step: "awaitBrand", source: "kleinanzeigen" });
    return tgApi.sendMessage(chatId,
      "🇩🇪 *Neue kleinanzeigen.de-Suche* (nur Tuning) — Marke?", brandKeyboard());
  }
  if (text.startsWith("/mobile")) {
    return sendMobile(env, tgApi, chatId);
  }
  if (text.startsWith("/scrape")) {
    return triggerScrape(env, tgApi, chatId);
  }
  if (text.startsWith("/list")) {
    return sendList(env, tgApi, chatId);
  }
  if (text.startsWith("/deletecar") || text.startsWith("/removecar")) {
    return sendDeleteMenu(env, tgApi, chatId);
  }
  if (text.startsWith("/deals")) {
    return sendDeals(env, tgApi, chatId);
  }
  if (text.startsWith("/zeig")) {
    const arg = text.replace(/^\/zeig(@\S+)?\s*/, "").trim();
    return arg ? sendZeig(env, tgApi, chatId, arg) : sendZeigMenu(env, tgApi, chatId);
  }
  if (text.startsWith("/ricardo")) {
    return sendRicardo(env, tgApi, chatId);
  }
  if (text.startsWith("/block")) {
    const word = text.replace(/^\/block(@\S+)?\s*/, "").trim();
    if (!word) {
      await setPending(env, chatId, { step: "awaitBlock" });
      return tgApi.sendMessage(chatId,
        "Welches Stichwort sperren? Tippe es (z. B. `Motorschaden`, `Motor macht Geräusche`):");
    }
    const all = await addBlockword(env, word);
    return tgApi.sendMessage(chatId,
      "🚫 Gesperrt: *" + word + "*\nInserate mit diesem Wort im Titel werden ab sofort ausgeblendet.\n\n" +
      "Gesperrt (" + all.length + "): " + all.join(", "));
  }
  if (text.startsWith("/blocklist")) {
    return sendBlocklist(env, tgApi, chatId);
  }
  // /favoriten, /favorites, /favs, /fav (Gross-/Kleinschreibung egal)
  if (/^\/fav(s|oriten|orites)?(@\S+)?(\s|$)/i.test(text)) {
    return sendFavorites(env, tgApi, chatId);
  }
  if (text.toLowerCase().startsWith("/clear")) {
    return clearChat(env, tgApi, chatId, msg.message_id);
  }

  // Not a command: maybe we're awaiting a typed brand or model
  const pending = await getPending(env, chatId);
  if (!pending) {
    // "mehr / noch ein paar mehr / weiter" → nächste /zeig-Seite
    if (/\b(mehr|weiter|noch|more|next|paar)\b/i.test(text)) {
      const ctx = await getZeigCtx(env, chatId);
      if (ctx && ctx.search) return showZeigPage(env, tgApi, chatId, ctx.search, ctx.next || 0);
    }
    return tgApi.sendMessage(chatId, "Tippe /zeig oder /addcar, oder /help.");
  }

  if (pending.step === "awaitBlock") {
    const all = await addBlockword(env, text);
    await clearPending(env, chatId);
    return tgApi.sendMessage(chatId,
      "🚫 Gesperrt: *" + text + "*\nWird ab sofort ausgeblendet.\n\nGesperrt (" + all.length + "): " + all.join(", "));
  }

  if (pending.step === "awaitBrand") {
    const { fetchMakes } = await import("./autoscout24.js");
    const makes = await fetchMakes();
    const t = norm(text);
    let mk = makes.find((m) => norm(m.name) === t || norm(m.key) === t) ||
             makes.find((m) => norm(m.name).startsWith(t) || norm(m.key).startsWith(t)) ||
             makes.find((m) => norm(m.name).includes(t));
    if (!mk) return tgApi.sendMessage(chatId, "Marke nicht gefunden. Versuch's nochmal (z. B. Subaru).");
    await setPending(env, chatId, { step: "awaitModel", makeKey: mk.key, makeName: mk.name });
    return showModelMenu(env, tgApi, chatId, mk.key, mk.name);
  }

  if (pending.step === "awaitModel") {
    let models = [];
    try { models = await fetchModels(pending.makeKey); } catch (e) {}
    const res = matchModel(models, text);
    if (!res) {
      await tgApi.sendMessage(chatId, "Modell nicht erkannt – nimm einfach die Buttons:");
      return showModelMenu(env, tgApi, chatId, pending.makeKey, pending.makeName);
    }
    const draft = {};
    if (res.model) { draft.modelKey = res.model.key; draft.modelName = res.model.name; }
    else if (res.group) { draft.modelGroupKey = res.group.key; draft.groupName = groupLabel(res.group.key, res.group.name); }
    return askFuel(env, tgApi, chatId, null, draft);
  }

  // --- kleinanzeigen-Flow: freitext-Modell ---
  if (pending.step === "kAwaitModel") {
    const t = text.trim();
    const isAll = !t || ["-", "alle", "alles", "all", "egal", "*"].includes(t.toLowerCase());
    await setPending(env, chatId, {
      ...pending, modelName: isAll ? null : t.slice(0, 40), step: "kAwaitKeyword",
    });
    return tgApi.sendMessage(chatId,
      "Stichwort? (frei eingeben — z.B. `e92`, `Stage 2`, `Eisenmann`)\n" +
      "Oder tippe `-` für *kein* Stichwort:");
  }

  // --- kleinanzeigen-Flow: freitext-Stichwort ---
  if (pending.step === "kAwaitKeyword") {
    const t = text.trim();
    const skip = !t || ["-", "egal", "nein", "no", "skip"].includes(t.toLowerCase());
    await setPending(env, chatId, {
      ...pending, keyword: skip ? null : t.slice(0, 40), step: "awaitFuel",
    });
    const name = pending.modelName || "alle Modelle";
    return tgApi.sendMessage(chatId,
      "Auswahl: 🇩🇪 *" + name + "*" + (skip ? "" : " · „" + t + "”") + "\nTreibstoff?",
      fuelKeyboard());
  }

  return tgApi.sendMessage(chatId, "Tippe /addcar oder /help.");
}

// ---------------- callback (button) handling ----------------
export async function handleCallback(env, tgApi, cq) {
  const chatId = cq.message.chat.id;
  const msgId = cq.message.message_id;
  const data = cq.data || "";

  // Quelle gewählt → in den passenden Marken-Schritt
  if (data === "src:a" || data === "src:k") {
    const source = data === "src:k" ? "kleinanzeigen" : "autoscout24";
    const flag = source === "kleinanzeigen" ? "🇩🇪 " : "🇨🇭 ";
    const name = source === "kleinanzeigen" ? "kleinanzeigen.de (nur Tuning)" : "AutoScout24";
    await setPending(env, chatId, { step: "awaitBrand", source });
    await tgApi.answerCallbackQuery(cq.id);
    return tgApi.editMessageText(chatId, msgId,
      flag + "*" + name + "* — wähle die Marke:", brandKeyboard());
  }

  if (data.startsWith("b:")) {
    const makeKey = data.slice(2);
    const found = POPULAR_BRANDS.find(([, k]) => k === makeKey);
    const makeName = found ? found[0] : makeKey.toUpperCase();
    const pending = (await getPending(env, chatId)) || {};
    const source = pending.source || "autoscout24";
    await tgApi.answerCallbackQuery(cq.id);
    if (source === "kleinanzeigen") {
      await setPending(env, chatId, {
        ...pending, step: "kAwaitModel", makeKey, makeName,
      });
      return tgApi.editMessageText(chatId, msgId,
        "Marke: 🇩🇪 *" + makeName + "*\n" +
        "Welches *Modell*? (tippen, z.B. `M3`, `335`, `Golf R`)\n" +
        "Oder tippe `-` für *die ganze Marke*:");
    }
    await setPending(env, chatId, { ...pending, step: "awaitModel", makeKey, makeName });
    return showModelMenu(env, tgApi, chatId, makeKey, makeName, msgId);
  }

  if (data === "bx") {
    const pending = (await getPending(env, chatId)) || {};
    await setPending(env, chatId, { ...pending, step: "awaitBrand" });
    await tgApi.answerCallbackQuery(cq.id);
    return tgApi.editMessageText(chatId, msgId, "Tippe die *Marke* (z. B. `Subaru`, `Jaguar`):");
  }

  // --- Modell-/Baureihen-Auswahl per Buttons ---
  if (data === "gall") {
    await tgApi.answerCallbackQuery(cq.id);
    return askFuel(env, tgApi, chatId, msgId, {});
  }

  if (data === "gtype") {
    const pending = await getPending(env, chatId);
    await setPending(env, chatId, { ...pending, step: "awaitModel" });
    await tgApi.answerCallbackQuery(cq.id);
    return tgApi.editMessageText(chatId, msgId,
      "Tippe *Modell* (`335`, `M3`), *Baureihe* (`3er`, `5er`) – oder `-` für die ganze Marke:");
  }

  if (data === "gback") {
    const pending = await getPending(env, chatId);
    await tgApi.answerCallbackQuery(cq.id);
    if (!pending) return;
    return showModelMenu(env, tgApi, chatId, pending.makeKey, pending.makeName, msgId);
  }

  if (data.startsWith("gw:")) {
    const groupKey = data.slice(3);
    const pending = await getPending(env, chatId);
    if (!pending) { await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu."); return; }
    let gname = groupKey;
    try {
      const models = await fetchModels(pending.makeKey);
      const g = models.find((x) => x.group && x.group.key === groupKey);
      if (g) gname = g.group.name;
    } catch (e) {}
    await tgApi.answerCallbackQuery(cq.id);
    return askFuel(env, tgApi, chatId, msgId, {
      modelGroupKey: groupKey, groupName: groupLabel(groupKey, gname),
    });
  }

  if (data.startsWith("g:")) {
    const groupKey = data.slice(2);
    await tgApi.answerCallbackQuery(cq.id);
    return showGroupModelMenu(env, tgApi, chatId, msgId, groupKey);
  }

  if (data.startsWith("m:")) {
    const modelKey = data.slice(2);
    const pending = await getPending(env, chatId);
    if (!pending) { await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu."); return; }
    let name = modelKey;
    try {
      const models = await fetchModels(pending.makeKey);
      const f = models.find((x) => x.key === modelKey);
      if (f) name = f.name;
    } catch (e) {}
    await tgApi.answerCallbackQuery(cq.id);
    return askFuel(env, tgApi, chatId, msgId, { modelKey, modelName: name });
  }

  if (data.startsWith("f:")) {
    const fk = data.slice(2);
    const pending = await getPending(env, chatId);
    if (!pending || pending.step !== "awaitFuel") {
      await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu starten.");
      return;
    }
    await setPending(env, chatId, {
      ...pending, step: "awaitPrice",
      fuelTypes: FUEL_KEYS[fk] || [], fuelChoice: fk === "egal" ? null : fk,
    });
    await tgApi.answerCallbackQuery(cq.id);
    const isKlein = pending.source === "kleinanzeigen";
    return tgApi.editMessageText(chatId, msgId,
      isKlein ? "Max. Preis (EUR)?" : "Max. Preis (CHF)?",
      isKlein ? priceEurKeyboard() : priceKeyboard());
  }

  if (data.startsWith("p:")) {
    const v = parseInt(data.slice(2), 10) || 0;
    const pending = await getPending(env, chatId);
    if (!pending || pending.step !== "awaitPrice") {
      await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu starten.");
      return;
    }
    await tgApi.answerCallbackQuery(cq.id);
    if (pending.source === "kleinanzeigen") {
      await setPending(env, chatId, { ...pending, step: "kAwaitYear", maxPrice: v || null });
      return tgApi.editMessageText(chatId, msgId, "Erstzulassung *ab*?", yearKeyboard());
    }
    await setPending(env, chatId, { ...pending, step: "awaitHp", maxPrice: v || null });
    return tgApi.editMessageText(chatId, msgId, "Mindest-Leistung?", hpKeyboard());
  }

  if (data.startsWith("ky:")) {
    const v = parseInt(data.slice(3), 10) || 0;
    const pending = await getPending(env, chatId);
    if (!pending || pending.step !== "kAwaitYear") {
      await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /kleinanzeigen neu starten.");
      return;
    }
    await setPending(env, chatId, { ...pending, step: "awaitHp", minYear: v || null });
    await tgApi.answerCallbackQuery(cq.id);
    return tgApi.editMessageText(chatId, msgId, "Mindest-Leistung?", hpKeyboard());
  }

  if (data.startsWith("h:")) {
    const minHp = parseInt(data.slice(2), 10) || 0;
    const pending = await getPending(env, chatId);
    if (!pending || pending.step !== "awaitHp") {
      await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu starten.");
      return;
    }
    await setPending(env, chatId, { ...pending, step: "awaitBody", minHp: minHp || null });
    await tgApi.answerCallbackQuery(cq.id);
    return tgApi.editMessageText(chatId, msgId, "Karosserie?", bodyKeyboard());
  }

  if (data.startsWith("cb:")) {
    const bodyKey = data.slice(3);
    const pending = await getPending(env, chatId);
    if (!pending || pending.step !== "awaitBody") {
      await tgApi.answerCallbackQuery(cq.id, "Abgelaufen – /addcar neu starten.");
      return;
    }
    const source = pending.source || "autoscout24";
    const search = {
      id: genId(),
      source,
      makeKey: pending.makeKey, makeName: pending.makeName,
      modelKey: pending.modelKey || null, modelName: pending.modelName || null,
      modelGroupKey: pending.modelGroupKey || null, groupName: pending.groupName || null,
      keyword: pending.keyword || null,
      minHp: pending.minHp || null,
      minYear: pending.minYear || null,
      bodyKey: bodyKey || null,
      bodyTypes: bodyKey ? [bodyKey] : [],
      fuelTypes: pending.fuelTypes || [],
      fuelChoice: pending.fuelChoice || null,
      maxPrice: pending.maxPrice != null ? pending.maxPrice : null,
    };
    search.label = searchLabel(search);
    await addSearch(env, search);
    await clearPending(env, chatId);
    const cur = source === "kleinanzeigen" ? "€" : "CHF";
    const priceTxt = search.maxPrice
      ? "bis " + search.maxPrice.toLocaleString("de-CH").replace(/,/g, "'") + " " + cur
      : "ohne Preislimit";
    await tgApi.answerCallbackQuery(cq.id, "Gespeichert!");
    const note = source === "kleinanzeigen"
      ? "🇩🇪 *Tuning-Filter* aktiv — du bekommst nur Inserate mit Tuning-Hinweisen " +
        "(Stage, Eisenmann, KW, Kompressor, etc.).\n" +
        "Erste Treffer kommen mit dem nächsten Scraper-Lauf (max. 30 Min)."
      : "Ich merke mir den aktuellen Bestand und melde ab jetzt *neue* Treffer automatisch. " +
        "Mit /zeig oder /deals siehst du sofort, was gerade online ist.";
    await tgApi.editMessageText(chatId, msgId,
      "✅ Suche aktiv:\n*" + search.label + "*\nBudget: " + priceTxt + ".\n\n" + note);
    await seedSearch(env, search);   // AS24: still seeden (no-op für kleinanzeigen)
    return;
  }

  if (data.startsWith("zg:")) {
    const id = data.slice(3);
    const searches = await getSearches(env);
    const s = searches.find((x) => x.id === id);
    await tgApi.answerCallbackQuery(cq.id, s ? "Hole Treffer…" : "Suche weg?");
    if (!s) return;
    return showZeigPage(env, tgApi, chatId, s, 0);
  }

  if (data === "zmore") {
    await tgApi.answerCallbackQuery(cq.id, "Mehr…");
    const ctx = await getZeigCtx(env, chatId);
    if (!ctx || !ctx.search) return tgApi.sendMessage(chatId, "Starte zuerst /zeig.");
    return showZeigPage(env, tgApi, chatId, ctx.search, ctx.next || 0);
  }

  if (data.startsWith("ub:")) {
    const word = data.slice(3);
    const kept = await removeBlockword(env, word);
    await tgApi.answerCallbackQuery(cq.id, "Entsperrt.");
    if (!kept.length) {
      return tgApi.editMessageText(chatId, msgId, "✅ Entsperrt. Keine gesperrten Stichwörter mehr.");
    }
    const rows = kept.map((w) => [{ text: "❌ " + w, data: "ub:" + w }]);
    return tgApi.editMessageText(chatId, msgId, "🚫 Gesperrte Stichwörter (tippen zum Entsperren):", keyboard(rows));
  }

  // ⭐ Merken-Button auf einer Inserat-Karte (toggle: merken / wieder entfernen).
  if (data.startsWith("fav:")) {
    const uid = data.slice(4);
    if (await isFavorite(env, uid)) {
      await removeFavorite(env, uid);
      await tgApi.answerCallbackQuery(cq.id, "Aus Favoriten entfernt");
      return tgApi.editMessageReplyMarkup(chatId, msgId,
        keyboard([[{ text: "⭐ Merken", data: "fav:" + uid }]]));
    }
    const l = await getCachedListing(env, uid);
    if (!l) {
      await tgApi.answerCallbackQuery(cq.id, "Inserat abgelaufen — mit /deals neu laden.");
      return;
    }
    await addFavorite(env, l);
    await tgApi.answerCallbackQuery(cq.id, "⭐ Gemerkt!");
    return tgApi.editMessageReplyMarkup(chatId, msgId,
      keyboard([[{ text: "✅ Gemerkt (entfernen)", data: "fav:" + uid }]]));
  }

  // ❌ Entfernen-Button in der /favoriten-Liste.
  if (data.startsWith("uf:")) {
    const uid = data.slice(3);
    await removeFavorite(env, uid);
    await tgApi.answerCallbackQuery(cq.id, "Entfernt");
    return tgApi.deleteMessage(chatId, msgId);
  }

  if (data.startsWith("d:")) {
    const id = data.slice(2);
    const kept = await removeSearch(env, id);
    await tgApi.answerCallbackQuery(cq.id, "Gelöscht.");
    if (!kept.length) {
      return tgApi.editMessageText(chatId, msgId, "🗑 Gelöscht. Keine aktiven Suchen mehr. /addcar für eine neue.");
    }
    const rows = kept.map((s) => [{ text: "🗑 " + s.label, data: "d:" + s.id }]);
    return tgApi.editMessageText(chatId, msgId, "🗑 Gelöscht. Aktive Suchen (tippen zum Löschen):", keyboard(rows));
  }

  await tgApi.answerCallbackQuery(cq.id);
}

// ---------------- helpers ----------------
// CH-zuerst-Sortierung: AS24 oben, kleinanzeigen unten.
function orderedSearches(searches) {
  const ch = searches.filter((s) => !s.source || s.source === "autoscout24");
  const de = searches.filter((s) => s.source === "kleinanzeigen");
  return [...ch, ...de];
}

async function sendList(env, tgApi, chatId) {
  const searches = orderedSearches(await getSearches(env));
  if (!searches.length) return tgApi.sendMessage(chatId, "Keine aktiven Suchen. /addcar legt eine an.");
  const lines = searches.map((s, i) => (i + 1) + ". *" + searchLabel(s) + "*");
  return tgApi.sendMessage(chatId, "🔎 *Aktive Suchen:*\n" + lines.join("\n"));
}

async function sendDeleteMenu(env, tgApi, chatId) {
  const searches = orderedSearches(await getSearches(env));
  if (!searches.length) return tgApi.sendMessage(chatId, "Keine aktiven Suchen zum Löschen.");
  const rows = searches.map((s) => [{ text: "🗑 " + searchLabel(s), data: "d:" + s.id }]);
  return tgApi.sendMessage(chatId, "Welche Suche löschen? (tippen)", keyboard(rows));
}

async function sendBlocklist(env, tgApi, chatId) {
  const words = await getBlockwords(env);
  if (!words.length) {
    return tgApi.sendMessage(chatId,
      "Keine gesperrten Stichwörter. Mit `/block Motorschaden` sperrst du eins.");
  }
  const rows = words.map((w) => [{ text: "❌ " + w, data: "ub:" + w }]);
  return tgApi.sendMessage(chatId, "🚫 Gesperrte Stichwörter (tippen zum Entsperren):", keyboard(rows));
}

// /favoriten: Banner + jede gemerkte Karte mit „entfernen"-Button.
async function sendFavorites(env, tgApi, chatId) {
  const favs = await getFavorites(env);
  if (!favs.length) {
    return tgApi.sendMessage(chatId,
      "⭐ *Deine Favoriten*\n\nNoch leer. Tippe bei einem Inserat (aus /deals, /zeig oder einem " +
      "Alarm) auf *⭐ Merken* — dann landet es hier.");
  }
  await tgApi.sendMessage(chatId,
    "⭐ *Deine Favoriten* (" + favs.length + ")\n" +
    "Tippe „❌ Aus Favoriten entfernen“, um eins rauszunehmen.");
  let budget = 40; // Worker-Subrequest-Schutz, jede Karte ~2
  for (const f of favs) {
    if (budget < 2) {
      await tgApi.sendMessage(chatId, "(Rest mit /favoriten erneut abrufen.)");
      break;
    }
    budget -= 2;
    await sendFavoriteCard(tgApi, chatId, f);
  }
}

// /clear: räumt den Chat auf, indem es Nachrichten löscht.
// Telegram hat keine „Chat leeren"-API und ein Bot kann Nachrichten, die ÄLTER
// als 48 h sind, GAR NICHT löschen (harte Telegram-Regel). Ausserdem sind pro
// Aufruf nur ~50 Lösch-Subrequests erlaubt. Wir merken uns darum in KV, wie weit
// runter wir schon geräumt haben (clearfloor), und arbeiten uns bei jedem /clear
// um einen weiteren Block nach unten — bis nichts Löschbares mehr übrig ist.
async function clearChat(env, tgApi, chatId, upToMsgId) {
  const MAX = 45; // unter dem Worker-Subrequest-Limit (50) bleiben
  const key = "clearfloor:" + chatId;
  const floor = parseInt((await env.BMW_KV.get(key)) || "0", 10);
  const ids = [];
  // 1) Nachrichten, die seit dem letzten /clear oben dazugekommen sind.
  if (floor && floor < upToMsgId) {
    for (let id = upToMsgId; id > floor && ids.length < MAX; id--) ids.push(id);
  } else {
    ids.push(upToMsgId); // erster Lauf: zumindest das /clear selbst
  }
  // 2) weiter nach unten in die History, bis das Budget voll ist.
  let lowest = floor && floor < upToMsgId ? floor : upToMsgId;
  for (let id = lowest - 1; id > 0 && ids.length < MAX; id--) { ids.push(id); lowest = id; }

  const res = await Promise.all(
    ids.map((id) => tgApi.deleteMessage(chatId, id).then((r) => r && r.ok).catch(() => false))
  );
  const deleted = res.filter(Boolean).length;
  await env.BMW_KV.put(key, String(lowest), { expirationTtl: 7 * 24 * 3600 });
  await clearPending(env, chatId); // halb fertiges /addcar nicht hängen lassen

  // Nichts mehr löschbar → wir sind am Ende des 48-h-Fensters angelangt.
  if (deleted === 0) {
    return tgApi.sendMessage(chatId,
      "✨ Hier ist alles weg, was ich löschen darf.\n\n" +
      "⚠️ Ältere Nachrichten (älter als 48 h) kann *kein* Bot löschen — das sperrt Telegram. " +
      "Für einen *komplett* leeren Chat: oben auf den Bot-Namen tippen → *Verlauf löschen*. " +
      "Das wischt alles auf einen Schlag.");
  }
  return tgApi.sendMessage(chatId,
    "🧹 " + deleted + " Nachrichten gelöscht. Tippe nochmal /clear, um weiter aufzuräumen.\n\n" +
    "Tipp: Ältere als 48 h kann ich nicht löschen — für ganz leer: Bot-Name oben → *Verlauf löschen*.");
}

// Eine /zeig-Seite zeigen (ab startIndex), Kontext speichern, "mehr" anbieten.
async function showZeigPage(env, tgApi, chatId, search, startIndex) {
  const r = await sendListingsPage(env, tgApi, chatId, search, startIndex, PAGE, { left: 30 });
  if (r.total === 0) {
    await tgApi.sendMessage(chatId, "Gerade keine (passenden) Treffer.");
    return;
  }
  await setZeigCtx(env, chatId, { search, next: r.next, total: r.total });
  if (r.next < r.total) {
    await tgApi.sendMessage(chatId,
      `Noch ${r.total - r.next} weitere. Schreib „mehr" – oder tippe:`,
      keyboard([[{ text: "➕ Mehr anzeigen", data: "zmore" }]]));
  } else if (startIndex > 0 || r.shown > 0) {
    await tgApi.sendMessage(chatId, `Das waren alle ${r.total} Treffer dieser Suche.`);
  }
}

// /zeig <Marke> [Modell] — einmalige Suche, zeigt nur das explizit Gefragte.
async function sendZeig(env, tgApi, chatId, arg) {
  if (!arg) {
    return tgApi.sendMessage(chatId,
      "So geht's: `/zeig BMW 335` · `/zeig BMW 3er` · `/zeig Audi A4` · `/zeig Porsche`\n(Marke + optional Modell oder Baureihe.)");
  }
  const parts = arg.split(/\s+/);
  const brandQ = parts[0];
  const modelQ = parts.slice(1).join(" ");
  const makes = await fetchMakes().catch(() => []);
  const nb = norm(brandQ);
  const mk =
    makes.find((m) => norm(m.name) === nb || norm(m.key) === nb) ||
    makes.find((m) => norm(m.name).startsWith(nb) || norm(m.key).startsWith(nb)) ||
    makes.find((m) => norm(m.name).includes(nb));
  if (!mk) return tgApi.sendMessage(chatId, "Marke nicht gefunden: *" + brandQ + "*");

  const search = { makeKey: mk.key, makeName: mk.name, maxPrice: DEFAULT_MAX_PRICE };
  let note = "";
  if (modelQ) {
    const models = await fetchModels(mk.key).catch(() => []);
    const res = matchModel(models, modelQ);
    if (res && res.model) {
      search.modelKey = res.model.key;
      search.modelName = res.model.name;
    } else if (res && res.group) {
      search.modelGroupKey = res.group.key;
      search.groupName = groupLabel(res.group.key, res.group.name);
    } else if (!(res && res.all)) {
      note = "\n(„" + modelQ + "“ nicht erkannt — zeige die ganze Marke.)";
    }
  }
  search.label = searchLabel(search);
  if (note) await tgApi.sendMessage(chatId, "🔎 " + search.label + note);
  await showZeigPage(env, tgApi, chatId, search, 0);
}

// /zeig (ohne Argument): Menü der gespeicherten Suchen (CH zuerst, DE unten).
async function sendZeigMenu(env, tgApi, chatId) {
  const searches = orderedSearches(await getSearches(env));
  if (!searches.length) {
    return tgApi.sendMessage(chatId, "Keine aktiven Suchen. /addcar legt eine an — oder direkt: `/zeig BMW 335`");
  }
  const rows = searches.map((s) => [{ text: searchLabel(s), data: "zg:" + s.id }]);
  return tgApi.sendMessage(chatId, "🔎 *Welche Suche zeigen?* (tippen)", keyboard(rows));
}

function ricardoCaption(l, label) {
  const lines = ["🟡 ricardo", "*" + l.title + "*", "💰 " + fmtPrice(l.price)];
  if (l.date) lines.push("🕐 " + l.date);
  if (l.location) lines.push("📍 " + l.location);
  lines.push("🔎 _" + label + "_");
  lines.push("[➜ Inserat ansehen](" + l.url + ")");
  return lines.join("\n");
}

// /ricardo: neueste ricardo-Treffer aus dem Cache (vom Browser-Roboter befüllt).
async function sendRicardo(env, tgApi, chatId) {
  const cache = await getRicache(env);
  if (!cache || !(cache.groups || []).length) {
    return tgApi.sendMessage(chatId,
      "🟡 *ricardo* hat gerade keine Daten. ricardo blockt den Gratis-Server oft (Cloudflare) — " +
      "sobald der Roboter durchkommt, erscheinen hier die neuesten Treffer (neue kommen ohnehin automatisch).");
  }
  const min = Math.round((Date.now() - cache.updated) / 60000);
  const age = min < 60 ? `vor ${min} Min` : `vor ${Math.round(min / 60)} Std`;
  await tgApi.sendMessage(chatId, `🟡 *ricardo* — neueste Treffer (Stand: ${age})`);
  let budget = 40;
  for (const g of cache.groups) {
    if (budget < 2 || !(g.listings || []).length) continue;
    await tgApi.sendMessage(chatId, "📋 *" + g.label + "*");
    for (const l of g.listings.slice(0, 6)) {
      if (budget < 2) break;
      budget--;
      const cap = ricardoCaption(l, g.label);
      if (l.image) {
        const r = await tgApi.sendPhoto(chatId, l.image, cap);
        if (r && r.ok) continue;
      }
      await tgApi.sendMessage(chatId, cap);
    }
  }
}

async function sendDeals(env, tgApi, chatId) {
  const all = await getSearches(env);
  // /deals = CH (AS24) only — DE-Suchen über /zeig <Suche> oder den Auto-Alarm.
  const searches = all.filter((s) => !s.source || s.source === "autoscout24");
  if (!searches.length) {
    const hint = all.length ? " (deine 🇩🇪 DE-Suchen siehst du via /zeig)" : "";
    return tgApi.sendMessage(chatId, "Keine aktiven 🇨🇭 CH-Suchen." + hint + " /addcar legt eine an.");
  }
  await tgApi.sendMessage(chatId, "⏳ Hole aktuelle 🇨🇭 Treffer …");
  // shared subrequest budget (Worker free tier ~50/Aufruf); each card costs ~2
  const budget = { left: 44 };
  const perSearch = Math.max(4, Math.floor(40 / searches.length));
  for (const s of searches) {
    if (budget.left < 3) {
      await tgApi.sendMessage(chatId, "(Limit erreicht — restliche Suchen mit /deals erneut abrufen.)");
      break;
    }
    try {
      await sendSnapshot(env, tgApi, chatId, s, perSearch, budget);
    } catch (e) {
      await tgApi.sendMessage(chatId, "Fehler bei " + s.label + ": " + String(e).slice(0, 100));
    }
  }
}

// /mobile — kuratierter mobile.de-Pool aus dem Scraper-Cache (keine Auto-Alerts).
function mobileCaption(l, label) {
  const lines = ["🇩🇪 *mobile.de* · 🔧 Tuning"];
  lines.push("*" + l.title + "*");
  // mobile.de-Preise sind EUR; "≈ CHF" als Hinweis
  if (l.price != null) {
    const eur = "€ " + l.price.toLocaleString("de-CH").replace(/,/g, "'");
    const chf = Math.round((l.price * 0.95) / 100) * 100;
    lines.push("💰 " + eur + "  (≈ CHF " +
      chf.toLocaleString("de-CH").replace(/,/g, "'") + ")");
  } else {
    lines.push("💰 Preis k.A.");
  }
  const spec = [];
  if (l.year) spec.push("📅 " + l.year);
  if (l.mileage != null) spec.push("🛣 " + l.mileage.toLocaleString("de-CH").replace(/,/g, "'") + " km");
  if (l.horsepower) spec.push("⚙ " + l.horsepower + " PS");
  if (spec.length) lines.push(spec.join("  "));
  if (l.location) lines.push("📍 " + l.location);
  if (label) lines.push("🔎 _" + label + "_");
  lines.push("[➜ Inserat ansehen](" + l.url + ")");
  return lines.join("\n");
}

async function sendMobile(env, tgApi, chatId) {
  const cache = await getMobileCache(env);
  if (!cache || !(cache.groups || []).length) {
    return tgApi.sendMessage(chatId,
      "🇩🇪 *mobile.de* hat gerade keine Daten. Der Scraper befüllt den Pool alle ~30 Min — " +
      "sobald frische Tuning-Inserate eintreffen, siehst du sie hier.");
  }
  const min = Math.round((Date.now() - cache.updated) / 60000);
  const age = min < 60 ? `vor ${min} Min` : `vor ${Math.round(min / 60)} Std`;
  await tgApi.sendMessage(chatId, `🇩🇪 *mobile.de* — kuratierte Tuning-Inserate (Stand: ${age})`);
  let budget = 40;
  for (const g of cache.groups) {
    if (budget < 2 || !(g.listings || []).length) continue;
    await tgApi.sendMessage(chatId, "📋 *" + g.label + "*");
    for (const l of g.listings.slice(0, 6)) {
      if (budget < 2) break;
      budget--;
      const cap = mobileCaption(l, g.label);
      if (l.image) {
        const r = await tgApi.sendPhoto(chatId, l.image, cap);
        if (r && r.ok) continue;
      }
      await tgApi.sendMessage(chatId, cap);
    }
  }
}
