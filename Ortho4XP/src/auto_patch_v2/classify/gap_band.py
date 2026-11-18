"""THE BAND GROUND ON A GAP SHEET IS APRON (owner sim read #2113, KBNA
1.0.557 2026-11-17T23:52Z: "they should all be apron"; #2113's rule: the
ground between the concourses is one continuous apron; #1976: THE PAVEMENT
WINS OVER THE STRIP).

``gap_mint`` cuts every gap piece out of the runway / taxi band envelope
(a gap piece never claims zone ground), so the pack's drawn pavement within
a taxiway band's reach of a taxi face was left to ``planar/zones``, which drew
a taxiway STRIP there — grass between the gates' apron and the taxilanes.
``gap_apron.fill_to_taxi`` closes only a gap whose far side is a taxi face
within one closing radius; where another apron, a corridor or a road stands
across it the band ground stayed strip (KBNA: 8 owner sites between the
concourses, 90,237 m2 of sheet ground inside the taxi bands, none refilled).

The rule, at its one derivation site: each connected part of the SHEET
ground the TAXI band envelope took (the sheet minus every standing cell at
its stand-off, inside the band envelope, outside the RUNWAY band — strip
area is never apron population, 2026-08-21d) that touches APRON is apron:

* a part touching an apron gap piece joins that piece (:func:`attach`);
* a part touching no piece is one more apron piece when it runs along a
  standing apron cell for at least §27's ``lot.airside_edge_min_m``, or a
  standing ROAD across its page cut it off an apron piece on that page
  (:func:`road_split`: the road stays a road, the page is apron).  Either
  way it clears the mint's piece floor.

No road judge: a road inside the band is a standing ribbon cell.  A part
touching no apron, on a page that carries none, stays the band's (a page
drawn beside a taxiway and no apron is not apron population).  Buildings and roads are standing
cells, so no part holds one."""
from __future__ import annotations

import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..law import Law
from .evidence import polygon_parts

__all__ = ["runway_knife", "band_parts", "attach", "road_split"]


def runway_knife(cells, law: Law, airport, off) -> Polygon:
    """The RUNWAY family's band envelope stood off by ``off`` — the ground
    no apron piece may take (strip area is never apron population)."""
    from .ribbon_mint import ribbon_extent  # lazy: as ``gap_mint``'s own
    from .roles import TAXI_FAMILY
    runway = ribbon_extent([c for c in cells if c.role not in TAXI_FAMILY], law,
                           Polygon(), getattr(airport, "runways", ()))
    return off(runway) if not runway.is_empty else Polygon()


def band_parts(free, band_knife, rknife, grid: float,
               min_m2: float = 1.0) -> list[Polygon]:
    """The connected parts of ``free`` (the sheet less the standing cells)
    inside ``band_knife`` and outside ``rknife``, on the snap grid; parts
    the grid split apart by under two cells are one part."""
    if free.is_empty or band_knife.is_empty:
        return []
    g = free.intersection(band_knife)
    if not rknife.is_empty:
        g = g.difference(rknife)
    g = shapely.set_precision(g, grid)
    parts = [p for p in polygon_parts(g) if p.area >= min_m2]
    if len(parts) < 2:
        return parts
    joined = polygon_parts(unary_union([p.buffer(grid) for p in parts]))
    groups: list[list[Polygon]] = [[] for _ in joined]
    for p in parts:
        groups[next(i for i, j in enumerate(joined) if j.intersects(p))].append(p)
    return [unary_union(ps) if len(ps) > 1 else ps[0] for ps in groups if ps]


def attach(parts: _t.Sequence[Polygon], pieces: _t.Sequence[Polygon | None],
           grid: float) -> tuple[dict[int, list[Polygon]], list[Polygon]]:
    """``(piece index -> the parts it takes, the parts no piece takes)``: a
    part touching several pieces joins the one it shares most rim with; a
    ``None`` piece takes nothing."""
    taken: dict[int, list[Polygon]] = {}
    loose = []
    for p in parts:
        near = [(p.boundary.intersection(q.buffer(2.0 * grid)).length, -i, i)
                for i, q in enumerate(pieces)
                if q is not None and p.distance(q) <= 2.0 * grid]
        if near:
            taken.setdefault(max(near)[2], []).append(p)
        else:
            loose.append(p)
    return taken, loose


def road_split(part: Polygon, sheets: _t.Sequence[Polygon],
               aprons: _t.Sequence[Polygon], roads: _t.Sequence[Polygon],
               tol: float) -> bool:
    """``part`` was cut off its page's apron by a ROAD across the page: a
    standing road of ``roads`` within ``tol`` of ``part`` is within ``tol``
    of an apron piece of ``aprons`` that lies on a page of ``sheets`` the
    part lies on too."""
    pages = [s for s in sheets if s.intersection(part).area >= 1.0]
    if not pages:
        return False
    mine = [a for a in aprons if any(s.intersection(a).area >= 1.0 for s in pages)]
    return any(r.distance(part) <= tol and any(r.distance(a) <= tol for a in mine)
               for r in roads)
