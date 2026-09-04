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

from ..airport.load import Inputs, load_with_report
from ..classify import classify, load_rules
from ..constraints import generate
from ..emit.graded import graded_surface
from ..emit.osm_adapter import PatchPaths, write_patch, write_tile_pieces
from ..airport.rebake_plan import plan as rebake_plan
from ..emit.rebake import deck_datum_from_surface
from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from ..planar.build import build as build_planar
from ..solve import Options, Solution, Weights
from ..solve.highs import solve
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


def _say(msg: str, out: _t.Callable[[str], None]) -> None:
    out(msg)


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
    if ss.bores:
        _say(f"[{icao}] structures: bores {ss.bores} (uncovered {ss.bores_uncovered})  "
             f"mouths {ss.mouths}  duals merged {ss.duals_merged}  tunnels {ss.tunnels}  "
             f"decks {ss.decks}  cells cut {ss.cells_cut}  refused {len(ss.refused)}", out)
        for r in ss.refused:
            _say(f"    refused {r}", out)
        for tn in pm.structures:
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
    t = time.perf_counter()
    cs, counts, gwalls = generate(pm, law, airport)
    wall["constraints"] = time.perf_counter() - t
    _say(f"[{icao}] constraints {wall['constraints']:.2f} s  {cs.counts()}", out)
    for name, n in counts.items():
        _say(f"    {name:28s} {n:8d}  {gwalls[name]:.3f} s", out)
    t = time.perf_counter()
    size: dict[str, int] = {}
    sol = solve(pm, cs, cfg.weights, cfg.options, size_out=size)
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
            sol = solve(pm, cs, cfg.weights, cfg.options, size_out=size)
            wall[f"solve_pass{n_pass}"] = time.perf_counter() - t
            _say(f"[{icao}] seam pass {n_pass}: {len(honoured)}/{len(pm.seam_vertices)} honoured, "
                 f"{counts2['seam_pin_pair_exempt']} pairs exempt, "
                 f"{wall[f'solve_pass{n_pass}']:.2f} s, status {sol.status.value}", out)
            if sol.status.value not in ("optimal", "feasible"):
                break
    _say(f"[{icao}] solve {wall['solve']:.2f} s  status {sol.status.value}  "
         f"LP {size}  {sol.message}", out)
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
        "seam": report_seam,
        "solve": {"status": sol.status.value, "wall_s": round(sol.wall_s, 3),
                  "iterations": sol.iterations, "message": sol.message,
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
                                exclude={oid for b in pm.basins for oid in b.objects})
            rebake_path = Path(out_dir) / f"{icao}.rebake.json"
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            rebake_path.write_text(rplan.to_json())
            wall["rebake_plan"] = time.perf_counter() - t
            rc = rplan.counts
            _say(f"[{icao}] rebake plan {wall['rebake_plan']:.2f} s  units {rc['units']}  "
                 f"members {rc['members']}  deck members {rc['deck_members']}  "
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
            summary = {k: len(v) for k, v in vrows.items()}
            _say(f"[{icao}] verify {wall['verify']:.2f} s  rows "
                 f"{sum(summary.values())}  " + ", ".join(
                     f"{k} {n}" for k, n in summary.items() if n), out)
            report["verify"] = {"by_family": summary,
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
