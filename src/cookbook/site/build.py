"""Render the cookbook: index with the origins map, one page per recipe, the
whole book on one printable page, and the method page.

Pages depend only on the recipes and the nutrition table — never the build
clock — so an unchanged book renders identical bytes and publishes nothing.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from ..fmt import line, minutes
from ..nutrition import FIELDS, Table, build_table
from ..recipes import (
    ALLERGENS,
    CATEGORIES,
    DESSERT_CATEGORIES,
    conventional,
    dairy_status,
    lines,
    load_recipes,
    load_traditional,
    validate,
    version,
)

REGIONS = [
    "North America",
    "Latin America & Caribbean",
    "Western Europe",
    "Southern Europe",
    "Northern Europe",
    "Central & Eastern Europe",
    "Middle East & North Africa",
    "Sub-Saharan Africa",
    "South Asia",
    "East Asia",
    "Southeast Asia",
    "Oceania",
]
TITLE = "The Low-Carb Kitchen"
SUBTITLE = "Desserts first — and a dairy-free way to make every recipe"


def _script_json(v) -> Markup:
    """JSON safe to inline in a <script> block: no autoescaping, no '</'."""
    text = json.dumps(v, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return Markup(text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("cookbook", "site/templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["minutes"] = minutes
    env.filters["tojson_compact"] = _script_json
    return env


def recipe_view(r: dict, table: Table, trad: dict | None = None) -> dict:
    ing = table.ingredients
    written, df = version(r, table), version(r, table, dairy_free=True)
    conv = conventional(r, table, trad if trad is not None else load_traditional())
    conv_swaps = [
        {
            "from": ing[a]["name"],
            "to": ing[b]["name"] if b else None,
            "ratio": ratio,
        }
        for a, b, ratio in conv.swaps
    ]
    groups: list[dict] = []
    for ln in r["ingredients"]:
        if "group" in ln:
            groups.append({"name": ln["group"], "lines": []})
            continue
        if not groups:
            groups.append({"name": "", "lines": []})
        measure, rest = line(ln, ing[ln["item"]])
        groups[-1]["lines"].append({"measure": measure, "text": rest, "item": ln["item"]})
    swaps = [
        {
            "from": ing[s["from"]]["name"],
            "to": ing[s["to"]]["name"],
            "ratio": s.get("ratio", 1.0),
            "note": s.get("note", ""),
        }
        for s in r.get("swaps", [])
    ]
    label_items = sorted(
        {ing[ln["item"]]["name"] for ln in lines(r) if table.source[ln["item"]] == "label"}
    )
    notes = sorted(
        {ing[ln["item"]]["dairy_note"] for ln in lines(r) if ing[ln["item"]].get("dairy_note")}
    )
    t = r.get("time", {})
    return {
        **r,
        "chapter": CATEGORIES[r["category"]],
        "dessert": r["category"] in DESSERT_CATEGORIES,
        "groups": groups,
        "swaps": swaps,
        "dairy": dairy_status(r, table),
        "per": written.per_serving.as_dict(),
        "per_df": df.per_serving.as_dict(),
        "per_conv": conv.version.per_serving.as_dict() if conv.version else None,
        "conv_swaps": conv_swaps,
        "conv_note": conv.note,
        "contains": [ALLERGENS[a] for a in written.contains],
        "contains_df": [ALLERGENS[a] for a in df.contains],
        "free_of": sorted({ALLERGENS[a] for a in ALLERGENS} - {ALLERGENS[a] for a in df.contains}),
        "label_items": label_items,
        "label_notes": notes,
        "total_min": sum(int(t.get(k, 0)) for k in ("prep_min", "cook_min", "rest_min")),
        "time": t,
    }


def load_menus() -> list[dict]:
    return json.loads(resources.files("cookbook").joinpath("data/menus.json").read_text())["menus"]


def menu_view(m: dict, by_id: dict[str, dict]) -> dict:
    """A menu with each item's recipe view and plate totals: one serving of every
    dish that is not an alternative, as written, dairy-free and not low-carb."""
    keys = ("net_carbs_g", "carbs_g", "fat_g", "protein_g", "kcal")
    totals = {k: {"per": 0.0, "per_df": 0.0, "per_conv": 0.0} for k in keys}
    courses = []
    for c in m["courses"]:
        items = []
        for it in c["items"]:
            v = by_id[it["recipe"]]
            batches = -(-int(m["people"]) // int(v["servings"]))
            items.append({"alt": bool(it.get("alt")), "r": v, "batches": batches})
            if it.get("alt"):
                continue
            for k in keys:
                totals[k]["per"] += v["per"][k]
                totals[k]["per_df"] += v["per_df"][k]
                totals[k]["per_conv"] += (v["per_conv"] or v["per"])[k]
        courses.append({"name": c["name"], "dishes": items})
    totals = {
        k: {s: round(x) if k == "kcal" else round(x, 1) for s, x in t.items()}
        for k, t in totals.items()
    }
    dishes = [i["r"] for c in courses for i in c["dishes"]]
    return {
        **m,
        "courses": courses,
        "totals": totals,
        "dairy_free_as_written": all(d["dairy"] == "dairy-free" for d in dishes),
        "count": len(dishes),
    }


def _card(v: dict) -> dict:
    """The fields the index's filter script needs, nothing more."""
    return {
        "id": v["id"],
        "t": v["title"],
        "c": v["category"],
        "n": v["per"]["net_carbs_g"],
        "nd": v["per_df"]["net_carbs_g"],
        "k": v["per"]["kcal"],
        "d": v["dairy"] == "dairy-free",
        "x": v["contains_df"],
        "f": v["origin"]["family"],
        "p": v["origin"]["place"],
        "r": v["origin"]["region"],
    }


def _places(views: list[dict]) -> list[dict]:
    by: dict[tuple, dict] = {}
    for v in views:
        o = v["origin"]
        key = (round(float(o["lat"]), 1), round(float(o["lon"]), 1))
        p = by.setdefault(
            key,
            {"lat": key[0], "lon": key[1], "place": o["place"], "region": o["region"], "items": []},
        )
        p["items"].append({"id": v["id"], "t": v["title"], "f": o["family"], "e": o["era"]})
    out = sorted(by.values(), key=lambda p: (p["region"], p["place"]))
    for p in out:
        p["items"].sort(key=lambda i: i["t"])
    return out


def build_site(fdc_zip: str, out_dir: str, log=None) -> dict:
    table = build_table(fdc_zip)
    recipes = load_recipes()
    errors = [e for r in recipes for e in validate(r, table)]
    if errors:
        raise ValueError("invalid recipes:\n  " + "\n  ".join(errors))
    for r in recipes:
        if r["origin"]["region"] not in REGIONS:
            raise ValueError(f"{r['id']}: unknown region {r['origin']['region']}")
    trad = load_traditional()
    views = [recipe_view(r, table, trad) for r in recipes]
    order = list(CATEGORIES)
    views.sort(key=lambda v: (order.index(v["category"]), v["title"].lower()))
    chapters = [
        {"key": c, "name": CATEGORIES[c], "recipes": [v for v in views if v["category"] == c]}
        for c in order
    ]
    chapters = [c for c in chapters if c["recipes"]]
    regions = defaultdict(list)
    for v in views:
        regions[v["origin"]["region"]].append(v)
    region_list = [
        {"name": r, "recipes": sorted(regions[r], key=lambda v: v["origin"]["family"])}
        for r in REGIONS
        if r in regions
    ]
    desserts = [v for v in views if v["dessert"]]
    stats = {
        "recipes": len(views),
        "desserts": len(desserts),
        "dairy_free": sum(1 for v in views if v["dairy"] == "dairy-free"),
        "dairy_option": sum(1 for v in views if v["dairy"] != "dairy-free"),
        "places": len(_places(views)),
        "regions": len(region_list),
        "median_net_dessert": sorted(v["per"]["net_carbs_g"] for v in desserts)[len(desserts) // 2]
        if desserts
        else 0,
        "max_net_dessert": max((v["per"]["net_carbs_g"] for v in desserts), default=0),
    }
    used = Counter(ln["item"] for r in recipes for ln in lines(r))
    used |= Counter(s["to"] for r in recipes for s in r.get("swaps", []))
    ingredient_rows = [
        {
            "key": k,
            "name": table.ingredients[k]["name"],
            "source": table.source[k],
            "per100": table.per100[k].as_dict(),
            "uses": used[k],
            "usda": table.ingredients[k].get("usda", ""),
            "usda_note": table.ingredients[k].get("usda_note", ""),
        }
        for k in sorted(used, key=lambda k: table.ingredients[k]["name"])
    ]
    swap_counts = Counter((s["from"], s["to"]) for r in recipes for s in r.get("swaps", []))
    swap_rows = [
        {"from": table.ingredients[a]["name"], "to": table.ingredients[b]["name"], "uses": n}
        for (a, b), n in sorted(swap_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    by_id = {v["id"]: v for v in views}
    menus = load_menus()
    missing = [
        (m["id"], it["recipe"])
        for m in menus
        for c in m["courses"]
        for it in c["items"]
        if it["recipe"] not in by_id
    ]
    if missing:
        raise ValueError(f"menus name unknown recipes: {missing}")
    menu_views = [menu_view(m, by_id) for m in menus]
    in_menus = defaultdict(list)
    for mv in menu_views:
        for c in mv["courses"]:
            for it in c["dishes"]:
                if mv not in in_menus[it["r"]["id"]]:
                    in_menus[it["r"]["id"]].append(mv)
    for v in views:
        v["menus"] = [{"id": mv["id"], "title": mv["title"]} for mv in in_menus[v["id"]]]
    env = _env()
    ctx = {
        "menus": menu_views,
        "title": TITLE,
        "subtitle": SUBTITLE,
        "chapters": chapters,
        "regions": region_list,
        "stats": stats,
        "cards": [_card(v) for v in views],
        "places": _places(views),
        "region_names": [r["name"] for r in region_list],
        "categories": [(c["key"], c["name"]) for c in chapters],
        "ingredients": ingredient_rows,
        "fields": FIELDS,
        "swap_rows": swap_rows,
    }
    out = Path(out_dir)
    pages = {
        "index.html": env.get_template("index.html").render(page="index", root="", **ctx),
        "book.html": env.get_template("book.html").render(page="book", root="", **ctx),
        "about.html": env.get_template("about.html").render(page="about", root="", **ctx),
        "menus.html": env.get_template("menus.html").render(page="menus", root="", **ctx),
    }
    mtpl = env.get_template("menu.html")
    for mv in menu_views:
        pages[f"menus/{mv['id']}.html"] = mtpl.render(page="menus", root="../", m=mv, **ctx)
    tpl = env.get_template("recipe.html")
    for i, v in enumerate(views):
        prev = views[i - 1] if i else None
        nxt = views[i + 1] if i + 1 < len(views) else None
        pages[f"recipes/{v['id']}.html"] = tpl.render(
            page="recipe", root="../", r=v, prev=prev, next=nxt, **ctx
        )
    total = 0
    for rel, html in sorted(pages.items()):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        data = html.encode("utf-8")
        p.write_bytes(data)
        total += len(data)
    if log:
        log(
            f"{len(views)} recipes ({stats['desserts']} desserts) in {len(chapters)} chapters, {stats['places']} places",
            level="info",
        )
    return {"paths": sorted(pages), "files": len(pages), "bytes": total, "stats": stats}
