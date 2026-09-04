"""BASIN / PIT GEOMETRY (M4b): the pack's own below-grade facilities,
derived from its objects (RULINGS 2026-08-26 "the cut shape is derived
from the objects themselves — region-level, not structure-level"), and
how they enter the planar map — a floor face at the declared floor, a
wall band whose crest is the ground, and the cut they make in every
pavement and pad they lie under.

THE MODEL (law ``structures.toml [basin]``; RULINGS 2026-08-25f/26,
2026-08-28c item 3, 2026-09-01c/e, 2026-09-03b):

* every placed OBJ8's genuine solids (thickness-gated) are clipped to
  their portion ``admission_depth_m`` below the LOCAL terrain
  (``airport/obj8.py``: a vertex renders at ``DEM(anchor) + agl + y``,
  judged against the ground under it); the union is closed at
  ``footprint_close_m``, split into connected REGIONS, holes filled,
  regions under ``min_area_m2`` dropped;
* OPENNESS: a region the pack's own geometry stands over — clipped
  ABOVE the contact band, unioned, intersected with the ring — by more
  than ``max_covered_fraction`` is a building's basement or a bore, not
  a pit: REFUSED loudly with the fraction;
* the FLOOR: ``R_est`` (the median DEM along the ring) + the deepest
  genuine solid relative to it − (``bridge.floor_below_object_deck_m``
  + ``seat_margin_m``) — err deep (08-26); the floor is ONE face (role
  ``tunnel_trench``, the v1 oracle's declared-plate role);
* ``tunnel.wall_gap_m`` of UNOWNED ground round the floor, then the WALL
  BAND (``tunnel.wall_band_width_m``, role ``retaining_wall``) whose
  crest is the ground: the DEM where bare, the governed ground's value
  where its outer edge is shared (the rim LEVEL with the apron, 08-28c
  item 3) — the generator's ground rule, as for the tunnel wall;
* the facility CUTS every pavement and pad it lies under (08-26: inside
  a below-grade region the trench is senior to every pad/building
  authority; ``cuts_pads``) — never the runway family
  (``cuts_runway_family = false``: refused) and never a tunnel
  structure (the two are refused as overlapping, reported);
* a component whose rendered TOP lies under the ground by more than the
  contact band is BURIED geometry, not a shell (``shell_reaches_grade``):
  a pit's walls come up to grade by definition (v1's pit seed reads the
  ground-contact band) — measured LEMD: a v1 bake left grass clumps
  20–44 m under the local terrain, 12 phantom "pits" without this.

Every vertex is born on the identity grid, the band snapped AWAY from
the floor so the gap survives the arrangement's rounding (the M4
``_snap_out`` precedent).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport import obj8
from ..classify.roles import Cell, Classification
from ..law import Law
from ..law.tables import role_side
from ..model.airport import Airport
from ..model.frame import XY
from ..model.structures import Basin, Tunnel

__all__ = ["BasinStats", "read_objects", "build_basins", "FLOOR_ROLE", "WALL_ROLE"]

FLOOR_ROLE = "tunnel_trench"
WALL_ROLE = "retaining_wall"
RUNWAY_FAMILY = ("runway", "runway_crossing")
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass
class BasinStats:
    """What the basin pass read, made and refused."""

    objects: obj8.ObjReport | None = None
    object_read_s: float = 0.0
    regions: int = 0
    basins: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    small_regions: list[str] = _dc.field(default_factory=list)
    cells_cut: int = 0


def read_objects(airport: Airport, law: Law, cache: obj8.ResourceCache | None = None
                 ) -> tuple[list[obj8.PlacedObject], obj8.ObjReport]:
    """Every placed OBJ8 of the pack read once (``airport/obj8.py``)."""
    bl = law.tables.structures.basin
    pack_root = airport.pack.apt_dat_path
    import os
    pack_root = os.path.dirname(os.path.dirname(pack_root)) if pack_root else None
    rows = []
    for o in airport.dsf_objects:
        if not o.path.lower().endswith(".obj"):
            continue
        rows.append((o.id, o.path, o.xy, o.heading_deg,
                     o.y_offset_m if o.kind == "OBJECT_AGL" else None, o.kind))
    # the loader already resolved: hand the resolved path through the
    # index mapping so obj8 never walks the pack a second time
    index = {o.path: o.resolved_path for o in airport.dsf_objects if o.resolved_path}
    return obj8.read_placed_objects(rows, None, index, airport.dem.z,
                                    bl.admission_depth_m, bl.min_solid_thickness_m,
                                    bl.contact_band_m, cache,
                                    shell_reaches_grade=bl.shell_reaches_grade)


def _snap_ring(poly: Polygon, grid: float) -> Polygon | None:
    p = shapely.set_precision(poly, grid)
    if p.is_empty:
        return None
    if p.geom_type != "Polygon":
        parts = [g for g in shapely.get_parts(p) if g.geom_type == "Polygon"]
        if not parts:
            return None
        p = max(parts, key=lambda g: g.area)
    return Polygon(p.exterior.coords) if p.is_valid else None


def _band(floor: Polygon, gap: float, bw: float, grid: float
          ) -> tuple[Polygon, Polygon, Polygon] | None:
    """``(band polygon with its hole, outer footprint, centreline ring)``
    — the inner edge buffered ``gap`` + one grid step off the floor and
    snapped, widened by grid steps until the snapped floor and band
    clear each other by the law's gap; ``None`` when they cannot."""
    for k in range(4):
        g = gap + grid * (1 + k)
        inner = _snap_ring(floor.buffer(g, **_MITRE), grid)
        outer = _snap_ring(floor.buffer(g + bw, **_MITRE), grid)
        if inner is None or outer is None:
            return None
        if not inner.contains(floor) or not outer.contains(inner):
            continue
        band = outer.difference(inner)
        if band.is_empty or band.geom_type != "Polygon" or not band.is_valid:
            continue
        if floor.distance(band) >= gap - 1e-6:
            centre = floor.buffer(g + bw / 2, **_MITRE)
            return band, outer, centre
    return None


def build_basins(airport: Airport, classification: Classification, law: Law,
                 tunnels: _t.Sequence[Tunnel], objects: _t.Sequence[obj8.PlacedObject],
                 cache: obj8.ResourceCache | None = None
                 ) -> tuple[Classification, tuple[Basin, ...], BasinStats]:
    """The classification with the basins applied (cells cut, floor and
    wall cells added, the footprints as keep-outs), the records, and the
    stats.  Nothing below grade comes back unchanged."""
    stats = BasinStats()
    bl = law.tables.structures.basin
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    if bl.floor != "deepest_solid" or bl.rim != "ground":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r}: only "
                         "'deepest_solid' / 'ground' are generated")
    below = [o for o in objects if o.below_grade is not None]
    if not below:
        return classification, (), stats
    u = unary_union([o.below_grade for o in below])
    u = u.buffer(bl.footprint_close_m, **_MITRE).buffer(-bl.footprint_close_m, **_MITRE)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and not g.is_empty]
    stats.regions = len(parts)
    rings: list[Polygon] = []
    for g in sorted(parts, key=lambda g: -g.area):
        if g.area < bl.min_area_m2:
            stats.small_regions.append(f"{g.area:.0f} m2 at {_ll(airport, g)}")
            continue
        rings.append(Polygon(g.exterior.coords))
    if not rings:
        return classification, (), stats

    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    runway_u = unary_union([p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    tunnel_u = unary_union([p for p, c in zip(polys, cells) if c.kind == "structure"]) \
        if any(c.kind == "structure" for c in cells) else None
    cache = cache or obj8.ResourceCache(bl.min_solid_thickness_m)
    boxed = [o for o in objects if o.plan_bbox is not None]
    box_tree = STRtree([o.plan_bbox for o in boxed]) if boxed else None
    cover_cache: dict[str, object] = {}
    grid = law.tables.emit.identity.min_distinct_spacing_m
    gap, bw = tn.wall_gap_m, tn.wall_band_width_m
    margins = br.floor_below_object_deck_m + bl.seat_margin_m
    basins: list[Basin] = []
    new_cells: list[tuple[str, str, Polygon, tuple[tuple[XY, ...], ...]]] = []
    knives: list[Polygon] = []
    for k, ring in enumerate(rings):
        bid = f"basin:{k}"
        members = [o for o in below if o.below_grade.intersects(ring)]
        # OPENNESS (founding spec §2.1 item 2): the pack's own geometry
        # above the contact band over the ring
        cov = 0.0
        if box_tree is not None:
            covering = []
            for i in box_tree.query(ring, predicate="intersects"):
                o = boxed[int(i)]
                if o.id not in cover_cache:
                    cover_cache[o.id] = obj8.above_grade_footprint(
                        o, cache, airport.dem.z, bl.contact_band_m)
                if cover_cache[o.id] is not None:
                    covering.append(cover_cache[o.id])
            if covering:
                cov = unary_union(covering).intersection(ring).area / ring.area
        if cov > bl.max_covered_fraction:
            stats.refused.append(f"{bid}: {cov:.0%} of its {ring.area:.0f} m2 is covered by "
                                 f"the pack's own geometry above the contact band "
                                 f"(max_covered_fraction {bl.max_covered_fraction:.0%}) at "
                                 f"{_ll(airport, ring)}")
            continue
        if runway_u is not None and ring.intersects(runway_u) and \
                ring.intersection(runway_u).area > 1e-6:
            stats.refused.append(f"{bid}: reaches the runway family (cuts_runway_family "
                                 f"= false) at {_ll(airport, ring)}")
            continue
        # R_est along the ring; the deepest genuine solid of the members
        rest = _rim_estimate(airport, ring, bl.rim_sample_step_m)
        if rest is None:
            stats.refused.append(f"{bid}: no DEM along the ring at {_ll(airport, ring)}")
            continue
        smin_z = min(o.solid_min_z for o in members if o.solid_min_z is not None)
        floor_z = rest + (smin_z - rest) - margins
        floor = _snap_ring(ring.simplify(grid / 2.0), grid)
        if floor is None or floor.area < bl.min_area_m2 * 0.5:
            stats.refused.append(f"{bid}: the ring does not survive the identity grid")
            continue
        geom = _band(floor, gap, bw, grid)
        if geom is None:
            stats.refused.append(f"{bid}: the wall band cannot clear the floor by the gap "
                                 f"(a bend tighter than the band) at {_ll(airport, ring)}")
            continue
        band, outer, centre = geom
        if tunnel_u is not None and outer.buffer(grid).intersects(tunnel_u):
            stats.refused.append(f"{bid}: overlaps a tunnel structure at {_ll(airport, ring)}")
            continue
        floor_ref, wall_ref = f"basin_floor:{k}", f"basin_wall:{k}"
        new_cells.append((FLOOR_ROLE, floor_ref, floor, ()))
        new_cells.append((WALL_ROLE, wall_ref, band,
                          tuple(tuple(h.coords)[:-1] for h in band.interiors)))
        knives.append(outer)
        notes = [f"{len(members)} object(s)", f"covered {cov:.0%}",
                 f"rendered deepest solid {smin_z:.2f}"]
        basins.append(Basin(bid, tuple(sorted({o.path for o in members})), floor_z,
                            floor_ref, wall_ref, tuple(floor.exterior.coords)[:-1],
                            tuple(centre.exterior.coords)[:-1], rest, smin_z, smin_z - rest,
                            cov, float(floor.area), _ll_pair(airport, ring), tuple(notes)))
    stats.basins = len(basins)
    if not basins:
        return classification, (), stats
    knife = unary_union(knives)
    out_cells: list[Cell] = []
    for c, p in zip(cells, polys):
        if c.role in RUNWAY_FAMILY or c.kind == "structure" or not p.intersects(knife):
            out_cells.append(c)
            continue
        if c.role == "building" and not bl.cuts_pads:
            out_cells.append(c)
            continue
        rest_p = p.difference(knife)
        stats.cells_cut += 1
        for j, part in enumerate(_parts(rest_p)):
            if part.area < 0.25:
                continue
            out_cells.append(Cell(len(out_cells), c.role, c.ref if j == 0 else f"{c.ref}#{j}",
                                  tuple(part.exterior.coords)[:-1],
                                  tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                  c.code_number, c.code_letter, c.side, c.kind,
                                  dict(c.evidence, basin_cut=1.0)))
    for role, ref, poly, holes in new_cells:
        out_cells.append(Cell(len(out_cells), role, ref, tuple(poly.exterior.coords)[:-1],
                              holes, None, None, role_side(law, role), "structure", {}))
    out_cells = [_dc.replace(c, id=i) for i, c in enumerate(out_cells)]
    cl = _dc.replace(classification, cells=tuple(out_cells),
                     keepouts=tuple(classification.keepouts)
                     + tuple(tuple(k.exterior.coords)[:-1] for k in knives),
                     stats={**dict(classification.stats), "basins": len(basins),
                            "basin_cells_cut": stats.cells_cut,
                            "basins_refused": len(stats.refused)})
    return cl, tuple(basins), stats


def _rim_estimate(airport: Airport, ring: Polygon, step: float) -> float | None:
    """``R_est``: the MEDIAN DEM along the ring, ``step`` apart (never a
    point sample at the anchor — OTHH Dewatering_01 read 0.80 against a
    rim of 0.71–2.96)."""
    from statistics import median
    ext = ring.exterior
    n = max(4, int(math.ceil(ext.length / step)))
    vals = []
    for i in range(n):
        p = ext.interpolate(ext.length * i / n)
        z = float(airport.dem.z(p.x, p.y))
        if not math.isnan(z):
            vals.append(z)
    return float(median(vals)) if vals else None


def _ll_pair(airport: Airport, ring: Polygon) -> tuple[float, float]:
    _to_xy, to_ll = airport.frame.transformers()
    p = ring.representative_point()
    return to_ll(p.x, p.y)


def _ll(airport: Airport, ring: Polygon) -> str:
    la, lo = _ll_pair(airport, ring)
    return f"{la:.6f},{lo:.6f}"


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]


def object_decks(objects: _t.Sequence[obj8.PlacedObject]) -> list[tuple[str, Polygon, float]]:
    """``(object id, hard-deck footprint, rendered deck top)`` per
    hard-deck object — the tunnel pass's object bridges."""
    out = []
    for o in objects:
        if o.hard_deck is None or o.deck_top_z is None:
            continue
        for part in _parts(o.hard_deck):
            out.append((o.id, part, float(o.deck_top_z)))
    return out
