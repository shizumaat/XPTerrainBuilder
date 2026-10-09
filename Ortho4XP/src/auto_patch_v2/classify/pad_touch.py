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
"""
from __future__ import annotations

import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..law import Law

__all__ = ["EVIDENCE_KEY", "gridded", "is_touching", "touch_distances",
           "touch_limit_m", "touch_records"]

#: the ``Cell.evidence`` key the witness is published under
EVIDENCE_KEY = "pad_touch"


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


def touch_records(cells: _t.Iterable[_t.Any], law: Law
                  ) -> list[dict[str, _t.Any]]:
    """THE WITNESS AS DATA, per pad: ``{pad, touching: [role:ref, ...],
    gapped: [{cell, gap_m}, ...]}`` over every cell carrying the evidence —
    what the sidecar publishes, so a pad's every groundside neighbour is
    named with its class and a gapped one with its gap."""
    by_pad: dict[str, dict[str, _t.Any]] = {}
    for c in cells:
        w = (getattr(c, "evidence", None) or {}).get(EVIDENCE_KEY)
        if not w:
            continue
        name = f"{c.role}:{c.ref}"
        for pad, d in w.items():
            rec = by_pad.setdefault(pad, {"pad": pad, "touching": [], "gapped": []})
            if is_touching(law, d):
                rec["touching"].append(name)
            else:
                rec["gapped"].append({"cell": name, "gap_m": float(d)})
    for rec in by_pad.values():
        rec["touching"].sort()
        rec["gapped"].sort(key=lambda g: (g["gap_m"], g["cell"]))
    return [by_pad[k] for k in sorted(by_pad)]
