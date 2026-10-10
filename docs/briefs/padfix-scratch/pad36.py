"""pad36.py ICAO REF [gapfree] — DRY READ (no solve) of one held pad on the registered pads67 capture under this tree:
its ring vertices on the FULL map with the faces each stands on, its datum column, its hold set, and every row
naming the datum column (head, stage-relevant partner roles)."""
import collections
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PF_ROOT", "/Users/noah/XPTerrainBuilder/.claude/worktrees/padfix/Ortho4XP"))
CAP = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/pads67")


def verts(r):
    t = type(r).__name__
    if t == "Linear":
        return [v for v, _c in r.terms]
    if t in ("Diff", "Offset"):
        return [r.a, r.b]
    if t in ("Pin", "Band"):
        return [r.v]
    if t == "Flat":
        return list(r.group)
    return []


def main(icao, refs, gap_free):
    sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("v2_solve_replay", ROOT / "tools" / "v2_solve_replay.py")
    rep = importlib.util.module_from_spec(spec); sys.modules["v2_solve_replay"] = rep; spec.loader.exec_module(rep)
    rep.pool_budget(1)
    prob = rep.replay_problem(CAP / f"{icao}.pkl", "classify", [], gap_free=gap_free)
    pm, cs, law = prob["pm"], prob["cs"], prob["law"]
    print("prob keys", sorted(prob.keys()))
    from auto_patch_v2.model.platform import HELD, datum_vertices, stage_air_vertices
    from auto_patch_v2.constraints.platform import hold_sets
    air = stage_air_vertices(pm, law)
    dvs = datum_vertices(pm, law)
    hs = {p: (dv, w, n, r) for p, dv, w, n, r in hold_sets(pm, law)}
    _to_xy, to_ll = prob["airport"].frame.transformers()
    faces_of = lambda v: sorted({f"{pm.faces[q].role}:{pm.faces[q].ref}" for q in pm.vertices[v].incident_faces})
    by_v = collections.defaultdict(list)
    for r in cs.rows():
        for v in verts(r):
            by_v[v].append(r)
    for ref in refs:
        vs = set()
        for f in pm.faces.values():
            if str(f.ref) == ref:
                for ring in (f.ring, *f.holes):
                    vs.update(pm.ring_vertices(ring))
        print(f"== {ref}: {len(vs)} vertices; HELD {({k: HELD[ref].get(k) for k in ('verdict', 'conforming')} if ref in HELD else None)}; "
              f"datum column {dvs.get(ref)}; hold set {hs.get(ref)}")
        for v in sorted(vs):
            x, y = pm.vertices[v].xy
            print(f"   v{v} ll {to_ll(x, y)} air {v in air} {faces_of(v)}")
        dv = dvs.get(ref)
        for v in sorted(vs - air):
            heads = collections.Counter()
            for r in by_v.get(v, []):
                others = sorted({pm.faces[q].role for u in verts(r) if u != v for q in pm.vertices[u].incident_faces})
                heads[(type(r).__name__, r.source.ruling.split(" (")[0][:64], tuple(others[:4]))] += 1
            print(f"   rows on v{v}{' (DATUM COLUMN)' if v == dv else ''}:")
            for h, n in heads.most_common(20):
                print(f"      {n:4d} {h}")


if __name__ == "__main__":
    a = sys.argv[1:]
    gf = "gapfree" in a
    a = [x for x in a if x != "gapfree"]
    main(a[0], a[1:], gf)
