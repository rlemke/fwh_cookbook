"""Where the cookbook keeps its downloads and pages: the shared domain storage layer."""

from __future__ import annotations

from facetwork.domains.storage import domain_storage, join

S = domain_storage("cookbook", layout="flat")


def raw_path(name: str) -> str:
    return join(S.cache_root(), "raw", name)
