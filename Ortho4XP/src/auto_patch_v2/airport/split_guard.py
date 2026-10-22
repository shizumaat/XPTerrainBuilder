"""THE SPLIT GUARD — which splits a DSF can carry (issue #1246).

A split re-anchors each body at its own point.  ``DSFTool --text2dsf``
refuses an object placed outside the DSF's tile (``ERROR: could not
place object LON, LAT``) and then refuses the WHOLE file, so one body of
a long object family that reached past the tile edge left every pack
object unconverted and unseated.  Two rules, both general:

* a split with a body anchor outside the tile box (the dump's
  ``PROPERTY sim/west|east|south|north``) is NOT made: the placement is
  written whole, as authored, and is listed as ``Kept``;
* a split whose body DSFTool still refuses is undone the same way and
  the write is tried again — one object never fails the pack.
"""
from __future__ import annotations

import dataclasses as _dc
import re
import typing as _t

from ..model.placement import Kept, PlacementPlan

__all__ = ["tile_box", "off_tile_splits", "refused_point", "split_at",
           "without_splits"]

_REFUSED = re.compile(r"could not place object\s+(-?[\d.]+)\s*,\s*(-?[\d.]+)")
#: a refused point is matched to a body anchor within this (deg, ~1 m)
_MATCH_DEG = 1e-5


def tile_box(text: str) -> tuple[float, float, float, float] | None:
    """``(west, south, east, north)`` from the dump's properties."""
    got: dict[str, float] = {}
    for raw in text.splitlines():
        toks = raw.split()
        if len(toks) == 3 and toks[0] == "PROPERTY" and toks[1] in (
                "sim/west", "sim/south", "sim/east", "sim/north"):
            got[toks[1][4:]] = float(toks[2])
    if len(got) != 4:
        return None
    return got["west"], got["south"], got["east"], got["north"]


def off_tile_splits(plan: PlacementPlan, box: _t.Sequence[float] | None
                    ) -> list[int]:
    """The placement indices of splits with a body anchor off the tile."""
    if box is None:
        return []
    w, s, e, n = box
    return [sp.placement.index for sp in plan.splits
            if any(not (w <= b.anchor.lon <= e and s <= b.anchor.lat <= n)
                   for b in sp.bodies)]


def refused_point(message: str) -> tuple[float, float] | None:
    """``(lon, lat)`` of the object DSFTool said it could not place."""
    m = _REFUSED.search(message or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def split_at(plan: PlacementPlan, lon: float, lat: float) -> int | None:
    """The split whose body is anchored at ``(lon, lat)``, if any."""
    for sp in plan.splits:
        for b in sp.bodies:
            if (abs(b.anchor.lon - lon) <= _MATCH_DEG
                    and abs(b.anchor.lat - lat) <= _MATCH_DEG):
                return sp.placement.index
    return None


def without_splits(plan: PlacementPlan, indices: _t.Collection[int],
                   reason: str) -> PlacementPlan:
    """``plan`` with those splits undone: each placement is ``Kept``."""
    idx = set(indices)
    gone = [sp for sp in plan.splits if sp.placement.index in idx]
    if not gone:
        return plan
    return _dc.replace(
        plan, splits=tuple(sp for sp in plan.splits
                           if sp.placement.index not in idx),
        kept=plan.kept + tuple(Kept(sp.placement.index, sp.placement.resource,
                                    reason) for sp in gone))
