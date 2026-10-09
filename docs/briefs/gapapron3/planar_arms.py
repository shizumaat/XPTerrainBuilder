"""S0: which gap-apron piece changes the runway's VERTEX SET in the planar map?
Classify once; per variant (a set of gap refs re-spelled apron, other pieces dropped)
re-run the planar stage only (--pad-read: dry) and dump the runway vertex keys."""
import dataclasses as _dc, json, sys, pickle
sys.path[:0] = ["src", ".", "tools"]
if __name__ == "__main__":
    pkl, out = sys.argv[1], sys.argv[2]
    variants = [v.split(",") if v != "-" else [] for v in sys.argv[3:]]
    import auto_patch_v2.classify as _pkg
    from auto_patch_v2.law.tables import role_side
    from auto_patch_v2.model.planar import is_gap_ref
    _orig = _pkg.classify
    memo = {}
    cur = {"apron": set()}
    def _classify(airport, law, rules=None, cache=None):
        if "cl" not in memo:
            memo["cl"] = _orig(airport, law, rules, cache=cache)
        cl = memo["cl"]
        cells, k = [], 0
        for c in cl.cells:
            if c.ref in cur["apron"]:
                cells.append(_dc.replace(c, role="apron", side=role_side(law, "apron"), kind="gap_apron",
                                         ref=f"gapapron:{k}", evidence={**dict(c.evidence), "gap_apron": 1.0, "gap_ref": c.ref}))
                k += 1
            elif is_gap_ref(c.ref):
                continue
            else:
                cells.append(c)
        return _dc.replace(cl, cells=tuple(_dc.replace(c, id=i) for i, c in enumerate(cells)))
    _pkg.classify = _classify
    import v2_solve_replay as _r
    from pathlib import Path
    res = {}
    for var in variants:
        cur["apron"] = set(var)
        r = _r.replay_problem(Path(pkl), "classify", [], None, (), placement={}, sites=[], pad_read_only=True)
        pm = r["pm"]
        keys = set()
        for f in pm.faces.values():
            if f.role in ("runway", "runway_crossing"):
                for ring in (f.ring, *f.holes):
                    for v in pm.ring_vertices(ring):
                        keys.add(tuple(pm.vertices[v].key))
        res[",".join(var) or "-"] = sorted(keys)
        print("VARIANT", var, "runway vertices", len(keys), flush=True)
        json.dump(res, open(out, "w"))
    base = set(map(tuple, res["-"]))
    for k, v in res.items():
        s = set(map(tuple, v))
        print(f"{k:60s} n {len(s)} only-variant {len(s - base)} only-base {len(base - s)}")
