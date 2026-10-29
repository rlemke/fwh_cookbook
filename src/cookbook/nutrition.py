"""Nutrition per ingredient and per serving, from USDA FoodData Central.

Base foods come from the SR Legacy release (public domain), read straight
from its CSV zip. Foods it does not carry — low-carb sweeteners, coconut
flour, dairy-free products — carry typical label values in
``data/ingredients.json`` and are reported as such.

**Net carbs** are total carbohydrate minus dietary fibre minus sugar
alcohols and allulose (``polyol_g``). That is the common low-carb
convention, not a regulatory one, so the polyol grams are always shown
beside it: erythritol and allulose barely raise blood glucose, but some
readers count them anyway.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from importlib import resources

# SR Legacy nutrient ids.
NUTRIENTS = {
    "1008": "kcal",
    "1003": "protein_g",
    "1004": "fat_g",
    "1005": "carbs_g",
    "1079": "fiber_g",
    "2000": "sugars_g",
}
FIELDS = ("kcal", "fat_g", "protein_g", "carbs_g", "fiber_g", "sugars_g", "polyol_g")


def load_ingredients() -> dict[str, dict]:
    raw = json.loads(resources.files("cookbook").joinpath("data/ingredients.json").read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _member(z: zipfile.ZipFile, name: str) -> str:
    for n in z.namelist():
        if n.rsplit("/", 1)[-1] == name:
            return n
    raise KeyError(f"{name} not in the FoodData Central zip")


def read_sr_legacy(zip_path: str, wanted: set[str]) -> dict[str, dict]:
    """Per-100 g values for each wanted SR Legacy description.

    Returns ``{description: {"fdc_id", kcal, fat_g, ...}}``. A description
    that is not in the release raises, so a renamed food is noticed rather
    than silently counted as zero.
    """
    with zipfile.ZipFile(zip_path) as z:
        with z.open(_member(z, "food.csv")) as f:
            ids = {
                r["fdc_id"]: r["description"]
                for r in csv.DictReader(io.TextIOWrapper(f, "utf-8"))
                if r["description"] in wanted
            }
        missing = wanted - set(ids.values())
        if missing:
            raise ValueError(f"not in SR Legacy: {sorted(missing)}")
        out = {d: {"fdc_id": int(i), **dict.fromkeys(FIELDS, 0.0)} for i, d in ids.items()}
        with z.open(_member(z, "food_nutrient.csv")) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, "utf-8")):
                d = ids.get(r["fdc_id"])
                k = NUTRIENTS.get(r["nutrient_id"])
                if d and k and r["amount"]:
                    out[d][k] = float(r["amount"])
    return out


@dataclass
class Facts:
    """Nutrition of an amount of food (not per 100 g)."""

    kcal: float = 0.0
    fat_g: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fiber_g: float = 0.0
    sugars_g: float = 0.0
    polyol_g: float = 0.0

    @property
    def net_carbs_g(self) -> float:
        return max(0.0, self.carbs_g - self.fiber_g - self.polyol_g)

    def __add__(self, o: Facts) -> Facts:
        return Facts(*(getattr(self, k) + getattr(o, k) for k in FIELDS))

    def scaled(self, f: float) -> Facts:
        return Facts(*(getattr(self, k) * f for k in FIELDS))

    def as_dict(self) -> dict:
        d = {k: round(getattr(self, k), 1) for k in FIELDS}
        d["kcal"] = round(self.kcal)
        d["net_carbs_g"] = round(self.net_carbs_g, 1)
        return d


@dataclass
class Table:
    """Per-100 g facts for every ingredient key, and where each came from."""

    per100: dict[str, Facts]
    source: dict[str, str]  # key -> "usda:<fdc_id>" or "label"
    ingredients: dict[str, dict] = field(default_factory=dict)

    def facts(self, key: str, grams: float) -> Facts:
        return self.per100[key].scaled(grams / 100.0)


def build_table(zip_path: str, ingredients: dict[str, dict] | None = None) -> Table:
    ing = ingredients if ingredients is not None else load_ingredients()
    sr = read_sr_legacy(zip_path, {v["usda"] for v in ing.values() if "usda" in v})
    per100, source = {}, {}
    for k, v in ing.items():
        if "usda" in v:
            row = sr[v["usda"]]
            per100[k] = Facts(*(row[f] for f in FIELDS))
            source[k] = f"usda:{row['fdc_id']}"
        elif "label" in v:
            per100[k] = Facts(*(float(v["label"].get(f, 0.0)) for f in FIELDS))
            source[k] = "label"
        else:
            raise ValueError(f"ingredient {k} has neither 'usda' nor 'label'")
    return Table(per100=per100, source=source, ingredients=ing)
