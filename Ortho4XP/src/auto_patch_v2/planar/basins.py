"""BASIN / PIT GEOMETRY (M4b, admission rewritten M4d): the pack's own
below-grade facilities, derived from its objects (RULINGS 2026-08-26 "the
cut shape is derived from the objects themselves — region-level, not
structure-level"; 2026-09-04i "admission is by the object's own
geometry, every refusal names its reason"), and how they enter the
planar map — a floor face at the declared floor, a wall band whose crest
is the ground, and the cut they make in every pavement and pad they lie
under.

THE ADMISSION RULE (law ``structures.toml [basin]``; RULINGS 2026-09-04i
04f-2/3, 2026-08-26, 2026-08-25 §2.1/§2.2, 2026-08-28c item 3,
2026-09-01c/e, 2026-09-03b):

1. FLOOR WITNESS — a genuine solid component (thickness ≥
   ``min_solid_thickness_m``, §2.1) whose shell RIM REACHES GRADE — its
   rendered top within ``contact_band_m`` of the local ground, neither
   buried under it (``shell_reaches_grade``) nor passing through it
   (``rim_reaches_grade``; v1's pit seed) — and which carries a FLOOR
   PLATE: near-horizontal solid faces (``floor_plate_normal_y_min``)
   lying ``admission_depth_m`` or more under the LOCAL ground
   (``airport/obj8.py``: a vertex renders at ``DEM(anchor) + agl + y``,
   judged against the ground under it).  Walls without a floor witness
   nothing — REFUSED by resource as "no genuine solid floor" (LEMD's
   flat-plane cargo skirts); a floor whose shell rises through the
   ground is a BUILDING standing on the pack's plane over real relief
   — REFUSED by resource with its height above the ground (LEMD's cargo
   terminal: slab 5.8 m under the local ground, walls 15 m above it).
2. REGION — the union of the witnesses' footprints BELOW THE GROUND
   (not below the admission plane: the cut must reach the shell's rim —
   under the 2.5 m clip OTHH's Drainage_06 bowl split into three pieces
   with its −2.51 m floor between them left uncut), closed at
   ``footprint_close_m``, one region per connected part.  NO AREA GATE:
   ``min_area_m2`` is reported per basin as a diagnostic.
3. RIM DIAGNOSTIC — the ring's stations (``rim_sample_step_m`` apart)
   farther than ``footprint_close_m`` from the member OBJECTS' at-grade
   geometry (every component's geometry from ``contact_band_m`` under
   the ground upward) are REPORTED per basin as its open length, never
   a refusal: OTHH's owner-accepted Dewatering pits read 1–2 of 46
   stations open (2.5–3.6 m) where a buried culvert leaves the shell.
4. COVER — the pack's geometry above the contact band over the region
   (EVERY solid component of every object: a roof sheet is cover) is
   REPORTED against ``max_covered_fraction`` (a diagnostic, never a
   refusal).  A covered region is a COVERED PIT — the cover is the
   object, the terrain still needs the cutout under it — UNLESS it is a
   BASEMENT: the floor lies wholly (to within a ``footprint_close_m / 2``
   sliver) under solid geometry the floor-owning objects THEMSELVES hold
   at or above the ground (a roof, a lid flush with the ground: LEMD's
   v1-sunk cargo sheds) — then no pit: the terrain there is the
   building's pad and the pad law governs (``building_pad``); REFUSED
   naming the pads.
5. KEPT — the runway family is never cut (``cuts_runway_family``), a
   tunnel structure is never cut (overlap refuses), the ring must have a
   DEM, survive the identity grid and clear its wall band by the gap.

THE FLOOR: ``R_est`` (the median DEM along the ring) + the deepest
genuine solid of the members relative to it − (``bridge.
floor_below_object_deck_m`` + ``seat_margin_m``) — err deep (08-26); the
floor is ONE face (role ``tunnel_trench``).  ``tunnel.wall_gap_m`` of
UNOWNED ground round the floor, then the WALL BAND (``tunnel.
wall_band_width_m``, role ``retaining_wall``) whose crest is the ground:
the DEM where bare, the governed ground's value where its outer edge is
shared (the rim LEVEL with the apron, 08-28c item 3 — the generator's
station tie).  The facility CUTS every pavement and pad it lies under
(08-26: inside a below-grade region the trench is senior to every
pad/building authority; ``cuts_pads``).

Every vertex is born on the identity grid, the band snapped AWAY from
the floor so the gap survives the arrangement's rounding (the M4
``_snap_out`` precedent).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import shapely
from shapely.geometry import Point, Polygon
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
    """What the basin pass read, made and refused.  ``refused`` carries
    every refusal with its reason and numbers (04i); ``small_regions``
    lists basins ADMITTED under the ``min_area_m2`` diagnostic."""

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
                                    shell_reaches_grade=bl.shell_reaches_grade,
                                    floor_plate_normal_y_min=bl.floor_plate_normal_y_min,
                                    rim_reaches_grade=bl.rim_reaches_grade)


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


def _rim_open(ring: Polygon, rim_geom, step: float, reach: float
              ) -> tuple[int, int, XY | None]:
    """The closed-region test (04i rule 3): ``(open stations, stations,
    the first open station)`` — a station is OPEN when it lies farther
    than ``reach`` from the founding shells' at-grade geometry."""
    ext = ring.exterior
    n = max(4, int(math.ceil(ext.length / step)))
    open_n = 0
    first: XY | None = None
    for i in range(n):
        p = ext.interpolate(ext.length * i / n)
        if rim_geom is None or rim_geom.distance(p) > reach:
            open_n += 1
            if first is None:
                first = (p.x, p.y)
    return open_n, n, first


def _no_floor_refusals(rep: obj8.ObjReport | None, bl) -> list[str]:
    """Rule 1's refusals, by resource: deep enough but no floor plate (a
    skirt), or a floor whose shell rises through the ground (a building
    standing on the pack's plane)."""
    if rep is None:
        return []
    out = []
    for path, (n, top, depth) in sorted(rep.through_grade.items(), key=lambda kv: -kv[1][1]):
        out.append(f"{os.path.basename(path)} x{n}: its floor lies {-depth:.2f} m under the local "
                   f"ground but the shell carrying it rises {top:.2f} m above the ground (> "
                   f"contact_band_m {bl.contact_band_m}) — a shell through the ground is a "
                   f"building on the pack's plane or a structure standing in a pit, never the "
                   f"pit itself (04i rule 1: a pit's rim tops out at grade)")
    for path, (n, depth, z_min) in sorted(rep.no_floor.items(), key=lambda kv: kv[1][1]):
        out.append(f"{os.path.basename(path)} x{n}: genuine solids reach {depth:.2f} m under "
                   f"the local ground (rendered {z_min:.2f}) but carry NO floor plate "
                   f"(0 m2 of solid faces with |n_y| >= {bl.floor_plate_normal_y_min} at "
                   f">= {bl.admission_depth_m} m depth) — a skirt, not a pit (04i rule 1)")
    return out


def build_basins(airport: Airport, classification: Classification, law: Law,
                 tunnels: _t.Sequence[Tunnel], objects: _t.Sequence[obj8.PlacedObject],
                 cache: obj8.ResourceCache | None = None,
                 report: obj8.ObjReport | None = None
                 ) -> tuple[Classification, tuple[Basin, ...], BasinStats]:
    """The classification with the basins applied (cells cut, floor and
    wall cells added, the footprints as keep-outs), the records, and the
    stats.  Nothing below grade comes back unchanged; nothing is refused
    without its reason."""
    stats = BasinStats()
    bl = law.tables.structures.basin
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    if bl.floor != "deepest_solid" or bl.rim != "ground":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r}: only "
                         "'deepest_solid' / 'ground' are generated")
    stats.refused.extend(_no_floor_refusals(report, bl))
    witnessed = [o for o in objects if o.witnesses]
    if not witnessed:
        return classification, (), stats
    u = unary_union([w.below for o in witnessed for w in o.witnesses])
    u = u.buffer(bl.footprint_close_m, **_MITRE).buffer(-bl.footprint_close_m, **_MITRE)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and not g.is_empty]
    stats.regions = len(parts)
    rings = [Polygon(g.exterior.coords) for g in sorted(parts, key=lambda g: -g.area)]

    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    runway_u = unary_union([p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    tunnel_u = unary_union([p for p, c in zip(polys, cells) if c.kind == "structure"]) \
        if any(c.kind == "structure" for c in cells) else None
    pads = [(p, c.ref) for p, c in zip(polys, cells) if c.role == "building"]
    cache = cache or obj8.ResourceCache(bl.min_solid_thickness_m)
    boxed = [o for o in objects if o.plan_bbox is not None]
    box_tree = STRtree([o.plan_bbox for o in boxed]) if boxed else None
    cover_cache: dict[str, object] = {}
    grade_cache: dict[str, tuple] = {}
    grid = law.tables.emit.identity.min_distinct_spacing_m
    gap, bw = tn.wall_gap_m, tn.wall_band_width_m
    margins = br.floor_below_object_deck_m + bl.seat_margin_m
    basins: list[Basin] = []
    new_cells: list[tuple[str, str, Polygon, tuple[tuple[XY, ...], ...]]] = []
    knives: list[Polygon] = []
    for k, ring in enumerate(rings):
        bid = f"basin:{k}"
        site = _ll(airport, ring)
        members = [o for o in witnessed if any(w.below.intersects(ring) for w in o.witnesses)]
        wits = [w for o in members for w in o.witnesses if w.below.intersects(ring)]
        member_ids = {o.id for o in members}
        plate = unary_union([w.plate for w in wits]).intersection(ring).area
        for o in members:
            if o.id not in grade_cache:
                grade_cache[o.id] = obj8.at_grade_geometry(o, cache, airport.dem.z,
                                                           bl.contact_band_m)
        # ── rule 3: the rim diagnostic (reported, never a refusal) ────
        lines = [grade_cache[o.id][0] for o in members if grade_cache[o.id][0] is not None]
        rim_geom = unary_union(lines) if lines else None
        open_n, n, first = _rim_open(ring, rim_geom, bl.rim_sample_step_m, bl.footprint_close_m)
        rim_note = (f"rim stations beyond {bl.footprint_close_m} m of the shells' at-grade "
                    f"geometry: {open_n} of {n} ({open_n * ring.exterior.length / n:.0f} of "
                    f"{ring.exterior.length:.0f} m"
                    + (f", first at {_ll(airport, Point(first))}" if first else "") + ")")
        # ── rule 4: cover — reported; basement → the pad ──────────────
        cov = cov_own = 0.0
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
        owning = [grade_cache[o.id][1] for o in members if grade_cache[o.id][1] is not None]
        own = unary_union(owning) if owning else None
        if own is not None:
            cov_own = own.intersection(ring).area / ring.area
        if own is not None and \
                ring.difference(own).buffer(-bl.footprint_close_m / 2, **_MITRE).is_empty:
            pad_refs = sorted(ref for p, ref in pads if p.intersects(ring))
            stats.refused.append(
                f"{bid}: {ring.area:.0f} m2, floor plate {plate:.0f} m2, {cov_own:.0%} under its own "
                f"objects' solids at or above the ground — a BASEMENT, not a pit: the terrain there is the "
                f"building's pad ({', '.join(pad_refs) if pad_refs else 'no pad cell'}) under the "
                f"pad law (04i rule 4) at {site}")
            continue
        # ── rule 5: never the runway family ───────────────────────────
        if runway_u is not None and ring.intersects(runway_u) and \
                ring.intersection(runway_u).area > 1e-6:
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 reaches the runway family "
                                 f"(cuts_runway_family = false) at {site}")
            continue
        # R_est along the ring; the deepest genuine solid of the members
        rest = _rim_estimate(airport, ring, bl.rim_sample_step_m)
        if rest is None:
            stats.refused.append(f"{bid}: no DEM along the ring at {site}")
            continue
        smin_z = min(o.solid_min_z for o in members if o.solid_min_z is not None)
        floor_z = rest + (smin_z - rest) - margins
        floor = _snap_ring(ring.simplify(grid / 2.0), grid)
        if floor is None or floor.area < grid * grid:
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 does not survive the identity grid "
                                 f"({grid} m) at {site}")
            continue
        geom = _band(floor, gap, bw, grid)
        if geom is None:
            stats.refused.append(f"{bid}: the wall band cannot clear the floor by the gap "
                                 f"(a bend tighter than the band) at {site}")
            continue
        band, outer, centre = geom
        if tunnel_u is not None and outer.buffer(grid).intersects(tunnel_u):
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 overlaps a tunnel structure "
                                 f"(structures are never cut) at {site}")
            continue
        floor_ref, wall_ref = f"basin_floor:{k}", f"basin_wall:{k}"
        new_cells.append((FLOOR_ROLE, floor_ref, floor, ()))
        new_cells.append((WALL_ROLE, wall_ref, band,
                          tuple(tuple(h.coords)[:-1] for h in band.interiors)))
        knives.append(outer)
        kind = "covered pit" if cov > 0.0 else "pit"
        notes = [kind, f"{len(members)} object(s)", f"floor plate {plate:.0f} m2",
                 f"covered {cov:.0%} (own {cov_own:.0%}; diagnostic max {bl.max_covered_fraction:.0%})",
                 rim_note, f"rendered deepest solid {smin_z:.2f}"]
        if floor.area < bl.min_area_m2:
            notes.append(f"under the diagnostic min_area_m2 {bl.min_area_m2:.0f} (admitted, 04i)")
            stats.small_regions.append(f"{bid} {floor.area:.0f} m2 at {site}")
        basins.append(Basin(bid, tuple(sorted({o.path for o in members})), floor_z,
                            floor_ref, wall_ref, tuple(floor.exterior.coords)[:-1],
                            tuple(centre.exterior.coords)[:-1], rest, smin_z, smin_z - rest,
                            cov, float(floor.area), _ll_pair(airport, ring), tuple(notes),
                            float(plate), kind))
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


def _ll_pair(airport: Airport, geom) -> tuple[float, float]:
    _to_xy, to_ll = airport.frame.transformers()
    p = geom.representative_point() if geom.geom_type != "Point" else geom
    return to_ll(p.x, p.y)


def _ll(airport: Airport, geom) -> str:
    la, lo = _ll_pair(airport, geom)
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
