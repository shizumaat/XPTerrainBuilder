import os, sys, json
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from pathlib import Path
import auto_patch_v2.verify.frame as F
box = {}
_of = F.Patch.of
def of(*a, **k):
    p = _of(*a, **k); box["p"] = p; return p
F.Patch.of = staticmethod(of) if not hasattr(_of, "__self__") else classmethod(lambda cls, *a, **k: of(*a, **k))
from auto_patch_v2.pipeline.build import Config, build as build_v2
from auto_patch_v2.planar.__main__ import default_inputs
from auto_patch_v2.verify.no_step import rate_breaches, no_step_roles
from auto_patch_v2.model.constraints import Linear
out = Path(SP) / "cyxy_probe"; out.mkdir(exist_ok=True)
res = build_v2("CYXY", default_inputs(), out, Config(), out=lambda m: None)
p = box.get("p")
print("patch stashed", p is not None, "joint drops", {k: v for k, v in res.counts.items() if "joint" in k})
law = p.law; r = law.ruleset.strip.arc_rate; rate = r.grade / r.per_m
q = law.tables.emit.instrument.coarse_noise_m; floor = law.tables.emit.materiality.grade
roles = no_step_roles(law)
for sh in p.shapes:
    if sh.role not in roles or len(sh.ids) < 3: continue
    for a, b, c, change, allowed, dp, dn in rate_breaches(sh.xy, sh.z, True, rate, q, floor):
        ids = (sh.ids[a], sh.ids[b], sh.ids[c])
        print("BREACH", sh.role, sh.key, "ids", ids, "change", round(change, 5), "allowed", round(allowed, 5), "dp dn", round(dp,1), round(dn,1), "z", [round(sh.z[i],3) for i in (a,b,c)])
        pm = res.planar
        for v in ids:
            print("   v", v, "faces", [pm.faces[f].role+"#"+str(f) for f in pm.vertices[v].incident_faces])
        S = set(ids)
        rows = [rw for rw in res.constraints.rows() if isinstance(rw, Linear) and S <= {v for v, _c in rw.terms}]
        print("   linear rows over the triple:", [(rw.source.generator, rw.source.ruling[:40]) for rw in rows][:6])
        pair_rows = [rw for rw in res.constraints.rows() if hasattr(rw, "a") and {rw.a, rw.b} <= S]
        print("   pair rows:", [(rw.source.generator, rw.a, rw.b) for rw in pair_rows][:8])
