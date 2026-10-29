"""Validate recipe files and print each one's net carbs per serving.

    python tools/check_recipes.py --fdc <FoodData_Central_sr_legacy_food_csv_*.zip> [recipe.json ...]

With no files, checks every recipe in the package. Exit 1 if any is invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cookbook.nutrition import build_table  # noqa: E402
from cookbook.recipes import (  # noqa: E402
    DESSERT_CATEGORIES,
    dairy_status,
    load_recipes,
    validate,
    version,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fdc", required=True)
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    table = build_table(a.fdc)
    recs = [json.loads(Path(f).read_text()) for f in a.files] if a.files else load_recipes()
    bad = 0
    for r in recs:
        errs = validate(r, table)
        if errs:
            bad += 1
            print("INVALID", *errs, sep="\n  ")
            continue
        v, df = version(r, table), version(r, table, dairy_free=True)
        p, q = v.per_serving, df.per_serving
        limit = {"sauces": (3, 4), "mains": (10, 12), "sides": (10, 12)}.get(
            r["category"], (8, 10) if r["category"] in DESSERT_CATEGORIES else None
        )
        flag = "  HIGH" if limit and (p.net_carbs_g > limit[0] or q.net_carbs_g > limit[1]) else ""
        print(
            f"{r['id']:<40} net {p.net_carbs_g:4.1f} g (dairy-free {q.net_carbs_g:4.1f}) "
            f"{round(p.kcal):4d} kcal  polyol {p.polyol_g:4.1f}  [{dairy_status(r, table)}]{flag}"
        )
    print(f"{len(recs)} recipes, {bad} invalid", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
