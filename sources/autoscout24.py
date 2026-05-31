"""AutoScout24.ch source — uses the official internal JSON API.

Endpoint reverse-engineered:  POST https://api.autoscout24.ch/v1/listings/search
Filter schema lives under "query":
    makeModelVersions: [{makeKey, modelKey}]
    priceFrom / priceTo
    firstRegistrationYearFrom / firstRegistrationYearTo
    mileageFrom / mileageTo
    cubicCapacityFrom / cubicCapacityTo   (Hubraum in ccm)
    horsePowerFrom / horsePowerTo
    fuelTypes: [petrol|diesel|electric|...]
Sort types: CREATED_DATE, PRICE, MILEAGE, FIRST_REGISTRATION_DATE, HORSE_POWER, RELEVANCE
"""
from __future__ import annotations
import truststore; truststore.inject_into_ssl()   # use Windows cert store (TLS-intercept machine)
import requests
from core import Listing

API = "https://api.autoscout24.ch/v1/listings/search"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Language": "de-CH,de;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.autoscout24.ch",
    "Referer": "https://www.autoscout24.ch/",
}
PAGE_SIZE = 20   # AutoScout24 caps page size at 20


def _build_query(profile) -> dict:
    q = {}
    if profile.autoscout24_models:
        q["makeModelVersions"] = profile.autoscout24_models
    if profile.price_min:
        q["priceFrom"] = profile.price_min
    if profile.price_max < 1_000_000:
        q["priceTo"] = profile.price_max
    if profile.year_min > 1900:
        q["firstRegistrationYearFrom"] = profile.year_min
    if profile.year_max < 2100:
        q["firstRegistrationYearTo"] = profile.year_max
    if profile.mileage_max < 10_000_000:
        q["mileageTo"] = profile.mileage_max
    if profile.cubic_capacity_min:
        q["cubicCapacityFrom"] = profile.cubic_capacity_min
    if profile.horsepower_min:
        q["horsePowerFrom"] = profile.horsepower_min
    if profile.fuel_types:
        q["fuelTypes"] = profile.fuel_types
    return q


def _to_listing(item: dict) -> Listing:
    seller = item.get("seller") or {}
    loc = " ".join(str(x) for x in [seller.get("zipCode", ""), seller.get("city", "")]).strip()
    make = (item.get("make") or {}).get("name", "")
    title = f"{make} {item.get('versionFullName', '')}".strip()
    lid = str(item.get("id"))
    images = item.get("images") or []
    img = ""
    if images:
        first = images[0]
        img = first if isinstance(first, str) else (first.get("url") or first.get("key") or "")
    return Listing(
        source="autoscout24",
        listing_id=lid,
        url=f"https://www.autoscout24.ch/de/d/{lid}",
        title=title or f"Listing {lid}",
        price=int(item["price"]) if item.get("price") is not None else None,
        year=item.get("firstRegistrationYear"),
        mileage=item.get("mileage"),
        horsepower=item.get("horsePower"),
        fuel=item.get("fuelType"),
        location=loc,
        image=img,
        raw=item,
    )


def fetch(profile, max_listings: int = 250) -> list[Listing]:
    """Return the cheapest `max_listings` current listings matching the profile.

    Cheapest-first (PRICE ASC) keeps the most deal-relevant cars even when the
    market is large, and gives a clean price distribution for deal scoring.
    """
    query = _build_query(profile)
    out: list[Listing] = []
    session = requests.Session()
    session.headers.update(HEADERS)
    page = 0
    while len(out) < max_listings:
        body = {
            "query": query,
            "sort": [{"type": "PRICE", "order": "ASC"}],
            "pagination": {"page": page, "size": PAGE_SIZE},
        }
        r = session.post(API, json=body, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"AutoScout24 API {r.status_code}: {r.text[:200]}")
        data = r.json()
        items = data.get("content") or []
        if not items:
            break
        out.extend(_to_listing(it) for it in items)
        if data.get("last") or page + 1 >= data.get("totalPages", 1):
            break
        page += 1
    return out[:max_listings]
