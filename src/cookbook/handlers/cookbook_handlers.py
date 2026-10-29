"""Thin dispatchers for the cookbook facets.

One ``handle(payload)`` entry point with a ``_DISPATCH`` table, because the
runner's handler cache is keyed on (module, entrypoint): several facets sharing
a module must share one entrypoint.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import sources


def _json(value: Any, default: Any) -> Any:
    """FFL may hand structured values over as JSON text."""
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def handle_sources(params: dict[str, Any]) -> dict[str, Any]:
    out = sources.plan()
    return {"sources": out, "count": len(out), "user_agent": sources.USER_AGENT}


def handle_site_build(params: dict[str, Any]) -> dict[str, Any]:
    """Validate every recipe, compute its nutrition, render the site, copy it to the maps store.

    Staged locally because an object store has no partial writes. An invalid
    recipe fails the step with every problem listed, rather than publishing a
    book with a hole in it.
    """
    from facetwork.domains.storage import is_remote, join

    from ..site import build_site
    from ..storage import S

    srcs = _json(params.get("sources"), [])
    paths = _json(params.get("paths"), [])
    if len(srcs) != len(paths):
        raise ValueError(f"{len(srcs)} sources but {len(paths)} fetched paths")
    local = {s["key"]: S.localize(p) for s, p in zip(srcs, paths)}
    if "fdc_sr_legacy" not in local:
        raise ValueError("missing source: fdc_sr_legacy")
    dest = join(S.maps_root(), "site", "cookbook")
    log = params.get("_step_log")
    with tempfile.TemporaryDirectory(prefix="cookbook_") as tmp:
        out = build_site(local["fdc_sr_legacy"], tmp, log=log)
        for rel in out["paths"]:
            target = join(dest, rel)
            if not is_remote(target):
                os.makedirs(os.path.dirname(target), exist_ok=True)
            S.write_bytes(target, Path(tmp, rel).read_bytes())
    return {
        "output_dir": dest,
        "files": out["files"],
        "bytes": out["bytes"],
        "recipes": out["stats"]["recipes"],
        "stats": out["stats"],
    }


_DISPATCH: dict[str, Callable[[dict], dict]] = {
    "cookbook.data.Sources": handle_sources,
    "cookbook.site.Build": handle_site_build,
}


def handle(payload: dict) -> dict:
    facet = payload.get("_facet_name", "")
    handler = _DISPATCH.get(facet)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register every facet with a RegistryRunner, all through ``handle``."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_poller(poller) -> None:
    """Register every facet with an AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
