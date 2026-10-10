"""pads64 scratch: the surplus PAD pieces of a graded.json and what borders each (shared ring edges), with levels — the
offline read behind the scrap rule; and the owner-site table (faces by role, ring vertices, building faces) at LAT,LON,R.
usage: scraps.py GRADED.json [--site LAT,LON,R] [--base REF]"""
import json, sys, math, collections, re
g = json.load(open(sys.argv[1])); a = sys.argv[2:]
site = base_want = None
while a:
    if a[0] == "--site": site = tuple(map(float, a[1].split(",")))
    if a[0] == "--base": base_want = a[1]
    a = a[2:]
V = {v[0]: v for v in g["vertices"]}          # id, lat, lon, z ...
def zof(i): return float(V[i][3])
mlat = 111320.0
def xy(i):
    la, lo = V[i][1], V[i][2]; return (lo * mlat * math.cos(math.radians(la)), la * mlat)
def area_len(ring):
    pts = [xy(i) for i in ring]; A = 0.0; L = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        A += x0 * y1 - x1 * y0; L += math.hypot(x1 - x0, y1 - y0)
    return abs(A) / 2, L
base = lambda ref: re.split(r"[#/]", str(ref))[0]
plateau_of = lambda ref: (str(ref).split("#plateau:")[1] if "#plateau:" in str(ref) else None)
F = g["faces"]
from shapely.geometry import Polygon
from shapely.strtree import STRtree
P = []
for f in F:
    try: P.append(Polygon([xy(i) for i in f["ring"]], [[xy(i) for i in h] for h in f.get("holes") or []]).buffer(0))
    except Exception: P.append(Polygon())
tree = STRtree(P)
info = []
for k, f in enumerate(F):
    A, L = area_len(f["ring"])
    for h in f.get("holes") or []: A -= area_len(h)[0]
    info.append((A, L))
big = {}
for k, f in enumerate(F):
    if f["role"] == "building" and plateau_of(f["ref"]) is None:
        b = base(f["ref"])
        if b not in big or info[k][0] > info[big[b]][0]: big[b] = k
cls = collections.Counter(); m2 = collections.Counter(); n = 0
for k, f in enumerate(F):
    if f["role"] != "building" or plateau_of(f["ref"]) is not None or big[base(f["ref"])] == k: continue
    b = base(f["ref"])
    if base_want and b != base_want: continue
    A, L = info[k]; nb = collections.Counter(); cov = 0.0
    ring = f["ring"]
    for q in tree.query(P[k].buffer(0.05), predicate="intersects"):
        q = int(q)
        if q == k: continue
        d = P[k].boundary.intersection(P[q].boundary.buffer(0.02)).length
        if d <= 0.05: continue
        o = F[q]
        kind = ("own" if o["role"] == "building" and base(o["ref"]) == b and plateau_of(o["ref"]) is None else
                "plateau" if plateau_of(o["ref"]) == b else o["role"])
        nb[kind] += d; cov += d
    zs = [zof(i) for i in ring]
    sig = "+".join(sorted(nb)) or "nothing"; cls[sig] += 1; m2[sig] += A; n += 1
    la = sum(V[i][1] for i in ring) / len(ring); lo = sum(V[i][2] for i in ring) / len(ring)
    if A < 2000 or base_want:
        print(f"  {str(f['ref']):22s} {A:9.1f} m2 w {2*A/L:6.2f} v {len(ring):3d} z {min(zs):.2f}..{max(zs):.2f} cov {100*cov/L:3.0f}% at {la:.6f},{lo:.6f} | " + ", ".join(f"{a} {d:.1f}" for a, d in nb.most_common()))
print(f"surplus pad pieces {n} by what borders them:"); [print(f"   {c:4d}  {m2[s]:10.1f} m2  {s}") for s, c in cls.most_common()]
if site:
    la0, lo0, R = site
    def near(i): return math.hypot((V[i][1] - la0) * mlat, (V[i][2] - lo0) * mlat * math.cos(math.radians(la0))) <= R
    fs = [k for k, f in enumerate(F) if any(near(i) for i in f["ring"])]
    roles = collections.Counter(("plateau" if plateau_of(F[k]["ref"]) else F[k]["role"]) for k in fs)
    rv = sum(len(F[k]["ring"]) + sum(len(h) for h in F[k].get("holes") or []) for k in fs)
    col = sum(1 for k in fs if "collar" in str(F[k]["ref"]))
    print(f"SITE {la0},{lo0} r {R:.0f}: faces {len(fs)} ring vertices {rv} collar {col} building {roles.get('building', 0)} | {dict(roles.most_common())}")
    for k in fs:
        if F[k]["role"] == "building":
            zs = [zof(i) for i in F[k]["ring"]]; print(f"     {str(F[k]['ref']):22s} {info[k][0]:10.1f} m2 z {min(zs):.2f}..{max(zs):.2f}")
