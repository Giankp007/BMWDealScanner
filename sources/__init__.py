"""Listing sources. Each source exposes  fetch(profile, max_listings) -> list[Listing]."""
from . import autoscout24

REGISTRY = {
    "autoscout24": autoscout24.fetch,
    # "tutti": tutti.fetch,        # scaffolded — see sources/tutti.py
    # "ricardo": ricardo.fetch,
    # "facebook": facebook.fetch,
}


def get(name):
    return REGISTRY.get(name)
