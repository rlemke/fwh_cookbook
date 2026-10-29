"""The one file the nutrition comes from.

USDA FoodData Central's SR Legacy release (April 2018, the final release of
the Standard Reference database; public domain). It no longer changes, so a
conditional GET answers 304 on every later run.
"""

from __future__ import annotations

from .storage import raw_path

FDC_SR_LEGACY = (
    "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
)
USER_AGENT = "facetwork-cookbook/0.1 (+https://github.com/rlemke/fwh_cookbook)"


def plan() -> list[dict]:
    return [
        {
            "key": "fdc_sr_legacy",
            "url": FDC_SR_LEGACY,
            "dest": raw_path("FoodData_Central_sr_legacy_food_csv_2018-04.zip"),
            "max_age_hours": 0.0,
        }
    ]
