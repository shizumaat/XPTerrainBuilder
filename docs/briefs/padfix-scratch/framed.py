"""framed.py ICAO [gapfree] — DRY READ (no solve): every object-framed structure (door well / wall corridor with a
pinched ramp) of the registered pads67 capture under this tree: its top_ground_z, and each rim / ramp-top vertex the
governed ground shares — the faces on it, the DEM by station, main's level (sw10 graded) and the merged level (sw11)."""
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PF_ROOT", "/Users/noah/XPTerrainBuilder/.claude/worktrees/padfix/Ortho4XP"))
CAP = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/pads67")


def zmap(p):
    return {(f"{v[1]:.11f}", f"{v[2]:.11f}"): v[3] for v in json.load(open(p))["vertices"]}


def main(icao, gap_free):
    sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("v2_solve_replay", ROOT / "tools" / "v2_solve_replay.py")
    rep = importlib.util.module_from_spec(spec); sys.modules["v2_solve_replay"] = rep; spec.loader.exec_module(rep)
    rep.pool_budget(1)
    prob = rep.replay_problem(CAP / f"{icao}.pkl", "classify", [], gap_free=gap_free)
    pm, airport = prob["pm"], prob["airport"]
    from shapely.geometry import LineString, Point
    from auto_patch_v2.constraints import structures as ST
    from auto_patch_v2.constraints.precedence import view
    law = prob["law"]
    vw = view(pm, law)
    za, zb = zmap(f"/tmp/harness/sw10_{icao}.v2/{icao}.graded.json"), zmap(f"/tmp/harness/sw11_{icao}.v2/{icao}.graded.json")
    _to_xy, to_ll = airport.frame.transformers()
    sroles = ("tunnel_ramp", ST.DOOR_RAMP_REF, *ST.WALL_CORRIDOR_ROLES, "retaining_wall")
    walls = ST.wall_faces_of(pm, pm.structures)
    ramps = ST.ramp_faces_of(pm, pm.structures)
    kinds = {}
    for tn in pm.structures:
        kinds[(tn.source, bool(tn.pinched))] = kinds.get((tn.source, bool(tn.pinched)), 0) + 1
        shared = lambda v: any(pm.faces[f].role not in sroles and vw.caps[f] is not None for f in vw.vertex_faces[v])
        rim = sorted({v for f in walls.get(tn.id, ()) for v in pm.ring_vertices(f.ring)})
        top = sorted({v for f in ramps.get(tn.id, ()) for v in pm.ring_vertices(f.ring)})
        sh = [v for v in sorted(set(rim) | set(top)) if shared(v)]
        if not sh:
            continue
        path = LineString(tn.wall_path) if len(tn.wall_path) >= 2 else None
        print(f"== {tn.id} source {tn.source} pinched {tn.pinched} top_ground_z {tn.top_ground_z} mouth_z {tn.mouth_z:.2f} "
              f"rim {len(rim)} ramp {len(top)} shared {len(sh)}")
        for v in sh[:40]:
            x, y = pm.vertices[v].xy
            lon, lat = to_ll(x, y)
            k = (f"{lat:.11f}", f"{lon:.11f}")
            dem = float(airport.dem.z(x, y))
            ds = float("nan")
            if path is not None:
                p = path.interpolate(path.project(Point(x, y))); ds = float(airport.dem.z(p.x, p.y))
            fr = sorted({f"{pm.faces[f].role}:{pm.faces[f].ref}" for f in vw.vertex_faces[v]})
            print(f"   v{v} {lat:.8f},{lon:.8f} dem {dem:.2f} dem_station {ds:.2f} main {za.get(k)} merged {zb.get(k)} {fr}")
    print("structures by (source, pinched):", kinds)


if __name__ == "__main__":
    main(sys.argv[1], len(sys.argv) > 2)
