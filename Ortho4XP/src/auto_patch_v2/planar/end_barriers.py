"""A RUNWAY END AREA ENDS AT THE FIRST BARRIER ACROSS IT (#2111 R2; spec
``Ortho4XP/docs/specs/2111-R2.md``).

The runway's zone-2 end rectangle (``planar/zones._runway_band``: the
extended centreline from the runway END out the recorded end length,
``model/end_area``, +/- the zone-2 half-width) is graded ground up to the
first pack barrier standing across it -- a blast fence, a wall, a tall
perimeter fence.  Behind it the ground is not the runway's: a public road
there follows its own ground (RULINGS 2026-10-20c (39)), and the bank
between is the DEM.  Measured KBNA 31 (#2111): the band ran 304.8 m out,
across the jet-blast shield, both perimeter fences and the bank, and the
road behind them took the band's ceiling (a +3.1 m rise).

A BARRIER is a pack LINE object (``Airport.edge_lines``) of no unit,
standing on ground (``airport/line_solidity.kind_of`` not ELEVATED) whose
top stands more than ``[service] line_low_barrier_max_solid_m`` over its
zero.  It QUALIFIES for an end when its part inside that end's rectangle

* crosses the extended centreline,
* is at least ``[edge_lines] min_run_m`` long, and
* stands more than :data:`PAVEMENT_CLEAR_M` off the runway pavement.

THE CUT is each qualifying part moved outward (along the centreline) by
the line's base half-width -- its far face -- swept outward to the
rectangle's end.  ``planar/zones.zone_regions`` subtracts it from the
runway's zone 1 and zone 2, after the road-beside cut and before the
through-road yields; the band's CLAIM keeps the uncut extent.  Thresholds
are the caller's (``classify/rules.toml``), handed in through
:class:`EndBarriers`."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..airport.line_solidity import ELEVATED, kind_of

__all__ = ["Barrier", "EndBarriers", "end_barriers", "runway_end_cut", "PAVEMENT_CLEAR_M"]

#: a part standing within this of the runway pavement is the pavement's own
#: furniture (a blast pad's edge), never the end of its end area (spec R2)
PAVEMENT_CLEAR_M = 1.0


@_dc.dataclass(frozen=True)
class Barrier:
    """One pack line standing across ground (module doc)."""

    id: str
    line: LineString
    half_width_m: float


@_dc.dataclass(frozen=True)
class EndBarriers:
    """The airport's barriers and the run a part must reach to qualify."""

    lines: tuple[Barrier, ...] = ()
    min_run_m: float = 0.0


def end_barriers(edge_lines: _t.Iterable, service, min_run_m: float) -> EndBarriers:
    """The barriers among ``edge_lines`` (``Airport.edge_lines``); ``service``
    is ``classify/rules.toml`` ``[service]`` (``line_*``), ``min_run_m``
    ``[edge_lines] min_run_m``."""
    tall = float(service.line_low_barrier_max_solid_m)
    out = []
    for el in edge_lines or ():
        if getattr(el, "unit", None) is not None or len(el.points) < 2:
            continue
        if kind_of(el, service) == ELEVATED:
            continue
        if float(el.top_y) - max(float(el.base_y), 0.0) <= tall:
            continue
        pts = list(el.points) + ([el.points[0]] if el.closed else [])
        line = LineString(pts)
        if line.length > 0.0:
            out.append(Barrier(el.id, line, max(0.0, float(el.half_width_m))))
    return EndBarriers(tuple(out), float(min_run_m))


def _sweep(part, unit, shift: float, length: float) -> list[Polygon]:
    """``part`` moved ``shift`` along ``unit`` and swept ``length`` on."""
    ux, uy = unit
    quads = []
    for g in shapely.get_parts(part):
        if g.geom_type != "LineString":
            continue
        c = [(x + ux * shift, y + uy * shift) for x, y in g.coords]
        for p, q in zip(c, c[1:], strict=False):
            quad = Polygon([p, q, (q[0] + ux * length, q[1] + uy * length),
                            (p[0] + ux * length, p[1] + uy * length)])
            quad = quad if quad.is_valid else quad.buffer(0.0)
            if not quad.is_empty and quad.area > 0.0:
                quads.append(quad)
    return quads


def _end_cut(end, unit, length: float, hw: float, pavement, barriers: EndBarriers
             ) -> tuple[Polygon | None, tuple[str, ...]]:
    """The cut past one END (module doc) and the ids of its barriers."""
    ray = LineString([end, (end[0] + unit[0] * length, end[1] + unit[1] * length)])
    rect = ray.buffer(hw, cap_style="flat")
    quads, ids = [], []
    for b in barriers.lines:
        if not b.line.intersects(rect):
            continue
        part = b.line.intersection(rect)
        if part.length < barriers.min_run_m or not part.intersects(ray) \
                or part.distance(pavement) <= PAVEMENT_CLEAR_M:
            continue
        ids.append(b.id)
        quads.extend(_sweep(part, unit, b.half_width_m, length))
    if not quads:
        return None, tuple(ids)
    cut = unary_union(quads).intersection(rect)
    return (None if cut.is_empty or cut.area <= 0.0 else cut), tuple(ids)


def runway_end_cut(rec: tuple, hw: float, rsa_m: float, pavement,
                   barriers: EndBarriers | None) -> tuple[Polygon | None, tuple[str, ...]]:
    """The cut over both ends of one runway: ``rec`` its zone record
    (``(ref, end_a, end_b, width_m[, len_a, len_b, ...])``, ``planar/
    overlay._runway_records``), ``hw`` its zone-2 half-width, ``rsa_m``
    the end length a record without one reads, ``pavement`` the runway's
    own faces.  ``(None, ())`` without a barrier across either end."""
    if barriers is None or not barriers.lines or hw <= 0.0:
        return None, ()
    a, b = rec[1], rec[2]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L <= 0.0:
        return None, ()
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    la, lb = (float(rec[4]), float(rec[5])) \
        if len(rec) >= 6 and rec[4] is not None else (rsa_m, rsa_m)
    cuts, ids = [], []
    for end, unit, length in ((a, (-ux, -uy), la), (b, (ux, uy), lb)):
        if length <= 0.0:
            continue
        g, got = _end_cut(end, unit, length, hw, pavement, barriers)
        ids.extend(got)
        if g is not None:
            cuts.append(g)
    return (unary_union(cuts) if cuts else None), tuple(ids)
