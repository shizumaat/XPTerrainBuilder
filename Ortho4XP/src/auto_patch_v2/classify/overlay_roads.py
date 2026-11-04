"""AN OVERLAY PAGE IS CUT AT THE MAPPED ROADS INSIDE IT (owner 2026-11-04,
"Yes, overlay pages"; #1598).

An overlay pack (``airport/overlay_pavement``) can draw a whole landside
road network as ONE page: at KATL an AEP page of 292,000 m2 east of the
cargo aprons carries 9 km of mapped roads, read as one lot that a 13 m
slope puts 5,263 census rows over the lot cap.  For OVERLAY pages only the
mapped roads inside are ROADS, not lot (RULINGS 2026-10-14a, "roads inside
a lot are the lot", stays for the pack's own pavement): each road's
carriageway (``airport/road_ways.ribbon_half_width_m``, the ribbon mint's
own width) is cut out of the page, so the road-face mint ribbons it
(``ribbon_mint``; the overlay lots never absorb a ribbon,
``lot_roads.lot_cells``) and the pieces between the roads are separate
lots, each scored on its own.
"""
from __future__ import annotations

from shapely.ops import unary_union

from ..airport.road_ways import ribbon_half_width_m
from ..model.airport import OVERLAY_PREFIX
from .evidence import polygon_parts

__all__ = ["overlay_cuts", "split_overlays_at_roads"]


def split_overlays_at_roads(pages, airport, law, rules) -> tuple[list, int]:
    """``pages`` (``(id, polygon)``, classify's admitted draped pages) with
    every overlay page cut at the carriageways of the mapped roads the
    ribbon mint ribbons; the pieces at least ``[cells] min_area_m2`` are
    ``<id>#r<k>``.  Returns ``(pages, overlay pages cut)``."""
    # lazy: ribbon_mint imports this package
    from .ribbon_mint import _ribbon_ways
    if law is None or not any(pid.startswith(OVERLAY_PREFIX) for pid, _g in pages):
        return list(pages), 0
    ways = _ribbon_ways(airport, rules)
    lanes = unary_union([ln.buffer(ribbon_half_width_m(w.tags, law), cap_style="flat")
                         for w, ln in ways]) if ways else None
    if lanes is None or lanes.is_empty:
        return list(pages), 0
    floor = float(rules.cells.min_area_m2)
    out, cut = [], 0
    for pid, poly in pages:
        if not pid.startswith(OVERLAY_PREFIX) or not poly.intersects(lanes):
            out.append((pid, poly))
            continue
        cut += 1
        out.extend((f"{pid}#r{k}", g) for k, g in enumerate(
            g for g in polygon_parts(poly.difference(lanes)) if g.area >= floor))
    return out, cut


def overlay_cuts(ev, region) -> list:
    """The boundaries of the overlay pieces inside ``region``, as cut lines
    for the slice: each piece is its OWN face, kinded and kept by its own
    evidence (``airside_edge.keep_overlay_groundside``), never dissolved
    into the airport's apron it touches -- as a §42 body cuts at its own
    boundary (``sources.object_body_cuts``)."""
    from ..geom.parts import line_parts
    gate = region.buffer(0.01)
    out: list = []
    for sid, g in ev.pavement_polys:
        if sid.startswith(OVERLAY_PREFIX) and g.area > 0.0:
            out.extend(line_parts(g.boundary.intersection(gate)))
    return out
