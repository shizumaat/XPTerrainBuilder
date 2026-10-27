"""THE RUNWAY-END CROSS-CHECK SOURCES (owner RULINGS 2026-10-25a, 26a;
issue #1342): per-end elevations from open data, read ONLY from an
explicit, hash-stamped cache.

The cross-check order is law (``law/runway_ends.toml`` ``crosscheck_order``:
FAA NASR → openAIP → OurAirports).  Each source is ONE provider module,
named ``runway_ref_<source>`` in this package and listed in
:data:`PROVIDERS`, exposing ``NAME``,
``ATTRIBUTION``, ``cache_path(mod_cache_root)``, ``lookup(icao,
mod_cache_root) -> {designator: RefEnd}`` and ``refresh(mod_cache_root)``.
A source in the order with no provider module, or with no cache on disk,
is skipped — so a build with no cache verifies on the DEM-only rules
(spec ``docs/findings/lrwypin-runway-end-pins.md`` §3).

THE BUILD NEVER FETCHES.  ``refresh`` is the provider's download, and its
only caller is the harness scope ``--refresh-data runway_refs`` (BUILD
ECONOMY; the refresh ledger records it).  The cache lives under the
airport mod cache (``Airport_mod_cache/_runway_refs/<source>/``), the data
root every build already mounts.
"""
from __future__ import annotations

import os
import typing as _t

from . import runway_ref_ourairports
from .runway_ref_record import REFS_DIR, RefEnd

__all__ = ["RefEnd", "REFS_DIR", "PROVIDERS", "providers", "lookup"]

#: THE PROVIDERS, by source name (imported statically: a module named in a
#: string is invisible to the import closure and to the freezer).  A new
#: source is a new ``runway_ref_<name>.py`` and one entry here.
PROVIDERS: dict[str, _t.Any] = {runway_ref_ourairports.NAME: runway_ref_ourairports}


def providers(order: _t.Sequence[str]) -> list[_t.Any]:
    """The provider modules of ``order`` that exist, in order (a source
    with no module yet — NASR and openAIP, follow-ups F1/F2 — is skipped)."""
    return [PROVIDERS[n] for n in order if n in PROVIDERS]


def lookup(icao: str, mod_cache_root: str | None, order: _t.Sequence[str]
           ) -> list[tuple[str, dict[str, RefEnd]]]:
    """``[(source, {designator: RefEnd})]`` for every provider of
    ``order`` whose cache holds this airport, in order.  Empty with no
    cache root, no cache file, or no rows — never a fetch."""
    if not mod_cache_root or not os.path.isdir(mod_cache_root):
        return []
    out = []
    for mod in providers(order):
        ends = mod.lookup(icao, mod_cache_root)
        if ends:
            out.append((mod.NAME, ends))
    return out
