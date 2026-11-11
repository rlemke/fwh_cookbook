"""Display helpers: kitchen fractions, ingredient lines, durations."""

from __future__ import annotations

import re

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
        approx = household(float(ln["g"]), ing, ln.get("note", ""))
        approx = f" ({approx})" if approx else ""
        return f"{amount(ln['g'])} g", f"{ing['name']}{approx}{note}"
    if "each" in ln:
        n = float(ln["each"])
        return amount(n), f"{plural(ing) if n > 1 else ing['name']}{note}"
    unit = next(u for u in _UNIT_NAMES if u in ln)
    n = float(ln[unit])
    one, many = _UNIT_NAMES[unit]
    weight = f" ({g:.0f} g)" if g >= 10 and unit != "drop" else ""
    return f"{amount(n)} {many if n > 1 else one}", f"{ing['name']}{weight}{note}"


_TSP_PER = {"cup": 48, "tbsp": 3, "tsp": 1}
# Sizes a US measuring-cup and spoon set actually has.
_CUP_STEPS = (0, 0.25, 0.333, 0.5, 0.667, 0.75, 1)
_HALF_STEPS = (0, 0.5, 1)
_QUARTER_STEPS = (0, 0.25, 0.5, 0.75, 1)
# A note that already gives a household measure ("one 12 oz bag", "about 1
# heaped cup", "(about 1/2 small onion)") makes a second one redundant.
_NOTE_MEASURE = re.compile(r"\b(cups?|tbsp|tsp|oz|lb|small|medium|large)\b", re.I)


def _snap(n: float, steps: tuple[float, ...]) -> float:
    """Round to the nearest whole-plus-step (1.3 cups -> 1⅓)."""
    whole = int(n)
    return whole + min(steps, key=lambda f: abs(n - whole - f))


def _by_weight(g: float) -> str:
    if g >= 440:  # a pound or more, give or take
        return f"about {amount(_snap(g / 453.6, _QUARTER_STEPS))} lb"
    oz = _snap(g / 28.35, _HALF_STEPS)
    return f"about {amount(oz)} oz" if oz else ""


def household(g: float, ing: dict, note: str = "") -> str:
    """An approximate US measure for a weight, for the reader without a scale.

    Volume (cups, tbsp, tsp) where the ingredient has a cup or spoon weight;
    a piece count where it has a weight per piece (onion, peach); otherwise
    ounces or pounds, the US convention for chocolate, meat and fish, which
    are bought by weight. Volumes over 4 cups (a bag of spinach, a head of
    cauliflower) are given by weight too: nobody measures 30 cups of spinach.
    '' when the note already gives a measure or nothing useful can be said.
    """
    if _NOTE_MEASURE.search(note):
        return ""
    known = {u: ing[f"{u}_g"] for u in _TSP_PER if f"{u}_g" in ing}
    if known:
        u, w = next(iter(known.items()))
        tsp = g / (w / _TSP_PER[u])
        if tsp > 4 * 48:
            return _by_weight(g)
        if tsp >= 12:  # a quarter cup or more
            n, one, many = _snap(tsp / 48, _CUP_STEPS), "cup", "cups"
        elif tsp >= 3:
            n, one, many = _snap(tsp / 3, _HALF_STEPS), "tbsp", "tbsp"
            if n >= 4:  # rounded up to a quarter cup
                n, one, many = 0.25, "cup", "cups"
        else:
            n, one, many = _snap(tsp, _QUARTER_STEPS), "tsp", "tsp"
        if n == 0:
            return "a pinch"
        return f"about {amount(n)} {many if n > 1 else one}"
    if "each_g" in ing:
        n = _snap(g / ing["each_g"], _QUARTER_STEPS)
        return f"about {amount(n)} {plural(ing) if n > 1 else ing['name']}" if n else ""
    return _by_weight(g)


def minutes(m: int) -> str:
    if not m:
        return ""
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    if h >= 24 and not r:
        return f"{h // 24} day" + ("s" if h >= 48 else "")
    return f"{h} h" + (f" {r} min" if r else "")
