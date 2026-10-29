from __future__ import annotations

import copy

import pytest

from cookbook.fmt import amount, line, minutes
from cookbook.nutrition import build_table
from cookbook.recipes import (
    conventional,
    grams,
    load_recipes,
    load_traditional,
    validate,
    version,
)
from cookbook.site.build import REGIONS, build_site


@pytest.fixture(scope="module")
def table(fdc_zip):
    return build_table(fdc_zip)


def test_every_recipe_is_valid(table):
    recipes = load_recipes()
    assert len(recipes) >= 100
    errs = [e for r in recipes for e in validate(r, table)]
    assert errs == []


def test_ids_match_and_are_unique():
    ids = [r["id"] for r in load_recipes()]
    assert len(ids) == len(set(ids))


def test_every_origin_is_placed(table):
    for r in load_recipes():
        o = r["origin"]
        assert o["region"] in REGIONS, r["id"]
        assert -90 <= float(o["lat"]) <= 90 and -180 <= float(o["lon"]) <= 180, r["id"]
        assert len(o["history"]) > 60, r["id"]


def test_measures_convert_through_the_ingredients_own_weight(table):
    ing = table.ingredients
    assert grams({"item": "almond_flour", "cup": 1}, ing["almond_flour"]) == 96
    assert grams({"item": "almond_flour", "tbsp": 1}, ing["almond_flour"]) == 6
    assert grams({"item": "egg", "each": 3}, ing["egg"]) == 150
    with pytest.raises(ValueError):
        grams({"item": "egg", "cup": 1}, ing["egg"])


def test_net_carbs_subtract_fibre_and_polyols(table):
    r = {
        "id": "t",
        "servings": 2,
        "ingredients": [{"item": "erythritol", "g": 100}, {"item": "coconut_flour", "g": 100}],
    }
    v = version(r, table).total
    assert v.carbs_g == pytest.approx(160)
    assert v.net_carbs_g == pytest.approx(160 - 33.3 - 100)


def test_dairy_needs_a_swap_and_the_swap_changes_the_numbers(table):
    base = {
        "id": "t",
        "title": "T",
        "category": "cakes",
        "summary": "s",
        "servings": 1,
        "steps": ["x"],
        "origin": {
            "family": "f",
            "place": "p",
            "region": "Oceania",
            "lat": 0,
            "lon": 0,
            "era": "e",
            "history": "h",
        },
        "ingredients": [{"item": "butter", "g": 100}],
    }
    assert any("no dairy-free swap" in e for e in validate(base, table))
    ok = copy.deepcopy(base)
    ok["swaps"] = [{"from": "butter", "to": "vegan_butter"}]
    assert validate(ok, table) == []
    assert version(ok, table, dairy_free=True).contains == []
    bad = copy.deepcopy(base)
    bad["swaps"] = [{"from": "butter", "to": "heavy_cream"}]
    assert any("still contains dairy" in e for e in validate(bad, table))


def test_formatting():
    assert amount(1.5) == "1½" and amount(0.333) == "⅓" and amount(2) == "2"
    assert minutes(480) == "8 h" and minutes(75) == "1 h 15 min" and minutes(1440) == "1 day"


def test_ingredient_line_shows_grams_for_spoons(table):
    m, rest = line({"item": "almond_flour", "cup": 1.5}, table.ingredients["almond_flour"])
    assert m == "1½ cups" and "(144 g)" in rest
    m, rest = line({"item": "egg", "each": 2}, table.ingredients["egg"])
    assert (m, rest) == ("2", "large eggs")


def test_site_builds_and_is_deterministic(fdc_zip, tmp_path):
    a = build_site(fdc_zip, str(tmp_path / "a"))
    build_site(fdc_zip, str(tmp_path / "b"))
    from cookbook.site.build import load_menus

    assert a["files"] == len(load_recipes()) + 4 + len(load_menus())
    for rel in a["paths"]:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes(), rel
    index = (tmp_path / "a" / "index.html").read_text()
    assert "leaflet@1.9.4" in index and 'id="map"' in index


def test_no_unknown_description_is_silently_zero(tmp_path):
    import zipfile

    from cookbook.nutrition import read_sr_legacy

    p = tmp_path / "z.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("food.csv", '"fdc_id","description"\n"1","Butter, salted"\n')
        z.writestr("food_nutrient.csv", '"fdc_id","nutrient_id","amount"\n')
    with pytest.raises(ValueError, match="not in SR Legacy"):
        read_sr_legacy(str(p), {"Butter, salted", "Nonexistent food"})


def test_conventional_estimate_swaps_stand_ins_back(table):
    trad = load_traditional()
    r = {
        "id": "t",
        "servings": 1,
        "ingredients": [
            {"item": "almond_flour", "g": 100},
            {"item": "erythritol", "g": 100},
            {"item": "xanthan_gum", "g": 2},
            {"item": "egg", "each": 1},
        ],
    }
    c = conventional(r, table, trad)
    want = table.facts("wheat_flour", 100) + table.facts("sugar", 70) + table.facts("egg", 50)
    assert c.version.per_serving.net_carbs_g == pytest.approx(want.net_carbs_g)
    assert c.version.per_serving.polyol_g == 0
    assert ("xanthan_gum", None, 1.0) in c.swaps
    # nothing to swap -> no estimate
    assert (
        conventional(
            {"id": "t", "servings": 1, "ingredients": [{"item": "egg", "each": 2}]}, table, trad
        ).version
        is None
    )
    # a dish may keep an ingredient its traditional form uses too
    kept = conventional(
        {"id": "marzipan", "servings": 1, "ingredients": [{"item": "almond_flour", "g": 100}]},
        table,
        trad,
    )
    assert kept.version is None


def test_conventional_ingredients_are_not_allowed_in_recipes(table):
    r = {
        "id": "t",
        "title": "T",
        "category": "cakes",
        "summary": "s",
        "servings": 1,
        "steps": ["x"],
        "origin": {
            "family": "f",
            "place": "p",
            "region": "Oceania",
            "lat": 0,
            "lon": 0,
            "era": "e",
            "history": "h",
        },
        "ingredients": [{"item": "sugar", "g": 10}],
    }
    assert any("not a low-carb ingredient" in e for e in validate(r, table))
    trad = load_traditional()
    for k, rule in trad["swaps"].items():
        assert k in table.ingredients and (rule["to"] is None or rule["to"] in table.ingredients)
    for rid in trad["recipes"]:
        assert rid in {x["id"] for x in load_recipes()}, rid


def test_every_menu_names_real_recipes_and_totals_skip_alternatives(table):
    from cookbook.site.build import load_menus, menu_view, recipe_view

    by_id = {r["id"]: recipe_view(r, table) for r in load_recipes()}
    for m in load_menus():
        for c in m["courses"]:
            assert c["items"], (m["id"], c["name"])
            assert not c["items"][0].get("alt"), f"{m['id']}: an 'or' item needs one before it"
            for it in c["items"]:
                assert it["recipe"] in by_id, (m["id"], it["recipe"])
        mv = menu_view(m, by_id)
        want = sum(
            by_id[it["recipe"]]["per"]["net_carbs_g"]
            for c in m["courses"]
            for it in c["items"]
            if not it.get("alt")
        )
        assert mv["totals"]["net_carbs_g"]["per"] == pytest.approx(want, abs=0.1)
