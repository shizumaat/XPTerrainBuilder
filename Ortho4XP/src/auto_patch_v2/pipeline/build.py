"""The orchestration (plan §1 row ``pipeline``): load → classify →
planar → constraints → solve → emit → verify, each stage timed, progress
lines on stdout.  The ONLY package that reads the environment (it does
not yet: inputs come from ``planar.__main__.default_inputs`` and the
CLI).  The objective's weights are LAW (``emit.toml [design]``, RULINGS
2026-09-08t), not a config object here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import time
import typing as _t
from pathlib import Path

from ..airport import flat_site as _flat
from ..airport.load import Inputs, load_with_report
from ..airport.road_profile import preferred_road_z
from ..classify import classify, load_rules
from .shapes import joint_steps, shape_constraints, shape_stage
from ..constraints.flat_site import GEN as FLAT_GEN
from ..constraints.routes import RIDGE_KIND
from ..constraints.runway_chord import ChordReport, with_runway_chord
from ..constraints.runway_profile import RUNWAY_FAMILY
from ..emit.bank import BankReport, with_bank
from ..emit.terrain_edge import with_terrain_edges
from ..emit.graded import graded_surface
from ..emit.osm_adapter import PatchPaths, write_patch, write_tile_pieces
from ..airport.rebake_plan import plan as rebake_plan
from ..emit.rebake import deck_datum_from_surface
from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from ..planar.build import build as build_planar
from ..solve import DesignReport, Options, Solution, solve_design
from .publication import face_tags, publication

__all__ = ["Config", "BuildResult", "build"]

@_dc.dataclass(frozen=True)
class Config:
    """Build configuration (a schema, never an env gate)."""

    options: Options = Options()
    verify: bool = True
    feather_m: float = 60.0
    #: Seam passes after the first solve (the exemption set = the seam
    #: vertices the previous solve held on the DEM), to a fixed point.
    seam_passes_max: int = 6
    #: Extra ``<osm>`` root attributes for the emitted patch (and every
    #: tile piece): a HOSTING tile build's rebuild-freshness stamps
    #: (the v1 tile driver reads them back through ``read_patch_source``
    #: before reusing a patch).  Applied over the adapter's own header, so
    #: a host may override ``o4_apt_dat`` with its percent-encoded form.
    header_extra: _t.Mapping[str, str] | None = None


@_dc.dataclass
class BuildResult:
    """Everything a build produced, for the report."""

    icao: str
    planar: PlanarMap
    constraints: ConstraintSet
    counts: dict[str, int]
    solution: Solution
    paths: PatchPaths | None
    verify_rows: dict[str, list[dict]] | None
    pieces: dict[tuple[int, int], PatchPaths] | None
    wall: dict[str, float]
    lp_size: dict[str, int]
    report: dict[str, _t.Any]
    #: ``<out>/<ICAO>.rebake.json`` — the post-mesh re-seat plan (04f-1)
    rebake_plan: Path | None = None


def _plate_seats(pm, law) -> dict[str, tuple[float, list]]:
    """Placement id -> ``(plate y, stations in frame xy)`` for every
    PLATE-seated structure member: a tunnel wall object (RULINGS
    2026-09-05n-4: plate height above its seat; the stations stand at the
    walls' OUTER FACE + ``emit.identity.min_distinct_spacing_m`` outward,
    every ``bridge.abutment_sample_step_m`` along the object's own
    footprint — RULINGS 2026-09-08d (c): never on the rim ring, whose
    vertices sample the trench drop (OTHH tunnels middle-west/-east
    −2.30 / −2.09), and whichever side of the outer face the rim stands
    on) and a basin member (RULINGS 2026-09-06b (3), ``basin.seat =
    "floor_plate"``: the family's floor-plate y — NEGATIVE, under the
    rendered y = 0 plane — and points ON the trench floor face, so the
    seat's delta = floor − (mesh(anchor) + agl + plate y) lands the plate
    on the floor — and, 2026-09-09ac (2), ONLY for the basin's own
    witness resource ``Basin.witness_id``, never for every member).  ``emit/rebake._plate_reading`` reads both alike."""
    from shapely.geometry import LineString as _LS, Point as _Pt, Polygon as _Poly
    grid = law.tables.emit.identity.min_distinct_spacing_m
    step = law.tables.structures.bridge.abutment_sample_step_m
    rim_off = law.tables.structures.tunnel.wall_gap_m + law.tables.structures.tunnel.wall_band_width_m
    tol = law.tables.structures.tunnel.wall_band_width_m + 2.0 * grid
    out: dict[str, tuple[float, list]] = {}
    for tn in pm.structures:
        if tn.source != "object" or not tn.objects:
            continue
        # RULINGS 2026-09-08o: the stations stand OUTSIDE the EMITTED rim
        # ring (``wall_path``) on at-grade ground, never on the mesh wall
        # face (57 of unit:8's 70 stations lay inside the rim ring, pushed
        # outside the outer face by the arrangement's snap) and never in
        # the ramp beyond the wall end
        beyond = None
        if tn.top_s > tn.wall_length_m + 1e-6 and len(tn.axis) >= 2:
            ax = _LS(tn.axis)
            s0, s1 = min(tn.wall_length_m, ax.length), min(tn.top_s, ax.length)
            if s1 - s0 > 1e-6:
                seg = [ax.interpolate(s0)] + [_Pt(q) for q in tn.axis
                                                if s0 < ax.project(_Pt(q)) < s1] + [ax.interpolate(s1)]
                beyond = _LS([(q.x, q.y) for q in seg]).buffer(tn.half_width_m + rim_off + grid)
        pts = plate_stations(tn.footprint, grid, step, tn.wall_path, beyond)
        if not pts:
            # no footprint recorded: the rim ring inside the walls (pre-08d)
            pts = list(tn.wall_path)
            if tn.wall_length_m > 0.0 and tn.top_s > tn.wall_length_m + 1e-6:
                ax = _LS(tn.axis)
                pts = [p for p in pts if ax.project(_Pt(p)) <= tn.wall_length_m + tol]
        for oid in tn.objects:
            # the seat reads the CREST (plate_y_m): an edge wall's depth
            # is the bore law's, its crest still goes flush (2026-09-06c)
            out[oid] = (float(tn.plate_y_m or tn.depth_m), pts)
    if law.tables.structures.basin.seat != "floor_plate":
        return out
    for b in pm.basins:
        floor = _Poly(b.ring)
        inner = floor.buffer(-2.0 * grid)
        pts = list((inner if not inner.is_empty and inner.geom_type == "Polygon"
                    else floor).exterior.coords)[:-1]
        if not pts:
            continue
        # RULINGS 2026-09-09ac (2): the plate seat is the BASIN'S OWN
        # WITNESS RESOURCE's — the object whose floor plate the basin cut
        # (``Basin.witness_id``, the deepest genuine solid, the one
        # ``plate_y_m`` is measured from).  Another member whose plate
        # merely SHARES that plate y is not plate-seated: it seats by its
        # feet like any other resource (measured at LEMD: 12 of the 13
        # "plate" members were terminal slabs the basin half claimed at
        # the T4S basin's own −7.048 / +5.206 / … plate y, standing them
        # 12–17 m off their own feet — spec §11.4).
        if b.witness_id:
            out.setdefault(b.witness_id, (float(b.plate_y_m), pts))
    return out


def plate_stations(footprint, standoff_m: float, step_m: float, rim_path=(),
                   exclude=None) -> list:
    """RULINGS 2026-09-08d (c) / 2026-09-08o: the plate seat's stations for
    a wall object of plan ``footprint`` (its walls' outer faces, a ring in
    frame xy): the footprint UNITED with the emitted rim ring (``rim_path``
    — the trench's at-grade rim as built, which the arrangement's outward
    snap can push OUTSIDE the outer face, 08e deviation 2) where that ring
    lies against the footprint, grown by ``standoff_m`` (mitred, so the
    corners stay corners) and sampled every ``step_m`` along the exterior
    — points OUTSIDE both the wall and the rim ring, on the at-grade
    ground, never on the mesh wall face; a station inside ``exclude`` (the
    ramp beyond the wall end) is dropped.  ``[]`` without a footprint."""
    import math as _m
    from shapely.geometry import Point as _Pt, Polygon as _Poly
    from shapely.ops import unary_union as _uu
    if not footprint or len(footprint) < 3:
        return []
    poly = _Poly(footprint)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return []
    region = poly
    rim = None
    if rim_path and len(rim_path) >= 3:
        rim = _Poly(rim_path)
        if not rim.is_valid:
            rim = rim.buffer(0)
        if not rim.is_empty:
            # only the rim's extent AGAINST the object: the rim beyond the
            # walls (an OSM stand-off along the climb) is the ramp's
            near = rim.intersection(poly.buffer(standoff_m * 2.0, join_style="mitre"))
            poke = near.difference(poly) if not near.is_empty else near
            if not poke.is_empty and poke.area > 1e-9:
                # the rim stands outside the wall somewhere: the region grows
                # by it (a rim wholly inside the wall leaves the footprint as
                # it is — the ring keeps its own vertex order)
                region = _uu([poly, near])
                if region.geom_type != "Polygon":
                    region = max((g for g in region.geoms if g.geom_type == "Polygon"),
                                 key=lambda g: g.area, default=poly)
    ring = region.buffer(standoff_m, join_style="mitre").exterior
    n = max(4, int(_m.ceil(ring.length / step_m)))
    pts = [tuple(ring.interpolate(k * ring.length / n).coords[0]) for k in range(n)]
    keep = []
    for q in pts:
        pq = _Pt(q)
        if rim is not None and not rim.is_empty and rim.contains(pq):
            continue
        if exclude is not None and not exclude.is_empty and exclude.contains(pq):
            continue
        keep.append(q)
    return keep


def _basin_polygon(b):
    """A basin's admitted region as a frame polygon (the deck signature's
    below-grade spanning evidence, 04k), ``None`` when degenerate."""
    from shapely.geometry import Polygon
    try:
        p = Polygon(b.region or b.ring)
        return p if p.is_valid and not p.is_empty else p.buffer(0)
    except (ValueError, TypeError):
        return None


def _say(msg: str, out: _t.Callable[[str], None]) -> None:
    out(msg)


#: The report's "moved" threshold (metres off the DEM sample) — a report
#: figure (M3b §4 / M5), not a law value.
MOVED_M = 0.5


def displacement_by_role(pm: PlanarMap, law: Law, sol: Solution
                         ) -> dict[str, dict[str, _t.Any]]:
    """Per role (a vertex counts for the SENIOR role touching it): how
    many vertices sit more than :data:`MOVED_M` off their DEM sample, and
    the largest such displacement — the M5 "what yielded where" figure."""
    from ..law.tables import senior_role, tiers
    tier_of = {r: k for k, t in enumerate(tiers(law)) for r in t}  # report order only
    acc: dict[str, dict[str, _t.Any]] = {}
    for vid, v in pm.vertices.items():
        if v.dem_z is None or not v.incident_faces:
            continue
        roles = [pm.faces[f].role for f in v.incident_faces]
        role = senior_role(law, roles)
        rec = acc.setdefault(role, {"tier": tier_of.get(role), "vertices": 0,
                                    "over": 0, "max_m": 0.0})
        d = abs(sol.z[vid] - v.dem_z)
        rec["vertices"] += 1
        if d > MOVED_M:
            rec["over"] += 1
        rec["max_m"] = max(rec["max_m"], d)
    for rec in acc.values():
        rec["max_m"] = round(rec["max_m"], 3)
    return dict(sorted(acc.items(), key=lambda kv: (kv[1]["tier"] is None, kv[1]["tier"])))


def build(icao: str, inputs: Inputs, out_dir: str | Path,
          config: Config | None = None, law: Law | None = None,
          out: _t.Callable[[str], None] = print) -> BuildResult:
    """Run every stage and write the patch + report into ``out_dir``."""
    cfg = config or Config()
    wall: dict[str, float] = {}
    t = time.perf_counter()
    law = law or Law.for_airport(icao)
    airport, lrep = load_with_report(icao, inputs, law)
    wall["load"] = time.perf_counter() - t
    _say(f"[{icao}] load {wall['load']:.2f} s  runways {len(airport.runways)}  "
         f"pavements {len(airport.pavements)}  buildings {len(airport.buildings)}", out)
    t = time.perf_counter()
    cl = classify(airport, law, load_rules())
    wall["classify"] = time.perf_counter() - t
    t = time.perf_counter()
    objects_out: list = []
    pm, pstats = build_planar(airport, cl, law, objects_out=objects_out)
    wall["planar"] = time.perf_counter() - t
    _say(f"[{icao}] planar {wall['planar']:.2f} s  faces {pstats.faces}  "
         f"edges {pstats.edges}  vertices {pstats.vertices}  "
         f"breaklines {pstats.breaklines}  T-vertices {pstats.t_vertices}"
         f"  seam bands {pstats.seam_bands}  seam vertices {pstats.seam_vertices}"
         f"  seam-band faces dropped {pstats.dropped_seam_faces}"
         f"  slivers merged {pstats.slivers_merged} (08d-4a)", out)
    sh = pstats.shapes
    if sh.faces:
        # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19)
        _say(f"[{icao}] " + pstats.terrain_edge.line(), out)
        # THE SHAPES (owner RULINGS 2026-09-08k; ``planar/shapes.py``)
        _say(f"[{icao}] network (08p): {sh.network_faces} of {sh.faces} pavement faces "
             f"({', '.join(f'{k} {n}' for k, n in sorted(sh.network_by_role.items()))}), "
             f"{sh.network_vertices} vertices, {sh.connected_stations} connected stations, "
             f"{sh.unconnected_station_edges} unconnected centreline edges; bodies {sh.body_faces} faces "
             f"({sh.faces_unlabelled} welded whole)", out)
        _say(f"[{icao}] shapes (08k): {sh.body_faces} body faces -> {sh.components} components, "
             f"{sh.bodies} bodies, {sh.shapes} shapes (strip welds {sh.welded_strip_pairs}, route welds {sh.welded_route_pairs}); "
             f"vertices {sh.vertices_labelled} (roads {sh.road_vertices_labelled} labelled / "
             f"{sh.road_vertices_relabelled} relabelled / {sh.road_vertices_unlabelled} freed; road faces "
             f"{sh.roads_along} along, {sh.roads_crossing} crossing -> {sh.road_ramps} ramps, 08r-2; pads relabelled "
             f"{sh.pads_relabelled}); joints {sh.contours} contours ({sh.contour_length_m:,.0f} m, "
             f"dangling faces {sh.dangling_faces}) + {sh.gap_joints} gap ({sh.gap_length_m:,.0f} m); "
             f"joint edges {sh.joint_edges}; {sh.wall_s:.2f} s", out)
        for sid, nf, a, nv, roles in sh.by_shape[:8]:
            _say(f"    shape {sid}: {nf} faces, {a:,} m2, {nv} vertices, {'/'.join(roles)}", out)
    ss = pstats.structures
    ts = pstats.tunnel_objects
    ds, rs = pstats.door_wells, pstats.sunken_roads
    ws = pstats.wall_corridors
    if ws.corridors or ws.refused:
        _say(f"[{icao}] wall corridors (09-08m/n Law C): {ws.corridors} corridors "
             f"({', '.join(f'{k} {n}' for k, n in sorted(ws.by_class.items()))}) from {ws.pairs} "
             f"pairs of {ws.bands} bands in {ws.families} families ({ws.read_s:.2f} s)  refused "
             f"{len(ws.refused)}", out)
        for r in ws.refused[:40]:
            _say(f"    refused wall corridor {r}", out)
    if ds.wells or ds.refused or rs.roads or rs.refused:
        _say(f"[{icao}] door wells (09-08b/c Law A): {ds.wells} of {ds.regions} regions in "
             f"{ds.families} families ({ds.sill_witnesses} sill witnesses over {ds.screened} "
             f"screened placements, {ds.basin_gate_components} basin-gate components left to the "
             f"basin pass; {ds.read_s:.2f} s)  sunken roads (Law B): {rs.roads} of {rs.plates} "
             f"plates in {rs.families} families ({rs.read_s:.2f} s)  refused {len(ds.refused)} / "
             f"{len(rs.refused)}", out)
        for r in ds.refused[:40]:
            _say(f"    refused door {r}", out)
        for r in rs.refused[:40]:
            _say(f"    refused sunken road {r}", out)
    if ss.bores or ss.object_corridors or ss.door_ramps or ss.sunken_roads or ss.wall_corridors \
            or ts.refused:
        _say(f"[{icao}] structures: bores {ss.bores} (uncovered {ss.bores_uncovered}, replaced by "
             f"objects {ss.bores_replaced_by_object})  mouths {ss.mouths}  duals merged "
             f"{ss.duals_merged}  object corridors {ss.object_corridors} (signatures "
             f"{ts.signatures} of {ts.resources} resources, merged {ts.merged}, "
             f"{ts.signature_s:.2f} s)  door ramps {ss.door_ramps}  sunken roads "
             f"{ss.sunken_roads}  wall corridors {ss.wall_corridors}  tunnels {ss.tunnels}  "
             f"decks {ss.decks}  "
             f"cells cut {ss.cells_cut}  refused {len(ss.refused) + len(ts.refused)}", out)
        for r in ts.refused:
            _say(f"    refused object {r}", out)
        for r in ss.refused:
            _say(f"    refused {r}", out)
        for r in ss.bore_precedence:
            _say(f"    {r}", out)
        for tn in pm.structures:
            if tn.source == "object":
                # round-2 spec §3.6: the per-corridor line
                inside = min(tn.top_s, tn.wall_length_m)
                _say(f"    {tn.id}: floor@mouth {tn.mouth_z:.2f} ground {tn.mouth_dem_z:.2f} "
                     f"depth {tn.depth_m:.2f} m ramp {tn.top_s:.1f} m (inside walls {inside:.1f} m, "
                     f"beyond {max(0.0, tn.top_s - tn.wall_length_m):.1f} m) grade "
                     f"{100.0 * tn.design_grade:.2f} % ends mouth={tn.mouth_kind} "
                     f"ground={tn.ground_kind} walls {tn.ends} width {tn.hull_width_m:.1f} m "
                     f"reseat expect {', '.join(f'{d:+.2f}' for d in tn.reseat_expect_m)} "
                     f"trench-outside {tn.trench_outside_max_m:.3f} m replaced mouths of "
                     f"[{', '.join(str(w) for w in tn.replaced_ways)}]  decks {len(tn.decks)}  "
                     f"{'; '.join(tn.notes)}", out)
                continue
            if tn.source == "wall_corridor":
                # RULINGS 2026-09-08m/n Law C: the per-site line the report quotes
                inside = [z for s, z in tn.profile if s <= tn.wall_length_m + 1e-6]
                _say(f"    {tn.id}: floor@mouth {tn.mouth_z:.2f} ground {tn.mouth_dem_z:.2f} "
                     f"floor {min(inside) if inside else tn.mouth_z:.2f}..{max(inside) if inside else tn.mouth_z:.2f} "
                     f"depth {tn.depth_m:.2f} m width {tn.hull_width_m:.1f} m walls "
                     f"{tn.wall_length_m:.1f} m ramp {max(0.0, tn.top_s - tn.climb_from_s):.1f} m at "
                     f"{100.0 * tn.design_grade:.2f} % top s {tn.top_s:.1f} ends {tn.ends} "
                     f"trench-outside {tn.trench_outside_max_m:.3f} m clipped '{tn.clipped_by}'  "
                     f"{'; '.join(tn.notes)}", out)
                continue
            if tn.source in ("door", "sunken_road"):
                # RULINGS 2026-09-08b/c: the per-site line the report quotes
                _say(f"    {tn.id}: {'sill' if tn.source == 'door' else 'cut'} {tn.mouth_z:.2f} "
                     f"ground {tn.mouth_dem_z:.2f} depth {tn.depth_m:.2f} m width "
                     f"{tn.hull_width_m:.1f} m well/plate {tn.wall_length_m:.1f} m ramp "
                     f"{max(0.0, tn.top_s - tn.climb_from_s):.1f} m at {100.0 * tn.design_grade:.2f} % "
                     f"top s {tn.top_s:.1f} ground {tn.top_ground_z if tn.top_ground_z is not None else float('nan'):.2f} "
                     f"trench-outside {tn.trench_outside_max_m:.3f} m clipped '{tn.clipped_by}'  "
                     f"{'; '.join(tn.notes)}", out)
                continue
            _say(f"    {tn.id}: mouth {tn.mouth_z:.2f} (DEM {tn.mouth_dem_z:.2f}) top {tn.top_s:.0f} m"
                 f"  half {tn.half_width_m:.1f} m  decks {len(tn.decks)}  {'; '.join(tn.notes)}", out)
    bs = pstats.basins
    if bs.objects is not None:
        o = bs.objects
        _say(f"[{icao}] objects: {o.placements} placements, {o.resolved} resolved "
             f"({o.unresolved} unresolved, {o.stock_placements} stock), "
             f"{o.resources_parsed} resources parsed in {bs.object_read_s:.2f} s, "
             f"{o.below_grade_objects} below grade, {o.hard_deck_objects} hard-deck, "
             f"{lrep.objects_restored_for_read} restored-for-read (.anchor_bak)", out)
        for up in o.unresolved_paths[:10]:
            _say(f"    unresolved {up}", out)
    if bs.regions or bs.refused:
        _say(f"[{icao}] basins: regions {bs.regions}  basins {bs.basins}  cells cut {bs.cells_cut}  "
             f"refused {len(bs.refused)}  under min area {len(bs.small_regions)}", out)
        for r in bs.refused:
            _say(f"    refused {r}", out)
        for b in pm.basins:
            _say(f"    {b.id}: floor {b.floor_z:.2f}  R_est {b.rim_estimate_m:.2f}  deepest solid "
                 f"{b.solid_min_y_m:+.2f} (rendered {b.solid_min_z:.2f})  floor area {b.area_m2:.0f} m2  "
                 f"seat expect {b.seat_expect_m:+.2f} (anchor "
                 f"{'inside' if b.anchor_inside_floor else 'outside'} the floor, plate y "
                 f"{b.plate_y_m:+.2f})  at {b.anchor_ll[0]:.6f},{b.anchor_ll[1]:.6f}  "
                 f"{'; '.join(b.notes)}", out)
    # THE FLAT-SITE VERDICT (RULINGS 2026-09-05k-2; ``airport/flat_site.py``):
    # measured here, after the planar stage read the pack's objects (S4),
    # on the production raster already in memory; the datum is a
    # preference the generator below prices, the runway keeps its pins
    t = time.perf_counter()
    fv = _flat.detect(airport, law, objects=objects_out[0] if objects_out else ())
    airport = _dc.replace(airport, flat_site=fv)
    wall["flat_site"] = time.perf_counter() - t
    lrep.flat_site = _flat.record(fv)
    _say(_flat.log_line(icao, fv) + f"  ({wall['flat_site']:.2f} s)", out)
    for ln in _flat.notes(icao, fv):
        _say(ln, out)
    # THE CORE SMOOTHS FIRST (RULINGS 2026-09-04t-4): every road-family
    # vertex's fit target is the core's clamped, laterally-levelled road
    # profile on this DEM (``airport/road_profile.py``); the cap rows
    # below stay and v2 moves a vertex off it only where one binds.
    t = time.perf_counter()
    road_pref, road_rep, _profiles = preferred_road_z(
        airport, pm, law, inputs.road_grade_limit, inputs.lane_width_m)
    pm = _dc.replace(pm, preferred_z=road_pref)
    wall["road_profile"] = time.perf_counter() - t
    # THE RUNWAY CHORD (RULINGS 2026-09-08d (1); ``constraints/runway_chord.py``):
    # every runway-family vertex of a two-pin runway fits the threshold
    # chord at ``runway_chord_fit``; the DEM fit stays for every other role
    chord_rep: ChordReport = {}
    pm = with_runway_chord(pm, law, airport, chord_rep)
    lrep.runway_chord = dict(chord_rep)
    _say(f"[{icao}] runway chord (08d-1): {chord_rep.get('runways', 0)} runways with two pins "
         f"({chord_rep.get('runways_without', 0)} without, DEM fit kept)  vertices "
         f"{chord_rep.get('vertices', 0)}  chord above DEM up to {chord_rep.get('max_above_dem_m', 0.0):.2f} m, "
         f"below up to {chord_rep.get('max_below_dem_m', 0.0):.2f} m", out)
    rs = road_rep["profiles"]
    _say(f"[{icao}] road profile {wall['road_profile']:.2f} s  ways {rs['ways']} "
         f"(osm {rs['ways_by_kind'].get('osm', 0)}, route {rs['ways_by_kind'].get('route', 0)}, "
         f"axis {rs['ways_by_kind'].get('axis', 0)})"
         f"  stations {rs['stations']}  clamped {rs['clamped_stations']} "
         f"(max lift {rs['max_lift_m']:.2f} m, cut {rs['max_cut_m']:.2f} m)  cap {rs['cap']:.3f}"
         f"  vertices {road_rep['vertices']}  preferred {road_rep['preferred']}"
         f"  DEM fallback {road_rep['dem_fallback']}"
         f"  off-DEM {road_rep['preferred_off_dem']} (max {road_rep['max_preferred_shift_m']:.2f} m)",
         out)
    # THE SHAPE STAGE (owner RULINGS 2026-09-08k; ``pipeline/shapes.py``):
    # the route bands, the withdraw set, the joint filter, the yield transform
    t = time.perf_counter()
    stage = shape_stage(pm, law, airport, cl, out=lambda m: _say(m, out))
    pm = stage.pm
    wall["shapes"] = time.perf_counter() - t
    t = time.perf_counter()
    cs, counts, gwalls = shape_constraints(pm, law, airport, stage)
    wall["constraints"] = time.perf_counter() - t
    if stage.dropped:
        _say(f"[{icao}] joints (08k): {sum(stage.dropped.values())} rows dropped across shape "
             f"boundaries — " + ", ".join(f"{g} {n}" for g, n in sorted(stage.dropped.items()))
             + f"; reach bands withdrawn {stage.bands_withdrawn}; flats straddling "
             f"{stage.flats_straddling}", out)
    _say(f"[{icao}] constraints {wall['constraints']:.2f} s  {cs.counts()}", out)
    for name, n in counts.items():
        # a ``<generator>.<stat>`` key is a statistic, not a timed generator
        _say(f"    {name:28s} {n:8d}  {gwalls[name]:.3f} s" if name in gwalls
             else f"    {name:28s} {n:8d}", out)
    t = time.perf_counter()
    size: dict[str, int] = {}
    sol, design_rep = solve_design(pm, cs, law, cfg.options, size_out=size)
    wall["solve"] = time.perf_counter() - t
    # ONE solve pass (owner RULINGS 2026-09-08k (4)): joints are geometric,
    # nothing is re-solved on a built step
    # SEAM PASSES: a seam vertex the solve could not hold on the DEM is
    # FREE, so the pairs the previous pass exempted as pin↔pin around it
    # come back as law rows (the census prices them) and the LP runs
    # again over exactly that set, to a fixed point of the honoured set.
    if sol.status.value in ("optimal", "feasible") and pm.seam_vertices:
        tol = law.tables.emit.materiality.elevation_m
        prev: frozenset[int] | None = None
        for n_pass in range(2, 2 + cfg.seam_passes_max):
            honoured = frozenset(v for v in pm.seam_vertices if pm.vertices[v].dem_z is not None
                                 and abs(sol.z[v] - pm.vertices[v].dem_z) <= tol)
            if len(honoured) == len(pm.seam_vertices) or honoured == prev:
                break                 # every seam value held, or a fixed point
            prev = honoured
            t = time.perf_counter()
            cs, counts2, _g = shape_constraints(pm, law, airport, stage,
                                                seam_honoured=honoured)
            counts["seam_pin_pair_exempt"] = counts2["seam_pin_pair_exempt"]
            sol, design_rep = solve_design(pm, cs, law, cfg.options,
                                           size_out=size)
            wall[f"solve_pass{n_pass}"] = time.perf_counter() - t
            _say(f"[{icao}] seam pass {n_pass}: {len(honoured)}/{len(pm.seam_vertices)} honoured, "
                 f"{counts2['seam_pin_pair_exempt']} pairs exempt, "
                 f"{wall[f'solve_pass{n_pass}']:.2f} s, status {sol.status.value}", out)
            if sol.status.value not in ("optimal", "feasible"):
                break
    _say(f"[{icao}] solve {wall['solve']:.2f} s  status {sol.status.value}  "
         f"LP {size}  {sol.message}", out)
    _say(f"[{icao}] {design_rep.line()}", out)
    if fv.substitutes and sol.z:
        tol = law.tables.emit.materiality.elevation_m
        dz = [abs(sol.z[r.terms[0][0]] - r.hi) for r in cs.linears
              if r.source.generator == FLAT_GEN]
        held = sum(1 for d in dz if d <= tol)
        lrep.flat_site["rows"] = len(dz)
        lrep.flat_site["rows_at_datum"] = held
        lrep.flat_site["max_off_datum_m"] = round(max(dz), 3) if dz else 0.0
        _say(f"[flat-site] {icao}: {held}/{len(dz)} datum rows at Z0 {fv.z0_m:.2f} "
             f"(max off {lrep.flat_site['max_off_datum_m']:.3f} m; the law rows outrank "
             f"the preference where they differ)", out)
    moved = displacement_by_role(pm, law, sol) if sol.z else {}
    if moved:
        _say(f"[{icao}] off-DEM > {MOVED_M} m by role: " + ", ".join(
            f"{r} {v['over']}/{v['vertices']} (max {v['max_m']:.2f})"
            for r, v in moved.items() if v["over"]), out)
    if sol.status.value in ("optimal", "feasible") and pm.seam_vertices:
        tol = law.tables.emit.materiality.elevation_m
        res_seam = sorted(((abs(sol.z[v] - pm.vertices[v].dem_z), v)
                           for v in pm.seam_vertices if pm.vertices[v].dem_z is not None),
                          reverse=True)
        off = [(d, v) for d, v in res_seam if d > tol]
        report_seam = {"seam_vertices": len(pm.seam_vertices), "honoured": len(res_seam) - len(off),
                       "residual": [{"vertex": v, "off_dem_m": round(d, 3)} for d, v in off]}
        _say(f"[{icao}] seam: {report_seam['honoured']}/{len(res_seam)} vertices on the DEM; "
             f"{len(off)} residual" + (f", max {off[0][0]:.3f} m at vertex {off[0][1]}" if off else ""), out)
    else:
        report_seam = None
    road_agree = None
    if sol.status.value in ("optimal", "feasible") and pm.preferred_z:
        from ..verify.roads import road_profile_agreement
        road_agree = road_profile_agreement(pm, law, sol.z)
        _say(f"[{icao}] roads vs core profile: {road_agree['vertices']} vertices, "
             f"mean |z-profile| {road_agree['mean_m']:.3f} m, max {road_agree['max_m']:.3f} m, "
             f"{road_agree['off']} off beyond materiality in {road_agree['faces_off']} "
             f"of {len(road_agree['faces'])} faces", out)
    if sol.residual is not None:
        r = sol.residual
        _say(f"    residual: pin {r.max_pin_m:.4f} diff {r.max_diff_m:.4f} "
             f"flat {r.max_flat_m:.4f} band {r.max_band_m:.4f} "
             f"offset {r.max_offset_m:.4f} m  objective {r.objective:.2f}", out)
    report: dict[str, _t.Any] = {
        "icao": icao, "ruleset": law.ruleset_key,
        "load": _dc.asdict(lrep), "planar": _dc.asdict(pstats),
        "basins": [_dc.asdict(b) for b in pm.basins],
        "constraints": {"by_generator": counts, "by_kind": cs.counts(),
                        "wall_s": {k: round(v, 4) for k, v in gwalls.items()}},
        "lp": size,
        # THE DESIGN SURFACE's residual per family (RULINGS 2026-09-08t):
        # replaces ``law_tiers`` — a law is a TARGET, so a missed one is a
        # residual to report, never a demotion to name
        "design": design_rep.as_dict(),
        "off_dem_by_role": moved,
        "road_profile": road_rep,
        "road_profile_agreement": road_agree,
        "seam": report_seam,
        "shapes": dict(stage.as_dict(), by_shape=pstats.shapes.by_shape),
        "joint_steps": joint_steps(pm, law, stage, sol.z) if sol.z else None,
        "solve": {"status": sol.status.value, "wall_s": round(sol.wall_s, 3),
                  "iterations": sol.iterations, "message": sol.message,
                  "rounds": design_rep.rounds, "converged": design_rep.converged,
                  "residual": None if sol.residual is None else _dc.asdict(sol.residual)},
    }
    paths = None
    vrows = None
    pieces = None
    if sol.status.value in ("optimal", "feasible"):
        t = time.perf_counter()
        surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                              {"law_ruleset": law.ruleset_key,
                               "pack": airport.pack.name})
        pub = publication(pm, law, airport, sol.z)
        # THE DESIGN SURFACE's own publication (RULINGS 2026-09-08t/v): the
        # residual per family (``design``, replacing ``law_tiers``) and the
        # rows the surface missed (``design_target``), which the census
        # counts law-true in their families and reports under one heading
        pub["design"] = design_rep.as_dict()
        pub["design_target"] = design_rep.targets
        js = report["joint_steps"]
        if js and js["contours"]:
            worst = max(js["contours"], key=lambda c: c["step_m"])
            _say(f"[{icao}] joint steps (08k): {len(js['contours'])} joints, max step "
                 f"{worst['step_m']:.2f} m (joint {worst['id']}, {worst['length_m']:.0f} m, "
                 f"shapes {worst['shapes']}, {'gap' if worst['gap'] else 'contour'}, "
                 f"{'/'.join(worst['roles'])}); by roles " + ", ".join(
                     f"{k} {v['edges']} edges max {v['max_step_m']:.2f}" for k, v in sorted(js["by_roles"].items()))
                 + (f"; roads: " + ", ".join(f"#{r['face']} {r['ref']} {r['step_m']:.2f} m"
                                             for r in js["roads"][:8]) if js["roads"] else ""), out)
        if js and js.get("ramps"):
            short = [r for r in js["ramps"] if r["too_short"]]
            _say(f"[{icao}] road ramps (08r-2): {len(js['ramps'])} roads crossing between shapes, steepest "
                 + ", ".join(f"#{r['face']} {r['ref']} {r['dz_m']:.2f} m over {r['length_m']:.0f} m = "
                             f"{100 * r['grade']:.2f} % (shapes {r['shapes']})" for r in js["ramps"][:6])
                 + (f"; TOO SHORT (at the cap): " + ", ".join(f"#{r['face']} {r['ref']}" for r in short)
                    if short else "; none at the cap"), out)
        header = {"o4_apt_dat": airport.pack.apt_dat_path,
                  "o4_pack": airport.pack.name}
        header.update(cfg.header_extra or {})
        # THE BANK (owner RULINGS 2026-09-09e; ``emit/bank.py``, spec §9):
        # the mesh does not blend, so the patch emits its own 1:3 bank out
        # to the DEM outside every boundary ring.  Only the EMITTED surface
        # carries it — the rebake plan below reads ``surf``, the pre-bank
        # one (spec §9.2 A7).
        brep = BankReport()
        surf_out = with_bank(surf, pm, law, airport, brep)
        # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c, spec §19.3 C12):
        # the edge segments published as open ways over the vertices they
        # already run through — the owner's KML read of where ground ends
        surf_out = with_terrain_edges(surf_out, pm, law)
        _say(brep.line(icao), out)
        report["bank"] = _dc.asdict(brep)
        paths = write_patch(surf_out, law, out_dir, pub, header,
                            face_tags(pm, law, airport))
        if pm.seam_vertices:
            pieces = write_tile_pieces(surf_out, law, out_dir, pub, header,
                                       face_tags(pm, law, airport))
        wall["emit"] = time.perf_counter() - t
        _say(f"[{icao}] emit {wall['emit']:.2f} s  ways {paths.ways}  nodes {paths.nodes}"
             f"  patch {paths.bytes_patch} B  sidecar {paths.bytes_sidecar} B", out)
        # THE RE-BAKE PLAN (RULINGS 04f-1): the units and witnesses the
        # post-mesh seat reads, from the pack as AUTHORED, with the solved
        # surface's value at every hard deck — ``emit/rebake.py``
        t = time.perf_counter()
        rplan = None
        if objects_out:
            _to_xy = airport.frame.transformers()[0]
            # a basin family is PLATE-seated onto its floor (2026-09-06b (3)),
            # never excluded; ``exclude`` stays for any other caller
            plates = _plate_seats(pm, law)
            excluded = set() if law.tables.structures.basin.seat == "floor_plate" \
                else {oid for b in pm.basins for oid in b.objects}
            # seat = "none" (RULINGS 2026-09-08b/c, spec §2 / §3): a door
            # ramp's or a sunken road's family is NEVER re-seated by its
            # trench — the cluster law would sink the well's neighbours into
            # the ramp (measured OTHH: 8 Parking-Left/Right objects written)
            excluded |= {oid for tn in pm.structures
                         if tn.source in ("door", "sunken_road", "wall_corridor")
                         for oid in tn.objects}
            rplan = rebake_plan(airport, objects_out[0], objects_out[1], law,
                                lambda ring, _s=surf: deck_datum_from_surface(_s, ring, _to_xy),
                                exclude=excluded,
                                tunnel_objects=plates,
                                below_grade=[(_basin_polygon(b), tuple(b.objects))
                                             for b in pm.basins])
            rebake_path = Path(out_dir) / f"{icao}.rebake.json"
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            rebake_path.write_text(rplan.to_json())
            wall["rebake_plan"] = time.perf_counter() - t
            rc = rplan.counts
            _say(f"[{icao}] rebake plan {wall['rebake_plan']:.2f} s  units {rc['units']}  "
                 f"members {rc['members']}  deck members {rc['deck_members']} "
                 f"(signature {rc.get('signature_decks', 0)} in {rc.get('deck_families', 0)} "
                 f"deck families)  "
                 f"parts {rc['parts']}  contacts {rc['contacts']}  pools {rc['pools']}  "
                 f"structures {rc['structures']}  skipped {len(rplan.skipped)} "
                 f"(stock {rc['stock']}, multi-anchor {rc['multi_anchor']}, "
                 f"outside pack {rc['outside_pack']}, msl {rc['msl']}, "
                 f"terrain-adapted {rc['terrain_adapted']}, below grade {rc['below_grade']})"
                 f"  -> {rebake_path}", out)
        for (tl, tn), pp in (pieces or {}).items():
            _say(f"    tile {tl:+03d}{tn:+04d}: ways {pp.ways}  nodes {pp.nodes}  "
                 f"-> {pp.patch}", out)
        report["rebake_plan"] = None if rplan is None else {
            "path": str(Path(out_dir) / f"{icao}.rebake.json"),
            "counts": dict(rplan.counts), "skipped": len(rplan.skipped)}
        report["emit"] = {"patch": str(paths.patch), "sidecar": str(paths.sidecar),
                          "ways": paths.ways, "nodes": paths.nodes,
                          "bytes_patch": paths.bytes_patch,
                          "bytes_sidecar": paths.bytes_sidecar,
                          "published": {k: len(v) for k, v in pub.items()},
                          "tiles": {f"{tl:+03d}{tn:+04d}": {"patch": str(pp.patch),
                                                             "ways": pp.ways,
                                                             "nodes": pp.nodes}
                                    for (tl, tn), pp in (pieces or {}).items()}}
        if cfg.verify:
            t = time.perf_counter()
            from ..constraints.roads import road_law_caps
            from ..verify import census
            vrows = census(surf, law, pub, road_law_caps(pm, law, airport))
            wall["verify"] = time.perf_counter() - t
            # RULINGS 2026-09-08t: every row is counted LAW-TRUE — there is
            # no relaxed / yielded scope any more.  A row here is a DESIGN
            # TARGET the surface missed; the census reports, never blocks.
            summary = {k: len(v) for k, v in vrows.items()}
            _say(f"[{icao}] verify {wall['verify']:.2f} s  rows "
                 f"{sum(summary.values())}  " + ", ".join(
                     f"{k} {n}" for k, n in summary.items() if n), out)
            from ..verify.census import DEFECT_KEYS
            defects = {k: len(vrows[k]) for k in DEFECT_KEYS if vrows.get(k)}
            for k, n in defects.items():
                _say(f"[{icao}] verify: DEFECT {k} {n} — " + "; ".join(
                    f"{r.get('way_a')} {r.get('reading')} {r.get('magnitude_m')} m"
                    for r in vrows[k][:10]) + (" ..." if n > 10 else ""), out)
            from ..verify.within import apron_over_preference as _v_pref
            from ..verify.frame import Patch as _Patch
            v_pref = _v_pref(_Patch.of(surf, law, pub, road_law_caps(pm, law, airport)))
            _say(f"[{icao}] verify: apron_over_preference {v_pref['over_preference']}/{v_pref['rows']} "
                 f"(max grade {v_pref['max_grade']:.4f}) — a report figure, the "
                 f"design surface has no preference ladder", out)
            report["verify"] = {"by_family": summary,
                                "apron_over_preference": v_pref,
                                "defects": defects,
                                "rows": {k: v for k, v in vrows.items() if v}}
    wall["total"] = sum(wall.values())
    report["wall_s"] = {k: round(v, 3) for k, v in wall.items()}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / f"{icao}.report.json").write_text(
        json.dumps(report, indent=1, default=str))
    _say(f"[{icao}] total {wall['total']:.2f} s  -> {out_dir}", out)
    return BuildResult(icao, pm, cs, counts, sol, paths, vrows, pieces, wall, size, report,
                       Path(out_dir) / f"{icao}.rebake.json" if report.get("rebake_plan")
                       else None)
