import os, sys, pickle, time, collections, dataclasses as _dc
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_stage, territory_constraints
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.planar.territories import row_vertices, NO_LABEL
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA"); w = weights_under_law(DEFAULT_WEIGHTS, law)
stage = territory_stage(pm, law, airport, cl, out=print); pm = stage.pm; terr = stage.terr
pickle.dump(stage, open(f"{SP}/HECA_t3_stage.pkl", "wb"))
cs, counts, walls = territory_constraints(pm, law, airport, stage)
print("dropped", stage.dropped, flush=True)
t = time.perf_counter(); sol = solve_hard(pm, cs, w, Options(diagnose_iis=True))
print("HARD", sol.status, f"{time.perf_counter()-t:.0f} s", "IIS", len(sol.iis), flush=True)
if sol.iis:
    c = collections.Counter((s.generator, s.ruling[:45]) for r, s in sol.iis)
    for k, n in c.most_common(12): print(n, k)
    for r, s in sol.iis:
        ids = row_vertices(r); labs = [terr.label.get(v, NO_LABEL) for v in ids]
        if s.generator in ("roads", "apron", "apron_edge_portion", "reach") or len(set(labs)) > 1:
            print(type(r).__name__, s.generator, ids, labs, getattr(r, "d", None), s.inputs[:2])
else:
    import numpy as np; print("v1444", np.asarray(sol.z)[1444])
