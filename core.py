"""Shared data structures for the deal scanner."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import hashlib


@dataclass
class Listing:
    """One car listing, normalized across all sources."""
    source: str                 # 'autoscout24', 'tutti', ...
    listing_id: str             # unique within the source
    url: str
    title: str
    price: Optional[int] = None
    year: Optional[int] = None
    mileage: Optional[int] = None
    horsepower: Optional[int] = None
    fuel: Optional[str] = None
    location: str = ""
    image: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.listing_id}"

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class Profile:
    """A search profile = what kind of car the user wants to be alerted about.

    Designed to be vehicle-agnostic: change the YAML, search anything.
    """
    name: str
    enabled: bool = True
    sources: list = field(default_factory=lambda: ["autoscout24"])

    # generic, source-independent criteria
    price_min: int = 0
    price_max: int = 1_000_000
    year_min: int = 1900
    year_max: int = 2100
    mileage_max: int = 10_000_000
    cubic_capacity_min: int = 0      # ccm, e.g. 2900 for >=3.0 L
    horsepower_min: int = 0
    fuel_types: list = field(default_factory=list)   # AS24 keys: petrol, diesel, ...

    # AutoScout24-specific: list of {makeKey, modelKey}
    autoscout24_models: list = field(default_factory=list)

    # for text-based sources (tutti / ricardo / facebook)
    keywords_any: list = field(default_factory=list)   # title must contain one of these

    # deal scoring
    deal_threshold: float = 0.15     # >=15% under median price counts as a deal

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        known = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**known)


def stable_id(*parts: str) -> str:
    """Deterministic id from arbitrary parts (used by text sources w/o clean id)."""
    return hashlib.sha1("|".join(parts).encode("utf-8", "ignore")).hexdigest()[:16]
