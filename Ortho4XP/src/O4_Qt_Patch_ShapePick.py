"""Clicking a patch LINE selects its whole shape, JOSM-style (issue #759;
spec patch-editor-20261015 §4 as amended 2026-10-15; the Mac app's
``SceneryKit/PatchShapePick.swift`` and ``PatchShapeStats.swift``).

Pure functions of the document and screen points, tested headless:

* :func:`click_target` — what a click lands on: node > "+" handle > edge >
  empty map (each already hit-tested at 8 px);
* :func:`shapes_on_edge` — the ways an edge belongs to, smallest plan area
  first (adjacent faces share vertices);
* :func:`choose_shape` — the repeat-click cycle: the same spot again
  (within 4 px, no move) steps to the next shape on that edge;
* :func:`shape_stats` — the shape inspector's numbers.
"""
from __future__ import annotations

import math
import typing as _t

from o4_engine import patch_edit as PE
from O4_Qt_Pack_Outlines import METRES_PER_DEG_LAT
from O4_Qt_Preview3D_Shapes import LocalFrame

__all__ = ["REPEAT_RADIUS_PX", "ShapeClick", "ShapeStats", "click_target",
           "shapes_on_edge", "choose_shape", "shape_stats"]

#: A repeat click within this many px of the last one cycles.
REPEAT_RADIUS_PX = 4.0


class ShapeClick(_t.NamedTuple):
    """The last click on a line: where, the shapes on that edge, the one
    it chose."""
    x: float
    y: float
    candidates: tuple[int, ...]
    chosen: int


class ShapeStats(_t.NamedTuple):
    node_count: int
    area_m2: float                 # 0 for an open way
    perimeter_m: float
    min_alt: float | None
    max_alt: float | None
    nodes_without_elevation: int
    neighbours: int                # other ways sharing at least one node


def click_target(node: int | None, on_handle: bool, on_edge: bool):
    """``("node", id)``, ``("handle",)``, ``("edge",)`` or ``("empty",)``."""
    if node is not None:
        return ("node", node)
    if on_handle:
        return ("handle",)
    return ("edge",) if on_edge else ("empty",)


def _plan_area(doc: PE.PatchDoc, way: PE.Way, frame: LocalFrame) -> float:
    if not way.closed:
        return 0.0
    # the engine's shoelace (lazy: the engine package is not app start-up's)
    from auto_patch_v2.geom.pad_evidence import ring_area
    ring = [(doc.nodes[r][1] - frame.origin_lat, doc.nodes[r][2] - frame.origin_lon)
            for r in way.refs[:-1] if r in doc.nodes]
    return ring_area(ring, METRES_PER_DEG_LAT, frame.m_per_deg_lon)


def shapes_on_edge(doc: PE.PatchDoc, a: int, b: int,
                   frame: LocalFrame | None = None) -> list[int]:
    """Ids of the ways in which ``a`` and ``b`` are consecutive (either
    direction), smallest plan area first (an open way has none), ties by
    way id."""
    frame = frame or LocalFrame.of(doc)
    hits = [w for w in doc.ways
            if any({p, q} == {a, b} for p, q in zip(w.refs, w.refs[1:]))]
    return [w.id for w in sorted(hits, key=lambda w: (_plan_area(doc, w, frame), w.id))]


def choose_shape(candidates: _t.Sequence[int], x: float, y: float,
                 previous: ShapeClick | None) -> ShapeClick | None:
    """The shape a click on an edge selects: a click within
    :data:`REPEAT_RADIUS_PX` of ``previous`` on the same candidates steps
    to the shape after the one it chose (wrapping); any other click picks
    the smallest.  ``None`` with no candidate."""
    candidates = tuple(candidates)
    if not candidates:
        return None
    chosen = candidates[0]
    if (previous is not None and previous.candidates == candidates
            and math.hypot(previous.x - x, previous.y - y) <= REPEAT_RADIUS_PX
            and previous.chosen in candidates):
        chosen = candidates[(candidates.index(previous.chosen) + 1) % len(candidates)]
    return ShapeClick(x, y, candidates, chosen)


def shape_stats(doc: PE.PatchDoc, way_id: int, frame: LocalFrame | None = None) -> ShapeStats:
    """The inspector's numbers for one way."""
    frame = frame or LocalFrame.of(doc)
    way = next(w for w in doc.ways if w.id == way_id)
    ids = sorted({r for r in way.refs if r in doc.nodes})
    pts = [frame.metres(doc.nodes[r][1], doc.nodes[r][2]) for r in way.refs if r in doc.nodes]
    perimeter = sum(math.hypot(float(q[0] - p[0]), float(q[1] - p[1])) for p, q in zip(pts, pts[1:]))
    alts = [doc.nodes[i][3] for i in ids if doc.nodes[i][3] is not None]
    mine = set(ids)
    neighbours = sum(1 for w in doc.ways if w.id != way_id and mine.intersection(w.refs))
    return ShapeStats(len(ids), _plan_area(doc, way, frame), perimeter,
                      min(alts) if alts else None, max(alts) if alts else None,
                      len(ids) - len(alts), neighbours)
