#!/usr/bin/env python3
"""THE v2 SOLVE REPLAY — capture one airport's v2 pipeline product at the
territory stage ONCE, then re-run the constraint generators and the solve
under the CURRENT tree as often as a change needs, without paying for the
load / classify / planar stages again (the synthetic-first solve-arm
pattern of ``docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py``,
promoted on its second use by lane ``v2chord``).

    venv/bin/python tools/v2_solve_replay.py --capture ICAO --out DIR/ICAO.pkl
    venv/bin/python tools/v2_solve_replay.py --replay DIR/ICAO.pkl [--from constraints|territory|planar]
        [--drop-generator G ...] [--json OUT.json] [--z-out Z.npy]

``--capture`` runs load → classify → planar → flat site → road profile →
territory stage exactly as ``pipeline/build.py`` does and pickles the
airport, the classification, the planar map and the territory stage.
``--replay`` resumes from the named stage (``constraints``: generators +
joint filter + solve, the default; ``territory``: the territory stage
too; ``planar``: the planar build too — for a change in the map) and
prints, per runway with two CIFP thresholds, the crown-ridge BOW (min of
z − the threshold line), the ridge minimum and its station, and z − DEM
over the ridge (mean / min / max); the law-tier line, the yielded-rows
figure per family (``solve.yielding.yielded_rows``), the joint steps and
the solve wall.  No patch is written: this is the solve arm, the emitted
patch is the closing build's (``harness/build_airport.py``).

Run it from ``Ortho4XP/``; read-only on the shared corpus (the capture
reads through the production loader like a build; nothing is written
outside ``--out`` / ``--json``)."""
from __future__ import annotations

import argparse
import dataclasses as _dc
import json
import math
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def capture(icao: str, out: Path) -> None:
    from auto_patch_v2.airport import flat_site as _flat
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline.__main__ import default_inputs
    from auto_patch_v2.pipeline.territory import territory_stage
    from auto_patch_v2.planar.build import build as build_planar
    law = Law.for_airport(icao)
    inputs = default_inputs()
    t = time.perf_counter()
    airport, _lrep = load_with_report(icao, inputs, law)
    cl = classify(airport, law, load_rules())
    objects_out: list = []
    pm, _pstats = build_planar(airport, cl, law, objects_out=objects_out)
    fv = _flat.detect(airport, law, objects=objects_out[0] if objects_out else ())
    airport = _dc.replace(airport, flat_site=fv)
    road_pref, _rep, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                           inputs.lane_width_m)
    pm = _dc.replace(pm, preferred_z=road_pref)
    stage = territory_stage(pm, law, airport, cl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        pickle.dump({"icao": icao, "airport": airport, "cl": cl, "pm": pm, "stage": stage,
                     "inputs": inputs}, fh)
    print(f"[{icao}] captured -> {out} in {time.perf_counter() - t:.0f} s "
          f"(vertices {len(pm.vertices)}, faces {len(pm.faces)})")


def runway_read(pm, law, airport, z) -> list[dict]:
    """Per runway with two thresholds: bow, ridge min, z − DEM over the ridge."""
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import ridge_chains
    chains = ridge_chains(view(pm, law))
    out = []
    for rw in airport.runways:
        e0, e1 = rw.ends
        if e0.threshold_elev_m is None or e1.threshold_elev_m is None:
            continue
        chs = chains.get(rw.id) or []
        vs = [v for ch in chs for v in ch]
        if not vs:
            continue
        L = math.dist(e0.xy, e1.xy)
        ux, uy = (e1.xy[0] - e0.xy[0]) / L, (e1.xy[1] - e0.xy[1]) / L
        rows = []
        for v in vs:
            x, y = pm.vertices[v].xy
            s = (x - e0.xy[0]) * ux + (y - e0.xy[1]) * uy
            line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
            rows.append((s, float(z[v]), line, pm.vertices[v].dem_z, v))
        bow = min(rows, key=lambda r: r[1] - r[2])
        zmin = min(rows, key=lambda r: r[1])
        off = [r[1] - r[3] for r in rows if r[3] is not None]
        out.append({"runway": rw.id, "bow_m": round(bow[1] - bow[2], 2), "bow_station_m": round(bow[0]),
                    "ridge_min_z": round(zmin[1], 2), "ridge_min_station_m": round(zmin[0]),
                    "z_dem_mean": round(sum(off) / len(off), 2) if off else None,
                    "z_dem_min": round(min(off), 2) if off else None,
                    "z_dem_max": round(max(off), 2) if off else None, "stations": len(rows)})
    return out


def replay(pkl: Path, resume: str, drop: list[str], json_out: Path | None,
           z_out: Path | None) -> int:
    import numpy as np
    from auto_patch_v2.airport.road_profile import preferred_road_z
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
    from auto_patch_v2.pipeline.territory import (joint_steps, territory_constraints,
                                                  territory_stage)
    from auto_patch_v2.planar.build import build as build_planar
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve.tiers import solve_law_ordered
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    icao, airport, cl, pm, stage, inputs = (cap["icao"], cap["airport"], cap["cl"], cap["pm"],
                                            cap["stage"], cap["inputs"])
    law = Law.for_airport(icao)
    t0 = time.perf_counter()
    if resume == "planar":
        pm, _ps = build_planar(airport, cl, law)
        road_pref, _r, _p = preferred_road_z(airport, pm, law, inputs.road_grade_limit,
                                             inputs.lane_width_m)
        pm = _dc.replace(pm, preferred_z=road_pref)
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.pipeline.territory import weld_built_steps
    if resume in ("planar", "territory"):
        pm = with_runway_chord(pm, law, airport)     # change 1 (build.py order: before the stage)
        stage = territory_stage(pm, law, airport, cl)
    else:
        stage = _dc.replace(stage, pm=with_runway_chord(stage.pm, law, airport))
    pm = stage.pm
    weights = weights_under_law(DEFAULT_WEIGHTS, law)
    size: dict = {}
    wall = 0.0
    passes = 0
    while True:
        cs, counts, _w = territory_constraints(pm, law, airport, stage)
        if drop:
            cs = ConstraintSet.from_rows([r for r in cs.rows() if r.source.generator not in drop])
        t = time.perf_counter()
        sol, rep = solve_law_ordered(pm, cs, law, weights, Options(diagnose_iis=False), size_out=size)
        wall += time.perf_counter() - t
        passes += 1
        if sol.status.value not in ("optimal", "feasible") or passes > 2:
            break
        stage2, n_label, n_terrace = weld_built_steps(stage, law, airport, cl, sol.z)
        if not (n_label or n_terrace):
            break
        print(f"[{icao}] joint step pass (08d-3): un-jointed {n_label} label contours, "
              f"{n_terrace} 06n joints on the built surface; re-solving")
        stage = stage2
        pm = stage.pm
    print(f"[{icao}] resume {resume}; rows {cs.counts()}; dropped generators {drop or '-'}; "
          f"solve {wall:.1f} s over {passes} pass(es) status {sol.status.value}; {rep.line()}")
    result = {"icao": icao, "resume": resume, "drop": drop, "status": sol.status.value,
              "solve_wall_s": round(wall, 1), "stage_wall_s": round(time.perf_counter() - t0 - wall, 1),
              "tiers": rep.line(), "counts": {k: v for k, v in counts.items()
                                               if not k.startswith("joint_dropped")},
              "joint_dropped": {k[14:]: v for k, v in counts.items() if k.startswith("joint_dropped.")}}
    if sol.status.value in ("optimal", "feasible"):
        z = np.asarray(sol.z, float)
        result["runways"] = runway_read(pm, law, airport, z)
        for r in result["runways"]:
            print(f"    {r['runway']}: bow {r['bow_m']:+.2f} at s={r['bow_station_m']}  ridge min "
                  f"{r['ridge_min_z']:.2f} at s={r['ridge_min_station_m']}  z-DEM mean "
                  f"{r['z_dem_mean']:+.2f} min {r['z_dem_min']:+.2f} max {r['z_dem_max']:+.2f}")
        try:
            from auto_patch_v2.constraints.yielding import yielded_rows
            yr = yielded_rows(cs, z, law)
            result["yielded_rows"] = yr
            print("    yielded_rows: " + ", ".join(
                f"{k} {v['yielded']}/{v['rows']} (max grade {v['max_grade']:.4f})"
                for k, v in sorted(yr.get("families", {}).items())))
        except ImportError:
            pass
        js = joint_steps(pm, law, stage, z)
        worst = sorted(js["contours"], key=lambda c: -c["step_m"])[:8]
        result["joints"] = {"contours": len(js["contours"]),
                            "over_2m": sum(1 for c in js["contours"]
                                           if c["step_m"] > law.tables.emit.terrace.max_step_m),
                            "worst": worst}
        # the 06n split joints (planar), read on the solved surface
        tj = [{"faces": [j.a, j.b], "step_m": round(max((abs(z[a] - z[b]) for a, b in j.pairs),
                                                         default=0.0), 2),
               "length_m": round(j.length_m)} for j in pm.terrace_joints]
        result["terrace_joints_06n"] = sorted(tj, key=lambda r: -r["step_m"])[:8]
        result["terrace_joints_06n_over_2m"] = sum(
            1 for j in tj if j["step_m"] > law.tables.emit.terrace.max_step_m)
        print(f"    joints (07g): {result['joints']['contours']} contours, over 2 m "
              f"{result['joints']['over_2m']}; worst {[(c['id'], c['step_m']) for c in worst]}")
        print(f"    joints (06n): {len(tj)} split joints, over 2 m {result['terrace_joints_06n_over_2m']}; "
              f"worst {[(j['faces'], j['step_m']) for j in result['terrace_joints_06n']]}")
        if z_out is not None:
            np.save(z_out, z)
    if json_out is not None:
        json_out.write_text(json.dumps(result, indent=1, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--capture", metavar="ICAO")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--replay", type=Path, metavar="PKL")
    ap.add_argument("--from", dest="resume", choices=("constraints", "territory", "planar"),
                    default="constraints")
    ap.add_argument("--drop-generator", action="append", default=[])
    ap.add_argument("--json", type=Path)
    ap.add_argument("--z-out", type=Path)
    a = ap.parse_args()
    if a.capture:
        if a.out is None:
            ap.error("--capture needs --out")
        capture(a.capture.upper(), a.out)
        return 0
    if a.replay:
        return replay(a.replay, a.resume, a.drop_generator, a.json, a.z_out)
    ap.error("one of --capture / --replay")
    return 2


if __name__ == "__main__":
    sys.exit(main())
