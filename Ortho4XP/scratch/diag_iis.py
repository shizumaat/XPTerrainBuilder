import os, sys, pickle, time, collections
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.planar.territories import row_vertices, NO_LABEL
stage = pickle.load(open(f"{SP}/HECA_t3_stage.pkl", "rb")); pm = stage.pm; terr = stage.terr
cs = pickle.load(open(f"{SP}/HECA_t3_cs.pkl", "rb"))
law = Law.for_airport("HECA"); w = weights_under_law(DEFAULT_WEIGHTS, law)
t = time.perf_counter()
sol = solve_hard(pm, cs, w, Options(diagnose_iis=True))
print("status", sol.status, f"{time.perf_counter()-t:.0f} s", "IIS rows", len(sol.iis), flush=True)
c = collections.Counter((s.generator, s.ruling[:50]) for r, s in sol.iis)
for k, n in c.most_common(20): print(n, k)
vs = collections.Counter(v for r, s in sol.iis for v in row_vertices(r))
print("vertices", len(vs), "top", vs.most_common(12))
for r, s in sol.iis[:40]:
    ids = row_vertices(r)
    print(type(r).__name__, s.generator, ids, [terr.label.get(v, NO_LABEL) for v in ids], getattr(r, "cap", None), getattr(r, "d", None), getattr(r, "z", None), getattr(r, "lo", None), getattr(r, "hi", None), s.ruling[:70], s.inputs[:2])
