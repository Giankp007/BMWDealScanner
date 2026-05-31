// KV-backed storage: active searches, seen-listing dedup, transient chat state.

const SEARCHES = "searches";
const SEEN = "seen";

export async function getSearches(env) {
  const raw = await env.BMW_KV.get(SEARCHES);
  return raw ? JSON.parse(raw) : [];
}

export async function saveSearches(env, searches) {
  await env.BMW_KV.put(SEARCHES, JSON.stringify(searches));
}

export async function addSearch(env, search) {
  const all = await getSearches(env);
  all.push(search);
  await saveSearches(env, all);
  return all;
}

export async function removeSearch(env, id) {
  const all = await getSearches(env);
  const kept = all.filter((s) => s.id !== id);
  await saveSearches(env, kept);
  return kept;
}

// --- seen dedup (one JSON object {uid: lastSeenTs}) ---
export async function getSeen(env) {
  const raw = await env.BMW_KV.get(SEEN);
  return raw ? JSON.parse(raw) : {};
}

export async function saveSeen(env, seen) {
  // prune entries older than 60 days to bound size
  const cutoff = Date.now() - 60 * 24 * 3600 * 1000;
  for (const k of Object.keys(seen)) if (seen[k] < cutoff) delete seen[k];
  await env.BMW_KV.put(SEEN, JSON.stringify(seen));
}

// --- blockwords (exclude listings whose text contains any of these) ---
const BLOCK = "blockwords";

export async function getBlockwords(env) {
  const raw = await env.BMW_KV.get(BLOCK);
  return raw ? JSON.parse(raw) : [];
}
export async function addBlockword(env, word) {
  const w = word.trim().toLowerCase();
  if (!w) return getBlockwords(env);
  const all = await getBlockwords(env);
  if (!all.includes(w)) all.push(w);
  await env.BMW_KV.put(BLOCK, JSON.stringify(all));
  return all;
}
export async function removeBlockword(env, word) {
  const all = (await getBlockwords(env)).filter((w) => w !== word);
  await env.BMW_KV.put(BLOCK, JSON.stringify(all));
  return all;
}

// --- favorites (cars the user starred from any card) ---
const FAVORITES = "favorites";

export async function getFavorites(env) {
  const raw = await env.BMW_KV.get(FAVORITES);
  return raw ? JSON.parse(raw) : [];
}
export async function isFavorite(env, uid) {
  return (await getFavorites(env)).some((f) => f.uid === uid);
}
export async function addFavorite(env, listing) {
  const all = await getFavorites(env);
  if (all.some((f) => f.uid === listing.uid)) return all;     // schon drin
  all.unshift({ ...listing, addedAt: Date.now() });           // neueste zuerst
  const capped = all.slice(0, 100);
  await env.BMW_KV.put(FAVORITES, JSON.stringify(capped));
  return capped;
}
export async function removeFavorite(env, uid) {
  const all = (await getFavorites(env)).filter((f) => f.uid !== uid);
  await env.BMW_KV.put(FAVORITES, JSON.stringify(all));
  return all;
}

// --- listing cache: ⭐-Button trägt nur die uid (64-Byte-Limit), die vollen
//     Inserat-Daten holen wir hieraus. TTL 60 Tage. ---
export async function cacheListing(env, l) {
  await env.BMW_KV.put("lc:" + l.uid, JSON.stringify(l), { expirationTtl: 60 * 24 * 3600 });
}
export async function getCachedListing(env, uid) {
  const raw = await env.BMW_KV.get("lc:" + uid);
  return raw ? JSON.parse(raw) : null;
}

// --- ricardo cache (filled by the browser-scraper companion) ---
export async function getRicache(env) {
  const raw = await env.BMW_KV.get("ricardo_cache");
  return raw ? JSON.parse(raw) : null;
}
export async function saveRicache(env, data) {
  await env.BMW_KV.put("ricardo_cache", JSON.stringify(data));
}

// --- kleinanzeigen cache: per-search list of latest tuning hits (no alerts here,
//     the scraper sends those directly to Telegram). Worker reads for /zeig.
//     Shape: { updated:ms, listings:[...] } keyed by `klein:<searchId>`.
export async function getKleinCache(env, searchId) {
  const raw = await env.BMW_KV.get("klein:" + searchId);
  return raw ? JSON.parse(raw) : null;
}
export async function saveKleinCache(env, searchId, data) {
  await env.BMW_KV.put("klein:" + searchId, JSON.stringify(data),
    { expirationTtl: 14 * 24 * 3600 });
}

// --- mobile.de cache: global "latest hot DE listings" pool, no per-search split.
//     Shape: { updated:ms, groups:[{label, listings:[...]}] }. /mobile reads this.
export async function getMobileCache(env) {
  const raw = await env.BMW_KV.get("mobile_cache");
  return raw ? JSON.parse(raw) : null;
}
export async function saveMobileCache(env, data) {
  await env.BMW_KV.put("mobile_cache", JSON.stringify(data),
    { expirationTtl: 14 * 24 * 3600 });
}

// --- /zeig pagination context per chat (which search + how far) ---
export async function setZeigCtx(env, chatId, ctx) {
  await env.BMW_KV.put("zeigctx:" + chatId, JSON.stringify(ctx), { expirationTtl: 86400 });
}
export async function getZeigCtx(env, chatId) {
  const raw = await env.BMW_KV.get("zeigctx:" + chatId);
  return raw ? JSON.parse(raw) : null;
}

// --- transient per-chat conversation state (TTL) ---
export async function setPending(env, chatId, state) {
  await env.BMW_KV.put("pending:" + chatId, JSON.stringify(state), { expirationTtl: 3600 });
}
export async function getPending(env, chatId) {
  const raw = await env.BMW_KV.get("pending:" + chatId);
  return raw ? JSON.parse(raw) : null;
}
export async function clearPending(env, chatId) {
  await env.BMW_KV.delete("pending:" + chatId);
}
