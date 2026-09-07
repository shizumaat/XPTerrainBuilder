"""The route graph's least-BUDGET path from the runway threshold pins to
05C/23C's ridge vertices (the reach floor), as a KML the owner can compare
with the gold route, plus the ridge profile: station, built z, reach
floor, threshold line."""
import os, sys, pickle, math
import numpy as np
from scipy.sparse.csgraph import dijkstra
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2lexi/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from auto_patch_v2.law import Law
from auto_patch_v2.constraints.routes import routes, RIDGE_KIND
cap = pickle.load(open(f"{SP}/HECA_capture.pkl", "rb"))
pm, cs, airport = cap["pm"], cap["cs"], cap["airport"]
law = Law.for_airport("HECA"); g = routes(pm, law, airport)
KIND = {0: "centreline", 1: "crossing", 2: "lateral hop", 3: "contact"}
pins = {p.v: (p.z, p.source.inputs[:2]) for p in cs.pins if p.source.generator == "runway_profile"}
idx = sorted(v for v in pins if v in g.nodes)
m = g.csr("budget")
D, P = dijkstra(m, directed=True, indices=idx, return_predecessors=True)
def ll(v):
    if g.is_foot(v):
        x, y = g.foot_xy[v - g.n_planar]
        # nearest planar vertex's key as an anchor for lat/lon conversion
        return None, (x, y)
    k = pm.vertices[v].key
    return k, pm.vertices[v].xy
# lat/lon from xy: fit an affine map from planar keys (key = (lat, lon)?)
ks = [(pm.vertices[v].key, pm.vertices[v].xy) for v in list(pm.vertices)[:2000]]
K = np.array([k for k, _ in ks], float); X = np.array([x for _, x in ks], float)
A = np.linalg.lstsq(np.c_[X, np.ones(len(X))], K, rcond=None)[0]
def xy2ll(x, y): return (A[0, 0]*x + A[1, 0]*y + A[2, 0], A[0, 1]*x + A[1, 1]*y + A[2, 1])
print("key sample", ks[0][0], "xy", ks[0][1], "fit", xy2ll(*ks[0][1]))
# the 05C/23C ridge
ridge = next(b for b in pm.breaklines.values() if b.kind == RIDGE_KIND and "05C" in str(b.ref))
vs = ridge.vertices(pm)
rw = next(r for r in airport.runways if "05C" in r.id); e0, e1 = rw.ends
L = math.dist(e0.xy, e1.xy); ux, uy = (e1.xy[0]-e0.xy[0])/L, (e1.xy[1]-e0.xy[1])/L
z_built = cap.get("z") or {}
print(f"pins: " + ", ".join(f"v{v} {z:.2f} {inp}" for v, (z, inp) in pins.items()))
rows = []
for v in vs:
    x, y = pm.vertices[v].xy; s = (x-e0.xy[0])*ux + (y-e0.xy[1])*uy
    line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
    ident = g.inbound(v)
    floors = [(pins[idx[i]][0] + D[i][ident], idx[i]) for i in range(len(idx)) if np.isfinite(D[i][ident])]
    fl = min(floors) if floors else (None, None)
    rows.append((v, s, line, fl[0], fl[1], pm.vertices[v].dem_z))
worst = min((r for r in rows if r[3] is not None), key=lambda r: r[3] - r[2])
print("ridge vertices", len(rows), "with reach", sum(r[3] is not None for r in rows))
print("station | line | reach CEILING | ceiling−line | dem | pin")
for r in rows[::max(1, len(rows)//24)] + [worst]:
    print(f"{r[1]:7.0f} | {r[2]:7.2f} | {r[3] if r[3] is None else round(r[3],2)} | {None if r[3] is None else round(r[3]-r[2],2)} | {r[5]:.2f} | v{r[4]}")
print("WORST ceiling vs line:", worst)
# path from the governing pin to the worst vertex and to v1444/v1480
def path_to(v):
    ident = g.inbound(v)
    i = min(range(len(idx)), key=lambda i: (pins[idx[i]][0] + D[i][ident]) if np.isfinite(D[i][ident]) else 1e9)
    ids = [ident]
    while ids[-1] != idx[i] and P[i][ids[-1]] >= 0:
        ids.append(int(P[i][ids[-1]]))
    ids.reverse()
    return idx[i], [int(g.vertex(k)) for k in ids]
wb = g.edge_budget()
edge_kind = {}
for k in range(len(g.a)):
    a, b = int(g.a[k]), int(g.b[k]); edge_kind[(min(a,b), max(a,b))] = (KIND.get(int(g.kind[k]), str(g.kind[k])), float(g.cap[k]), float(g.length[k]), int(g.face[k]))
kml = ['<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>HECA reach CEILING path: 05L/23R pin to 05C/23C ridge</name>',
       '<Style id="cl"><LineStyle><color>ff00ffff</color><width>4</width></LineStyle></Style>',
       '<Style id="hop"><LineStyle><color>ff0000ff</color><width>5</width></LineStyle></Style>',
       '<Style id="x"><LineStyle><color>ffff00ff</color><width>5</width></LineStyle></Style>']
for label, v in (("worst ridge vertex", worst[0]), ("v1444 (why chain start)", 1444)):
    pin, path = path_to(v)
    tot_len = tot_bud = 0.0
    kml.append(f'<Folder><name>{label} v{v}: from pin v{pin} ({pins[pin][0]:.2f} m)</name>')
    print(f"\nPATH to {label} v{v} from pin v{pin} z {pins[pin][0]:.2f}: {len(path)-1} hops")
    for a, b in zip(path, path[1:]):
        kd, cp, ln, fc = edge_kind.get((min(a,b), max(a,b)), ("?", 0, 0, -1))
        tot_len += ln; tot_bud += cp * ln
        pa = g.foot_xy[a - g.n_planar] if g.is_foot(a) else pm.vertices[a].xy
        pb = g.foot_xy[b - g.n_planar] if g.is_foot(b) else pm.vertices[b].xy
        (la1, lo1), (la2, lo2) = xy2ll(*pa), xy2ll(*pb)
        st = {"centreline": "cl", "crossing": "x"}.get(kd, "hop")
        kml.append(f'<Placemark><name>{kd} {ln:.0f} m @ {100*cp:.2f}% (Σ {tot_len:.0f} m, {tot_bud:.2f} m)</name><styleUrl>#{st}</styleUrl>'
                   f'<LineString><coordinates>{lo1:.7f},{la1:.7f},0 {lo2:.7f},{la2:.7f},0</coordinates></LineString></Placemark>')
        if kd != "centreline" or ln > 100:
            print(f"   {kd:12s} {ln:7.1f} m @ {100*cp:.2f}% face {fc}  Σ {tot_len:.0f} m / {tot_bud:.2f} m")
    print(f"   TOTAL {tot_len:.0f} m, budget {tot_bud:.2f} m → ceiling {pins[pin][0]+tot_bud:.2f}")
    kml.append('</Folder>')
kml.append('</Document></kml>')
open(f"{SP}/v2routecap_kml/HECA_reach_path.kml", "w").write("\n".join(kml))
