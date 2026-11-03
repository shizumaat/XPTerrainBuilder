"""ROADS INSIDE A LOT ARE THE LOT (owner RULINGS 2026-10-14a (2), extending
the free-road ruling of 2026-07-27 — "roads inside or edge-sharing an apron
ARE the apron" — to groundside lots; issue #609).

The owner: "stop trying to treat lanes in the lot as roads, only roads
where there's a gap of no pavement, roads connecting between lots, etc."
A mapped road that runs INSIDE a lot is never ribboned (the mint subtracts
every standing cell).  This module reads the other half: a stretch of a
mapped road whose ribbon runs ALONG a lot's edge — its axis within the
ribbon's half-width (no pavement gap: THE GAP, below) of the
lot, outside it, over at least two lane widths — is SPLIT OFF as a LOT
CANDIDATE (:func:`split_lot_candidates`, issue #684): a ribbon cell of its
own, the road it is until the ramp is read (``airport/lot_road_settle``
settles it: on the road's climb to a raised pad it stays road, owner Q366;
elsewhere it becomes the lot).  A road meeting a lot END-ON (its mouth: the
axis comes within the half-width over about one half-width) and a road
across open ground between two lots stay road.

THE GAP (owner 2026-11-03, #684 Q350 / Q363): "If there's no gap between
lot and road pavement it becomes part of the lot.  If there's more than
0.5m gap, it stays separate road", and a gap up to 0.5 m is the lot too
(Q363 a).  The ribbon is the way's axis buffered by its half-width, so the
PAVEMENT GAP beside the axis is its distance to the lot less the
half-width: up to :data:`LOT_GAP_M` (plus one step of the slice's noding
grid) is the lot, more is road.  The airside bands' envelope is no
exception (the owner's rule replaces 13ar's question there; a candidate
is late, so stage 1 never reads it).

ONE SPLIT SITE, AFTER EVERY MINT (issue #684; 14h (c) "after stage 1 is
insulated"): the ribbons are minted, gap-pieced, welded and cut at the
walls as roads, and only then split — the footprint is a partition of the
ribbon, so every earlier reader saw the road it sees today.  A candidate is
a RIBBON (``model.planar.is_osm_ribbon_ref``, so a late cell): it joins the
finished map (pass C) as a ribbon, so stage 1 — the airside — never reads
it, and every reader before the ramp reads it as the road it is.
MEASURED (lane lotroads arm A, the strips minted at mint time as stage-1
cells): HECA apron ``dsf:objpav402`` 0.62 m and 30 pads up to 0.87 m.

A LOT is a standing groundside pavement cell that is not road: roles
:data:`LOT_ROLES`, never a §53 gap piece (a last-stage follower; a lot
minted beside it would stand before the piece it is part of) and never a
§52 facade strip (a pad-level kerb under a canopy, not a lot).

MEASURED SPJC building24 (main 62db0dd93): pad road ``-6132#1`` ran
between two concrete lots (``dsf:pol37``, ``dsf:pol36#1``) along the pad's
east rim, welded to the pad at 24.36 m and to the lots at 28.1 m across
its 7 m width — the cross-fall rows of #658."""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..airport.road_ways import ribbon_half_width_m
from ..geom.parts import line_parts
from ..model.planar import (
    OSM_RIBBON_FEEDS,
    is_facade_strip_ref,
    is_gap_ref,
    is_osm_ribbon_ref,
)
from .evidence import polygon_parts

__all__ = ["LOT_ROLES", "LOT_GAP_M", "split_lot_candidates"]

#: The groundside pavement a road along it becomes part of: the lot and
#: the landside paved island (``roles.open_pavement_role`` / the demotion
#: ladder's two landside classes).
LOT_ROLES = ("parking_lot", "groundside_pavement")

#: The pavement gap (m) up to which a road beside a lot IS the lot; a wider
#: gap is a separate road (owner 2026-11-03, #684 Q350 / Q363 a).
LOT_GAP_M = 0.5


def _lot_cells(cells) -> list[tuple[object, Polygon]]:
    """The standing lots among ``cells``: ``(cell, polygon)``.  Never a §52
    facade STRIP: it stands at its host pad's level (``model.planar.
    facade_strip_host``), and a road along it is not inside a parking lot
    (MEASURED SPJC: the kerb roads beside five terminal canopies read as
    ``facstrip:…#road<k>`` and moved ``big_roads:-331`` 6.1 m)."""
    return [(c, Polygon(c.ring, c.holes)) for c in cells
            if c.role in LOT_ROLES and c.side == "groundside"
            and not is_gap_ref(getattr(c, "ref", ""))
            and not is_facade_strip_ref(getattr(c, "ref", ""))]


def _lot_stretches(line: LineString, lots_union, reach_m: float,
                  min_along_m: float) -> list[tuple[float, float]]:
    """The arclength intervals of ``line`` that run ALONG a lot: outside
    ``lots_union``, within ``reach_m`` of it, each at least ``min_along_m``
    long (a mouth meeting the lot end-on is shorter)."""
    if lots_union.is_empty or line.length <= 0.0:
        return []
    band = lots_union.buffer(reach_m).difference(lots_union)
    out = []
    for part in line_parts(line.intersection(band)):
        if part.length < min_along_m:
            continue
        a = line.project(shapely.geometry.Point(part.coords[0]))
        b = line.project(shapely.geometry.Point(part.coords[-1]))
        a, b = min(a, b), max(a, b)
        if b - a >= min_along_m:
            out.append((a, b))
    return sorted(out)


def _split_lot_ribbon(rib, line: LineString, lots: list[tuple[object, Polygon]],
                     hw: float, grid: float, min_area: float,
                     gap_m: float = LOT_GAP_M):
    """``rib`` (one way's ribbon) cut in two: ``(road, parts)`` — the road's
    remainder and the lot parts, each ``(lot cell, polygon)`` with the lot
    it runs along (the nearest; the one it shares most edge with on a tie).
    A PARTITION of ``rib``: a lot part under ``min_area`` stays road, a road
    part under it joins the lot part it shares most edge with.  ``gap_m``:
    the pavement gap read as none (module doc, THE GAP)."""
    if not lots or rib.is_empty:
        return rib, []
    reach = grid + gap_m
    near = [(c, p) for c, p in lots if p.distance(rib) <= reach]
    if not near:
        return rib, []
    union = unary_union([p for _c, p in near])
    spans = _lot_stretches(line, union, hw + reach, 2.0 * hw)
    if not spans:
        return rib, []
    zone = unary_union([substring(line, a, b).buffer(
        hw + reach, cap_style="flat", join_style="mitre", mitre_limit=2.0)
        for a, b in spans])
    parts = []
    for part in polygon_parts(shapely.intersection(rib, zone, grid_size=grid)):
        if part.area < min_area:
            continue
        best = min(near, key=lambda cp: (
            round(cp[1].distance(part), 3),
            -cp[1].buffer(reach).intersection(part.boundary).length))
        parts.append([best[0], part])
    if not parts:
        return rib, []
    road = shapely.difference(rib, unary_union([p for _c, p in parts]), grid_size=grid)
    kept = []
    for piece in polygon_parts(road):
        if piece.area >= min_area:
            kept.append(piece)
            continue
        shared = [(piece.intersection(p.boundary).length, k) for k, (_c, p) in enumerate(parts)]
        best_len, k = max(shared)
        merged = shapely.union(parts[k][1], piece, grid_size=grid)
        if best_len <= 0.0 or merged.geom_type != "Polygon":
            kept.append(piece)
            continue
        parts[k][1] = merged
    road = unary_union(kept) if kept else Polygon()
    return road, [(c, p) for c, p in parts]


def split_lot_candidates(cells, airport, law, rules):
    """RULINGS 2026-10-14a (2) / 14h (c), issue #684: every mapped-road
    ribbon cell (``service_road``, :func:`model.planar.is_osm_ribbon_ref` —
    the patch's ribbons, the reach's and the pad roads alike) split at its
    stretches along a standing lot with no pavement gap
    (:func:`_split_lot_ribbon`, module doc THE GAP).  The lots are read
    ONCE, before any split (not transitive: a road beside a candidate is
    not lot).  A CANDIDATE is a ribbon cell like its road — role, side,
    kind and the ribbon's whole evidence — ref ``<feed>:<way id>#<k>`` (the
    way's next serial) plus ``lot_candidate`` = the lot's ref; the road's
    first remainder keeps the ribbon's ref, further ones take the next
    serials.  No lot role here: ``airport/lot_road_settle`` decides.
    Returns ``(cells, stats)``; ids re-numbered (they are positional)."""
    from .ribbon_mint import _ribbon_ways  # lazy: it imports roles
    stats = {"lot_candidates": 0, "lot_candidate_m2": 0.0}
    lots = _lot_cells(cells)
    ribs = [i for i, c in enumerate(cells)
            if c.role == "service_road" and is_osm_ribbon_ref(c.ref)]
    if not lots or not ribs:
        return list(cells), stats
    ways = {f"{OSM_RIBBON_FEEDS[w.kind]}:{w.id}": (w, ln)
            for w, ln in _ribbon_ways(airport, rules)}
    tree = STRtree([p for _c, p in lots])
    grid = rules.cells.snap_grid_m
    min_area = rules.cells.min_area_m2
    serial = _serials(cells)
    out_of: dict[int, list] = {}
    for i in ribs:
        c = cells[i]
        base = str(c.ref).split("#", 1)[0]
        if base not in ways:
            continue
        w, line = ways[base]
        rib = Polygon(c.ring, c.holes)
        near = [lots[j] for j in tree.query(rib.buffer(grid + LOT_GAP_M).envelope)]
        if not near:
            continue
        road, parts = _split_lot_ribbon(rib, line, near,
                                        ribbon_half_width_m(w.tags, law), grid, min_area)
        if not parts:
            continue
        pieces = [(None, p) for p in polygon_parts(road)] + list(parts)
        new = []
        for k, (lot, piece) in enumerate(pieces):
            ref = c.ref if k == 0 else f"{base}#{serial[base]}"
            if k:
                serial[base] += 1
            ev = c.evidence if lot is None else {**c.evidence, "lot_candidate": lot.ref}
            new.append(_dc.replace(c, ref=ref, ring=tuple(piece.exterior.coords)[:-1],
                                   holes=tuple(tuple(h.coords)[:-1] for h in piece.interiors),
                                   evidence=ev))
            if lot is not None:
                stats["lot_candidates"] += 1
                stats["lot_candidate_m2"] += piece.area
        out_of[i] = new
    stats["lot_candidate_m2"] = round(stats["lot_candidate_m2"], 1)
    out = [n for i, c in enumerate(cells) for n in out_of.get(i, (c,))]
    return [_dc.replace(c, id=i) for i, c in enumerate(out)], stats


def _serials(cells) -> dict[str, int]:
    """Per ribbon ref base (``<feed>:<way id>``), the next free serial: one
    past the largest ``#<k>`` its cells carry."""
    out: dict[str, int] = {}
    for c in cells:
        if not is_osm_ribbon_ref(c.ref):
            continue
        base, _sep, rest = str(c.ref).partition("#")
        k = int(rest) if rest.isdigit() else 0
        out[base] = max(out.get(base, 1), k + 1)
    return out
