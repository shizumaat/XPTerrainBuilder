import sys; sys.path.insert(0, "tests/auto_patch_v2"); sys.path.insert(0, "src")
import test_v2terrace3 as T
from auto_patch_v2.law import Law
law = Law.for_airport("ZZZZ")
cell, cut = T._east(900.0)
airport, pm, stage, ps, cl = T._airport(law, [T.RUNWAY, T.APRON, T.STUB_W, cell], [T.CUT_W, cut])
from auto_patch_v2.pipeline.territory import territory_constraints
from auto_patch_v2.solve import Options, solve
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.steps import terrace_joints_m, joint_index
from auto_patch_v2.verify.within import within_shape
cs,_c,_w = territory_constraints(pm, law, airport, stage)
sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
pub = publication(pm, law, airport, sol.z, label_joints=stage.joints, straddles=stage.terr.straddles)
for r in pub["terrace_joints"]: print("REC", r["step_m"], r["pairs"], r.get("label_boundary"), r["points"][:3], len(r["points"]))
for j in stage.joints: print("JOINT", j.id, j.length_m, len(j.pairs), j.points[:4], j.roles)
print("edges", stage.edges[:6], len(stage.edges))
p = Patch.of(surf, law, pub)
jm = terrace_joints_m(p); print("joints_m", [(len(pts), s, pts[:2]) for pts, s in jm])
w, x = within_shape(p)
for r in w[:4]: print("ROW", r["magnitude_m"], r["distance_m"], r["site_m"], r["lat"], r["lon"])
idx = joint_index(p)
for r in w[:4]:
    a, b = r["site_m"]; print("allow", idx.allowance(tuple(a), tuple(b)))
