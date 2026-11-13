"""THE FRONTAGE ROAD AND ITS KERBSIDE (issue #2057; owner sim read
2026-11-13T16:01Z on KASE, the terminal's groundside forecourt).

The owner: the paved road area along the terminal "slopes down steeply from
the building ... that paved area graded relatively flat (cross-slope), the
slope moved into the unpaved area beyond, and the roads ramping down at
either END (longitudinally) rather than laterally".

MEASURED (KASE, control build ``lkase_ctl_KASE`` at 6c6d71d58, the drawn
mesh): the terminal's pad stands at 2370.07 m; the mapped road along its
landside facade (``airport_small_roads:-407``, ``tertiary``) runs 15-17 m
off the facade, so its ribbon (half-width 4 m) leaves an 11-13 m KERBSIDE
the map does not draw — the drop-off lanes and the walk, paved right up to
the building in the imagery.  Neither the road nor the kerbside was patch:
the road stood outside the airside envelope and was no pad road (it never
touches the pad: RULINGS 2026-10-09j (2), "a road with any gap is free").
The core drew the road level on the DEM and the kerbside as the slope
between the pad's edge and the road: 12-14 % over 20 m, ~20 % over the last
13 m to the facade.

THE RULE.  A mapped at-grade road whose ribbon stands within ``[road_contact]
contact_reach_m`` (the reach at which a road is in contact with a senior
surface it shares no vertex with) of a building pad SERVES that pad's
frontage: the gap between them is its kerbside, pavement the map does not
draw.  The stretch of the road within that reach (plus its half-width) of
the pad is minted as a PAD ROAD (``pad_road`` evidence: the #609 machinery
from here on), and the kerbside between the pad and the stretch's ribbon
(``geom/lens.lens_to_roads``, the pad fill's lens) as more of the same road,
welded to the pad by the one touch witness (``roles._cut_back_groundside``,
which the caller runs on every pad road).  So the kerbside and the road
take the pad's level at the rim and fall away from it only within the
road's hard 2 % cross-section (``road_cross_section (2026-08-25g)``,
RULINGS 2026-09-13bb); the road leaves the frontage along its own axis at
the design ramp grade (``pad_road_exit``, the last stage); beyond the far
kerb the ground is the DEM's, and it takes the relief.

Minted LAST, with the pad roads: nothing standing is overlapped or re-cut
(the ribbon and the kerbside are each cut by every cell standing), a road
already ribboned in the patch is never re-minted and gets no kerbside, and
airside is never touched (every airside cell is standing)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.road_ways import ribbon_half_width_m
from ..geom.lens import lens_to_roads
from ..law import Law
from ..model.airport import Airport
from ..model.planar import OSM_RIBBON_FEEDS
from .evidence import polygon_parts
from .lot_roads import lot_cells
from .ribbon_mint import (
    _interval_minus,
    _mint_spans,
    _Occupied,
    _ribbon_ways,
    _way_intervals,
    bridge_gaps,
)
from .rules import Rules

__all__ = ["mint_frontage_roads", "KERBSIDE_KEY"]

#: ``Cell.evidence`` flag of a kerbside cell (the pavement between a pad
#: and the road serving its frontage)
KERBSIDE_KEY = "kerbside"


def _serials(cells) -> dict[str, int]:
    """Per ref base, the next free ``#k`` (``pad_road_exit``'s numbering)."""
    out: dict[str, int] = {}
    for c in cells:
        base, _h, k = str(c.ref).partition("#")
        out[base] = max(out.get(base, 0), (int(k) if k.isdigit() else 0) + 1)
    return out


def _fronted(line, hw: float, pads: list[Polygon], reach: float) -> list[Polygon]:
    """The pads whose footprint the ribbon of ``line`` (half-width ``hw``)
    stands within ``reach`` of."""
    rib = line.buffer(hw, cap_style="flat")
    return [p for p in pads if rib.distance(p) <= reach]


def _frontage_span(line, pad: Polygon, reach: float) -> tuple[float, float] | None:
    """The arclength span of ``line`` along ``pad``'s frontage: from the
    first to the last of its stretches within ``reach`` of the footprint —
    ONE stretch per pad, so a facade's jogs (a recess the road passes a
    few metres too far from) never cut the road along it into pieces."""
    ivs = _way_intervals(line, pad.buffer(reach, join_style=2))
    return (ivs[0][0], max(b for _a, b in ivs)) if ivs else None


def _depth(line, span: tuple[float, float], pad: Polygon, hw: float, reach: float,
           step_m: float = 2.0) -> float:
    """THE KERBSIDE'S DEPTH along one pad's frontage span: the widest gap
    between the ribbon and the footprint over the span (a facade's recess
    is still the kerbside the road serves), at least ``reach`` and at most
    twice it (a courtyard behind the facade line is no kerbside)."""
    a, b = span
    n = max(2, int((b - a) / step_m) + 1)
    far = max(line.interpolate(a + (b - a) * i / (n - 1)).distance(pad) for i in range(n))
    return min(max(far - hw, reach), 2.0 * reach)


def _kerbside(pad: Polygon, rib, depth: float, occupied: _Occupied, keep_off):
    """The parts of the lens between ``pad`` and ``rib`` (``geom/lens``)
    on ground nothing holds yet, each touching both.  The lens is read at
    TWICE the kerbside's ``depth``, so its closing (half the reach) spans
    the whole gap: at ``depth`` a facade's recess as deep as the kerbside
    was left out — MEASURED KASE (lkase_arm_KASE, 39.21962, -106.86405): a
    1.4 m trough of DEM ground between the terminal's recess and the
    kerbside.  ``keep_off`` (the airside, one weld wide) is never taken:
    a kerbside is junior to the pad and the road, and welded to an apron
    it would be held by the apron's level as well (MEASURED SBRJ,
    ``small_roads:-2931``: 0.75 m against ``apron`` within its face)."""
    box = pad.buffer(4.0 * depth, join_style=2)
    held = unary_union([box.difference(occupied.cut(box)), keep_off.intersection(box)])
    lens = lens_to_roads(pad, [rib], 2.0 * depth, held)
    if lens is None:
        return []
    return [q for q in polygon_parts(lens.difference(pad)) if q.distance(rib) <= 1e-3]


def mint_frontage_roads(airport: Airport, cells: list, law: Law, rules: Rules,
                        add: _t.Callable) -> dict[str, float]:
    """Mint every frontage road stretch and its kerbside (module doc) with
    ``add`` (``roles.classify``'s); returns the stats."""
    stats = {"frontage_roads": 0, "frontage_road_m2": 0.0, "kerbsides": 0,
             "kerbside_m2": 0.0}
    reach = float(law.tables.emit.road_contact.contact_reach_m)
    pads = [Polygon(c.ring, c.holes) for c in cells if c.role == "building"]
    ways = _ribbon_ways(airport, rules)
    if reach <= 0.0 or not pads or not ways:
        return stats
    tree = STRtree(pads)
    standing = unary_union([Polygon(c.ring, c.holes) for c in cells])
    occupied = _Occupied(standing)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    sliver = 0.5 * weld
    # the airside, off which a road strip stands by one weld
    # (``planar/fill_road.road_strips``' own rule)
    keep_off = unary_union([Polygon(c.ring, c.holes) for c in cells
                            if c.side == "airside" and c.role != "building"]).buffer(weld)

    kept: list[Polygon] = []

    def stray(poly: Polygon, hw: float) -> bool:
        """A piece the standing cells cut off: thinner than one weld, or
        smaller than the shortest ribbon a road is minted at
        (``osm_roads.min_len_m`` x its width)."""
        return poly.area < rules.osm_roads.min_len_m * 2.0 * hw or \
            poly.buffer(-sliver).is_empty

    def keep(role, ref, poly, *rest):
        """``add``, less a stray piece of the ribbon."""
        if not stray(poly, hw):
            add(role, ref, poly, *rest)
            kept.append(poly)
    serial = _serials(cells)
    lots = lot_cells(cells)
    for w, line in ways:
        hw = ribbon_half_width_m(w.tags, law)
        near = [pads[j] for j in
                tree.query(line, predicate="dwithin", distance=hw + reach).tolist()]
        fronted = [(p, sp) for p in (_fronted(line, hw, near, reach) if near else [])
                   if (sp := _frontage_span(line, p, hw + reach))]
        # a stretch already patch (a ribbon, a pad road, a lot) is never
        # re-minted: only what the frontage adds, each piece a road's length
        spans = [(a, b) for a, b in _interval_minus(
            bridge_gaps(sorted(sp for _p, sp in fronted), 1e-6),
            _way_intervals(line, standing)) if b - a >= rules.osm_roads.min_len_m]
        if not spans:
            continue
        kept.clear()
        _k, _m2, rib = _mint_spans(w, line, spans, occupied, serial, Polygon(), law, rules,
                                   keep, {"pad_road": 1.0, "frontage_road": 1.0}, lots=lots)
        if rib is None:
            continue
        occupied.add(rib)
        if not kept:
            continue
        stats["frontage_roads"] += len(kept)
        stats["frontage_road_m2"] += sum(q.area for q in kept)
        rib = unary_union(kept)
        ref = f"{OSM_RIBBON_FEEDS[w.kind]}:{w.id}"
        for p, sp in fronted:
            depth = _depth(line, sp, p, hw, reach)
            for part in _kerbside(p, rib, depth, occupied, keep_off):
                if stray(part, hw):
                    continue
                n = serial.get(ref, 0)
                serial[ref] = n + 1
                add("service_road", ref if n == 0 else f"{ref}#{n}", part, "service_road",
                    None, None, {"osm_ribbon": 1.0, "highway": str(w.tags.get("highway")),
                                 "pad_road": 1.0, "frontage_road": 1.0, KERBSIDE_KEY: 1.0})
                occupied.add(part)
                stats["kerbsides"] += 1
                stats["kerbside_m2"] += part.area
    stats["frontage_road_m2"] = round(stats["frontage_road_m2"], 1)
    stats["kerbside_m2"] = round(stats["kerbside_m2"], 1)
    return stats
