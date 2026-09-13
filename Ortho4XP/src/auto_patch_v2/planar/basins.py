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
   lying ``admission_depth_m`` or more under the LOCAL ground.  The rim
   is the shell's GROUND-CONTACT RING (RULINGS 2026-09-06f): solids of
   the same component above the band are cover or protrusions (a
   tower, a vent) up to ``rim_protrusion_max_fraction`` of its face
   area (LEMD85: 3.4 %, its tower +11.4 m over a 27,000 m2 plate);
   more is a shell through the ground
   (``airport/obj8.py``: a vertex renders at ``DEM(anchor) + agl + y``,
   judged against the ground under it).  Walls without a floor witness
   nothing — REFUSED by resource as "no genuine solid floor" (LEMD's
   flat-plane cargo skirts); a floor whose shell rises through the
   ground is a BUILDING standing on the pack's plane over real relief
   — REFUSED by resource with its height above the ground (LEMD's cargo
   terminal: slab 5.8 m under the local ground, walls 15 m above it).
2. REGION — the union of the witnessing components' OUTER PLAN
   FOOTPRINTS (spec §24 (4), owner RULINGS 2026-09-13g: the wall face at
   the TOP of the walls, ``FloorWitness.outer``), closed at
   ``footprint_close_m``, one region per connected part.  NO AREA GATE:
   ``min_area_m2`` is reported per basin as a diagnostic.  It was the
   witnesses' footprints CLIPPED BELOW THE GROUND — and that clip is
   taken at ONE plane per component (the DEM under its centroid), so
   every part of the shell standing above that plane was missing from
   the region: at LEMD's T4S pit the modelled road ramp left the cut the
   moment it climbed through 593.00, a 52 x 11 m notch a building pad
   then filled 2.92 m over the ramp.  (The clip is still the ADMISSION's
   evidence — rule 1 reads a floor under the ground.)
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
   BASEMENT: the floor lies under solid geometry the floor-owning
   objects THEMSELVES hold at or above the ground (a roof, a lid flush
   with the ground: LEMD's v1-sunk cargo sheds) over at least
   ``basement_cover_min`` of the region (RULINGS 2026-09-06c (1): a
   fraction, never an erosion test) — then no pit: the terrain there is
   the building's pad and the pad law governs (``building_pad``);
   REFUSED naming the pads.  Anything less covered is a pit.
5b. THE DATUM (RULINGS 2026-09-09ag, spec §13) — a basin is a SUNKEN
   SOLID: the depth is AUTHORED.  Applied INSIDE rule 1, at the witness
   (``obj8``), so nothing downstream ever sees a datum-relief slab: a
   component witnesses only when its floor stands ``authored_depth_min_m``
   under the placement's OWN render datum (``anchor_z + agl``, its
   rendered y = 0 plane) as well as under the local ground.  REFUSED by
   resource with its authored depth.  An ABSOLUTE cap on the datum's drop
   under the ground was REFUTED (measured): at 1.0 m it refused OTHH's 8
   tunnel objects, whose datum stands 3–8 m under the ground and whose
   floors are authored 15 m down.  Rule 1's local ground is the DEM at
   the component, so a pack authored as ONE FLAT PLANE over real relief
   (LEMD: Aerosoft, 32 m of relief under the terminal) reads an ordinary
   ground-floor slab — authored 0.5 m under its own datum — as 15 m
   under the local ground, with a genuine floor plate, a shell topping
   out in the band and a CLOSED rim.  Measured: OTHH's Drainage /
   Dewatering pits and LEMD's genuine ``Ground-FSX-LEMD37`` basin read
   3.82 / 13.14 / 15.0 / 7.05 m of AUTHORED depth; LEMD's 33 terminal-slab
   basins author 0.22–1.67 m, four of them a "floor" ABOVE their own
   datum.  A datum above the ground never relaxes the gate — the ground
   still governs there (a pit dug through a rise is measured from it).

5. KEPT — the runway family is never cut (``cuts_runway_family``), a
   tunnel structure is never cut (overlap refuses), the ring must have a
   DEM, survive the identity grid and clear its wall band by the gap.

THE FLOOR AND THE RIM (RULINGS 2026-09-06b (1)/(3); ``[cutout]``,
``basin.seat``): the floor is the RENDERED deepest genuine solid of the
members (``DEM(anchor) + agl + y``: the floor plate itself, no margin —
the anchor family is re-seated after the mesh so the plate lands ON it,
``basin.seat = "floor_plate"``); the floor face(s) (role
``tunnel_trench``) are the members' floor plates ⊕ ``floor_overlap_m``
(closed at ``footprint_close_m``); THE CUT HUGS THE WALL (owner RULINGS
2026-09-11t, spec §24 (1)): the at-grade RIM *is* the admitted region —
the shells' footprint below the ground, the object's outer wall face at
its top — set inside it only by ``rim_inset_fraction`` × the shell's
measured plan thickness (2026-09-08a), never widened outward, and the
stand-off that keeps the mesh's wall band distinct comes out of the
FLOOR (:func:`_floors_inside`); the VOID between them is one face (role ``retaining_wall``, exterior = the
rim, holes = the floors) never emitted as a surface — its rim is
emitted as a constrained ring at the ground (the DEM where bare, the
governed ground's value where shared: the rim LEVEL with the apron,
08-28c item 3) and the mesh makes the wall.  The facility CUTS every
pavement and pad it lies under at the rim (08-26: inside a below-grade
region the trench is senior to every pad/building authority;
``cuts_pads``).

THE FLOOR FOLLOWS A RAMP (owner RULINGS 2026-09-13g, spec §24 (5)): a
component of the basin's own shell whose near-horizontal DECK faces climb
from the floor plate to the rim at a drivable grade (``ramp_max_grade``)
is a RAMP CORRIDOR — its plan is a floor face of the trench and the
terrain under it takes the deck's authored elevation minus
``floor_clearance_m`` per station (``constraints/structures.basins``,
``Basin.deck_z_at``), never the one depth.  A bowl's BANK climbs from
floor to rim as well and is refused by its grade; every candidate is
reported in the basin's notes with its reading.

Every vertex is born on the identity grid; the FLOOR is snapped away
from the rim so the gap survives the arrangement's rounding (the M4
``snap_out`` precedent, now applied to the yielding side — the rim may
not move off the wall face, 11t §24 (1)).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport import basin_witness as _basin_witness
from ..airport import obj8
from ..classify.roles import Cell, Classification
from ..law import Law
from ..law.tables import role_side
from ..model.airport import Airport
from ..model.frame import XY
from ..model.structures import Basin, Tunnel
from .structure_geometry import rim_standoff

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


#: THE PACK READ ONCE, AND THE BASIN ADMISSION READ FIRST (owner
#: RULINGS 2026-09-10ax (2)): rule 1 — which placements carry a floor
#: witness — lives in ``airport/basin_witness.py`` so the skirt reader
#: and the re-seat plan can ask it BEFORE this region pass runs.  One
#: implementation, memoised on the shared ``ResourceCache``; the name
#: stays here because every caller of the region pass reads it here.
read_objects = _basin_witness.read_objects


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


def _floors(plates, overlap: float, close: float, grid: float) -> list[Polygon]:
    """The floor face(s): the plates ⊕ ``overlap``, closed at ``close``,
    snapped to the grid and widened by grid steps until every snapped
    part stands ≥ ``overlap`` outside the plates it covers (the overlap
    is a stand-off: never rounded under), largest first."""
    for k in range(4):
        g = plates.buffer(overlap + k * grid, **_MITRE)
        g = g.buffer(close, **_MITRE).buffer(-close, **_MITRE)
        out: list[Polygon] = []
        ok = True
        for fp in sorted(_parts(g), key=lambda q: -q.area):
            f = _snap_ring(fp.simplify(grid / 2.0), grid)
            if f is None or f.area < grid * grid:
                continue
            inside = plates.intersection(fp)
            if not inside.is_empty and (not f.contains(inside.buffer(-1e-6))
                                        or inside.distance(f.exterior) < overlap - 1e-6):
                ok = False
            out.append(f)
        if ok or k == 3:
            return out
    return []


def shell_thickness_m(region: Polygon, plates, step_m: float = 1.0,
                      max_m: float | None = None, exclude=None) -> float:
    """A basin shell's plan WALL thickness: the smallest distance from the
    floor ``plates``' edges (sampled every ``step_m``) to the shells'
    at-grade footprint ``region``'s edge — the thinnest wall between
    floor and footprint (OTHH's drainage shells: a plate inset 0.75 m
    all round reads 0.75).  A plate reaching the footprint's edge reads
    0 (no wall to hide the rim in); thicker than ``max_m``
    (``tunnel.object.wall_face_max_thickness_m``: a plan solid past it
    is a slab, not a wall) is capped there — an area ratio is NOT a
    thickness (LEMD basin:3, a 366 m² plate in a 452 m² region, read
    29 m by one).  Plate-edge samples inside ``exclude`` are not wall
    samples (RULINGS 2026-09-08b/c: a door well's sill line, where the
    plate leaves the well into the building)."""
    if plates.is_empty:
        return 0.0
    ext = region.exterior
    best = None
    for part in _parts(plates):
        ring = part.exterior
        n = max(4, int(math.ceil(ring.length / max(step_m, 1e-6))))
        for i in range(n):
            q = ring.interpolate(ring.length * i / n)
            if exclude is not None and exclude.intersects(q):
                continue
            d = float(ext.distance(q))
            best = d if best is None else min(best, d)
    t = best or 0.0
    return min(t, max_m) if max_m is not None else t


def _outer(w) -> Polygon:
    """THE REGION IS BUILT FROM THE SHELL'S OUTER PLAN FOOTPRINT (owner
    RULINGS 2026-09-13g, spec §24 (4)) — the wall face at the TOP of the
    walls, not ``FloorWitness.below``'s clip at the DEM under the
    component's centroid.  ``below`` is the ADMISSION's evidence (rule 1
    reads a floor under the ground); as the REGION it made the cut follow
    a contour of the terrain through the middle of the shell: at LEMD's
    T4S pit 11 of the 59 ring nodes stood 6–15 m from any wall, and the
    modelled road ramp — the shell's own deck, rising through that one
    plane — was cut out of the region as a 52 x 11 m notch that a
    building pad then filled 2.92 m over the ramp.  A record made before
    §24 (4) (a fixture) keeps ``below``."""
    return w.below if getattr(w, "outer", None) is None else w.outer


def _rim(region: Polygon, inset: float, grid: float) -> Polygon | None:
    """THE CUT HUGS THE WALL (owner RULINGS 2026-09-11t, spec §24 (1)):
    the at-grade rim is ``region`` — the shells' own footprint below the
    ground, i.e. THE OBJECT'S OUTER WALL FACE AT ITS TOP — set INWARD by
    ``inset`` (``cutout.rim_inset_fraction`` × the measured shell
    thickness, 2026-09-08a: the terrain drop happens inside the wall,
    hidden by the object) and snapped to the identity grid.  Nothing
    else: no buffer, no widening.

    WHAT WAS HERE BEFORE, AND WHY IT WENT (the owed 08e deviation (2)):
    the rim was widened OUTWARD by whole grid steps — every station, not
    the offending ones — until it contained every floor and cleared it by
    the stand-off.  A shell whose plate reaches its own footprint edge
    (LEMD's T4S pit reads shell 0.00 m thick) needs the floor's own
    ``floor_overlap_m`` plus the stand-off of room that the wall does not
    have, so the loop ran to k = 4 and put all 56 rim vertices 1.75–4.12 m
    (median 2.06) OUTSIDE the wall face — the owner's "gap between the
    outer edge and the apron" on 1.0.315, a shelf of pavement standing
    over nothing.  The stand-off is now taken from the FLOOR instead
    (:func:`_floors_inside`), at the region's ONE derivation site rather
    than by pushing the cut away from the object it is cutting for.
    ``None`` when the ring does not survive the grid."""
    return _snap_ring(region.buffer(-inset, **_MITRE) if inset > 1e-9 else region, grid)


def _floors_inside(floors: list[Polygon], rim: Polygon, standoff: float, grid: float
                   ) -> list[Polygon]:
    """The floor faces TRIMMED to stand ``standoff`` inside ``rim`` (§24
    (1)): the void the mesh makes the wall in is taken out of the FLOOR,
    never out of the cut's outline.  A floor already clear is returned
    unchanged (the identity case, and every basin whose shell has real
    thickness); one that survives the trim with no area at all is
    dropped, and an empty return refuses the basin exactly as a rim that
    could not clear used to."""
    inner = rim.buffer(-standoff, **_MITRE)
    if inner.is_empty:
        return []
    out: list[Polygon] = []
    for f in floors:
        if rim.contains(f) and f.distance(rim.exterior) >= standoff - 1e-6:
            out.append(f)
            continue
        for part in _parts(f.intersection(inner)):
            g = _snap_ring(part, grid)
            if g is None or g.area < grid * grid:
                continue
            # the snap may round a vertex back out: keep only what still
            # clears, taking one more grid step in when it does not
            if not (rim.contains(g) and g.distance(rim.exterior) >= standoff - 1e-6):
                g2 = _snap_ring(part.buffer(-grid, **_MITRE), grid)
                if g2 is None or g2.area < grid * grid or not rim.contains(g2):
                    continue
                g = g2
            out.append(g)
    return sorted(out, key=lambda q: -q.area)


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
                   f"contact_band_m {bl.contact_band_m}) over more than rim_protrusion_max_fraction "
                   f"{bl.rim_protrusion_max_fraction:.0%} of its face area — a shell through the "
                   f"ground is a building on the pack's plane or a structure standing in a pit, "
                   f"never the pit itself (04i rule 1: a pit's rim tops out at grade; "
                   f"2026-09-06f: a smaller protrusion is cover)")
    for path, (n, drop, depth, authored) in sorted(rep.datum_relief.items(),
                                                   key=lambda kv: -kv[1][1]):
        out.append(f"{os.path.basename(path)} x{n}: its floor reads {-depth:.2f} m under the local "
                   f"ground but only {authored:.2f} m under the placement's OWN render datum "
                   f"(< authored_depth_min_m {bl.authored_depth_min_m}), which itself stands "
                   f"{drop:.2f} m under that ground — a slab sitting on datum relief, not a sunken "
                   f"solid: the depth is the pack's flat plane over real relief, never authored "
                   f"(2026-09-09ag rule 5b)")
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
    co = law.tables.structures.cutout
    if bl.floor != "deepest_solid" or bl.rim != "ground" or bl.seat != "floor_plate":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r} / seat {bl.seat!r}: only "
                         "'deepest_solid' / 'ground' / 'floor_plate' are generated")
    if co.emit_wall_band:
        raise ValueError("cutout.emit_wall_band = true: only false is generated (RULINGS "
                         "2026-09-06b (1): no wall band, the mesh makes the wall)")
    stats.refused.extend(_no_floor_refusals(report, bl))
    witnessed = [o for o in objects if o.witnesses]
    if not witnessed:
        return classification, (), stats
    u = unary_union([_outer(w) for o in witnessed for w in o.witnesses])
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
    basins: list[Basin] = []
    new_cells: list[tuple[str, str, Polygon, tuple[tuple[XY, ...], ...]]] = []
    knives: list[Polygon] = []
    for k, ring in enumerate(rings):
        bid = f"basin:{k}"
        site = _ll(airport, ring)
        members = [o for o in witnessed if any(_outer(w).intersects(ring) for w in o.witnesses)]
        wits = [w for o in members for w in o.witnesses if _outer(w).intersects(ring)]
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
        # THE BASEMENT TEST IS A FRACTION (RULINGS 2026-09-06c (1)): own
        # cover of at least basement_cover_min = a basement; less = a pit,
        # covered or open.  The 04i erosion test ("wholly covered to
        # within a sliver") fired at 38 % on LEMD building16's 2 m2
        # regions — a sliver-wide remainder erodes to nothing.
        if own is not None and cov_own >= bl.basement_cover_min:
            pad_refs = sorted(ref for p, ref in pads if p.intersects(ring))
            stats.refused.append(
                f"{bid}: {ring.area:.0f} m2, floor plate {plate:.0f} m2, {cov_own:.0%} under its own "
                f"objects' solids at or above the ground (>= basement_cover_min "
                f"{bl.basement_cover_min:.0%}) — a BASEMENT, not a pit: the terrain there is the "
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
        # THE FLOOR = the rendered deepest genuine solid: the floor plate
        # itself (2026-09-06b (3); the plate seat below puts it there)
        deepest = min((o for o in members if o.solid_min_z is not None),
                      key=lambda o: o.solid_min_z)
        smin_z = float(deepest.solid_min_z)
        floor_z = smin_z
        # RULE 5b (RULINGS 2026-09-09ag, spec §13) is applied at its
        # SINGLE DERIVATION SITE — the floor witness (``obj8``, where the
        # component's own ground and the placement's render datum are both
        # in hand), so a datum-relief slab never founds a region, never
        # enters the below-grade seat skip and never takes a plate seat.
        # What is recorded here is the region-level reading of it.
        datum_z = float(deepest.anchor_z) + float(deepest.agl_m)
        datum_drop = rest - datum_z
        # the floor face(s): the members' floor plates ⊕ floor_overlap_m,
        # closed at footprint_close_m, on the identity grid
        plates_u = unary_union([w.plate for w in wits]).intersection(ring)
        floors = _floors(plates_u, co.floor_overlap_m, bl.footprint_close_m, grid)
        if not floors:
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 — no floor plate ({plate:.0f} m2) "
                                 f"survives the identity grid ({grid} m) at {site}")
            continue
        # the rim INSIDE the shells' footprint by rim_inset_fraction of
        # their thickness (09-08a), clearing the floors by the stand-off;
        # the void between
        shell_t = shell_thickness_m(ring, plates_u, grid,
                                    law.tables.structures.tunnel.object.wall_face_max_thickness_m)
        inset, standoff = rim_standoff(shell_t, co, grid)
        rim = _rim(ring, inset, grid)
        if rim is None:
            stats.refused.append(f"{bid}: the rim (shell {shell_t:.2f} m thick, inset "
                                 f"{inset:.2f}) does not survive the identity grid "
                                 f"({grid} m) at {site}")
            continue
        # THE STAND-OFF COMES OUT OF THE FLOOR (§24 (1)), never out of the
        # cut's outline: the rim is the wall face and the floor is trimmed
        # to clear it by the mesh wall band's width
        # ── §24 (5): THE FLOOR FOLLOWS A RAMP ─────────────────────────
        # The shell's own deck climbing from the floor to the rim is a
        # RAMP: the terrain under it is part of the trench (so the cut
        # reaches it at all) and follows the deck per station
        # (``constraints/structures.basins``), never the one depth.
        ramps: list[tuple[Polygon, list]] = []
        for o in members:
            idx = [w.comp_index for w in o.witnesses
                   if w.comp_index >= 0 and _outer(w).intersects(ring)]
            if not idx:
                continue
            ramps.extend(_basin_witness.ramp_decks(o, cache, idx, floor_z, rest, bl.contact_band_m,
                                         bl.floor_plate_normal_y_min, grid,
                                         bl.ramp_max_grade))
        trimmed = _floors_inside(floors, rim, standoff, grid)
        if not trimmed:
            stats.refused.append(f"{bid}: no floor plate ({plate:.0f} m2) survives the "
                                 f"stand-off {standoff:.2f} m inside the rim (shell "
                                 f"{shell_t:.2f} m thick) at {site}")
            continue
        floor_trim_m2 = sum(f.area for f in floors) - sum(f.area for f in trimmed)
        floors = trimmed
        # the ramp corridors become floor faces of their own, the plate's
        # floor keeping every metre it already had (``ring`` — the plate
        # seat's stations, 09ac (2) — is the plate face's, untouched)
        plate_floor_u = unary_union(floors)
        ramp_floors: list[Polygon] = []
        ramp_faces: list[tuple] = []
        for r in ramps:
            if not r["admitted"]:
                continue
            for part in _parts(r["ring"].intersection(rim).difference(plate_floor_u)):
                ramp_floors.extend(_floors_inside([part], rim, standoff, grid))
        ramp_floors = [f for f in ramp_floors if f.area >= grid * grid]
        # THE PUBLISHED DECK IS THE DECK OVER THE FLOOR IT GOVERNS.  A
        # corridor read off the shell runs past the trench — over the pit's
        # own floor plate at its foot, and out beyond the rim — and a face
        # there would state a profile for terrain no basin row owns (at
        # LEMD 78 of 138 deck vertices then read "buried" against the APRON
        # over them, −8.91 m, which is the wall, not the ramp).
        if ramp_floors:
            gov = unary_union(ramp_floors).buffer(grid, **_MITRE)
            for r in ramps:
                if not r["admitted"]:
                    continue
                ramp_faces.extend(t for t in r["faces"]
                                  if gov.covers(Point(sum(q[0] for q in t) / 3.0,
                                                      sum(q[1] for q in t) / 3.0)))
        if tunnel_u is not None and rim.buffer(grid).intersects(tunnel_u):
            # a sunken road (2026-09-08b/c Law B) is a STRUCTURE before this
            # pass runs: its plate is never a basement, by ORDER (spec §4)
            owner = next((t.id for t in tunnels if t.source != "osm" and len(t.axis) >= 2
                          and LineString(t.axis).buffer(t.half_width_m + grid).intersects(rim)),
                         None) if len(tunnels) else None
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 overlaps a tunnel structure "
                                 f"({owner or 'a bore ramp'}; structures are never cut) at {site}")
            continue
        all_floors = floors + ramp_floors
        void = rim.difference(unary_union(all_floors))
        floor_ref, wall_ref = f"basin_floor:{k}", f"basin_wall:{k}"
        for j, f in enumerate(all_floors):
            new_cells.append((FLOOR_ROLE, floor_ref if j == 0 else f"{floor_ref}#{j}", f, ()))
        for part in _parts(void):
            new_cells.append((WALL_ROLE, wall_ref, part,
                              tuple(tuple(h.coords)[:-1] for h in part.interiors)))
        knives.append(rim)
        kind = "covered pit" if cov > 0.0 else "pit"
        floor_area = sum(f.area for f in all_floors)
        # THE SEAT THE DESIGN IMPLIES (2026-09-06b (3)): the family's plate
        # y (the deepest member's, relative to its rendered y = 0 plane);
        # an anchor INSIDE the floor renders on the floor after the mesh,
        # one outside on its own ground — the post-mesh seat measures it
        plate_y = smin_z - deepest.anchor_z - deepest.agl_m
        a_pt = Point(deepest.xy)
        inside = any(f.contains(a_pt) for f in floors)
        mesh_pred = floor_z if inside else float(deepest.anchor_z)
        seat_expect = floor_z - (mesh_pred + deepest.agl_m + plate_y)
        prot = max(wits, key=lambda w: w.protrusion_fraction)
        notes = [kind, f"{len(members)} object(s)", f"floor plate {plate:.0f} m2",
                 f"shell {shell_t:.2f} m thick: rim inset {inset:.2f} m inside its footprint "
                 f"(THE CUT HUGS THE WALL, 11t §24 (1): the rim IS the outer face, never widened), "
                 f"stand-off {standoff:.2f} m taken out of the floor ({floor_trim_m2:.0f} m2 "
                 f"trimmed, 09-08a)",
                 f"covered {cov:.0%} (own {cov_own:.0%}; diagnostic max {bl.max_covered_fraction:.0%})",
                 rim_note, f"rendered deepest solid {smin_z:.2f} = the floor",
                 f"datum {datum_z:.2f} stands {datum_drop:+.2f} m under the ring's ground; "
                 f"authored depth {datum_z - smin_z:.2f} of {rest - smin_z:.2f} m below grade "
                 f"(>= authored_depth_min_m {bl.authored_depth_min_m}, 09ag rule 5b)",
                 (f"rim protrusion {prot.protrusion_fraction:.1%} of the shell's face area above "
                  f"the contact band, top +{prot.protrusion_top_m:.2f} m (<= "
                  f"rim_protrusion_max_fraction {bl.rim_protrusion_max_fraction:.0%}, 2026-09-06f: "
                  f"cover, not the rim)") if prot.protrusion_fraction > 0.0
                 else "rim tops out in the contact band",
                 f"floor faces {len(all_floors)} ({floor_area:.0f} m2 of {ring.area:.0f} m2 "
                 f"region)",
                 (f"ramp corridors {len(ramp_floors)} ({sum(f.area for f in ramp_floors):.0f} m2, "
                  f"{len(ramp_faces)} deck face(s)): the floor under them follows the deck "
                  f"per station (13g §24 (5))" if ramp_floors
                  else "no ramp corridor: the one depth stands everywhere (§24 (5))"),
                 "deck candidates: " + ("; ".join(
                     f"{r['area_m2']:.0f} m2 rise {r['rise_m']:.2f} m over run {r['run_m']:.1f} m "
                     f"= grade {r['grade']:.2f} — "
                     + ("RAMP" if r["admitted"] else f"refused ({r['reason']})")
                     for r in ramps) or "none"),
                 f"anchor {'INSIDE' if inside else 'outside'} the floor: plate y {plate_y:+.2f}, "
                 f"seat expect {seat_expect:+.2f} m"]
        if ring.area < bl.min_area_m2:
            notes.append(f"under the diagnostic min_area_m2 {bl.min_area_m2:.0f} (admitted, 04i)")
            stats.small_regions.append(f"{bid} {ring.area:.0f} m2 at {site}")
        basins.append(Basin(bid, tuple(sorted({o.path for o in members})), floor_z,
                            floor_ref, wall_ref, tuple(floors[0].exterior.coords)[:-1],
                            tuple(rim.exterior.coords)[:-1], rest, smin_z, smin_z - rest,
                            cov, float(floor_area), _ll_pair(airport, ring), tuple(notes),
                            float(plate), kind, tuple(ring.exterior.coords)[:-1],
                            tuple(o.id for o in members), float(plate_y),
                            str(deepest.id), inside,
                            float(seat_expect), float(deepest.agl_m),
                            tuple(tuple(f.exterior.coords)[:-1] for f in ramp_floors),
                            tuple(ramp_faces),
                            tuple(tuple(_lonlat(airport, x, y)
                                        for x, y in tuple(f.exterior.coords)[:-1])
                                  for f in ramp_floors),
                            tuple(tuple(_lonlat(airport, q[0], q[1]) + (q[2],) for q in t)
                                  for t in ramp_faces)))
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


def _lonlat(airport: Airport, x: float, y: float) -> tuple[float, float]:
    """``(lon, lat)`` — the SIDECAR's own ordering (the published corridor
    is read back by ``verify`` against the patch's lat/lon, never the
    planar frame's metres)."""
    la, lo = airport.frame.transformers()[1](x, y)
    return (float(lo), float(la))


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
