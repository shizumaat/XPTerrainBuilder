"""Interventional read (mechanism before fix): which HARD row family pins
HECA 05C/23C's low point?  Weighted objective, the captured set, one arm
per dropped family; bow + v1444 per arm."""
import os, sys, pickle, time, math, dataclasses as _dc
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2lexi/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
import numpy as np
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import ConstraintSet
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.constraints.routes import RIDGE_KIND
cap = pickle.load(open(f"{SP}/HECA_capture.pkl", "rb"))
airport, pm, cs = cap["airport"], cap["pm"], cap["cs"]
law = Law.for_airport("HECA")
w = _dc.replace(weights_under_law(DEFAULT_WEIGHTS, law), lexicographic=None)
def bow_05c(z):
    for b in pm.breaklines.values():
        if b.kind != RIDGE_KIND or "05C" not in str(b.ref): continue
        vs = b.vertices(pm)
        rw = next(r for r in airport.runways if "05C" in r.id)
        e0, e1 = rw.ends; L = math.dist(e0.xy, e1.xy)
        ux, uy = (e1.xy[0]-e0.xy[0])/L, (e1.xy[1]-e0.xy[1])/L
        worst = None
        for v in vs:
            x, y = pm.vertices[v].xy; s = (x-e0.xy[0])*ux + (y-e0.xy[1])*uy
            line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
            dz = z[v] - line
            if worst is None or dz < worst[0]: worst = (dz, s, v, z[v])
        return worst
ARMS = {
    "drop_face364_rows": lambda r: not any(i == "face:364" for i in r.source.inputs),
    "drop_apron_all": lambda r: r.source.generator not in ("apron", "apron_edge_portion"),
    "drop_no_step": lambda r: r.source.generator != "no_step",
    "drop_junction_mesh": lambda r: r.source.generator != "junction_mesh",
    "drop_taxi": lambda r: r.source.generator != "taxi",
    "drop_zones": lambda r: r.source.generator != "zones",
    "drop_roads": lambda r: r.source.generator != "roads",
    "drop_strips": lambda r: r.source.generator != "strips",
    "drop_transverse": lambda r: r.source.generator != "transverse",
    "drop_runway_profile_nonpin": lambda r: r.source.generator != "runway_profile" or type(r).__name__ == "Pin",
    "drop_pads_proximity": lambda r: r.source.generator not in ("pads", "proximity"),
    "drop_apron_junction": lambda r: r.source.generator not in ("apron", "apron_edge_portion", "junction_mesh"),
    "drop_apron_junction_taxi": lambda r: r.source.generator not in ("apron", "apron_edge_portion", "junction_mesh", "taxi"),
    "drop_apron_junction_taxi_roads": lambda r: r.source.generator not in ("apron", "apron_edge_portion", "junction_mesh", "taxi", "roads"),
    "runway_no_step": lambda r: r.source.generator in ("runway_profile", "no_step"),
    "runway_transverse": lambda r: r.source.generator in ("runway_profile", "transverse"),
    "runway_pads_prox": lambda r: r.source.generator in ("runway_profile", "pads", "proximity"),
    "runway_roads": lambda r: r.source.generator in ("runway_profile", "roads"),
    "runway_taxi": lambda r: r.source.generator in ("runway_profile", "taxi"),
    "runway_junction": lambda r: r.source.generator in ("runway_profile", "junction_mesh"),
    "runway_apron": lambda r: r.source.generator in ("runway_profile", "apron", "apron_edge_portion"),
    "runway_taxi_box": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "taxi" and "short-pair box" in r.source.ruling),
    "runway_taxi_chain": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "taxi" and ("chain" in r.source.ruling or "centreline" in r.source.ruling)),
    "runway_taxi_plane": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "taxi" and "plane_gradient" in r.source.ruling),
    "runway_nostep_pairs": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "no_step" and "route pairs (2026-08-27" in r.source.ruling),
    "runway_nostep_rate": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "no_step" and "rate" in r.source.ruling),
    "runway_nostep_pad": lambda r: r.source.generator == "runway_profile" or (r.source.generator == "no_step" and "pad contact" in r.source.ruling),
    "runway_only": lambda r: r.source.generator == "runway_profile",
    "runway_zones_strips": lambda r: r.source.generator in ("runway_profile", "zones", "strips"),
}
for name in sys.argv[1:] or ARMS:
    keep = ARMS[name]
    rows = [r for r in cs.rows() if keep(r)]
    sub = ConstraintSet.from_rows(rows)
    t = time.perf_counter()
    sol = solve_hard(pm, sub, w, Options(diagnose_iis=False))
    wall = time.perf_counter() - t
    if sol.status not in (Status.OPTIMAL, Status.FEASIBLE):
        print(f"== {name}: {sol.status} {sol.message[:120]} ({wall:.0f} s)"); continue
    z = np.asarray(sol.z, float); b = bow_05c(z)
    print(f"== {name}: dropped {len(cs.rows())-len(rows)} rows; bow 05C/23C {b[0]:+.2f} m at s={b[1]:.0f} (v{b[2]} z {b[3]:.2f}); v1444 z {z[1444]:.3f} (dem {pm.vertices[1444].dem_z:.2f}); v1480 dem {pm.vertices[1480].dem_z:.2f}; wall {wall:.0f} s", flush=True)
