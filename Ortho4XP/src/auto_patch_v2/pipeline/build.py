"""The orchestration (plan §1 row ``pipeline``): load → classify →
planar → constraints → solve → emit → verify, each stage timed, progress
lines on stdout.  The ONLY package that reads the environment (it does
not yet: inputs come from ``planar.__main__.default_inputs`` and the
CLI).  Solver weights are a config object here — preferences, not law.
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
from ..constraints import generate
from ..constraints.flat_site import GEN as FLAT_GEN
from ..emit.graded import graded_surface
from ..emit.osm_adapter import PatchPaths, write_patch, write_tile_pieces
from ..airport.rebake_plan import plan as rebake_plan
from ..emit.rebake import deck_datum_from_surface
from ..law import Law
from ..law.tables import flat_datum_group, flat_datum_weight
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from ..planar.build import build as build_planar
from ..solve import Options, Solution, Weights
from ..solve.tiers import TierReport, solve_law_ordered
from .publication import face_tags, publication

__all__ = ["Config", "DEFAULT_WEIGHTS", "BuildResult", "build"]

#: DEM-fit weights by role — the objective's preferences (plan §2:
#: airside high, groundside 1); a role absent here takes ``default``.
DEFAULT_WEIGHTS = Weights(
    by_role={"runway": 20.0, "runway_crossing": 20.0, "primary_parallel": 8.0,
             "secondary_parallel": 8.0, "stub": 8.0, "cross_connector": 8.0,
             "junction": 8.0, "apron": 4.0, "building": 1.0,
             "service_road": 2.0, "service_junction": 2.0,
             "groundside_pavement": 1.0, "graded_strip": 1.0},
    zone3=100.0, smoothness=0.5, default=1.0)


@_dc.dataclass(frozen=True)
class Config:
    """Build configuration (a schema, never an env gate)."""

    weights: Weights = DEFAULT_WEIGHTS
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
    """Placement id -> ``(plate height, wall-band stations in frame xy)``
    for every tunnel wall object (RULINGS 2026-09-05n-4): the band's
    centreline points inside the object's own walls (the ramp's bands
    beyond the walls are the OSM law's)."""
    from shapely.geometry import Point as _Pt
    tol = (law.tables.structures.tunnel.wall_band_width_m
           + 2.0 * law.tables.emit.identity.min_distinct_spacing_m)
    out: dict[str, tuple[float, list]] = {}
    for tn in pm.structures:
        if tn.source != "object" or not tn.objects:
            continue
        pts = list(tn.wall_path)
        if tn.wall_length_m > 0.0 and tn.top_s > tn.wall_length_m + 1e-6:
            from shapely.geometry import LineString as _LS
            ax = _LS(tn.axis)
            pts = [p for p in pts if ax.project(_Pt(p)) <= tn.wall_length_m + tol]
        for oid in tn.objects:
            out[oid] = (float(tn.depth_m), pts)
    return out


def _basin_polygon(b):
    """A basin's admitted region as a frame polygon (the deck signature's
    below-grade spanning evidence, 04k), ``None`` when degenerate."""
    from shapely.geometry import Polygon
    try:
        p = Polygon(b.ring)
        return p if p.is_valid and not p.is_empty else p.buffer(0)
    except (ValueError, TypeError):
        return None


def _say(msg: str, out: _t.Callable[[str], None]) -> None:
    out(msg)


def weights_under_law(weights: Weights, law: Law) -> Weights:
    """``Weights`` with the flat-site datum's preference group priced from
    the table (``law/flat_site.toml [datum] weight``; RULINGS 2026-09-05k-2)
    — the group name and its weight are law, never a literal here."""
    pref = dict(weights.preference)
    pref[flat_datum_group(law)] = flat_datum_weight(law)
    return _dc.replace(weights, preference=pref)


#: The report's "moved" threshold (metres off the DEM sample) — a report
#: figure (M3b §4 / M5), not a law value.
MOVED_M = 0.5


def displacement_by_role(pm: PlanarMap, law: Law, sol: Solution
                         ) -> dict[str, dict[str, _t.Any]]:
    """Per role (a vertex counts for the SENIOR role touching it): how
    many vertices sit more than :data:`MOVED_M` off their DEM sample, and
    the largest such displacement — the M5 "what yielded where" figure."""
    from ..law.tables import senior_role, tiers
    tier_of = {r: k for k, t in enumerate(tiers(law)) for r in t}
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


def relaxed_publication(rep: TierReport) -> list[dict[str, _t.Any]]:
    """The sidecar ``relaxed_rows`` records (RULINGS 2026-09-04t(1)): one
    per relaxed row — kind, family, ruling, face, slack metres, the
    vertices' lat/lon identities — so every census can count the rows on
    them under the "relaxed by 04t(1)" heading."""
    if rep.mode != "relaxed" or not rep.relaxation:
        return []
    return [{"kind": r["kind"], "family": r["family"], "ruling": r["ruling"],
             "face": r.get("face"), "slack_m": r["slack_m"], "ll": r["ll"],
             **({"slope": r["slope"], "extent_m": r["extent_m"]} if r["kind"] == "pad"
                else {"cap": r.get("cap"), "cap_after": r.get("cap_after"),
                      "distance_m": r.get("distance_m")})}
            for r in rep.relaxation.get("rows", [])]


def relaxation_lines(rep: TierReport) -> list[str]:
    """The relaxation's rows for the build log (``relaxed by 04t(1)``)."""
    rl = rep.relaxation or {}
    if not rl.get("applied"):
        return []
    out = [f"relaxed by 04t(1) over the {rl.get('scope')} scope: {len(rl['rows'])} rows; "
           f"slack stats {rl.get('stats')}; certificate {rl.get('certificate')}"]
    for r in rl["rows"]:
        if r["kind"] == "pad":
            out.append(f"  pad   face {r['face']} {r['inputs'][1:2]} slope {r['slope']:.5f} "
                       f"rise {r['slack_m']:.4f} m over {r['extent_m']:.1f} m")
        else:
            out.append(f"  {r['kind']:5s} {r['family']:8s} face {r['face']} slack {r['slack_m']:.4f} m"
                       + (f" cap {r['cap']:.4f} -> {r['cap_after']:.5f} over {r['distance_m']:.1f} m"
                          if r["kind"] == "diff" else ""))
    for u in rl.get("unrelaxed", []):
        out.append(f"  held  {u['kind']} {u['family']} ({u['ruling'][:60]})")
    return out


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
         f"  seam-band faces dropped {pstats.dropped_seam_faces}", out)
    ss = pstats.structures
    ts = pstats.tunnel_objects
    if ss.bores or ss.object_corridors or ts.refused:
        _say(f"[{icao}] structures: bores {ss.bores} (uncovered {ss.bores_uncovered}, replaced by "
             f"objects {ss.bores_replaced_by_object})  mouths {ss.mouths}  duals merged "
             f"{ss.duals_merged}  object corridors {ss.object_corridors} (signatures "
             f"{ts.signatures} of {ts.resources} resources, merged {ts.merged}, "
             f"{ts.signature_s:.2f} s)  tunnels {ss.tunnels}  decks {ss.decks}  "
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
                 f"{b.solid_min_y_m:+.2f} (rendered {b.solid_min_z:.2f})  area {b.area_m2:.0f} m2  "
                 f"at {b.anchor_ll[0]:.6f},{b.anchor_ll[1]:.6f}  {'; '.join(b.notes)}", out)
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
    weights = weights_under_law(cfg.weights, law)
    # THE CORE SMOOTHS FIRST (RULINGS 2026-09-04t-4): every road-family
    # vertex's fit target is the core's clamped, laterally-levelled road
    # profile on this DEM (``airport/road_profile.py``); the cap rows
    # below stay and v2 moves a vertex off it only where one binds.
    t = time.perf_counter()
    road_pref, road_rep, _profiles = preferred_road_z(
        airport, pm, law, inputs.road_grade_limit, inputs.lane_width_m)
    pm = _dc.replace(pm, preferred_z=road_pref)
    wall["road_profile"] = time.perf_counter() - t
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
    t = time.perf_counter()
    cs, counts, gwalls = generate(pm, law, airport)
    wall["constraints"] = time.perf_counter() - t
    _say(f"[{icao}] constraints {wall['constraints']:.2f} s  {cs.counts()}", out)
    for name, n in counts.items():
        # a ``<generator>.<stat>`` key is a statistic, not a timed generator
        _say(f"    {name:28s} {n:8d}  {gwalls[name]:.3f} s" if name in gwalls
             else f"    {name:28s} {n:8d}", out)
    t = time.perf_counter()
    size: dict[str, int] = {}
    sol, tier_rep = solve_law_ordered(pm, cs, law, weights, cfg.options, size_out=size)
    wall["solve"] = time.perf_counter() - t
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
            cs, counts2, _g = generate(pm, law, airport, seam_honoured=honoured)
            counts["seam_pin_pair_exempt"] = counts2["seam_pin_pair_exempt"]
            sol, tier_rep = solve_law_ordered(pm, cs, law, weights, cfg.options,
                                              size_out=size)
            wall[f"solve_pass{n_pass}"] = time.perf_counter() - t
            _say(f"[{icao}] seam pass {n_pass}: {len(honoured)}/{len(pm.seam_vertices)} honoured, "
                 f"{counts2['seam_pin_pair_exempt']} pairs exempt, "
                 f"{wall[f'solve_pass{n_pass}']:.2f} s, status {sol.status.value}", out)
            if sol.status.value not in ("optimal", "feasible"):
                break
    _say(f"[{icao}] solve {wall['solve']:.2f} s  status {sol.status.value}  "
         f"LP {size}  {sol.message}", out)
    _say(f"[{icao}] {tier_rep.line()}", out)
    if tier_rep.failure:
        # THE NAMED FAILURE (RULINGS 2026-09-05u): a governed family the
        # ladder made yield is not a lawful surface — the patch is still
        # written (the census reads it), the app fails the airport by name
        _say(f"[{icao}] FAILURE: {tier_rep.failure}", out)
    relaxed_rows = relaxed_publication(tier_rep)
    for ln in relaxation_lines(tier_rep):
        _say(f"    {ln}", out)
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
        "law_tiers": tier_rep.as_dict(),
        "off_dem_by_role": moved,
        "road_profile": road_rep,
        "road_profile_agreement": road_agree,
        "seam": report_seam,
        "solve": {"status": sol.status.value, "wall_s": round(sol.wall_s, 3),
                  "iterations": sol.iterations, "message": sol.message,
                  # RULINGS 2026-09-05u: which scope answered, and the
                  # governed families the ladder demoted (a NAMED FAILURE)
                  "scope": tier_rep.scope, "demoted": tier_rep.demoted_governed,
                  "failure": tier_rep.failure,
                  "residual": None if sol.residual is None else _dc.asdict(sol.residual),
                  "iis": [{"row": repr(r), "generator": s.generator,
                           "ruling": s.ruling, "inputs": list(s.inputs)}
                          for r, s in sol.iis]},
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
        if relaxed_rows:
            pub["relaxed_rows"] = relaxed_rows
        header = {"o4_apt_dat": airport.pack.apt_dat_path,
                  "o4_pack": airport.pack.name}
        header.update(cfg.header_extra or {})
        paths = write_patch(surf, law, out_dir, pub, header,
                            face_tags(pm, law, airport))
        if pm.seam_vertices:
            pieces = write_tile_pieces(surf, law, out_dir, pub, header,
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
            rplan = rebake_plan(airport, objects_out[0], objects_out[1], law,
                                lambda ring, _s=surf: deck_datum_from_surface(_s, ring, _to_xy),
                                exclude={oid for b in pm.basins for oid in b.objects},
                                tunnel_objects=_plate_seats(pm, law),
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
                 f"feet {rc['feet']}  skipped {len(rplan.skipped)} "
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
            from ..verify.census import RELAXED_KEY
            relaxed_v = {k: sum(1 for r in v if r.get(RELAXED_KEY)) for k, v in vrows.items()}
            summary = {k: len(v) - relaxed_v[k] for k, v in vrows.items()}
            _say(f"[{icao}] verify {wall['verify']:.2f} s  rows "
                 f"{sum(summary.values())}  " + ", ".join(
                     f"{k} {n}" for k, n in summary.items() if n), out)
            if any(relaxed_v.values()):
                _say(f"[{icao}] verify: relaxed by 04t(1) (lawful last-resort rows, counted "
                     f"apart): {sum(relaxed_v.values())}  " + ", ".join(
                         f"{k} {n}" for k, n in relaxed_v.items() if n), out)
            from ..verify.census import DEFECT_KEYS
            defects = {k: len(vrows[k]) for k in DEFECT_KEYS if vrows.get(k)}
            for k, n in defects.items():
                _say(f"[{icao}] verify: DEFECT {k} {n} — " + "; ".join(
                    f"{r.get('way_a')} {r.get('reading')} {r.get('magnitude_m')} m"
                    for r in vrows[k][:10]) + (" ..." if n > 10 else ""), out)
            report["verify"] = {"by_family": summary,
                                "relaxed_by_04t1": {k: n for k, n in relaxed_v.items() if n},
                                "defects": defects,
                                "rows": {k: v for k, v in vrows.items() if v}}
    else:
        for r, s in sol.iis[:50]:
            _say(f"    IIS {s.generator} [{s.ruling}] {s.inputs}: {r!r}", out)
    wall["total"] = sum(wall.values())
    report["wall_s"] = {k: round(v, 3) for k, v in wall.items()}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / f"{icao}.report.json").write_text(
        json.dumps(report, indent=1, default=str))
    _say(f"[{icao}] total {wall['total']:.2f} s  -> {out_dir}", out)
    return BuildResult(icao, pm, cs, counts, sol, paths, vrows, pieces, wall, size, report,
                       Path(out_dir) / f"{icao}.rebake.json" if report.get("rebake_plan")
                       else None)
