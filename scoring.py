"""Deal scoring: how good is a listing's price vs the current market for its profile."""
from __future__ import annotations
import statistics
from core import Listing


def market_median(listings: list[Listing]) -> float | None:
    prices = [l.price for l in listings if l.price]
    if len(prices) < 4:
        return None
    return statistics.median(prices)


def score(listing: Listing, median: float | None) -> dict:
    """Return {discount, tier, label}. discount = fraction below median (0..1)."""
    if not median or not listing.price:
        return {"discount": 0.0, "tier": "new", "label": "🆕 Neu"}
    discount = (median - listing.price) / median
    if discount >= 0.25:
        tier, label = "hot", "🔥 TOP-DEAL"
    elif discount >= 0.15:
        tier, label = "good", "👍 Guter Deal"
    elif discount >= 0.0:
        tier, label = "fair", "🆕 Neu (Marktpreis)"
    else:
        tier, label = "above", "🆕 Neu (über Markt)"
    return {"discount": discount, "tier": tier, "label": label}
