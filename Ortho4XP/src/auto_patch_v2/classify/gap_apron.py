"""THE CLASS OF AN APRON-TOUCHING GAP PIECE (spec §59; owner RULINGS
2026-10-08c (6), 08g): "if a road touches apron then it stays a road from
the point where it touches the apron away, and gets road grade, otherwise it
must be treated as part of the apron and be graded with the whole apron."

Two reads, both the standing readers' — no second road-evidence rule:

* :func:`judge` — ROAD EVIDENCE through ``roles._road_evidence`` (the OSM
  roads ON the sheet from one more ``evidence._osm_roads`` call; the road
  family across the mint's stand-off), then THE CLASS through §27's
  ``airside_edge.airside_edge_flip`` with that verdict handed in
  (``road_class=``): a road-evidenced part is apron only when it SITS
  against the apron (§37 (2)'s share of its perimeter); a part with no road
  evidence is the apron.
* :func:`close_rim` — an apron part's rim is closed onto every apron ring
  within the weld spacing, so pass A nodes the two rims as one (§59 (2) 4).

``classify/gap_mint`` is the one caller."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import family
from ..model.airport import Airport
from .airside_edge import airside_edge_flip
from .evidence import Evidence, _osm_roads, polygon_parts
from .rules import Rules

__all__ = ["Verdict", "judge", "close_rim"]


@_dc.dataclass(frozen=True)
class Verdict:
    """One apron-touching part's class: ``apron`` (else ROAD, the §55 late
    piece), whether a road reaches it, and §27's lateral airside metres
    (``None`` where §27 did not flip it)."""

    apron: bool
    road_evidence: bool
    airside_edge_m: float | None


def judge(parts: _t.Sequence[Polygon], airport: Airport, ev: Evidence,
          cells: _t.Sequence, sheet, touch_tol_m: float, law: Law,
          rules: Rules, role: str, kind: str) -> list[Verdict]:
    """The §59 class of each apron-touching gap ``part`` (born ``role`` /
    ``kind``), against the standing ``cells``; ``sheet`` is the gap sheets'
    union, ``touch_tol_m`` the mint's stand-off plus the weld spacing."""
    from .roles import _road_evidence          # lazy: roles calls the mint
    road_roles = tuple(family(law, "road_cross_section").roles)
    standing = [(Polygon(c.ring, c.holes), c.role) for c in cells
                if c.role in road_roles]
    ev_sheet = _dc.replace(ev, road_chains=_osm_roads(
        airport, ev.truck_chains, sheet, rules,
        len(ev.taxi_chains) + len(ev.truck_chains) + len(ev.road_chains)))
    scored = [(p, role) for p in parts] + standing
    evidenced = {i for i in _road_evidence(scored, ev_sheet, rules,
                                           touch_tol_m=touch_tol_m,
                                           touch_roles=road_roles)
                 if i < len(parts)}
    final = [[role, str(i), p, None, {}, kind] for i, p in enumerate(parts)]
    airside_edge_flip(final, cells, law, rules,
                      [c.line for c in ev.truck_chains], road_class=evidenced)
    out = []
    for i, f in enumerate(final):
        flipped = f[0] == "apron"
        # THE RULING'S WORDS: no road evidence IS apron — also where §27
        # itself would not flip the part (its sliver floor)
        out.append(Verdict(flipped or i not in evidenced, i in evidenced,
                           float(f[4]["airside_edge_m"]) if flipped else None))
    return out


def close_rim(part: Polygon, aprons: _t.Sequence[Polygon], tree: STRtree | None,
              keep_out: _t.Iterable, weld_m: float, grid: float) -> Polygon:
    """``part`` with the ground BETWEEN it and the apron rings absorbed: the
    morphological closing of the two at ``weld_m`` (what lies within
    ``weld_m`` of BOTH across a gap, the whole gap and nothing beside it — a
    contact's end grows no ear, and no slit is left along either rim), less
    each geometry of ``keep_out`` (every standing cell with its stand-off,
    the band envelope, the other pieces); only a body of it that reaches
    BOTH rims is taken.  Where the two rims ran within the weld spacing
    without coinciding they now coincide."""
    if tree is None:
        return part

    def off(g, d):
        return g.buffer(d, join_style="mitre", mitre_limit=2.0)
    near = [aprons[int(j)] for j in tree.query(off(part, 2.0 * weld_m),
                                               predicate="intersects")]
    if not near:
        return part
    apron = unary_union(near)
    both = unary_union([part, apron])
    between = off(off(both, weld_m), -weld_m).difference(both)
    for g in keep_out:
        if not g.is_empty and between.intersects(g):
            between = between.difference(g)
    fill = [g for g in polygon_parts(shapely.set_precision(between, grid))
            if g.distance(part) <= grid and g.distance(apron) <= grid]
    if not fill:
        return part
    grown = shapely.set_precision(unary_union([part, *fill]), grid)
    bodies = [g for g in polygon_parts(grown) if g.intersects(part)]
    return max(bodies, key=lambda g: g.area) if bodies else part
