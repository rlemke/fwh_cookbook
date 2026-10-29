"""Display helpers: kitchen fractions, ingredient lines, durations."""

from __future__ import annotations

from .recipes import grams

_FRACTIONS = {
    0.125: "⅛",
    0.25: "¼",
    0.333: "⅓",
    0.375: "⅜",
    0.5: "½",
    0.625: "⅝",
    0.667: "⅔",
    0.75: "¾",
    0.875: "⅞",
}
_UNIT_NAMES = {
    "cup": ("cup", "cups"),
    "tbsp": ("tbsp", "tbsp"),
    "tsp": ("tsp", "tsp"),
    "drop": ("drop", "drops"),
}


def amount(n: float) -> str:
    """1.5 -> '1½', 0.333 -> '⅓', 2 -> '2'."""
    whole = int(n)
    frac = n - whole
    if frac < 0.02:
        return str(whole)
    sym = min(_FRACTIONS, key=lambda f: abs(f - frac))
    if abs(sym - frac) > 0.03:
        return f"{n:g}"
    return f"{whole or ''}{_FRACTIONS[sym]}"


def plural(ing: dict) -> str:
    if "plural" in ing:
        return ing["plural"]
    name = ing["name"]
    head, sep, tail = name.partition(" (")
    if head.endswith(("s", "sh", "ch", "x")):
        head += "es" if head.endswith(("sh", "ch", "x")) else ""
    else:
        head += "s"
    return head + sep + tail


def line(ln: dict, ing: dict) -> tuple[str, str]:
    """An ingredient line as (measure, rest), e.g. ('1½ cups', 'almond flour (144 g)')."""
    g = grams(ln, ing)
    note = f", {ln['note']}" if ln.get("note") else ""
    if "g" in ln:
        return f"{amount(ln['g'])} g", f"{ing['name']}{note}"
    if "each" in ln:
        n = float(ln["each"])
        return amount(n), f"{plural(ing) if n > 1 else ing['name']}{note}"
    unit = next(u for u in _UNIT_NAMES if u in ln)
    n = float(ln[unit])
    one, many = _UNIT_NAMES[unit]
    weight = f" ({g:.0f} g)" if g >= 10 and unit != "drop" else ""
    return f"{amount(n)} {many if n > 1 else one}", f"{ing['name']}{weight}{note}"


def minutes(m: int) -> str:
    if not m:
        return ""
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    if h >= 24 and not r:
        return f"{h // 24} day" + ("s" if h >= 48 else "")
    return f"{h} h" + (f" {r} min" if r else "")
