"""rows_at.py ICAO LAT,LON[,R] ... — THE ROWS ON A SITE'S VERTICES (a read of the replay's own constraint set on the
registered pads67 capture under this tree; no solve): per site, the vertices within R m and, per vertex, the rows
that name it grouped by ruling head, with the other vertices' roles for the zone / hold / plane rows."""
import collections
import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/padsweep/Ortho4XP")
CAP = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/pads67")


def verts(r):
    t = type(r).__name__
    if t in ("Linear",):
        return [v for v, _c in r.terms]
    if t in ("Diff", "Offset"):
        return [r.a, r.b]
    if t in ("Pin", "Band"):
        return [r.v]
    if t == "Flat":
        return list(r.group)
    return []


def main(icao, sites):
    sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("v2_solve_replay", ROOT / "tools" / "v2_solve_replay.py")
    rep = importlib.util.module_from_spec(spec); sys.modules["v2_solve_replay"] = rep; spec.loader.exec_module(rep)
    rep.pool_budget(1)
    prob = rep.replay_problem(CAP / f"{icao}.pkl", "classify", [], gap_free=True)
    pm, cs = prob["pm"], prob["cs"]
    from auto_patch_v2.model.platform import HELD
    faces_of = lambda v: sorted({(pm.faces[q].role, str(pm.faces[q].ref)) for q in pm.vertices[v].incident_faces})
    by_v = collections.defaultdict(list)
    for r in cs.rows():
        for v in verts(r):
            by_v[v].append(r)
    to_xy, _to_ll = prob["airport"].frame.transformers()
    for s in sites:
        p = [float(x) for x in s.split(",")]
        lat, lon, R = p[0], p[1], (p[2] if len(p) > 2 else 3.0)
        x0, y0 = to_xy(lon, lat)
        near = sorted((math.hypot(vx.xy[0] - x0, vx.xy[1] - y0), v) for v, vx in pm.vertices.items()
                      if math.hypot(vx.xy[0] - x0, vx.xy[1] - y0) <= R)
        print(f"== site {lat}, {lon} R {R}: {len(near)} vertices")
        for d, v in near[:6]:
            print(f"  v{v} d {d:.1f} m faces {faces_of(v)}")
            heads = collections.Counter()
            ex = {}
            for r in by_v.get(v, []):
                h = (type(r).__name__, r.source.ruling.split(" (")[0][:70], "soft" if getattr(r, "soft", None) else "")
                heads[h] += 1
                ex.setdefault(h, r)
            for h, n in heads.most_common(14):
                r = ex[h]
                others = sorted({f[0] for u in verts(r) if u != v for f in faces_of(u)})
                b = (getattr(r, "lo", None), getattr(r, "hi", None)) if type(r).__name__ in ("Linear", "Band") else (getattr(r, "cap", None), getattr(r, "d", None))
                print(f"      {n:4d} {h[0]:6s} {h[1]:70s} {h[2]:4s} e.g. bounds {b} inputs {r.source.inputs[:3]} other-vertex roles {others[:5]}")
        refs = {f[1] for _d, v in near for f in faces_of(v) if f[0] == "building"}
        for ref in sorted(refs):
            print(f"  HELD[{ref}]: {({k: HELD[ref].get(k) for k in ('verdict', 'conforming', 'blocks')} if ref in HELD else 'NOT IN HELD')}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
