"""pads61 instrument table (the padreview2 reading): per arm — solve-owned movers by family, runway movers,
hard_conflict by tier, welded total, movers > 0.3 m (far-field = beyond D m of a building-face vertex of the arm's own graded.json),
relaxed pavement_max_grade ceiling rows at given sites, and the per-cluster welded diff against a reference arm.
usage: inst.py ICAO D [--sites lat,lon;lat,lon] [--ref NAME] name=ARMDIR ..."""
import json, sys, math, collections, os
a = sys.argv[1:]
icao, D = a[0], float(a[1]); a = a[2:]
sites, ref = [], None
while a and a[0].startswith("--"):
    if a[0] == "--sites": sites = [tuple(map(float, s.split(","))) for s in a[1].split(";")]
    if a[0] == "--ref": ref = a[1]
    a = a[2:]
def dist(la, lo, lb, ob):
    return math.hypot((la - lb) * 111320.0, (lo - ob) * 111320.0 * math.cos(math.radians(la)))
def load(d):
    e = f"{d}/{icao}_emit"
    sc = json.load(open(f"{e}/{icao}_auto.patch.osm.axes.json"))
    avd = json.load(open(f"{d}/avd_{icao}.json"))["frames"]["solve-owned"] if os.path.exists(f"{d}/avd_{icao}.json") else None
    g = json.load(open(f"{e}/{icao}.graded.json"))
    return sc, avd, g
def far_fn(g):
    V = {v[0]: (v[1], v[2]) for v in g["vertices"]}
    pad = [V[i] for f in g["faces"] if f["role"] == "building" for i in f["ring"] if i in V]
    la0 = pad[0][0]; mlat = 111320.0; mlon = mlat * math.cos(math.radians(la0)); cell = max(D, 50.0)
    grid = collections.defaultdict(list)
    for la, lo in pad: grid[(int(la * mlat // cell), int(lo * mlon // cell))].append((la * mlat, lo * mlon))
    def near(la, lo):
        x, y = la * mlat, lo * mlon; cx, cy = int(x // cell), int(y // cell)
        return any(math.hypot(px - x, py - y) <= D for dx in (-1, 0, 1) for dy in (-1, 0, 1) for px, py in grid.get((cx + dx, cy + dy), ()))
    return near
def welded_by_cluster(sc):
    w = collections.Counter()
    for p in sc["platforms"]: w[p.get("unit") or p["ref"]] += int(p.get("welded") or 0)
    out = {}
    for c in sc["cluster_pads"]:
        out[c["id"]] = (sum(w.get(r, 0) for r in c.get("pads") or ()), c.get("level"), c.get("pads"))
    return out, sum(int(p.get("welded") or 0) for p in sc["platforms"])
arms = {}
for spec in a:
    n, d = spec.split("=", 1); arms[n] = load(d)
print(f"{'arm':6s} {'movers':>6s} {'runway':>6s} {'taxi/worst':>12s} {'apron/worst':>12s} {'strip/worst':>12s} {'>0.3(far)':>10s} {'hc taxi':>7s} {'pad':>4s} {'gnd':>4s} {'welded':>6s} {'pads':>4s} {'absorbed':>8s}")
W = {}
for n, (sc, avd, g) in arms.items():
    tiers = collections.Counter(r.get("tier") for r in sc["hard_conflict"])
    wb, wt = welded_by_cluster(sc); W[n] = wb
    nabs = sum(len(c.get("roads_absorbed") or ()) for c in sc["cluster_pads"])
    row = f"{n:6s} "
    if avd:
        mv = avd["moved"]; fam = collections.Counter(m["family"] for m in mv)
        worst = {f: max(abs(m["dz_m"]) for m in mv if m["family"] == f) for f in fam}
        near = far_fn(g)
        big = [m for m in mv if abs(m["dz_m"]) > 0.3]
        far = [m for m in big if not near(float(m["lat"]), float(m["lon"]))]
        cell = lambda f: f"{fam.get(f, 0)}/{worst.get(f, 0):.2f}"
        row += f"{len(mv):6d} {fam.get('runway', 0):6d} {cell('taxi'):>12s} {cell('apron'):>12s} {cell('strip'):>12s} {f'{len(big)}({len(far)})':>10s} "
        rw = [m for m in mv if m["family"] == "runway"]
    else:
        row += " " * 64; rw = []
    row += f"{tiers.get('taxi', 0):7d} {tiers.get('pad', 0):4d} {tiers.get('groundside', 0):4d} {wt:6d} {len(sc['cluster_pads']):4d} {nabs:8d}"
    print(row)
    for m in rw: print(f"        RUNWAY {m['dz_m']:+.3f} at {m['lat']},{m['lon']} {m.get('roles')}")
    for la, lo in sites:
        hit = [r for r in sc["hard_conflict"] if any("pavement_max_grade ceiling" in k for k in (r.get("against") or {}))
               and r.get("site") and dist(la, lo, r["site"][0], r["site"][1]) <= 60.0]
        tx = [r for r in hit if r.get("tier") == "taxi"]
        print(f"        site {la},{lo}: pavement_max_grade ceiling rows within 60 m: {len(hit)} (taxi-tier {len(tx)}, max s_m {max((r.get('s_m') or 0 for r in tx), default=0):.2f})")
if ref and ref in W:
    for n in W:
        if n == ref: continue
        ids = sorted(set(W[n]) | set(W[ref]))
        diff = [(i, W[ref].get(i), W[n].get(i)) for i in ids if (W[ref].get(i) or (None,))[0] != (W[n].get(i) or (None,))[0]]
        print(f"-- welded per cluster, {n} vs {ref}: {len(diff)} of {len(ids)} differ")
        for i, r, x in diff[:60]:
            print(f"   {i:22s} {ref} {r and (r[0], r[1], r[2])}  ->  {n} {x and (x[0], x[1], x[2])}")
