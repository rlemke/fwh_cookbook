"""Recipes: loading, validation, and the arithmetic of a serving.

Each recipe is one JSON file in ``data/recipes``. Ingredients name a key in
``data/ingredients.json`` and an amount in grams, pieces, or US measures
(cup, tbsp, tsp, drop), which convert to grams through that ingredient's own
weights — a cup of almond flour is not a cup of water.

Every recipe must be dairy-free as written or carry a swap for each dairy
ingredient; the dairy-free version's nutrition is computed from the swaps,
not assumed equal.

Every recipe with egg must either carry an egg-free swap for each egg
ingredient (``vegan_swaps``) or name a similar recipe that is vegan
(``vegan_alternative``), for dishes where the egg is the point. The vegan
version is the dairy-free swaps plus ``vegan_swaps``, which may also replace
gelatin, stock and fish sauces; a dish with meat stays egg-free, not vegan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from .nutrition import Facts, Table

CATEGORIES = {
    "cakes": "Cakes",
    "cheesecakes": "Cheesecakes",
    "cookies": "Cookies & biscuits",
    "bars": "Bars & brownies",
    "pies": "Pies & tarts",
    "custards": "Puddings & custards",
    "mousses": "Mousses & creams",
    "frozen": "Frozen desserts",
    "candy": "Candy & confections",
    "fat-bombs": "Fat bombs",
    "fruit": "Fruit desserts",
    "drinks": "Drinks",
    "breakfast": "Breakfast",
    "breads": "Breads & crackers",
    "mains": "Main dishes",
    "sides": "Sides, salads & starters",
    "sauces": "BBQ sauces, rubs & marinades",
    "basics": "Basics, crusts & sauces",
}
DESSERT_CATEGORIES = set(CATEGORIES) - {
    "breakfast",
    "breads",
    "drinks",
    "basics",
    "mains",
    "sides",
    "sauces",
}
UNITS = ("g", "each", "cup", "tbsp", "tsp", "drop")
ALLERGENS = {
    "dairy": "dairy",
    "egg": "eggs",
    "tree_nuts": "tree nuts",
    "peanuts": "peanuts",
    "coconut": "coconut",
    "soy": "soy",
    "sesame": "sesame",
    "fish": "fish",
    "shellfish": "shellfish",
}
# Contained groups that rule out vegan; meat, gelatin and the like carry
# ``"animal": true`` in the ingredient vocabulary instead.
NON_VEGAN = {"dairy", "egg", "fish", "shellfish"}
VEGAN_STATUSES = ("vegan", "vegan option")
REQUIRED = ("id", "title", "category", "summary", "servings", "ingredients", "steps", "origin")
ORIGIN_REQUIRED = ("family", "place", "region", "lat", "lon", "era", "history")


def load_recipes() -> list[dict]:
    d = resources.files("cookbook").joinpath("data/recipes")
    out = [json.loads(p.read_text()) for p in d.iterdir() if p.name.endswith(".json")]
    return sorted(out, key=lambda r: r["id"])


def grams(line: dict, ing: dict) -> float:
    """The weight of one ingredient line, in grams."""
    for unit in UNITS:
        if unit in line:
            n = float(line[unit])
            break
    else:
        raise ValueError(f"{line.get('item')}: no amount (one of {', '.join(UNITS)})")
    if unit == "g":
        return n
    if unit == "each":
        if "each_g" not in ing:
            raise ValueError(f"{line['item']}: counted in pieces but has no each_g")
        return n * ing["each_g"]
    if unit == "drop":
        return n * ing.get("drop_g", 0.05)
    # Any one spoon or cup weight gives the others (1 cup = 16 tbsp = 48 tsp).
    tsp_per = {"cup": 48, "tbsp": 3, "tsp": 1}
    known = {u: ing[f"{u}_g"] for u in tsp_per if f"{u}_g" in ing}
    if unit in known:
        per = known[unit]
    elif known:
        u, w = next(iter(known.items()))
        per = w / tsp_per[u] * tsp_per[unit]
    else:
        per = None
    if per is None:
        raise ValueError(f"{line['item']}: measured by {unit} but has no weight for it")
    return n * per


def lines(recipe: dict) -> list[dict]:
    return [ln for ln in recipe["ingredients"] if "item" in ln]


def is_animal(entry: dict) -> bool:
    """Not vegan: meat, fish, gelatin, stock, or anything containing dairy or egg."""
    return bool(entry.get("animal")) or bool(set(entry["contains"]) & NON_VEGAN)


def is_egg(entry: dict) -> bool:
    return "egg" in entry["contains"]


def validate(recipe: dict, table: Table) -> list[str]:
    """Everything wrong with a recipe, as readable messages (empty = valid)."""
    errs = []
    rid = recipe.get("id", "?")
    for k in REQUIRED:
        if k not in recipe:
            errs.append(f"{rid}: missing {k}")
    if errs:
        return errs
    if recipe["category"] not in CATEGORIES:
        errs.append(f"{rid}: unknown category {recipe['category']}")
    if not isinstance(recipe["servings"], int) or recipe["servings"] < 1:
        errs.append(f"{rid}: servings must be a positive integer")
    for k in ORIGIN_REQUIRED:
        if k not in recipe["origin"]:
            errs.append(f"{rid}: origin missing {k}")
    ing = table.ingredients
    for ln in lines(recipe):
        if ln["item"] not in ing:
            errs.append(f"{rid}: unknown ingredient {ln['item']}")
            continue
        if ing[ln["item"]].get("conventional"):
            errs.append(f"{rid}: {ln['item']} is not a low-carb ingredient")
        try:
            grams(ln, ing[ln["item"]])
        except ValueError as e:
            errs.append(f"{rid}: {e}")
    for s in recipe.get("swaps", []):
        for side in ("from", "to"):
            if s.get(side) not in ing:
                errs.append(f"{rid}: swap {side} unknown ingredient {s.get(side)}")
            elif ing[s[side]].get("conventional"):
                errs.append(f"{rid}: swap {side} {s[side]} is not a low-carb ingredient")
    items = {ln["item"] for ln in lines(recipe)}
    for s in recipe.get("vegan_swaps", []):
        frm, to = s.get("from"), s.get("to")
        if frm not in items:
            errs.append(f"{rid}: vegan swap from {frm}, which the recipe does not use")
        if to not in ing:
            errs.append(f"{rid}: vegan swap to unknown ingredient {to}")
        elif ing[to].get("conventional"):
            errs.append(f"{rid}: vegan swap to {to} is not a low-carb ingredient")
        elif is_animal(ing[to]):
            errs.append(f"{rid}: vegan swap to {to} is not vegan")
        if frm in {d.get("from") for d in recipe.get("swaps", [])}:
            errs.append(f"{rid}: {frm} has both a dairy-free and a vegan swap")
    alt = recipe.get("vegan_alternative")
    if alt is not None and (
        not isinstance(alt, dict) or not alt.get("recipe") or not alt.get("note")
    ):
        errs.append(f"{rid}: vegan_alternative needs a recipe id and a note")
    if not errs:
        unswapped = sorted(
            i
            for i in items
            if is_egg(ing[i]) and i not in {s["from"] for s in recipe.get("vegan_swaps", [])}
        )
        if unswapped and alt is None:
            errs.append(
                f"{rid}: egg ingredient(s) {', '.join(unswapped)} have no egg-free swap "
                "and the recipe names no vegan alternative"
            )
        for s in recipe.get("swaps", []):
            if is_animal(ing[s["to"]]) and "dairy" not in ing[s["to"]]["contains"]:
                errs.append(f"{rid}: dairy-free swap to {s['to']} is not vegan")
    if not errs:
        dairy = {ln["item"] for ln in lines(recipe) if "dairy" in ing[ln["item"]]["contains"]}
        swapped = {s["from"] for s in recipe.get("swaps", [])}
        for item in sorted(dairy - swapped):
            errs.append(f"{rid}: dairy ingredient {item} has no dairy-free swap")
        for s in recipe.get("swaps", []):
            if "dairy" in ing[s["to"]]["contains"]:
                errs.append(f"{rid}: swap to {s['to']} still contains dairy")
    return errs


@dataclass
class Version:
    """One way of making a recipe: its ingredient weights and nutrition."""

    total: Facts
    per_serving: Facts
    contains: list[str]


def version(recipe: dict, table: Table, dairy_free: bool = False, vegan: bool = False) -> Version:
    """As written, dairy-free (the dairy swaps), or vegan (those plus ``vegan_swaps``)."""
    ing = table.ingredients
    swaps = {s["from"]: s for s in recipe.get("swaps", [])} if dairy_free or vegan else {}
    if vegan:
        swaps |= {s["from"]: s for s in recipe.get("vegan_swaps", [])}
    total = Facts()
    contains: set[str] = set()
    for ln in lines(recipe):
        item, g = ln["item"], grams(ln, ing[ln["item"]])
        if item in swaps:
            s = swaps[item]
            item, g = s["to"], g * float(s.get("ratio", 1.0))
        total = total + table.facts(item, g)
        contains |= set(ing[item]["contains"])
    n = recipe["servings"]
    return Version(total=total, per_serving=total.scaled(1 / n), contains=sorted(contains))


def load_traditional() -> dict:
    return json.loads(resources.files("cookbook").joinpath("data/traditional.json").read_text())


@dataclass
class Conventional:
    """A rough conventional (not low-carb) version: the low-carb stand-ins
    swapped back to what an ordinary recipe uses. ``version`` is None when
    nothing in the recipe is a stand-in."""

    version: Version | None
    swaps: list[tuple[str, str | None, float]]  # (from, to or None = dropped, ratio)
    note: str


def conventional(recipe: dict, table: Table, trad: dict) -> Conventional:
    """Swap each low-carb stand-in for its conventional counterpart (as written
    otherwise, dairy included). An estimate for comparison, never a recipe."""
    over = trad.get("recipes", {}).get(recipe["id"], {})
    rules = {k: v for k, v in trad["swaps"].items() if k not in over.get("keep", [])}
    rules.update(over.get("swaps", {}))
    ing = table.ingredients
    total = Facts()
    applied: dict[str, tuple[str | None, float]] = {}
    for ln in lines(recipe):
        item, g = ln["item"], grams(ln, ing[ln["item"]])
        rule = rules.get(item)
        if rule is not None:
            ratio = float(rule.get("ratio", 1.0))
            applied[item] = (rule["to"], ratio)
            if rule["to"] is None:
                continue
            item, g = rule["to"], g * ratio
        total = total + table.facts(item, g)
    note = over.get("note", "")
    if not applied:
        return Conventional(None, [], note)
    n = recipe["servings"]
    v = Version(total=total, per_serving=total.scaled(1 / n), contains=[])
    return Conventional(v, [(k, t, r) for k, (t, r) in applied.items()], note)


def dairy_status(recipe: dict, table: Table) -> str:
    """'dairy-free' as written, or 'dairy-free option' through its swaps."""
    ing = table.ingredients
    has = any("dairy" in ing[ln["item"]]["contains"] for ln in lines(recipe))
    return "dairy-free option" if has else "dairy-free"


def vegan_status(recipe: dict, table: Table) -> str:
    """'vegan' as written, 'vegan option' through its swaps, else ''."""
    ing = table.ingredients
    animal = {ln["item"] for ln in lines(recipe) if is_animal(ing[ln["item"]])}
    if not animal:
        return "vegan"
    covered = {s["from"] for s in recipe.get("swaps", [])}
    covered |= {s["from"] for s in recipe.get("vegan_swaps", [])}
    return "vegan option" if animal <= covered else ""


def egg_status(recipe: dict, table: Table) -> str:
    """'egg-free' as written, 'egg-free option' through its swaps, else
    'alternative' (it names a similar vegan recipe instead)."""
    ing = table.ingredients
    eggs = {ln["item"] for ln in lines(recipe) if is_egg(ing[ln["item"]])}
    if not eggs:
        return "egg-free"
    if eggs <= {s["from"] for s in recipe.get("vegan_swaps", [])}:
        return "egg-free option"
    return "alternative"


def validate_book(recipes: list[dict], table: Table) -> list[str]:
    """Checks across recipes: every vegan alternative is a real, vegan recipe."""
    by_id = {r["id"]: r for r in recipes}
    errs = []
    for r in recipes:
        alt = r.get("vegan_alternative")
        if not alt:
            continue
        other = by_id.get(alt["recipe"])
        if other is None or other["id"] == r["id"]:
            errs.append(f"{r['id']}: vegan alternative {alt['recipe']} is not another recipe")
        elif vegan_status(other, table) not in VEGAN_STATUSES:
            errs.append(f"{r['id']}: vegan alternative {alt['recipe']} is not vegan")
    return errs
