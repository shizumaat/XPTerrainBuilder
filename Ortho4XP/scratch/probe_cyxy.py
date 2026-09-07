import os, sys, json, pickle
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from pathlib import Path
from auto_patch_v2.pipeline.build import Config, build as build_v2
from auto_patch_v2.planar.__main__ import default_inputs
out = Path(SP) / "cyxy_probe"; out.mkdir(exist_ok=True)
res = build_v2("CYXY", default_inputs(), out, Config())
print("status", res.solution.status, "wall", round(res.wall["total"], 1))
rows = res.verify_rows.get("airside_no_step") or []
print("airside_no_step rows:", rows)
side = json.load(open(res.paths.sidecar))
tj = side.get("terrace_joints") or []
print("terrace_joints", len(tj), [ (r.get("kind"), r.get("label_boundary"), round(float(r.get("step_m") or 0),2), round(float(r.get("length_m") or 0)), r.get("roles")) for r in tj][:12])
st = getattr(res, "territory", None) or getattr(res, "stage", None)
print("res attrs", [a for a in dir(res) if not a.startswith("_")])
