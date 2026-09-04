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
from ..emit.osm_adapter import PatchPaths, write_patch
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
    wall: dict[str, float]
    lp_size: dict[str, int]
    report: dict[str, _t.Any]


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
    pm, pstats = build_planar(airport, cl, law)
    wall["planar"] = time.perf_counter() - t
    _say(f"[{icao}] planar {wall['planar']:.2f} s  faces {pstats.faces}  "
         f"edges {pstats.edges}  vertices {pstats.vertices}  "
         f"breaklines {pstats.breaklines}  T-vertices {pstats.t_vertices}", out)
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
    _say(f"[{icao}] solve {wall['solve']:.2f} s  status {sol.status.value}  "
         f"LP {size}  {sol.message}", out)
    if sol.residual is not None:
        r = sol.residual
        _say(f"    residual: pin {r.max_pin_m:.4f} diff {r.max_diff_m:.4f} "
             f"flat {r.max_flat_m:.4f} band {r.max_band_m:.4f} "
             f"offset {r.max_offset_m:.4f} m  objective {r.objective:.2f}", out)
    report: dict[str, _t.Any] = {
        "icao": icao, "ruleset": law.ruleset_key,
        "load": _dc.asdict(lrep), "planar": _dc.asdict(pstats),
        "constraints": {"by_generator": counts, "by_kind": cs.counts(),
                        "wall_s": {k: round(v, 4) for k, v in gwalls.items()}},
        "lp": size,
        "solve": {"status": sol.status.value, "wall_s": round(sol.wall_s, 3),
                  "iterations": sol.iterations, "message": sol.message,
                  "residual": None if sol.residual is None else _dc.asdict(sol.residual),
                  "iis": [{"row": repr(r), "generator": s.generator,
                           "ruling": s.ruling, "inputs": list(s.inputs)}
                          for r, s in sol.iis]},
    }
    paths = None
    vrows = None
    if sol.status.value in ("optimal", "feasible"):
        t = time.perf_counter()
        surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs,
                              {"law_ruleset": law.ruleset_key,
                               "pack": airport.pack.name})
        pub = publication(pm, law, airport, sol.z)
        paths = write_patch(surf, law, out_dir, pub,
                            {"o4_apt_dat": airport.pack.apt_dat_path,
                             "o4_pack": airport.pack.name},
                            face_tags(pm, law))
        wall["emit"] = time.perf_counter() - t
        _say(f"[{icao}] emit {wall['emit']:.2f} s  ways {paths.ways}  nodes {paths.nodes}"
             f"  patch {paths.bytes_patch} B  sidecar {paths.bytes_sidecar} B", out)
        report["emit"] = {"patch": str(paths.patch), "sidecar": str(paths.sidecar),
                          "ways": paths.ways, "nodes": paths.nodes,
                          "bytes_patch": paths.bytes_patch,
                          "bytes_sidecar": paths.bytes_sidecar,
                          "published": {k: len(v) for k, v in pub.items()}}
        if cfg.verify:
            t = time.perf_counter()
            from ..constraints.roads import road_law_caps
            from ..verify import census
            vrows = census(surf, law, pub, road_law_caps(pm, law))
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
    return BuildResult(icao, pm, cs, counts, sol, paths, vrows, wall, size, report)
