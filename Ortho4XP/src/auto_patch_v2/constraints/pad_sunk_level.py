"""THE HELD TERRACE BELOW THE AIRSIDE SITS AT ITS OWN GROUND (issue #2188
item 2; ``classify/pad_sunk`` holds the pad off the airside it touches).

A held pad fronts nothing, so no frontage row levels it, and the §9b
ground it would otherwise follow is read at its RIM — the bund crest or
the slope it is cut into, never the floor the objects stand on (MEASURED
ELLX ``building49``: rim DEM 348-372 m, its area's median 360.4 m).  ONE
row pair per pad face here holds the face's MEAN at the pad's own ground
(``PlanarMap.sunk_pads``, the median DEM over its area): a level row,
never a per-vertex pull, so the plate (``pads.pad_flats``) stays one
plane.  It carries §20's level head (``pads.LEVEL_RULING``), so it is
priced as a pad's level is — one-way, the pad the follower."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .pads import GEN_LEVEL, LEVEL_RULING, _pad_groups

__all__ = ["pad_sunk_level"]


def pad_sunk_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The level rows (module docstring).  A generator."""
    levels = getattr(planar, "sunk_pads", None) or {}
    if not levels:
        return []
    rows: list[Row] = []
    for fid, ref, group in _pad_groups(planar, law):
        target = levels.get(str(ref))
        if target is None or not group:
            continue
        terms = tuple((v, 1.0 / len(group)) for v in group)
        src = Source(GEN_LEVEL, LEVEL_RULING + " (#2188 held terrace at its own ground)",
                     (f"face:{fid}", str(ref)))
        follows = tuple(group)
        rows += [Linear(terms, None, float(target), src, follows=follows),
                 Linear(tuple((v, -c) for v, c in terms), None, -float(target), src,
                        follows=follows)]
    return rows
