"""Low-carb cookbook domain — desserts first, every recipe dairy-free or with a dairy-free swap.

Recipes are data (``data/recipes/*.json``); nutrition is computed from USDA
FoodData Central at build time, per serving, for both the recipe as written
and its dairy-free version. Each recipe also records where its kind of dish
comes from, so the site can map the book by historical region.

Discovered by the Facetwork runner via the ``facetwork.domains`` entry point::

    [project.entry-points."facetwork.domains"]
    cookbook = "cookbook:domain"
"""

from __future__ import annotations

from pathlib import Path

try:
    from facetwork.domains import DomainPackage
except ImportError:  # the recipe tools and the site build work without the runtime
    DomainPackage = None

if DomainPackage is not None:
    from .handlers import register_all_registry_handlers

    domain = DomainPackage(
        name="cookbook",
        ffl_dir=Path(__file__).parent / "ffl",
        register_handlers=register_all_registry_handlers,
    )
else:
    domain = None
