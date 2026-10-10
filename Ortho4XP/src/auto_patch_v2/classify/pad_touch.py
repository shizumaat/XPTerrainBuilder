"""THE TOUCH WITNESS (spec §63 (3) Rule T; owner RULINGS 2026-10-09j: "if
the pavement overlaps or has no gap the road must stay welded to the pad;
if there's any gap the road can climb or descend and leave a steep wall or
embankment"; the touch is read on the SOURCE geometry).

One question, asked at the one site that used to manufacture every gap
(``classify/roles._cut_back_groundside``, BEFORE its knife): how far does
this groundside pavement cell AS DRAWN stand from this pad?  Both are read
on the identity grid (``emit.identity.min_distinct_spacing_m``), because a
gap the grid cannot hold cannot stand in the planar map (RULINGS
2026-09-04u: a 0.6 m pre-snap gap noded to ONE vertex):

* ``d <= min_distinct_spacing_m`` — TOUCHING: an overlap, a shared
  boundary, or a gap narrower than one identity cell.
* otherwise — GAPPED, with ``d`` recorded.

The only numbers are the identity grid and the frontage radius
(``emit.design.pad_frontage_m``, beyond which a pad and a cell have no
relation at all); no key of its own.  Published on the cell's evidence as
``pad_touch`` (``{pad ref: d}``) and read back by :func:`is_touching` /
:func:`touch_records`.

RULE W's PLAN (spec §63 (4)) is derived from the witness here and applied
at the same site: a TOUCHING pair is WELDED — the cell is clipped at the
pad's footprint and shares its rim (:func:`weld_partners` names the pads
``planar/weld`` then welds it to) — unless it is a §28 (6) HILLSIDE
TERRACE (owner RULINGS 2026-09-13o/13p, 2026-10-09f: "the one lawful
exception"), which keeps the set-back knife and is named under
``pad_held``.  :func:`dem_step_m` is that exception's quantity read where
the knife is: the DEM under the cell's edge facing the pad minus the DEM
under the pad's seat.  A GAPPED pair is left as drawn.
"""
from __future__ import annotations

import typing as _t

import statistics

import shapely
from shapely.geometry import Polygon
from shapely.ops import triangulate
from shapely.strtree import STRtree

from ..law import Law

__all__ = ["EVIDENCE_KEY", "HELD_KEY", "WELD_KEY", "STRIP_KEY", "is_rim_strip", "dem_step_m", "gridded",
           "is_held_step", "is_touching", "part_evidence", "touch_distances",
           "touch_limit_m", "touch_records", "weld_partners"]

#: the ``Cell.evidence`` key the witness is published under
EVIDENCE_KEY = "pad_touch"
#: the ``Cell.evidence`` key naming the pads a touching cell is HELD off
#: as a §28 (6) hillside terrace (the knife stands; never welded)
HELD_KEY = "pad_held"
#: ``Cell.evidence`` flag of a cell clipped at a pad's footprint (Rule W)
WELD_KEY = "pad_weld"
#: evidence key of the STRIP between the set-back knife and the rim that a
#: welded cell bounding airside is cut into (``roles._cut_back_groundside``,
#: §63 M1).  The strip stands where the knife's stand-off stood: readers of
#: the standing cells that claim ground by the cell SET (the zone claim)
#: read the body alone, as they read the knifed cell
STRIP_KEY = "pad_rim_strip"


def touch_limit_m(law: Law) -> float:
    """The largest distance read as TOUCHING: one identity cell."""
    return float(law.tables.emit.identity.min_distinct_spacing_m)


def is_touching(law: Law, d: float) -> bool:
    """Rule T's verdict for a witnessed distance ``d``."""
    return float(d) <= touch_limit_m(law)


def gridded(poly: Polygon, grid: float) -> Polygon:
    """``poly`` on the identity grid with the precision model stripped
    again (a buffer or a difference of a gridded geometry is otherwise
    itself rounded to the grid — ``planar/build._snapped``).  A polygon
    the grid collapses is returned as drawn."""
    if grid <= 0.0:
        return poly
    q = shapely.set_precision(shapely.set_precision(poly, grid), 0.0)
    if q.is_empty or q.geom_type != "Polygon":
        return poly
    return q


def touch_distances(ground: _t.Sequence[Polygon],
                    pads: _t.Sequence[tuple[str, Polygon]],
                    law: Law) -> list[dict[str, float]]:
    """Per groundside polygon (already on the identity grid) the witness
    ``{pad ref: d}`` against every pad (``(ref, gridded polygon)``) within
    the frontage radius — millimetres, the pad nearest first.  Two faces
    of one pad ref read as their nearest."""
    if not ground or not pads:
        return [{} for _ in ground]
    r = float(law.tables.emit.design.pad_frontage_m)
    tree = STRtree([p for _ref, p in pads])
    out: list[dict[str, float]] = []
    for g in ground:
        got: dict[str, float] = {}
        for k in tree.query(g, predicate="dwithin", distance=r):
            ref, p = pads[int(k)]
            d = round(float(g.distance(p)), 3)
            if d <= r and d < got.get(ref, float("inf")):
                got[ref] = d
        out.append(dict(sorted(got.items(), key=lambda kv: (kv[1], kv[0]))))
    return out


def _median_dem(geom, dem, step: float) -> float | None:
    """The median DEM along a line geometry, sampled at its vertices and
    every ``step`` metres between them; ``None`` for an empty one."""
    if geom is None or geom.is_empty:
        return None
    pts = shapely.get_coordinates(shapely.segmentize(geom, step))
    if len(pts) == 0:
        return None
    return statistics.median(float(dem.z(float(x), float(y))) for x, y in pts)


def _area_dem(pad: Polygon, dem) -> float | None:
    """The pad's AREA-WEIGHTED DEM over its own outline — the fallback
    datum of a pad with no airside frontage (owner RULINGS 2026-09-18c
    (1); the quantity of ``constraints.pad_frontage_gs
    .pad_area_weighted_dem``, read off the build's DEM at the outline's
    own corners)."""
    num = den = 0.0
    for tri in triangulate(pad):
        if not pad.contains(tri.centroid):
            continue
        zs = [float(dem.z(float(x), float(y)))
              for x, y in list(tri.exterior.coords)[:3]]
        num += tri.area * (sum(zs) / 3.0)
        den += tri.area
    return None if den <= 0.0 else num / den


def dem_step_m(cell: Polygon, pad: Polygon, knife: Polygon, airside,
               dem, law: Law) -> float | None:
    """§28 (6)'s QUANTITY FOR ONE TOUCHING PAIR, read at the knife's own
    site (owner RULINGS 2026-09-13o/13p, 2026-09-18c (1)): the median DEM
    along the edge the cell WOULD keep facing the pad (its boundary, cut
    back by ``knife``, within the frontage radius of the pad) minus the
    pad's own datum — the median DEM along its rim within the radius of
    AIRSIDE pavement (``airside``: that pavement's union ALREADY WIDENED
    by the radius, or ``None``), else its area-weighted DEM.  ``None`` where either side cannot be read (no DEM,
    nothing left of the cell): a pair is welded unless it is MEASURED to
    be a hillside.

    The same quantity ``constraints.pad_frontage_gs.pair_dem_step_m``
    reads off the planar map's vertices for the pairs that reach the
    solve; this one exists because the decision it serves — knife or weld
    — is taken before there is a map."""
    if dem is None:
        return None
    r = float(law.tables.emit.design.pad_frontage_m)
    near = pad.buffer(r)
    fd = _median_dem(cell.difference(knife).boundary.intersection(near), dem, r)
    if fd is None:
        return None
    pd = None
    if airside is not None and not airside.is_empty:
        pd = _median_dem(pad.boundary.intersection(airside), dem, r)
    if pd is None:
        pd = _area_dem(pad, dem)
    return None if pd is None else fd - pd


def is_held_step(law: Law, step: float | None) -> bool:
    """§28 (6): a pair whose DEM step exceeds ``[design]
    frontage_step_max_m`` is a hillside terrace."""
    return step is not None and \
        abs(step) > float(law.tables.emit.design.frontage_step_max_m)


def part_evidence(parent: _t.Mapping[str, _t.Any], part: Polygon,
                  pads: _t.Mapping[str, Polygon], law: Law
                  ) -> dict[str, _t.Any]:
    """The witness a PART of a cut cell carries: its parent's, restricted
    to the pads the part itself still stands within the frontage radius
    of (the SOURCE distance is kept — the part's own distance is the
    engine's doing), and the held pads likewise.  A part that left every
    pad's radius carries neither key."""
    r = float(law.tables.emit.design.pad_frontage_m)
    ev = {k: v for k, v in parent.items() if k not in (EVIDENCE_KEY, HELD_KEY)}
    w = {ref: d for ref, d in (parent.get(EVIDENCE_KEY) or {}).items()
         if ref in pads and part.distance(pads[ref]) <= r}
    if w:
        ev[EVIDENCE_KEY] = w
        held = tuple(ref for ref in parent.get(HELD_KEY, ()) if ref in w)
        if held:
            ev[HELD_KEY] = held
    return ev


def is_rim_strip(cell: _t.Any) -> bool:
    """``cell`` is the rim STRIP of a welded cell (:data:`STRIP_KEY`)."""
    return bool((getattr(cell, "evidence", None) or {}).get(STRIP_KEY))


def weld_partners(cell: _t.Any, law: Law) -> list[str]:
    """The pad refs ``cell`` is WELDED to (Rule W): the pads it touches
    in the source geometry, less the ones it is held off as a terrace."""
    ev = getattr(cell, "evidence", None) or {}
    held = set(ev.get(HELD_KEY, ()))
    return [ref for ref, d in (ev.get(EVIDENCE_KEY) or {}).items()
            if is_touching(law, d) and ref not in held]


def touch_records(cells: _t.Iterable[_t.Any], law: Law
                  ) -> list[dict[str, _t.Any]]:
    """THE WITNESS AS DATA, per pad: ``{pad, touching: [{cell}, ...],
    held: [{cell}, ...], gapped: [{cell, gap_m}, ...]}`` over every cell
    carrying the evidence (``cell`` is ``role:ref``) — what the sidecar
    publishes, so a pad's every groundside neighbour is named with its
    class and a gapped one with its gap.  ``touching`` are the WELDED
    cells; ``held`` the cells that touch in the source and are kept off
    the pad as a §28 (6) terrace."""
    by_pad: dict[str, dict[str, _t.Any]] = {}
    for c in cells:
        w = (getattr(c, "evidence", None) or {}).get(EVIDENCE_KEY)
        if not w:
            continue
        name = f"{c.role}:{c.ref}"
        held = set(c.evidence.get(HELD_KEY, ()))
        for pad, d in w.items():
            rec = by_pad.setdefault(pad, {"pad": pad, "touching": [],
                                          "held": [], "gapped": []})
            if pad in held:
                rec["held"].append({"cell": name})
            elif is_touching(law, d):
                rec["touching"].append({"cell": name})
            else:
                rec["gapped"].append({"cell": name, "gap_m": float(d)})
    for rec in by_pad.values():
        rec["touching"].sort(key=lambda g: g["cell"])
        rec["held"].sort(key=lambda g: g["cell"])
        rec["gapped"].sort(key=lambda g: (g["gap_m"], g["cell"]))
    return [by_pad[k] for k in sorted(by_pad)]
