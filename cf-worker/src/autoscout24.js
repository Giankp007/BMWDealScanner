// AutoScout24.ch client — internal JSON API (no browser needed).
// POST https://api.autoscout24.ch/v1/listings/search  with filters under "query".

const API = "https://api.autoscout24.ch/v1/listings/search";
const MAKES = "https://api.autoscout24.ch/v1/makes?vehicleCategory=car";
const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
  "Accept": "application/json",
  "Accept-Language": "de-CH,de;q=0.9",
  "Content-Type": "application/json",
  "Origin": "https://www.autoscout24.ch",
  "Referer": "https://www.autoscout24.ch/",
};
const PAGE_SIZE = 20; // API caps page size at 20

function buildQuery(search) {
  const q = {};
  if (search.makeKey) {
    const mm = { makeKey: search.makeKey };
    if (search.modelKey) mm.modelKey = search.modelKey;
    if (search.modelGroupKey) mm.modelGroupKey = search.modelGroupKey;  // Baureihe, z. B. "3-series"
    q.makeModelVersions = [mm];
  }
  if (search.bodyTypes && search.bodyTypes.length) q.bodyTypes = search.bodyTypes;
  if (search.maxPrice) q.priceTo = search.maxPrice;
  if (search.minPrice) q.priceFrom = search.minPrice;
  if (search.minYear) q.firstRegistrationYearFrom = search.minYear;
  if (search.maxYear) q.firstRegistrationYearTo = search.maxYear;
  if (search.maxMileage) q.mileageTo = search.maxMileage;
  if (search.minCcm) q.cubicCapacityFrom = search.minCcm;
  if (search.minHp) q.horsePowerFrom = search.minHp;
  if (search.fuelTypes && search.fuelTypes.length) q.fuelTypes = search.fuelTypes;
  return q;
}

const IMG_BASE = "https://listing-images.autoscout24.ch/";

function imageUrl(item) {
  const imgs = item.images || [];
  if (!imgs.length) return "";
  const first = imgs[0];
  const key = typeof first === "string" ? first : first.key || first.url || "";
  if (!key) return "";
  return key.startsWith("http") ? key : IMG_BASE + key;
}

function toListing(item) {
  const seller = item.seller || {};
  const loc = [seller.zipCode || "", seller.city || ""].join(" ").trim();
  const make = (item.make || {}).name || "";
  const id = String(item.id);
  return {
    source: "autoscout24",
    uid: "autoscout24:" + id,
    url: "https://www.autoscout24.ch/de/d/" + id,
    title: (make + " " + (item.versionFullName || "")).trim() || "Listing " + id,
    price: item.price != null ? Math.round(item.price) : null,
    year: item.firstRegistrationYear || null,
    mileage: item.mileage != null ? item.mileage : null,
    horsepower: item.horsePower || null,
    fuel: item.fuelType || null,
    location: loc,
    teaser: item.teaser || "",
    image: imageUrl(item),
    created: item.createdDate || null,
  };
}

// AS24-Listing-IDs sind rein numerisch. Hart darauf festnageln, damit nichts
// anderes (z. B. ein manipuliertes uid) in den API-Pfad gelangen kann.
function safeListingId(id) {
  const s = String(id);
  return /^\d+$/.test(s) ? s : null;
}

// Full listing description (for keyword filtering on the ad text).
export async function fetchDescription(id) {
  const sid = safeListingId(id);
  if (!sid) return "";
  try {
    const r = await fetch("https://api.autoscout24.ch/v1/listings/" + sid, { headers: HEADERS });
    if (!r.ok) return "";
    const d = await r.json();
    return [d.description || "", d.teaser || ""].join(" ");
  } catch (e) {
    return "";
  }
}

// Alle Bild-URLs eines Detail-Items (für die /mehrinfo-Galerie).
function allImageUrls(item) {
  const imgs = item.images || [];
  const out = [];
  for (const im of imgs) {
    const key = typeof im === "string" ? im : im.key || im.url || "";
    if (!key) continue;
    out.push(key.startsWith("http") ? key : IMG_BASE + key);
  }
  return out;
}

// Vollständiges Inserat (für /mehrinfo). Liefert das rohe Detail-Objekt + alle
// Bild-URLs. Null bei Fehler/Nicht-gefunden.
export async function fetchListingDetail(id) {
  const sid = safeListingId(id);
  if (!sid) return null;
  try {
    const r = await fetch("https://api.autoscout24.ch/v1/listings/" + sid, { headers: HEADERS });
    if (!r.ok) return null;
    const d = await r.json();
    d._images = allImageUrls(d);
    return d;
  } catch (e) {
    return null;
  }
}

// Fetch up to maxListings cheapest matching listings (PRICE ASC).
export async function fetchListings(search, maxListings = 250) {
  const query = buildQuery(search);
  const out = [];
  let page = 0;
  while (out.length < maxListings) {
    const body = {
      query,
      sort: [{ type: "PRICE", order: "ASC" }],
      pagination: { page, size: PAGE_SIZE },
    };
    const r = await fetch(API, { method: "POST", headers: HEADERS, body: JSON.stringify(body) });
    if (!r.ok) throw new Error("AS24 " + r.status + ": " + (await r.text()).slice(0, 200));
    const data = await r.json();
    const items = data.content || [];
    if (!items.length) break;
    for (const it of items) out.push(toListing(it));
    if (data.last || page + 1 >= (data.totalPages || 1)) break;
    page++;
  }
  return out.slice(0, maxListings);
}

// All makes (key + name), for validating typed brands / matching.
export async function fetchMakes() {
  const r = await fetch(MAKES, { headers: HEADERS });
  if (!r.ok) throw new Error("AS24 makes " + r.status);
  const d = await r.json();
  const items = Array.isArray(d) ? d : d.content || [];
  return items.map((m) => ({ key: m.key, name: m.name }));
}

// Models of a make (key + name + group), for matching typed model names.
export async function fetchModels(makeKey) {
  const url = "https://api.autoscout24.ch/v1/makes/key/" + encodeURIComponent(makeKey) +
    "/models?vehicleCategory=car";
  const r = await fetch(url, { headers: HEADERS });
  if (!r.ok) throw new Error("AS24 models " + r.status);
  const d = await r.json();
  const items = Array.isArray(d) ? d : d.content || [];
  return items.map((m) => ({
    key: m.key,
    name: m.name,
    // Baureihe als Objekt {key,name} — z. B. {key:"3-series", name:"3 SERIES"}.
    group: m.group && m.group.key ? { key: m.group.key, name: m.group.name || "" } : null,
  }));
}
