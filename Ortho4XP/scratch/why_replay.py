"""why on the HECA capture under the 07g stage: what binds v1444 now."""
import os, sys, pickle, time, math, json
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
import numpy as np
prog = open(f"{ROOT}/scratch/.progress", "a")
def stamp(s): prog.write(f"{time.strftime('%H:%M:%S')} why_replay: {s}\n"); prog.flush(); print(s, flush=True)
stamp("START")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.why import _prepare_solved, chain_kml
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve.why import chain_trace, family_of
from auto_patch_v2.planar.territories import NO_LABEL
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA")
w = weights_under_law(DEFAULT_WEIGHTS, law)
stage_box = {}
import auto_patch_v2.pipeline.why as W
orig = W.territory_stage if hasattr(W, "territory_stage") else None
prep = _prepare_solved("HECA", airport, pm, law, w, out=stamp, cl=cl)
pm = prep.pm
stamp(f"v1444 z {prep.z[1444]:.3f}")
# labels for the attribution: recompute the stage (cheap now) to read labels
from auto_patch_v2.pipeline.territory import territory_stage
stage = territory_stage(pm, law, airport, cl, out=lambda m: None)
lab = stage.terr.label
tr = chain_trace(prep, [1444])
stamp(f"chain from v1444: {len(tr.steps)} steps, terminal {tr.terminal} {tr.terminal_kind} {tr.terminal_note}; sum dz {tr.sum_dz:.2f}")
to_xy, to_ll = airport.frame.transformers()
tot = 0.0
for i, s in enumerate(tr.steps):
    r = s.row; src = r.source
    la, lb = lab.get(s.v, NO_LABEL), lab.get(s.u, NO_LABEL)
    d = getattr(r, "d", None); cap_ = getattr(r, "cap", None)
    fv = [pm.faces[f].role + "#" + str(f) for f in pm.vertices[s.v].incident_faces][:3]
    tot += s.dz
    stamp(f"  {i+1:2d}. {s.family:18s} {src.generator:16s} v{s.v}->v{s.u} dz {s.dz:+.2f} (Σ {tot:+.2f}) bound {s.bound_m} d {None if d is None else round(d,1)} cap {cap_} labels {la}/{lb} {'JOINT?' if la!=lb and la!=NO_LABEL and lb!=NO_LABEL and stage.terr.joint(la,lb) else ''} faces {fv} inputs {src.inputs[:2]} ruling {src.ruling[:60]}")
fid = next(f for f in pm.vertices[1444].incident_faces if pm.faces[f].role == "runway")
os.makedirs(f"{SP}/v2terrace3_kml", exist_ok=True)
path = f"{SP}/v2terrace3_kml/HECA_v1444_chain_replay.kml"
tr2 = chain_kml(prep, fid, path)
stamp(f"KML {path} ({len(tr2.steps)} steps from runway face #{fid})")
pickle.dump({"steps": [(s.v, s.u, s.family, s.row.source.generator, s.dz) for s in tr.steps], "z": prep.z}, open(f"{SP}/HECA_t3_why.pkl", "wb"))
stamp("EXIT")
