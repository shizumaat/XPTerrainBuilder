"""F3 acceptance: the rebake plan re-derived from a build's screen sidecar with
its deck datums RE-READ off a graded surface under this tree's reader.
usage: plan_from_screen.py ICAO SCREEN.json GRADED.json MAIN_PLAN.json"""
import dataclasses as dc, hashlib, json, sys
sys.path[:0] = ["src", "."]
from auto_patch_v2.airport import rebake_screen as rs
from auto_patch_v2.emit.rebake import deck_datum_from_surface
from auto_patch_v2.emit.surface import GradedSurface
from auto_patch_v2.law import Law
icao, screen_p, graded_p, main_p = sys.argv[1:5]
law = Law.for_airport(icao)
sc = rs.read(screen_p)
if graded_p.endswith(".pkl"):   # the build's own in-memory surface (pre terrain-edges), off a --solved-out pickle
    import pickle
    sys.path.insert(0, "tools")
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.solve.api import Solution, Status
    sv = pickle.load(open(graded_p, "rb"))
    ap = sv["airport"]
    surf = graded_surface(sv["pm"], law, Solution(tuple(float(v) for v in sv["z"]), Status.OPTIMAL, None),
                          ap.frame.origin, ap.frame.crs, {})
    del sv
else:
    surf = GradedSurface.from_json(open(graded_p).read())
if len(sys.argv) > 5:           # --all: the reader of the tree before F3 (every vertex)
    import auto_patch_v2.emit.rebake as _rb
    _rb.standing_vertex_ids = lambda s: frozenset(v.id for v in s.vertices)
to_xy = sc.frame.transformers()[0]
new = tuple((ring, deck_datum_from_surface(surf, ring, to_xy)) for ring, _z in sc.deck_datum)
ch = [(i, a[1], b[1]) for i, (a, b) in enumerate(zip(sc.deck_datum, new)) if a[1] != b[1]]
print("deck rings", len(new), "re-read differs from the screen's:", ch)
plan = rs.build_plan(dc.replace(sc, deck_datum=new), law)
txt = plan.to_json()
h = hashlib.sha256(txt.encode()).hexdigest()
m = open(main_p).read(); hm = hashlib.sha256(m.encode()).hexdigest()
d = json.loads(txt)
print("plan sha", h[:12], "main sha", hm[:12], "IDENTICAL" if h == hm else "DIFFERENT")
print("counts", d.get("counts"))
for u in d["units"]:
    for mm in u["members"]:
        r = mm["resource"].split("/")[-1]
        if "Bridge" in r or "TerminalRoads" in r or "Emiri_Terminal_17" in r:
            if mm.get("deck_ring") is not None:
                print("  ", u["id"], r, "datum", mm.get("deck_datum_z"), "ends" if mm.get("deck_ends") else "-")
if h != hm:
    a, b = json.loads(m), d
    def walk(x, y, path=""):
        if type(x) != type(y): print("  DIFF", path, repr(x)[:80], repr(y)[:80]); return
        if isinstance(x, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y: print("  KEY", path + "/" + k, k in x, k in y)
                else: walk(x[k], y[k], path + "/" + k)
        elif isinstance(x, list):
            if len(x) != len(y): print("  LEN", path, len(x), len(y))
            for i, (p, q) in enumerate(zip(x, y)): walk(p, q, f"{path}[{i}]")
        elif x != y: print("  DIFF", path, repr(x)[:80], repr(y)[:80])
    walk(a, b)
    print("bytes", len(m), len(txt), "dumps-equal", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
