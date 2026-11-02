"""THE WALL SLOPE: THE HILL OVER A RETAINING WALL GRADES TO ITS TOP (issue
#1661; owner RULINGS 2026-10-29a Q299 (a): "the top of a retaining wall,
which the hill grades down to, is the wall object's top edge as it sits.
The grass embankment above it is graded ground, and the back of the wall
is buried").

A retaining wall's upper band (``airport/wall_sides``: ``smear`` wide beside
its upper face) is where the lidar DEM smears the step, so ground left to
the mesh there falls away from the wall's top (KATL ``muro_27R.obj``,
capture on f82de7dfe: 0.2-8.1 m under its top along 479 m).  The band a
runway or taxiway grades stops short of it (spec §3 (2),
``wall_sides.band_setbacks``), and most of it lies past any band at all
(71 % at ``muro_27R``).  So that band is graded ground of its own: one
``graded_strip`` piece per part of it no other region holds, its ref under
``model/wall_reach.WALL_SLOPE_REF_PREFIX`` (a zone region's family, no zone
class — the zone law binds no foot to it).  Its outer ring meets the band or the mesh at their
level; its ring on the upper face is held at the wall's top
(``constraints/wall_zone.face_top``, ``constraints/road_ramp.wall_release``).

THE FOOT, the mirror (issue #1662): the LOWER band (``WallSides.lower``) of
a wall whose foot is read (``foot_profile``) is graded ground the same way,
its ring on the lower face held at the wall's bottom edge
(``constraints/wall_zone.face_foot``; owner RULINGS 2026-10-03c "terrain
should be flattened out to the bottom of the wall").  MEASURED KATL
``muro_concreto`` (capture on f82de7dfe): the strip between pad
``building46/p5`` (289.29 m) and the foot (289.5 m) was left to a slumped
mesh at 296-301 m, and pavement draped there showed through the wall.
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely

from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..model.wall_reach import WALL_SLOPE_REF_PREFIX

__all__ = ["wall_slopes", "SLOPE_VERTEX_M"]

#: the longest ring edge of a wall-slope piece: its face edge carries a
#: vertex at least this often, so the ground follows the wall's top / foot
#: profile between them (#1662, measured KATL ``muro_concreto``: one face
#: edge 56 m long ran straight across the foot's 8 m fall at the wall's end)
SLOPE_VERTEX_M = 5.0


def wall_slopes(walls: _t.Sequence, taken: _t.Sequence, apart: _t.Sequence,
                cut_m: float, hairline_m: float) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per wall-slope piece: every retaining wall's upper
    band (``WallSides.upper``) whose top is read (``top_profile``) and its
    lower band (``WallSides.lower``) whose foot is read (``foot_profile``,
    #1662), less
    its footprint, every polygon in ``taken`` (the zone bands: the slope
    welds to their edge) and every polygon in ``apart`` grown by ``cut_m``
    (the cells — pavement, pads, roads —, the late road ribbons and the
    structure keep-outs, at the zones' groundside stand-off): a slope
    shares no vertex with a cell, whose level is its own law — a road or a
    pad past the wall's end stands at the lower level, and the gap
    terraces (measured KATL replay: a slope vertex shared with a road past
    ``muro_concreto``'s end held it 11.7 m over its own run)."""
    live = [(w, band) for w in walls for band, read in
            ((w.upper, getattr(w, "top_profile", None)),
             (getattr(w, "lower", None), getattr(w, "foot_profile", None)))
            if read and band is not None and not band.is_empty]
    if not live:
        return []
    held = canonical_union([g for g in taken if g is not None and not g.is_empty]
                           + [g.buffer(cut_m, join_style="mitre", mitre_limit=2.0)
                              for g in apart if g is not None and not g.is_empty])
    out: list[tuple[str, _t.Any]] = []
    k = 0
    for w, band in live:
        g = fixed_difference(band, w.poly)
        if held is not None and not held.is_empty:
            g = fixed_difference(g, held)
        if out:     # two walls' bands meet: the first piece holds the overlap
            g = fixed_difference(g, canonical_union([p for _r, p in out]))
        for part in shapely.get_parts(g):
            if part.geom_type != "Polygon" or part.area < 1.0 \
                    or is_hairline(part, hairline_m):
                continue
            out.append((f"{WALL_SLOPE_REF_PREFIX}{w.resource}#{k}",
                        shapely.segmentize(part, SLOPE_VERTEX_M)))
            k += 1
    return out
