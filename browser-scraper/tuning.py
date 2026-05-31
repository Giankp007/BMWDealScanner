"""Tuning-Verdacht-Filter für DE-Inserate.

Regel ("Tuning-Verdacht reicht"):
  durchgelassen, wenn IRGENDEIN klassisches Tuning-Stichwort im Text vorkommt
  ODER eine explizite PS/kW-Angabe ≥ Schwelle gefunden wird (default 320, bzw.
  ≥ search.minHp falls grösser).

Geprüft wird der ganze sichtbare Card-Text: Titel + Teaser + JSON-LD-Description.
"""
import re

TUNING_KEYWORDS = [
    # Power / Software
    "stage 1", "stage 2", "stage 3", "stage1", "stage2", "stage3",
    "chiptuning", "chip-tuning", "chip tuning",
    "remap", "leistungssteigerung", "leistungsgesteigert",
    "mehr leistung", "powerkit", "power kit", "performance kit",
    "jb4", "mhd flash", "mhd-flash", "bm3", "bootmod3",
    "ecu flash", "ecu-flash", "ecu remap",
    "ets racing", "ess tuning", "g-power", "gpower", "g power", "alpina",
    "ac schnitzer", "hamann motorsport", "manhart", "mr car design",
    "wiesmann", "dahler",

    # Forced induction
    "kompressor", "supercharger", "supercharged", "kompressorumbau",
    "turboumbau", "big turbo", "bigturbo", "single turbo",
    "fmic", "intercooler", "ladeluftkühler",

    # Abgas
    "eisenmann", "akrapovic", "akrapovič", "supersprint", "milltek",
    "remus auspuff", "borla", "fi exhaust", "fi-exhaust",
    "klappenauspuff", "klappensteuerung", "klappenanlage",
    "downpipe", "katlos", "kat-los", "ohne kat", "ohne opf",
    "krümmer fächer", "fächerkrümmer", "pops & bangs", "popcorn",
    "burble", "knallumbau",

    # Fahrwerk / Räder
    "tieferlegung", "gewindefahrwerk", "kw fahrwerk", "kw gewinde",
    "bilstein b16", "bilstein b14", "öhlins", "ohlins", "kw v3", "kw v2", "kw v1",
    "h&r gewinde", "h+r gewinde", "hr fahrwerk", "eibach gewinde",
    "vossen", "rotiform", "adv.1", "hre wheels", "hre felgen",
    "schmiederäder", "schmiedefelgen", "konkav",

    # Karosserie / Optik
    "carbon", "widebody", "wide body", "wide-body",
    "fender flares", "kotflügelverbreiterung",
    "ducktail", "frontsplitter", "heckdiffusor",
    "carbon-paket", "carbon paket", "carbon spoiler",

    # Modellspezifisch hot
    "n54 tuned", "n55 tuned", "s55 tuned", "s65 tuned",
    "rb turbo", "vtt turbo", "pure turbo", "pure stage", "purestage",
    "n54 build", "n55 build", "n54-aufbau",

    # Catch-all
    "getunt", "getuned", "getuned!", "tuning", "individualisiert",
    "umgebaut", "kompletter umbau", "umbau bmw",
    "modifiziert", "show car", "show-car", "showcar",
    "leistungsstark optimiert", "softwareoptimierung",
    "ppk umbau", "ppk bmw",
]

PS_RX = re.compile(r"(\d{2,4})\s*PS\b", re.I)
KW_RX = re.compile(r"(\d{2,4})\s*kW\b", re.I)
# Stock-PS-Hinweis ignorieren: typische Serien-Bezeichnungen direkt vor PS,
# die KEIN Tuning-Verdacht sind. Wenn das einzige PS-Hit "306 PS" / "326 PS" /
# "313 PS" ist (Serie N54/N55/335d), ist das KEIN Tuning-Signal.
STOCK_HPS = {306, 326, 313, 286, 265, 258, 211, 218, 192}


def extract_hp(text: str):
    """Höchste plausible PS-Angabe aus dem Text (PS direkt oder kW→PS).

    Liefert auch (None, []) zurück, wenn nichts gefunden wurde.
    Gibt ein Tuple (max_hp, all_hits) zurück.
    """
    if not text:
        return None, []
    hits = []
    for m in PS_RX.finditer(text):
        v = int(m.group(1))
        if 60 <= v <= 1500:
            hits.append(v)
    for m in KW_RX.finditer(text):
        v = int(round(int(m.group(1)) * 1.35962))
        if 60 <= v <= 1500:
            hits.append(v)
    return (max(hits) if hits else None, hits)


def is_tuned(title: str, teaser: str = "") -> bool:
    """Rückwärtskompatibel: nur klassische Stichworte (kein PS-Override)."""
    blob = ((title or "") + " " + (teaser or "")).lower()
    return any(k in blob for k in TUNING_KEYWORDS)


def is_tuning_candidate(title: str, teaser: str = "", min_hp_threshold: int = 0) -> bool:
    """Tuning-Verdacht reicht: Stichwort ODER PS-Schwelle überschritten.

    Args:
        title, teaser: kompletter Card-Text (inkl. JSON-LD-description, falls
            der Scraper sie schon dazugepackt hat — siehe sites.py).
        min_hp_threshold: PS-Wert ab dem eine im Text genannte PS-Zahl allein
            schon als Tuning-Verdacht zählt. Wir nehmen MAX(threshold, 320),
            weil unter 320 PS bei BMW-Reihensechsern noch alles Serie ist.
    """
    blob = ((title or "") + " " + (teaser or "")).lower()
    # 1) klassisches Stichwort
    if any(k in blob for k in TUNING_KEYWORDS):
        return True
    # 2) PS im Text ≥ Schwelle (Serien-PS ignorieren, wenn das die einzige Zahl ist)
    threshold = max(int(min_hp_threshold or 0), 320)
    top, hits = extract_hp(blob)
    if not top:
        return False
    non_stock = [h for h in hits if h not in STOCK_HPS]
    candidate = max(non_stock) if non_stock else top
    return candidate >= threshold
