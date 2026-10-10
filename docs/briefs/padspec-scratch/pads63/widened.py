"""pads63 scratch: the rows the pad weld floor widened (RULINGS 2026-10-08d (2)) on a --solved-out pickle — per misfit
block: datum, misfit, contacts, rows widened, rows that USE the widening (|dz| over the unwidened bound) and the
steepest resulting grade against its own cap, with coordinates.
usage: widened.py SOLVED.pkl SIDECAR.axes.json"""
import pickle, json, sys, collections
sys.path.insert(0, "src")
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.constraints.weld_floor import ruling_note
sv = pickle.load(open(sys.argv[1], "rb")); sc = json.load(open(sys.argv[2]))
pm, cs, z = sv["pm"], sv["cs"], sv["z"]
k11 = lambda ll: (round(float(ll[0]), 11), round(float(ll[1]), 11))
key2v = {k11(v.key): i for i, v in (pm.vertices.items() if isinstance(pm.vertices, dict) else enumerate(pm.vertices))}
head = lambda r: r.source.ruling.split(" (")[0].strip()
roles = lambda v: "|".join(sorted({pm.faces[f].role for f in pm.vertices[v].incident_faces}))
rows = [d for d in cs.diffs if ruling_note in d.source.ruling]
print(f"widened Diff rows in the solved set: {len(rows)}; widened Linear rows: {sum(1 for l in cs.linears if ruling_note in l.source.ruling)}")
for p in sc["platforms"]:
    w = p.get("weld_widened")
    if not w: continue
    con = {key2v[k11(c)]: (float(c[2]) if len(c) > 2 else float(w["floor_m"])) for c in w["contacts"] if k11(c) in key2v}
    used = []; byh = collections.Counter(); seen = set()
    for d in rows:
        a, b = int(d.a), int(d.b)
        if a not in con and b not in con: continue
        fl = max(con.get(a, 0.0), con.get(b, 0.0))
        dz = abs(float(z[a]) - float(z[b]) - float(d.rel)); cap0 = d.cap - fl / d.d
        byh[head(d)] += 1
        if dz > cap0 * d.d + 0.005 and (min(a, b), max(a, b), head(d)) not in seen:
            seen.add((min(a, b), max(a, b), head(d)))
            used.append((dz - cap0 * d.d, dz / d.d, cap0, d.d, head(d), a, b))
    used.sort(reverse=True)
    print(f"== {p['ref']} at {p.get('centroid_ll')} {p.get('pad_m2')} m2: datum {p.get('datum')} misfit {p.get('misfit_m')} m, contacts {len(w['contacts'])}, "
          f"give max {max(con.values(), default=0):.3f}, sealed {w.get('sealed')} (max {w.get('sealed_max_m')}), rows widened {w.get('rows')} (runway rows kept {w.get('runway_rows_kept')}), released {p.get('released')}/{p.get('released_max_m')}")
    print("   widened rows by head:", dict(byh.most_common()))
    print(f"   rows USING the widening (|dz| over the unwidened bound by > 5 mm): {len(used)}")
    if used:
        g = max(used, key=lambda u: u[1]); e = used[0]
        for tag, u in (("steepest", g), ("largest give", e)):
            ex, gr, cap0, d, h, a, b = u
            print(f"   {tag}: {100*gr:.2f} % vs cap {100*cap0:.2f} % over {d:.1f} m (+{ex:.3f} m) | {h} | {list(pm.vertices[a].key)} [{roles(a)}] -> {list(pm.vertices[b].key)} [{roles(b)}]")
        over = [u for u in used if u[3] >= 5.0]
        if over:
            g = max(over, key=lambda u: u[1]); ex, gr, cap0, d, h, a, b = g
            print(f"   steepest over a chord >= 5 m: {100*gr:.2f} % vs cap {100*cap0:.2f} % over {d:.1f} m | {h} | {list(pm.vertices[a].key)} -> {list(pm.vertices[b].key)}")
