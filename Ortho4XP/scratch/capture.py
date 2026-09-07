"""Lane v2terrace3 capture (pattern: v2_capture.py / lexi_capture.py): ICAO's
load -> classify -> pass-1 planar map from THIS tree, pickled for the
synthetic-first territory iteration.  Run from the lane's Ortho4XP dir."""
import os, sys, pickle, time
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src"); sys.path.insert(0, ROOT + "/tools/harness")
icao = sys.argv[1].upper()
prog = open(f"{ROOT}/scratch/.progress", "a")
def stamp(s): prog.write(f"{time.strftime('%H:%M:%S')} capture {icao}: {s}\n"); prog.flush(); print(s, flush=True)
stamp("START")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.__main__ import shared_repo_guard
from auto_patch_v2.planar.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.planar.build import build as build_planar
law = Law.for_airport(icao)
inputs = default_inputs(None, None, None, 60.0, "production", False)
with shared_repo_guard():
    t = time.perf_counter(); airport, lrep = load_with_report(icao, inputs, law); stamp(f"load {time.perf_counter()-t:.1f}s")
    t = time.perf_counter(); cl = classify(airport, law, load_rules()); stamp(f"classify {time.perf_counter()-t:.1f}s cells {len(cl.cells)}")
    objects_out = []
    t = time.perf_counter(); pm, pstats = build_planar(airport, cl, law, objects_out=objects_out); stamp(f"planar {time.perf_counter()-t:.1f}s faces {len(pm.faces)} vertices {len(pm.vertices)}")
with open(f"{SP}/{icao}_t3_capture.pkl", "wb") as fh:
    pickle.dump({"icao": icao, "airport": airport, "cl": cl, "pm": pm, "pstats": pstats}, fh)
stamp("EXIT ok")
