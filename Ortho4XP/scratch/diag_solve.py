import os, sys, pickle, time, dataclasses as _dc
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_constraints
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl = cap["airport"], cap["cl"]
stage = pickle.load(open(f"{SP}/HECA_t3_stage.pkl", "rb")); pm = stage.pm   # the fallback+simplify-40 stage (pre chord-cap)
law = Law.for_airport("HECA"); w = weights_under_law(DEFAULT_WEIGHTS, law)
cs, counts, walls = territory_constraints(pm, law, airport, stage)
print("dropped", stage.dropped, flush=True)
t = time.perf_counter()
sol = solve_hard(pm, cs, w, Options(diagnose_iis=False, time_limit_s=400))
print("HARD", sol.status, f"{time.perf_counter()-t:.0f} s", sol.message[:160], flush=True)
if sol.status in (Status.OPTIMAL, Status.FEASIBLE):
    import numpy as np; z = np.asarray(sol.z); print("v1444", z[1444])
pickle.dump(cs, open(f"{SP}/HECA_t3_cs.pkl", "wb"))
