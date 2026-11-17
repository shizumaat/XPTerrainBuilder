"""A BANK OF GRADED GROUND ROUND A LEVEL: its width and its cut, shared by
the bank families that mint a ring of ``graded_strip`` pieces from a level
down (or up) to the DEM -- an AGP plate's (``planar/agp_ground``, #2090 C2)
and a walled pit's open edge (``planar/pit_bank``, #1949 R3).

* :func:`bank_width` -- ``max([emit.design] bank_min_width_m, rise /
  bank_slope)``: the 1:3 slope a pilot reads as ground, never narrower than
  the narrowest collar.
* :func:`knives` -- what a bank yields to: it welds to the zone bands
  (``taken``), stands off every other cell, road ribbon and keep-out
  (``apart``) by ``cut_m`` and the airside cells by ``[design]
  pad_frontage_m``; the road ribbons' own stand-off is returned apart, the
  witness of a bank a road cuts short.
* :func:`pieces` -- one geometry cut by the knife into the pieces the map
  takes: polygons of a square metre or more, no hairline, a vertex every
  ``vertex_m``.

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely
import shapely.prepared

from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline

__all__ = ["bank_width", "knives", "pieces"]


def bank_width(rise: float, law) -> float:
    """The bank's plan width for a ``rise`` (metres, level against DEM)."""
    d = law.tables.emit.design
    return max(float(d.bank_min_width_m), float(rise) / float(d.bank_slope))


def knives(outline, taken: _t.Sequence, apart: _t.Sequence, airside: _t.Sequence,
           ribbons: _t.Sequence, cut_m: float, law) -> tuple:
    """``(knife, ribbon stand-off)`` near ``outline`` (the banks' plan
    reach) -- module doc."""
    front = float(law.tables.emit.design.pad_frontage_m)
    near = shapely.prepared.prep(outline.buffer(cut_m + front + 1.0))

    def _near(gs) -> list:
        return [g for g in gs if g is not None and not g.is_empty and near.intersects(g)]
    knife = canonical_union(_near(taken)
                            + [g.buffer(cut_m, join_style="mitre", mitre_limit=2.0)
                               for g in _near(apart)]
                            + [g.buffer(front, join_style="mitre", mitre_limit=2.0)
                               for g in _near(airside)])
    rib = canonical_union([g.buffer(cut_m, join_style="mitre", mitre_limit=2.0)
                           for g in _near(ribbons)])
    return knife, rib


def pieces(geom, knife, hairline_m: float, vertex_m: float) -> list:
    """``geom`` less ``knife`` as the map's pieces (module doc)."""
    out = []
    for part in shapely.get_parts(fixed_difference(geom, knife)):
        if part.geom_type != "Polygon" or part.area < 1.0 or is_hairline(part, hairline_m):
            continue
        for q in shapely.get_parts(shapely.segmentize(part, vertex_m)):
            if q.geom_type == "Polygon" and q.area >= 1.0:
                out.append(q)
    return out
