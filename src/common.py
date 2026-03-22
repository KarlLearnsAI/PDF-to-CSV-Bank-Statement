"""Shared constants and utilities for PDF bank statement parsing."""
import re


MONTHS_PATTERN = r"(?:Jan|Feb|März|Mrz|Apr|Mai|Juni?|Juli?|Aug|Sept|Okt|Nov|Dez)"

MONTH_MAP = {
    "Jan": "Jan", "Feb": "Feb", "März": "Mar", "Mrz": "Mar",
    "Apr": "Apr", "Mai": "May", "Jun": "Jun", "Juni": "Jun",
    "Jul": "Jul", "Juli": "Jul",
    "Aug": "Aug", "Sept": "Sep", "Okt": "Oct", "Nov": "Nov", "Dez": "Dec",
}

INCOME_KEYWORDS = [
    "Incoming", "Einzahlung", "Zinszahlung", "Zinsen",
    "Gutschrift", "Ertrag", "Empfehlung", "Verkauf", "Steuern",
]


def to_float(s: str) -> float:
    """Convert European-formatted currency string to float.

    Handles dots as thousands separators, commas as decimal separators,
    trailing minus (e.g. '5,39-' -> -5.39), and the euro symbol.
    """
    if not isinstance(s, str):
        return 0.0
    s = s.strip()
    negative = s.endswith('-')
    if negative:
        s = s[:-1]
    clean = s.replace("€", "").replace(".", "").replace(",", ".").strip()
    try:
        val = float(clean)
        return -val if negative else val
    except (ValueError, TypeError):
        return 0.0


def group_words_into_lines(words, y_tolerance=4):
    """Group pdfplumber words into lines by Y-position proximity."""
    lines = []
    for w in words:
        placed = False
        for line in lines:
            if abs(w["top"] - line["top"]) < y_tolerance:
                line["words"].append(w)
                placed = True
                break
        if not placed:
            lines.append({"top": w["top"], "words": [w]})
    lines.sort(key=lambda L: L["top"])
    for L in lines:
        L["words"].sort(key=lambda w: w["x0"])
        L["text"] = " ".join(w["text"] for w in L["words"])
    return lines
