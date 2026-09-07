import os, sys, pickle, json
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_stage
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.no_step import no_step_edges
from auto_patch_v2.model.constraints import Diff
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
rp = pickle.load(open(f"{SP}/HECA_t3_replay.pkl", "rb")); z = rp["z"]
law = Law.for_airport("HECA")
stage = territory_stage(pm, law, airport, cl, out=lambda m: None); terr = stage.terr
_to_xy, to_ll = airport.frame.transformers()
ll = {v: tuple(map(float, to_ll(*pm.vertices[v].xy))) for v in pm.vertices}
id_of = {(round(la, 7), round(lo, 7)): v for v, (la, lo) in ll.items()}
edges = no_step_edges(pm, law, airport)
print("no_step_edges", len(edges), "sample", edges[0])
strad_ids = [(a, b) for a, b, c, d in edges if terr.straddles((a, b))]
print("generator edges that straddle", len(strad_ids), strad_ids[:6])
pub = publication(pm, law, airport, z, label_joints=stage.joints, straddles=terr.straddles)
pe = pub["airside_no_step_edges"]; print("published no_step edges", len(pe))
s2 = 0
for e in pe:
    ia = id_of.get((round(float(e["a"][0]), 7), round(float(e["a"][1]), 7))); ib = id_of.get((round(float(e["b"][0]), 7), round(float(e["b"][1]), 7)))
    if ia is not None and ib is not None and terr.straddles((ia, ib)): s2 += 1
print("published edges that straddle", s2)
tgt = {(10498,10500),(10206,10208),(10499,10501)}
for a, b, c, d in edges:
    if (min(a,b), max(a,b)) in tgt: print("generator edge", a, b, "cap", round(c,4), "route d", round(d,1), "budget", round(c*d,3))
print("published record sample", pe[0])
cs, counts, walls = generate(pm, law, airport)
for p in sorted(tgt):
    rs = [r for r in cs.rows() if isinstance(r, Diff) and {r.a, r.b} == set(p)]
    print("unfiltered rows", p, [(r.source.generator, round(r.cap,4), round(r.d,1)) for r in rs])
