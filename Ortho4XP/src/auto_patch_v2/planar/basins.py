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

THE FLOOR IS THE WHOLE ADMITTED REGION (owner RULINGS 2026-09-14n item 1 /
2026-09-14p, spec §24 (7)).  Once a region is admitted as a pit, the trench
floor covers the region MINUS the rim stand-off; the witnessed plate
DELIMITS NOTHING — it witnesses DEPTH.  (a) The witness is read over the
whole ADMITTED FAMILY: a sibling placement whose deep horizontal plate lies
inside an admitted region contributes it even when its own shell never
reaches grade (the ``buried_components`` skip in ``obj8`` is a pit-SEED
test), and every skipped buried component is NAMED with its area and depth.
(b) Where no plate lies under part of the region the floor still takes
``floor_z``: a rim-level island inside a pit is terrain standing inside the
object's walls.  MEASURED at OTHH 1.0.332 (the owner's read): the ten basins
cut 10–56 % of their regions — basin:6 879 of 4,330 m2, its middle a V-funnel
of raw terrain between two cut ends, because the 2,998 m2 floor slab is a
SIBLING placement skipped as buried.  After: 0.81–0.93 of the region, the
remainder being the 0.5 m wall band the rim needs (:func:`_region_floor`).

THE FLOOR FOLLOWS A RAMP (owner RULINGS 2026-09-13g, spec §24 (5)): a
component of the basin's own shell whose near-horizontal DECK faces climb
from the floor plate to the rim at a drivable grade (``ramp_max_grade``)
is a RAMP CORRIDOR — its plan is a floor face of the trench and the
terrain under it takes the deck's authored elevation minus
``floor_clearance_m`` per station (``constraints/structures.basins``,
``Basin.deck_z_at``), never the one depth.  A bowl's BANK climbs from
floor to rim as well and is refused by its grade; every candidate is
reported in the basin's notes with its reading.  Its ring is RE-NODED at
``ramp_station_m`` along the climb axis before emission (spec §24 (8), owner
RULINGS 2026-09-14s): the constraint half pins vertices that EXIST, and
VHHH's ``basin_floor:5#1`` — 2,794 m2 over 6.9 m of drop — carried four
interior vertices, so the per-station profile came out a four-triangle fan
with a 42 % step at its mouth (:func:`_renode`).

Every vertex is born on the identity grid; the FLOOR is snapped away
from the rim so the gap survives the arrangement's rounding (the M4
``snap_out`` precedent, now applied to the yielding side — the rim may
not move off the wall face, 11t §24 (1)).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time as _time
import typing as _t
from collections import OrderedDict as _od

import numpy as _np
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
from .basin_geometry import (_floors, _floors_inside, _outer, _ramp_axis, _region_floor,
                             _renode, _rim, _snap_ring, shell_thickness_m)
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
    #: THE AT-GRADE READ, TIMED (owner RULINGS 2026-09-13bp (iii)).  The
    #: rim and cover clips were UNTIMED beside a 6.8e-06 s
    #: ``object_read_s``, so VHHH's 2,626 s planar stage read as a hang.
    #: ``grade_calls`` is the placements asked, ``grade_unions`` the
    #: clip+union actually run (one per distinct ``(resource, planes)``),
    #: ``grade_vertices`` what they consumed.
    grade_geometry_s: float = 0.0
    #: THE REGION LOOP'S OWN UNIONS, TIMED PER SITE (owner 2026-09-13, round
    #: 2).  With the at-grade read memoised and the rim diagnostic indexed,
    #: VHHH's ``build_basins`` was still 1,378 s of a 1,755 s structure
    #: stage, and 1,038 s of it was 634 ``unary_union`` calls made HERE — an
    #: aggregate no report named.  Seconds per call site.
    union_s: dict = _dc.field(default_factory=dict)
    union_n: dict = _dc.field(default_factory=dict)
    grade_calls: int = 0
    grade_unions: int = 0
    grade_vertices: int = 0
    regions: int = 0
    basins: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    small_regions: list[str] = _dc.field(default_factory=list)
    #: EVERY SKIPPED BURIED COMPONENT NAMED (spec §24 (7) (a)): the
    #: object reader's own lines, carried here because the basin report
    #: is where a missing floor plate is looked for.
    buried_named: list[str] = _dc.field(default_factory=list)
    cells_cut: int = 0


#: THE PACK READ ONCE, AND THE BASIN ADMISSION READ FIRST (owner
#: RULINGS 2026-09-10ax (2)): rule 1 — which placements carry a floor
#: witness — lives in ``airport/basin_witness.py`` so the skirt reader
#: and the re-seat plan can ask it BEFORE this region pass runs.  One
#: implementation, memoised on the shared ``ResourceCache``; the name
#: stays here because every caller of the region pass reads it here.
read_objects = _basin_witness.read_objects

#: the end of the member walk (a member's index may legitimately be ``None``)
_DONE = object()



def _rim_open(ring: Polygon, rim_trees: _t.Iterable, step: float, reach: float
              ) -> tuple[int, int, XY | None]:
    """The closed-region test (04i rule 3): ``(open stations, stations,
    the first open station)`` — a station is OPEN when it lies farther
    than ``reach`` from the founding shells' at-grade geometry.

    ``rim_trees`` is a LAZY sequence of ONE INDEX PER MEMBER, never one
    index over the union — lazy because holding all of them is the same
    peak (owner 2026-09-13, round 2)
    (owner 2026-09-13, round 2).  The distance from a point to a set of
    lines is the minimum over the set, so unioning the members changes
    neither the point set nor that minimum — but at VHHH the union cost
    979.5 s over 96 rings, and materialising every member's linework at
    once cost basin:0 alone 60,402,378 ``LineString`` objects, 96.4 s and
    12.4 -> 34.9 GB of resident memory.  Per member, each index is one
    shell's parts; a station once closed is never asked again, so the
    query shrinks as the members are walked."""
    ext = ring.exterior
    n = max(4, int(math.ceil(ext.length / step)))
    pts = shapely.line_interpolate_point(ext, [ext.length * i / n for i in range(n)])
    near = _np.zeros(n, dtype=bool)
    todo = _np.arange(n)
    walk = iter(rim_trees)
    while todo.size:
        tree = next(walk, _DONE)
        if tree is _DONE:
            break
        if tree is None:
            continue
        hit = tree.query_nearest(pts[todo], max_distance=reach, all_matches=False)
        idx = _np.asarray(hit[0] if _np.ndim(hit) == 2 else hit, dtype=int)
        if idx.size:
            near[todo[idx]] = True
            keep = _np.ones(todo.size, dtype=bool)
            keep[idx] = False
            todo = todo[keep]
    open_i = _np.flatnonzero(~near)
    if open_i.size == 0:
        return 0, n, None
    p0 = pts[int(open_i[0])]
    return int(open_i.size), n, (float(p0.x), float(p0.y))


def _rim_index(geom):
    """One member's at-grade linework as an index over its PARTS: a point
    against a whole multi-part rim is an O(parts) GEOS distance (VHHH's
    96 rings cost 549,207 of them, 1,196 s of a 3,580 s build), and the
    rim reading is a REPORTED DIAGNOSTIC that refuses nothing.

    THE EMPTY TEST IS VECTORISED (owner RULINGS 2026-09-14q, scout
    ``v2partcost2``): ``g.is_empty`` is a PROPERTY read per part, and
    VHHH's 336 calls of ~370 k parts each made 120,820,793 of them — 137 s
    profiled, ~105 s shipped, to filter a list that is almost never
    filtered.  ``shapely.is_empty`` over the array is one C call and
    yields the same parts in the same order."""
    if geom is None:
        return None
    parts = shapely.get_parts(geom)
    if parts.size:
        parts = parts[~shapely.is_empty(parts)]
    return STRtree(parts) if parts.size else None


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


#: How many PLACEMENT-frame at-grade geometries the region loop keeps
#: alive at once (owner RULINGS 2026-09-13bp (ii)).  A ring asks each of
#: its members two or three times in one iteration and rings are disjoint
#: regions, so a window this wide is all the reuse there is — and it
#: bounds the retention that took VHHH's worker to 34.9 GB.  The
#: RESOURCE-level clip and union behind it are memoised for the whole
#: pass on the shared ``ResourceCache``; this only re-applies an affine.
_GRADE_WINDOW = 16

#: How many MEMBER RIM INDEXES the region loop keeps at once.  One shell's
#: linework can be 1.6 M parts, so this window is the ceiling on what the
#: rim diagnostic holds; the same two shells found their way into ~40 of
#: VHHH's rings, so a window at all is worth 1.25 s of part-derivation each.
_RIM_TREE_WINDOW = 4


class _LRU:
    """A tiny bounded most-recently-used map (``None`` = miss)."""

    def __init__(self, cap: int) -> None:
        self._cap = cap
        self._d: "_od[str, object]" = _od()

    def get(self, k: str):
        v = self._d.get(k)
        if v is not None:
            self._d.move_to_end(k)
        return v

    def put(self, k: str, v) -> None:
        self._d[k] = v
        self._d.move_to_end(k)
        while len(self._d) > self._cap:
            self._d.popitem(last=False)


class _UnionClock:
    """``unary_union`` with the call SITE named, so the region loop's cost
    is attributable without a profiler (owner 2026-09-13, round 2)."""

    def __init__(self, s: dict, n: dict) -> None:
        self._s, self._n = s, n

    def __call__(self, site: str, parts):
        t0 = _time.perf_counter()
        u = unary_union(parts)
        self._s[site] = self._s.get(site, 0.0) + _time.perf_counter() - t0
        self._n[site] = self._n.get(site, 0) + 1
        return u


def _record_grade(stats: BasinStats, cache: obj8.ResourceCache, bl) -> None:
    """The at-grade read's timer into the report, and the vertex-budget
    REFUSAL naming the pack (owner RULINGS 2026-09-13bp (iii)) — instead
    of 44 silent minutes."""
    st = cache.grade
    stats.grade_geometry_s = st.seconds
    stats.grade_calls = st.calls
    stats.grade_unions = st.unions
    stats.grade_vertices = st.vertices
    if st.over_budget:
        stats.refused.append(
            f"at-grade read REFUSED over the vertex budget: pack {st.pack()} — "
            f"{st.calls} custom objects over {len(st.resources)} resources, "
            f"{st.vertices} vertices, {st.seconds:.1f} s past "
            f"rim_read_vertex_budget = {int(bl.rim_read_vertex_budget)}; the rim and "
            f"cover diagnostics of the regions read after it are EMPTY")


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
    uu = _UnionClock(stats.union_s, stats.union_n)
    bl = law.tables.structures.basin
    co = law.tables.structures.cutout
    if bl.floor != "deepest_solid" or bl.rim != "ground" or bl.seat != "floor_plate":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r} / seat {bl.seat!r}: only "
                         "'deepest_solid' / 'ground' / 'floor_plate' are generated")
    if co.emit_wall_band:
        raise ValueError("cutout.emit_wall_band = true: only false is generated (RULINGS "
                         "2026-09-06b (1): no wall band, the mesh makes the wall)")
    stats.refused.extend(_no_floor_refusals(report, bl))
    if report is not None:
        stats.buried_named = list(report.buried_named)
    witnessed = [o for o in objects if o.witnesses]
    if not witnessed:
        return classification, (), stats
    u = uu("regions", [_outer(w) for o in witnessed for w in o.witnesses])
    u = u.buffer(bl.footprint_close_m, **_MITRE).buffer(-bl.footprint_close_m, **_MITRE)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and not g.is_empty]
    stats.regions = len(parts)
    rings = [Polygon(g.exterior.coords) for g in sorted(parts, key=lambda g: -g.area)]

    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    runway_u = uu("runway_u", [p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    tunnel_u = uu("tunnel_u", [p for p, c in zip(polys, cells) if c.kind == "structure"]) \
        if any(c.kind == "structure" for c in cells) else None
    pads = [(p, c.ref) for p, c in zip(polys, cells) if c.role == "building"]
    cache = cache or obj8.ResourceCache(bl.min_solid_thickness_m)
    boxed = [o for o in objects if o.plan_bbox is not None]
    box_tree = STRtree([o.plan_bbox for o in boxed]) if boxed else None
    # ── THE AT-GRADE READ (owner RULINGS 2026-09-13bp (i)/(ii)) ──────────
    # The clip + union is memoised per RESOURCE on the shared cache; what
    # is left here is the placement affine, which is cheap.  These two are
    # a small BOUNDED window over the ring's own members (a ring asks for
    # the same placement three times) — never one ~25 MB geometry per
    # placement retained to the end of the pass (VHHH: 2.2 -> 10.0 GB in
    # 7 minutes, the app's worker 34.9 GB).
    cache.grade.vertex_budget = int(bl.rim_read_vertex_budget)
    grade_cache: _LRU = _LRU(_GRADE_WINDOW)
    cover_cache: _LRU = _LRU(_GRADE_WINDOW)

    def grade_of(o) -> tuple:
        v = grade_cache.get(o.id)
        if v is None:
            v = obj8.at_grade_geometry(o, cache, airport.dem.z, bl.contact_band_m)
            grade_cache.put(o.id, v)
        return v

    rim_tree_cache: _LRU = _LRU(_RIM_TREE_WINDOW)

    def rim_tree_of(o):
        v = rim_tree_cache.get(o.id)
        if v is None:
            v = (_rim_index(grade_of(o)[0]),)
            rim_tree_cache.put(o.id, v)
        return v[0]

    def cover_of(o):
        v = cover_cache.get(o.id)
        if v is None:
            v = (obj8.above_grade_footprint(o, cache, airport.dem.z, bl.contact_band_m),)
            cover_cache.put(o.id, v)
        return v[0]

    grid = law.tables.emit.identity.min_distinct_spacing_m
    # ── §24 (7) (a): THE BURIED PLATES OFFERED TO THE REGIONS ─────────
    # A component whose shell never reaches grade seeds no pit (no rim),
    # but its deep plate witnesses inside a region another placement's
    # shell admitted (``airport/obj8.py``).  Indexed once; a ring takes
    # the plates that lie in it.
    buried_wits = [(o, w) for o in objects for w in getattr(o, "buried", ())]
    buried_tree = STRtree([w.plate for _, w in buried_wits]) if buried_wits else None
    basins: list[Basin] = []
    new_cells: list[tuple[str, str, Polygon, tuple[tuple[XY, ...], ...]]] = []
    knives: list[Polygon] = []
    for k, ring in enumerate(rings):
        bid = f"basin:{k}"
        site = _ll(airport, ring)
        members = [o for o in witnessed if any(_outer(w).intersects(ring) for w in o.witnesses)]
        wits = [w for o in members for w in o.witnesses if _outer(w).intersects(ring)]
        member_ids = {o.id for o in members}
        # §24 (7) (a): a sibling's buried plate inside this admitted region
        # is a floor witness OF THIS PIT — it witnesses depth, it does not
        # delimit the floor (that is the region, below)
        taken = []
        if buried_tree is not None:
            for i in buried_tree.query(ring, predicate="intersects"):
                o, w = buried_wits[int(i)]
                if w.plate.intersection(ring).area >= grid * grid:
                    taken.append((o, w))
        wits.extend(w for _, w in taken)
        buried_note = ("buried plates taken from the admitted family (§24 (7) (a)): "
                       + "; ".join(f"{os.path.basename(o.path)} {w.plate_area_m2:.0f} m2 "
                                   f"at {w.z_min:.2f}" for o, w in taken)) if taken else \
            "no buried sibling plate inside the region (§24 (7) (a))"
        plate = uu("wits.plate", [w.plate for w in wits]).intersection(ring).area
        # ── rule 3: the rim diagnostic (reported, never a refusal) ────
        open_n, n, first = _rim_open(ring, (rim_tree_of(o) for o in members),
                                     bl.rim_sample_step_m, bl.footprint_close_m)
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
                cv = cover_of(o)
                if cv is not None:
                    covering.append(cv)
            if covering:
                cov = uu("cover", covering).intersection(ring).area / ring.area
        owning = [g1 for g1 in (grade_of(o)[1] for o in members) if g1 is not None]
        own = uu("own_cover", owning) if owning else None
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
        plates_u = uu("plates_u", [w.plate for w in wits]).intersection(ring)
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
        plate_floor_u = uu("plate_floor", floors)
        ramp_floors: list[Polygon] = []
        ramp_faces: list[tuple] = []
        renoded = 0
        for r in ramps:
            if not r["admitted"]:
                continue
            # §24 (8): the corridor's own climb axis, so the floor faces
            # carry a vertex per station for §24 (5)'s per-station pins
            ax = _ramp_axis(r["faces"])
            for part in _parts(r["ring"].intersection(rim).difference(plate_floor_u)):
                for f in _floors_inside([part], rim, standoff, grid):
                    if f.area < grid * grid:
                        continue
                    if ax is not None:
                        g2 = _renode(f, ax, bl.ramp_station_m, grid)
                        renoded += len(g2.exterior.coords) - len(f.exterior.coords)
                        f = g2
                    ramp_floors.append(f)
        # THE PUBLISHED DECK IS THE DECK OVER THE FLOOR IT GOVERNS.  A
        # corridor read off the shell runs past the trench — over the pit's
        # own floor plate at its foot, and out beyond the rim — and a face
        # there would state a profile for terrain no basin row owns (at
        # LEMD 78 of 138 deck vertices then read "buried" against the APRON
        # over them, −8.91 m, which is the wall, not the ramp).
        if ramp_floors:
            gov = uu("ramp_gov", ramp_floors).buffer(grid, **_MITRE)
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
        # ── §24 (7): THE FLOOR IS THE WHOLE ADMITTED REGION ───────────
        # The plate floors above are the ADMISSION's evidence and the
        # gates they pass (the identity grid, the stand-off) still refuse
        # the basin; what the trench EMITS is the region minus the rim
        # stand-off, the ramp corridors carved out of it.
        plate_floor_m2 = sum(f.area for f in floors)
        floors = _region_floor(rim, standoff, ramp_floors, grid)
        if not floors:
            stats.refused.append(f"{bid}: {ring.area:.0f} m2 — the region floor (rim minus the "
                                 f"{standoff:.2f} m stand-off, §24 (7)) does not survive the "
                                 f"identity grid ({grid} m) at {site}")
            continue
        all_floors = floors + ramp_floors
        void = rim.difference(uu("void", all_floors))
        floor_ref, wall_ref = f"basin_floor:{k}", f"basin_wall:{k}"
        for j, f in enumerate(all_floors):
            # the region floor carries the ramp corridors as HOLES (§24 (7)):
            # they govern their own ground per station (§24 (5))
            new_cells.append((FLOOR_ROLE, floor_ref if j == 0 else f"{floor_ref}#{j}", f,
                              tuple(tuple(h.coords)[:-1] for h in f.interiors)))
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
                 rim_note, buried_note,
                 f"rendered deepest solid {smin_z:.2f} = the floor",
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
                 f"THE FLOOR IS THE WHOLE ADMITTED REGION (§24 (7)): the witnessed plates "
                 f"({plate:.0f} m2, floor faces {plate_floor_m2:.0f} m2) witness the depth; the "
                 f"trench floor is the rim minus the {standoff:.2f} m stand-off "
                 f"({rim.buffer(-standoff, **_MITRE).area:.0f} m2 of the {rim.area:.0f} m2 rim) — "
                 f"{floor_area:.0f} m2, {floor_area / ring.area:.0%} of the region",
                 (f"ramp corridors {len(ramp_floors)} ({sum(f.area for f in ramp_floors):.0f} m2, "
                  f"{len(ramp_faces)} deck face(s)): the floor under them follows the deck "
                  f"per station (13g §24 (5)), re-noded at ramp_station_m "
                  f"{bl.ramp_station_m} m along the climb axis (+{renoded} vertices, §24 (8)); "
                  f"floor ring vertices "
                  + "/".join(str(len(f.exterior.coords) - 1) for f in ramp_floors)
                  if ramp_floors
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
    _record_grade(stats, cache, bl)
    if not basins:
        return classification, (), stats
    knife = uu("knife", knives)
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
