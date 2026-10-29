"""A tiny synthetic FoodData Central zip, so tests run offline.

It carries every SR Legacy description the ingredient vocabulary names, each
with simple made-up nutrient values, plus the nutrient rows the reader looks
for.
"""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

from cookbook.nutrition import load_ingredients

DIR = "FoodData_Central_sr_legacy_food_csv_2018-04/"


def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, quoting=csv.QUOTE_ALL).writerows(rows)
    return buf.getvalue()


@pytest.fixture(scope="session")
def fdc_zip(tmp_path_factory) -> str:
    descs = sorted({v["usda"] for v in load_ingredients().values() if "usda" in v})
    food = [["fdc_id", "data_type", "description", "food_category_id", "publication_date"]]
    nutr = [
        [
            "id",
            "fdc_id",
            "nutrient_id",
            "amount",
            "data_points",
            "derivation_id",
            "min",
            "max",
            "median",
            "footnote",
            "min_year_acquired",
        ]
    ]
    n = 1
    for i, d in enumerate(descs, start=100000):
        food.append([i, "sr_legacy_food", d, "1", "2019-04-01"])
        # 100 kcal, 5 fat, 5 protein, 10 carbs, 2 fibre, 3 sugars per 100 g
        for nid, amt in (
            ("1008", 100),
            ("1004", 5),
            ("1003", 5),
            ("1005", 10),
            ("1079", 2),
            ("2000", 3),
        ):
            nutr.append([n, i, nid, amt, "", "", "", "", "", "", ""])
            n += 1
    food.append([999999, "sr_legacy_food", "Not an ingredient", "1", "2019-04-01"])
    p = tmp_path_factory.mktemp("fdc") / "sr.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(DIR + "food.csv", _csv(food))
        z.writestr(DIR + "food_nutrient.csv", _csv(nutr))
    return str(p)
