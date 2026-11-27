"""A HARD DECK NEEDS SOMETHING PASSING UNDER IT (owner 2026-11-27T00:15Z on
PHLI's front kerb, asked whether a road or trench runs under it: "No,
that's just road and parking lot, one level"; lane lfront3 round 3).

``planar/deck_bridge`` reads a pack deck the airport's pavement drives
across as a HARD-DECK BRIDGE (RULINGS 2026-10-30a): its floor is cut
``[tunnel] clearance_m`` (or the frame's bottom) under the deck, and a
walled frame's floor holds every vertex between its walls there
(``constraints/walled_floor``).  The witness was the pavement ACROSS the
deck alone.  MEASURED PHLI: ``terminal-tiki-walls.obj`` (``dsf:obj7663``,
an ``ATTR_hard_deck`` plate over the whole 21,468 m2 terminal frontage)
read as a bridge whose walled floor stood 5.0 m under the kerb -- the
kerb road and its corridor held 3-4 m under the forecourt -- while the
ways under it only clip its corners (road -552 5.1 m, -389 2.5 m,
footways under 3 m).

THE RULE (:func:`passes_under`): a deck piece is a bridge only where
something crosses UNDER it -- a mapped way (road, rail, waterway, a mapped
tunnel's ramp) whose run inside the piece is at least half the piece's
narrow width (its minimum rotated rectangle's short side: a bridge spans
what passes under it, which runs the deck's width), or a co-placed trench
object stating its walls (the caller's ``walled``).  Without one the deck
is no bridge: the object seats at grade and the ground is one level.
Nothing here names an airport."""
from __future__ import annotations

from shapely.geometry import LineString

__all__ = ["UNDER_SHARE", "UNDER_TAGS", "passes_under"]

#: the share of a piece's narrow width a way runs under it to cross it
UNDER_SHARE = 0.5
#: the mapped ways that pass under a deck
UNDER_TAGS = ("highway", "railway", "waterway")


def _narrow(piece) -> float:
    r = piece.minimum_rotated_rectangle
    c = list(r.exterior.coords)
    if len(c) < 4:
        return 0.0
    a = LineString(c[:2]).length
    b = LineString(c[1:3]).length
    return min(a, b)


def passes_under(piece, airport) -> list[tuple[object, float]]:
    """``[(way id, its run inside the piece)]`` of every mapped way that
    crosses UNDER the deck piece (module docstring); ``[]`` where none."""
    need = UNDER_SHARE * _narrow(piece)
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if not any(tags.get(k) for k in UNDER_TAGS) or len(w.points) < 2:
            continue
        x = LineString(w.points).intersection(piece)
        run = max((g.length for g in getattr(x, "geoms", [x]) if g.geom_type == "LineString"),
                  default=0.0)
        if run > 0.0 and run >= need:
            out.append((getattr(w, "id", None), round(run, 1)))
    return out
