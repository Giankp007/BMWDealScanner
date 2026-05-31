// Scanning, deal scoring, keyword filtering and rich (photo) messages.
import { fetchListings, fetchDescription } from "./autoscout24.js";
import { getSearches, getSeen, saveSeen, getBlockwords, cacheListing,
         getKleinCache } from "./store.js";
import { keyboard } from "./telegram.js";

// Rough EUR→CHF for the parenthetical hint on DE listings. Update every few months.
const EUR_TO_CHF = 0.95;

// Quelle = AS24 (CH) oder kleinanzeigen/mobile (DE)?
function isDeSource(s) {
  return s === "kleinanzeigen" || s === "mobile";
}
function flagFor(source) {
  return isDeSource(source) ? "🇩🇪" : "🇨🇭";
}
function sourceLabel(source) {
  if (source === "kleinanzeigen") return "kleinanzeigen.de";
  if (source === "mobile") return "mobile.de";
  return "AutoScout24";
}

// "€ 15'900  (≈ CHF 15'100)" for DE listings.
function fmtEurChf(p) {
  if (p == null) return "Preis k.A.";
  const eur = "€ " + p.toLocaleString("de-CH").replace(/,/g, "'");
  const chf = Math.round((p * EUR_TO_CHF) / 100) * 100;
  return eur + "  (≈ CHF " + chf.toLocaleString("de-CH").replace(/,/g, "'") + ")";
}

function median(nums) {
  const xs = nums.filter((n) => n != null).sort((a, b) => a - b);
  if (xs.length < 4) return null;
  const m = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[m] : (xs[m - 1] + xs[m]) / 2;
}

export function fmtPrice(p) {
  return p != null ? "CHF " + p.toLocaleString("de-CH").replace(/,/g, "'") : "Preis k.A.";
}

export function score(price, med) {
  if (!med || price == null) return { discount: 0, label: "🆕 Neu" };
  const discount = (med - price) / med;
  if (discount >= 0.25) return { discount, label: "🔥 TOP-DEAL" };
  if (discount >= 0.15) return { discount, label: "👍 Guter Deal" };
  if (discount >= 0) return { discount, label: "🆕 Neu (Marktpreis)" };
  return { discount, label: "🆕 Neu (über Markt)" };
}

// "online seit" — relative date from an ISO timestamp.
function fmtAge(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "heute";
  if (days === 1) return "gestern";
  if (days < 30) return "vor " + days + " Tagen";
  return d.toLocaleDateString("de-CH");
}

function specLine(l) {
  const parts = [];
  if (l.year) parts.push("📅 " + l.year);
  if (l.mileage != null) parts.push("🛣 " + l.mileage.toLocaleString("de-CH").replace(/,/g, "'") + " km");
  if (l.horsepower) parts.push("⚙ " + l.horsepower + " PS");
  if (l.fuel) parts.push("⛽ " + l.fuel);
  return parts.join("  ");
}

// Keyword filter: does any blocked word appear in the given text?
function hits(text, blockwords) {
  const t = (text || "").toLowerCase();
  return blockwords.some((w) => w && t.includes(w));
}

// Full block check: title/teaser first (cheap), then the ad description (1 fetch).
async function isBlocked(l, blockwords) {
  if (!blockwords.length) return false;
  if (hits((l.title || "") + " " + (l.teaser || ""), blockwords)) return true;
  const id = l.uid.split(":")[1];
  const desc = await fetchDescription(id);
  return hits(desc, blockwords);
}

// Caption for a listing card (used for photo + text fallback).
// Header trägt prominent die Flagge der Quelle — 🇨🇭 für AS24, 🇩🇪 für kleinanzeigen/mobile.
function buildCaption(l, searchLabel, sc) {
  const de = isDeSource(l.source);
  let header;
  if (de) {
    header = flagFor(l.source) + " *" + sourceLabel(l.source) + "* · 🔧 Tuning-Fund";
  } else {
    const note = sc.discount
      ? "  (" + (sc.discount >= 0 ? "+" : "") + Math.round(sc.discount * 100) + "% vs. Median)"
      : "";
    header = flagFor(l.source) + " " + sc.label + note;
  }
  const priceLine = "💰 " + (de ? fmtEurChf(l.price) : fmtPrice(l.price));
  const lines = [header, "*" + l.title + "*", priceLine];
  const spec = specLine(l);
  if (spec) lines.push(spec);
  const meta = [];
  if (l.location) meta.push("📍 " + l.location);
  const age = fmtAge(l.created);
  if (age) meta.push("🕐 online " + age);
  if (meta.length) lines.push(meta.join("  ·  "));
  lines.push("🔎 _" + searchLabel + "_");
  lines.push("[➜ Inserat ansehen](" + l.url + ")");
  return lines.join("\n");
}

// Send one listing as a photo card (falls back to text if no/!image).
// Caches the listing so the ⭐ button (carries only the uid) can find it again.
async function sendCard(env, tgApi, chatId, l, searchLabel, sc) {
  await cacheListing(env, { ...l, searchLabel });
  const caption = buildCaption(l, searchLabel, sc);
  const kb = keyboard([[{ text: "⭐ Merken", data: "fav:" + l.uid }]]);
  if (l.image) {
    const res = await tgApi.sendPhoto(chatId, l.image, caption, kb);
    if (res && res.ok) return;
  }
  await tgApi.sendMessage(chatId, caption, kb);
}

// Send one favorite as a card with an "entfernen" button (used by /favoriten).
export async function sendFavoriteCard(tgApi, chatId, f) {
  const caption = buildCaption(f, f.searchLabel || "", { discount: 0, label: "⭐ Favorit" });
  const kb = keyboard([[{ text: "❌ Aus Favoriten entfernen", data: "uf:" + f.uid }]]);
  if (f.image) {
    const res = await tgApi.sendPhoto(chatId, f.image, caption, kb);
    if (res && res.ok) return;
  }
  await tgApi.sendMessage(chatId, caption, kb);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Send one page of a search's listings as photo cards.
// Source-aware: AS24 → live API + median scoring; kleinanzeigen → KV cache
// (already tuning-gefiltert vom Scraper, kein Median, Reihenfolge wie geliefert).
// Returns {next, total, shown}.
export async function sendListingsPage(env, tgApi, chatId, search, startIndex, topN, budget) {
  const blockwords = await getBlockwords(env);
  const isKlein = search.source === "kleinanzeigen";
  budget.left -= 1;

  let listings, med = null, header;
  if (isKlein) {
    const c = await getKleinCache(env, search.id);
    listings = (c && c.listings) || [];
    const min = c ? Math.round((Date.now() - c.updated) / 60000) : null;
    const age = min == null ? "—" : (min < 60 ? "vor " + min + " Min" : "vor " + Math.round(min / 60) + " Std");
    header = "🇩🇪 *" + search.label + "* — " + listings.length + " Tuning-Treffer · Stand: " + age;
  } else {
    listings = await fetchListings(search, 250); // AS24, PRICE ASC
    med = median(listings.map((l) => l.price));
    header = "🇨🇭 *" + search.label + "* — " + listings.length + " Treffer · Median " +
      (med ? fmtPrice(Math.round(med)) : "—");
  }
  if (startIndex === 0) await tgApi.sendMessage(chatId, header);

  let shown = 0, i = startIndex;
  for (; i < listings.length && shown < topN; i++) {
    if (budget.left < 3) break;
    const l = listings[i];
    budget.left -= 1;
    // Kleinanzeigen: nur Titel/Teaser-basierter Blockcheck (keine /description-API).
    if (isKlein) {
      const t = ((l.title || "") + " " + (l.teaser || "")).toLowerCase();
      if (blockwords.some((w) => w && t.includes(w))) continue;
    } else {
      if (await isBlocked(l, blockwords)) continue;
      budget.left -= 1;
    }
    await sendCard(env, tgApi, chatId, l, search.label, score(l.price, med));
    shown++;
    await sleep(120); // gentle on Telegram rate limits
  }
  return { next: i, total: listings.length, shown };
}

// /deals: top N per search (no pagination footer).
export async function sendSnapshot(env, tgApi, chatId, search, topN, budget) {
  const r = await sendListingsPage(env, tgApi, chatId, search, 0, topN, budget);
  if (r.total === 0) {
    await tgApi.sendMessage(chatId, "Gerade keine Treffer.");
  } else if (r.shown === 0) {
    await tgApi.sendMessage(chatId, "(Alle Treffer durch gesperrte Stichwörter ausgefiltert.)");
  }
}

// Seed a freshly added search into "seen" without alerting.
// Kleinanzeigen: no-op — der Python-Scraper hat sein eigenes seen-State und
// markiert die Suche beim ersten Lauf als "geseedet".
export async function seedSearch(env, search) {
  if (search.source === "kleinanzeigen") return 0;
  const seen = await getSeen(env);
  try {
    const listings = await fetchListings(search, 250);
    const now = Date.now();
    for (const l of listings) seen[l.uid] = now;
    await saveSeen(env, seen);
    return listings.length;
  } catch (e) {
    return 0;
  }
}

// Cron scan: alert on genuinely new, non-blocked listings (photo cards).
// Always reports back — even with nothing new — so Giank never has to ask.
// CH zuerst: kleinanzeigen-Suchen werden hier übersprungen (Python-Scraper sendet
// die DE-Alerts separat, damit AS24 nicht von DE übertönt wird).
export async function scanAndAlert(env, tgApi, chatId) {
  const allSearches = await getSearches(env);
  const searches = allSearches.filter((s) => !s.source || s.source === "autoscout24");
  if (!searches.length) {
    if (!allSearches.length) {
      await tgApi.sendMessage(chatId,
        "🔄 Check gemacht — du hast aktuell keine aktiven Suchen. Mit /addcar legst du eine an.");
    }
    // Nur DE-Suchen aktiv → Worker macht nichts, Scraper meldet sich.
    return;
  }
  const seen = await getSeen(env);
  const blockwords = await getBlockwords(env);
  const now = Date.now();
  const budget = { left: 46 }; // Worker free-tier subrequest guard
  let sent = 0;
  let truncated = false;
  outer: for (const search of searches) {
    let listings;
    try {
      budget.left -= 1;
      listings = await fetchListings(search, 250);
    } catch (e) {
      continue;
    }
    const med = median(listings.map((l) => l.price));
    for (const l of listings) {
      if (seen[l.uid]) {
        seen[l.uid] = now;
        continue;
      }
      // leave remaining unseen so the next scan picks them up
      if (budget.left < 3) { truncated = true; break outer; }
      budget.left -= 1;
      const blocked = await isBlocked(l, blockwords);
      seen[l.uid] = now; // decided -> mark seen
      if (blocked) continue;
      budget.left -= 1;
      await sendCard(env, tgApi, chatId, l, search.label, score(l.price, med));
      sent++;
      await sleep(120);
    }
  }
  await saveSeen(env, seen);

  // Heartbeat: melde dich IMMER, damit klar ist, dass der Scanner lebt.
  if (sent === 0) {
    await tgApi.sendMessage(chatId,
      "😕 Leider habe ich keine neuen Inserate gefunden. Nächster Check in ~30 Min. 🔄");
  } else if (truncated) {
    await tgApi.sendMessage(chatId,
      "ℹ️ Das waren " + sent + " neue Treffer — es gibt noch mehr, die kommen beim nächsten Scan.");
  }
}
