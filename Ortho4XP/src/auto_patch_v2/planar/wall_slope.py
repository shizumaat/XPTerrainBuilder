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
THE FILL (issue #1600): a retaining wall's FOOTPRINT, left to the mesh, read
the lidar's smeared step, and a wall drawn as two sheets with no top (KATL
``muro_concreto5``: two faces 3.4 m apart, open between them) showed it as
a hole behind the wall.  The back of the wall is buried (Q299 (a)): the
footprint is graded ground too, one more piece of the family, less the
:data:`~..model.wall_reach.FILL_SLOT_M` strip along the lower face (the
mesh makes the step from top to foot there, behind the lower face); its
vertices off the faces are held at the wall's top
(``constraints/wall_zone.fill_top``).
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import shapely

from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..model.wall_reach import FILL_SLOT_M, WALL_SLOPE_REF_PREFIX, is_wall_slope_ref

__all__ = ["wall_slopes", "slope_sides", "SLOPE_VERTEX_M"]

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
    its footprint, and the fill of its footprint (#1600, :func:`_fill`);
    each less every polygon in ``taken`` (the zone bands: the slope
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
    live = [(w, fixed_difference(band, w.poly)) for w, band in live] \
        + [(w, f) for w in walls if _retains(w)
           for f in (_fill(w),) if f is not None and not f.is_empty]
    if not live:
        return []
    held = canonical_union([g for g in taken if g is not None and not g.is_empty]
                           + [g.buffer(cut_m, join_style="mitre", mitre_limit=2.0)
                              for g in apart if g is not None and not g.is_empty])
    out: list[tuple[str, _t.Any]] = []
    k = 0
    for w, band in live:
        g = band
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


def _retains(w) -> bool:
    """The wall's top retains a hill at one station at least."""
    return any(z is not None for _s, z in (getattr(w, "top_profile", None) or ()))


def _fill(w):
    """THE FILL (module doc): the footprint less the
    :data:`FILL_SLOT_M` strip along its lower face; ``None`` unread."""
    face = getattr(w, "lower_face", None)
    if face is None or w.poly is None or w.poly.is_empty:
        return None
    return fixed_difference(w.poly, face.buffer(FILL_SLOT_M, cap_style="flat",
                                                join_style="mitre", mitre_limit=2.0))


def slope_sides(faces: _t.Mapping[int, _t.Any],
                incident: _t.Mapping[int, _t.Iterable[int]]) -> dict:
    """``faces`` with every wall-slope piece on THE SIDE OF THE GROUND IT
    GRADES (#1777).  A piece welded (a shared vertex) to an airside face —
    a zone band, the apron or a pad it is graded with — directly or through
    the pieces it is welded to, is airside ground (airside is king); a piece
    welded to no airside face is ground of its own past the airside's
    adjacent ground, so groundside (KCLT ``paredes_10_charlotte``: welded to
    nothing, 6 m from the nearest road).  ``incident`` is every vertex's
    face ids.  The role stays ``graded_strip``: only the census partition
    moves."""
    slope = {fid for fid, f in faces.items() if is_wall_slope_ref(f.ref)}
    if not slope:
        return dict(faces)
    welded: dict[int, set[int]] = {fid: set() for fid in slope}
    for fids in incident.values():
        for fid in slope.intersection(fids):
            welded[fid].update(fids)
    out = dict(faces)
    seen: set[int] = set()
    for start in sorted(slope):
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            fid = stack.pop()
            if fid not in comp:
                comp.add(fid)
                stack.extend(welded[fid] & slope)
        seen |= comp
        side = "airside" if any(faces[o].side == "airside" for fid in comp
                                for o in welded[fid] - slope) else "groundside"
        for fid in comp:
            if faces[fid].side != side:
                out[fid] = _dc.replace(faces[fid], side=side)
    return out
