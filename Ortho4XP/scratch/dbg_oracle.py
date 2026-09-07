import sys; sys.path.insert(0, "tests/auto_patch_v2"); sys.path.insert(0, "src"); sys.path.insert(0,"tools/harness"); sys.path.insert(0,"tools")
import test_v2terrace3 as T
from auto_patch_v2.law import Law
law = Law.for_airport("ZZZZ")
cell, cut = T._east(900.0)
airport, pm, stage, ps, cl = T._airport(law, [T.RUNWAY, T.APRON, T.STUB_W, cell], [T.CUT_W, cut])
from auto_patch_v2.constraints import generate
from auto_patch_v2.solve import Options, solve
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication, face_tags
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
import check_grade as cg, tempfile
cs,_c,_w = generate(pm, law, airport)   # CONTROL: no territory stage at all
sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False)); print("control status", sol.status)
surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
pub = publication(pm, law, airport, sol.z)
d = tempfile.mkdtemp(); paths = write_patch(surf, law, d, pub, face_tags=face_tags(pm, law))
fam={}; cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
for v in fam.get("within_shape", [])[:5]: print("CONTROL ROW", v.grade_pct, v.distance_m, v.de_m, getattr(v.way_a,'role',None), v.elev_a, v.elev_b)
print("control within_shape rows", len(fam.get("within_shape", [])))
