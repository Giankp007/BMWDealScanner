"""tutti.ch source — SCAFFOLD (noch nicht aktiv).

tutti.ch und ricardo.ch liefern Daten nur über einen echten Browser zuverlässig
(Anti-Bot). Geplante Umsetzung mit Playwright:

    1. Browser-Session öffnen (browser.py), Cookie-Banner akzeptieren.
    2. Suchseite mit den keywords_any des Profils ansteuern, z.B.
       https://www.tutti.ch/de/q/autos/<keyword>
    3. Inserat-Karten aus dem DOM lesen (Titel, Preis, Ort, Link, Bild).
    4. In core.Listing umwandeln; Preis/Jahr/km client-seitig gegen das
       Profil filtern (price_max, year_min, ...), da tutti weniger Filter bietet.

Sobald implementiert, in sources/__init__.py REGISTRY freischalten:
    "tutti": tutti.fetch,
"""
from core import Listing, stable_id


def fetch(profile, max_listings: int = 250) -> list[Listing]:
    raise NotImplementedError(
        "tutti.ch-Quelle ist noch nicht implementiert. "
        "AutoScout24 deckt aktuell den Grossteil des CH-Markts ab."
    )
