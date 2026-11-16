"""AN AIRCRAFT STAND ON A GAP SHEET IS APRON (owner sim read #2113, KBNA
2026-11-16T16:56:54Z: "this should be continuous apron from the building
over to the other terminal concourse ... The roads and taxiways are
supposed to become part of the apron"; law: RULINGS 2026-09-11ac item 7 —
a face carrying 1300 STARTUPS is airside on evidence — and the free-road
ruling, a road sharing an edge with an apron IS the apron).

A pack may draw the ground between its concourses only as draped photo
pages (``Airport.gap_sheets``, admitted as §53 GAP PIECES), the gates'
stands on them.  The gap pieces are minted LAST (``gap_mint``), so the §27
airside-edge pass never saw them: a service-road corridor across the apron
in front of the gates read the stands' ground as nothing and kept its road
role (12.7 % of its perimeter on apron, under §37 (2)'s 20 %), and the
gates' pieces, cut off from the apron by it, stayed groundside pavement.

Two reads, one rule:

* :func:`stand_ground` — the STAND GROUND §27 measures against: each part
  of the gap sheets left by the faces already classified and the pads that
  holds a 1300 startup.  It is a contact witness only (``airside_edge_flip``
  ``stands=``), never a cell: the pieces themselves are still minted once,
  by ``gap_mint``.
* :func:`holds_stand` — the piece-level test ``gap_mint`` applies: a gap
  piece that holds a startup is apron whatever road evidence it carries.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .evidence import polygon_parts

__all__ = ["stand_ground", "holds_stand", "startup_tree"]


def startup_tree(airport) -> STRtree | None:
    """The 1300 startups of ``airport`` as a tree of points (frame xy)."""
    pts = [Point(st.xy) for st in getattr(airport, "startups", ()) or ()]
    return STRtree(pts) if pts else None


def holds_stand(part: Polygon, tree: STRtree | None) -> bool:
    """``part`` contains a 1300 startup."""
    return tree is not None and len(tree.query(part, predicate="contains")) > 0


def _sheet(g) -> Polygon | None:
    try:
        p = Polygon(g.outer, g.holes)
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0.0)
    return None if p.is_empty else p


def stand_ground(airport, faces: _t.Iterable[Polygon], tree: STRtree | None,
                 min_area_m2: float) -> list[Polygon]:
    """The parts of the gap sheets outside every face of ``faces`` that hold
    a startup of ``tree`` and reach ``min_area_m2`` (module doc)."""
    if tree is None:
        return []
    sheets = [p for p in (_sheet(g) for g in getattr(airport, "gap_sheets", ()) or ())
              if p is not None]
    if not sheets:
        return []
    taken = unary_union([f for f in faces if f is not None and not f.is_empty])
    ground = unary_union(sheets)
    if not taken.is_empty:
        ground = ground.difference(taken)
    return [p for p in polygon_parts(ground)
            if p.area >= min_area_m2 and holds_stand(p, tree)]
