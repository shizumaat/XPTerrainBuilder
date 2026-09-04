"""R1.3 offline reader: re-run the engine's own L-U envelope
(`one_solve._stall_envelope_gap`, want_pred=True) on the dumped pass-2 inputs
and attribute every infeasible node to the two CONSTANTS whose values
contradict.  Scratch (single use); promote if used twice."""
import json, sys, math, statistics, collections
from pathlib import Path
import numpy as np

ROOT = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/r1pins/Ortho4XP")
for p in (ROOT / "src", ROOT, ROOT / "tests", ROOT / "tools" / "harness"):
    sys.path.insert(0, str(p))

dumpdir, capture, vertices, sidecar, outdir = map(Path, sys.argv[1:6])
outdir.mkdir(parents=True, exist_ok=True)

from auto_patch.elevation_per_surface.route_profile.one_solve import _stall_envelope_gap
from auto_patch.layout import authority_rank

# ── pins (FGP node space) ────────────────────────────────────────────
pins = {}
meta = None
for line in open(next(dumpdir.glob("pass2_pins_*.jsonl"))):
    r = json.loads(line)
    if r.get("kind") == "meta":
        meta = r; continue
    pins[r["idx"]] = r
n = meta["n"]
print("pins", n, meta["tiers"])
ll2idx = {}
for i, r in pins.items():
    ll2idx.setdefault((round(r["lat"], 6), round(r["lon"], 6)), i)

# ── sidecar publications → edge provenance ───────────────────────────
sc = json.load(open(sidecar))
def _k(ll): return (round(float(ll[0]), 6), round(float(ll[1]), 6))
nostep = {}
for e in sc.get("airside_no_step_edges") or ():
    a = ll2idx.get(_k(e["a"])); b = ll2idx.get(_k(e["b"]))
    if a is None or b is None: continue
    nostep[frozenset((a, b))] = e
lattice = {}
for e in sc.get("apron_lattice_edges") or ():
    a = ll2idx.get(_k(e["a"])); b = ll2idx.get(_k(e["b"]))
    if a is None or b is None: continue
    lattice[frozenset((a, b))] = e
print("resolved no-step", len(nostep), "lattice", len(lattice))

# ── vertex history (control, who_wrote --vertex-dump) ────────────────
vh = collections.defaultdict(list)
vsites = None
with open(vertices) as fh:
    for line in fh:
        r = json.loads(line)
        if r.get("kind") == "meta":
            vsites = r["sites"]; continue
        vh[(round(r["x"], 3), round(r["y"], 3))].append(r)
FGP_SITE = next(i for i, s in enumerate(vsites) if s.startswith("solve.py:") and "final_grade_projection" in s.split(" <- ")[0] and ":10859:" in s)
def site_name(k):
    s = vsites[k].split(" <- ")
    return s[0] if len(s) < 2 else s[0] + " <- " + s[1].split(":")[0] + ":" + s[1].split(":")[1]

def who_pinned(i):
    """(pinner, pre_fgp_value, fgp_value, fgp_moved, last_pre_writer, joined)"""
    r = pins[i]
    recs = vh.get((r["x"], r["y"]), [])
    best = None
    for rec in recs:
        if f"{rec['role']}:{rec['ref']}" in r["roles"] or not r["roles"]:
            best = rec; break
    if best is None and recs: best = recs[0]
    if best is None:
        return ("UNJOINED", None, None, None, None, False)
    hist = best["hist"]
    pre = None; fgp = None; last_pre = None
    for (s, v) in hist:
        if s < FGP_SITE:
            pre = v; last_pre = s
        elif s == FGP_SITE and fgp is None:
            fgp = v
    moved = (pre is not None and fgp is not None and abs(fgp - pre) >= 0.01)
    if fgp is None:
        pinner = f"pre-FGP:{site_name(last_pre)}" if last_pre is not None else "UNKNOWN"
    elif moved:
        pinner = "FGP main projection (solve.py final_grade_projection, pass 1)"
    else:
        pinner = f"pre-FGP:{site_name(last_pre)}" if last_pre is not None else "seed"
    return (pinner, pre, fgp, moved, last_pre, True)

# ── DEM from the capture ─────────────────────────────────────────────
from auto_patch.solve_capture import load_capture
from auto_patch import elevation as _el
tail, man = load_capture(capture)
layout = tail["layout"]
dem = _el._DEM_CACHE.get((30, 31))
def dem_at(lat, lon):
    try:
        return _el._sample_dem(dem, 30, 31, lat, lon)
    except Exception:
        return None

# ── the pass-2 envelope with predecessors ────────────────────────────
f = sorted(dumpdir.glob("env*_pass2_conform_exit_*.npz"))
assert f, "no pass2 exit dump"
d = np.load(f[0])
ei, ej, eb = d["endpoint_i"], d["endpoint_j"], d["raw_budget"]
im, wi, wj, z = d["interval_mask"], d["weight_i"], d["weight_j"], d["z"]
reps = d["flat_group_reps"]; pairs = [tuple(p) for p in d["pairs"]]
print("pass2 columns", f[0].name, "edges", len(ei), "pairs", pairs)
v = _stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, int(d["n"]), pairs,
                        flat_group_reps=set(int(r) for r in reps), want_pred=True)
print("infeasible", v["infeasible"], "reachable", v["reachable"], "max_gap", v["max_gap"], "pairs", v["pairs"])
gap = v["gap"]; upper = v["upper"]; lower = v["lower"]
pu, pl = v["pred_upper"], v["pred_lower"]
shadow_inv = {s: r for r, s in v["shadow"].items()}
ntot = v["n_total"]
def norm(k): return shadow_inv.get(int(k), int(k))
def walk(pred, i):
    path = [i]; cur = i; seen = set()
    while True:
        p = int(pred[cur])
        if p < 0: return None
        if p == n: return path
        if p in seen: return None
        seen.add(p); path.append(norm(p)); cur = p
adj = collections.defaultdict(dict)
sym = ~im
for a, b, bud in zip(ei[sym], ej[sym], eb[sym]):
    if bud > 0:
        a, b = int(a), int(b)
        adj[a][b] = min(adj[a].get(b, 1e9), float(bud)); adj[b][a] = adj[a][b]
def edge_kind(a, b):
    k = frozenset((a, b)); bud = adj[a].get(b)
    dz = abs(z[a] - z[b])
    if k in nostep:
        e = nostep[k]; cap = e["budget_m"] / max(e["dist_m"], 1e-9)
        cname = "APRON_MAX_GRADE 0.01 (config.py:1004)" if abs(cap - 0.01) < 1e-4 else ("TAXI_MAX_GRADE 0.015 (config.py:821)" if abs(cap - 0.015) < 1e-4 else f"cap {cap:.4f}")
        return f"no_step t{e['tier_a']}-t{e['tier_b']} imposed={e['imposed']} {cname} dist {e['dist_m']:.1f} m", bud
    if k in lattice:
        return f"apron_lattice published budget {lattice[k]['budget_m']:.3f}", bud
    if bud is not None and abs(bud - dz) < 1e-6:
        return "own-law RELAXED to pass-1 residual (§H1.2)", bud
    return "own-law (within-shape/station/transverse)", bud
def tier_class(i):
    r = pins[i]; t = r["tier"]; roles = [x.split(":")[0] for x in r["roles"]]
    if t == 1: return "runway(t1)"
    if t == 3: return "pad(t3)"
    if t == 2:
        if any(x == "apron_station" for x in roles): return "spine_station(t2)"
        return "taxi_family(t2)"
    if t == 4: return "apron_membrane(t4)"
    return "non-airside(" + ",".join(sorted(set(roles))[:2]) + ")"
def rank(i):
    roles = [x.split(":")[0] for x in pins[i]["roles"]]
    return min((authority_rank(r) for r in roles), default=99)
def senior(a, b):
    ta, tb = pins[a]["tier"], pins[b]["tier"]
    if ta != tb and ta in (1,2,3) and tb in (1,2,3): return "L" if ta < tb else "U"
    ra, rb = rank(a), rank(b)
    if ra != rb: return "L" if ra < rb else "U"
    return "peer"

bad = np.flatnonzero(np.isfinite(gap) & (gap > 1e-9))
rows = []
for i in bad:
    i = int(i)
    PU = walk(pu, i); PL = walk(pl, i)
    aU = PU[-1] if PU else None; aL = PL[-1] if PL else None
    rows.append({"i": i, "gap": float(gap[i]), "aU": aU, "aL": aL,
                 "dU": (float(upper[i] - z[aU]) if aU is not None else None),
                 "dL": (float(z[aL] - lower[i]) if aL is not None else None),
                 "pathU": PU, "pathL": PL})
rows.sort(key=lambda r: -r["gap"])
print("rows", len(rows), "unwalkable", sum(1 for r in rows if r["aU"] is None or r["aL"] is None))

def anchor_desc(a):
    r = pins[a]; wp = who_pinned(a); dm = dem_at(r["lat"], r["lon"])
    return {"idx": a, "ll": f"{r['lat']:.7f},{r['lon']:.7f}", "xy": (r["x"], r["y"]), "tier": r["tier"],
            "class": tier_class(a), "pin": r["pin"], "roles": r["roles"][:4], "z": r["z"],
            "z_solve": r["z_solve"], "dem": None if dm is None else round(dm, 2),
            "pinner": wp[0], "pre_fgp": wp[1], "fgp": wp[2], "fgp_moved": wp[3], "joined": wp[5]}

# top-10 distinct anchor pairs
top = []; seenp = set()
for r in rows:
    if r["aU"] is None or r["aL"] is None: continue
    key = (r["aL"], r["aU"])
    if key in seenp: continue
    seenp.add(key); top.append(r)
    if len(top) == 10: break
def chain_desc(path):
    out = []
    for a, b in zip(path[:-1], path[1:]):
        kind, bud = edge_kind(a, b)
        out.append(f"{a}->{b} [{tier_class(b)}] bud {bud:.3f} dz {z[a]-z[b]:+.3f} :: {kind}")
    return out
top_out = []
for r in top:
    top_out.append({"node": r["i"], "node_desc": anchor_desc(r["i"]), "gap": r["gap"],
                    "high_anchor(L)": anchor_desc(r["aL"]), "low_anchor(U)": anchor_desc(r["aU"]),
                    "dL": r["dL"], "dU": r["dU"], "senior": senior(r["aL"], r["aU"]),
                    "chain_from_L": chain_desc(r["pathL"]), "chain_from_U": chain_desc(r["pathU"]),
                    "n_nodes_sharing_pair": sum(1 for q in rows if (q["aL"], q["aU"]) == (r["aL"], r["aU"]))})
json.dump(top_out, open(outdir / "top10_pairs.json", "w"), indent=1, default=str)

# grouping of all infeasible nodes
groups = collections.defaultdict(list)
for r in rows:
    if r["aU"] is None or r["aL"] is None: groups[("UNWALKABLE", "", "", "", "")].append(r["gap"]); continue
    cL = tier_class(r["aL"]); cU = tier_class(r["aU"])
    pL = who_pinned(r["aL"])[0].split(" <- ")[0]; pU = who_pinned(r["aU"])[0].split(" <- ")[0]
    groups[(cL, pL, cU, pU, senior(r["aL"], r["aU"]))].append(r["gap"])
gl = []
for k, gs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    gl.append({"high(L)_class": k[0], "high_pinner": k[1], "low(U)_class": k[2], "low_pinner": k[3], "senior": k[4],
               "n": len(gs), "p50": round(statistics.median(gs), 3), "max": round(max(gs), 3)})
json.dump(gl, open(outdir / "groups.json", "w"), indent=1)
coarse = collections.defaultdict(list)
for r in rows:
    if r["aU"] is None or r["aL"] is None: continue
    coarse[(tier_class(r["aL"]), tier_class(r["aU"]), senior(r["aL"], r["aU"]))].append(r["gap"])
cl = [{"high(L)": k[0], "low(U)": k[1], "senior": k[2], "n": len(g), "p50": round(statistics.median(g), 3), "max": round(max(g), 3)} for k, g in sorted(coarse.items(), key=lambda kv: -len(kv[1]))]
json.dump(cl, open(outdir / "groups_coarse.json", "w"), indent=1)
# distinct anchors
anch = collections.Counter()
for r in rows:
    if r["aL"] is not None: anch[("L", r["aL"])] += 1
    if r["aU"] is not None: anch[("U", r["aU"])] += 1
print("distinct high anchors", len({a for (s, a) in anch if s == "L"}), "low anchors", len({a for (s, a) in anch if s == "U"}))
json.dump([{"side": s, **anchor_desc(a), "n_nodes": c} for (s, a), c in anch.most_common(40)], open(outdir / "anchors_top.json", "w"), indent=1, default=str)

# sites
def near(lat, lon, radius=25):
    out = []
    for r in rows:
        p = pins[r["i"]]
        dy = (p["lat"] - lat) * 111320; dx = (p["lon"] - lon) * 111320 * math.cos(math.radians(lat))
        if dx*dx + dy*dy <= radius*radius: out.append(r)
    return out
sites = {}
for name, (lat, lon) in {"apron_-10270": (30.11056, 31.39529), "apron_-10165_bld_-10749": (30.1108, 31.3984)}.items():
    nr = near(lat, lon)
    sites[name] = {"n_infeasible_within_25m": len(nr), "worst": None if not nr else {"node": anchor_desc(nr[0]["i"]), "gap": nr[0]["gap"], "L": anchor_desc(nr[0]["aL"]) if nr[0]["aL"] is not None else None, "U": anchor_desc(nr[0]["aU"]) if nr[0]["aU"] is not None else None}}
# carrier nodes
for c in (2379, 24595, 24935):
    sites[f"carrier_{c}"] = anchor_desc(c) | {"gap": float(gap[c]) if np.isfinite(gap[c]) else None}
json.dump(sites, open(outdir / "sites.json", "w"), indent=1, default=str)

# ── addendum: per-row anchor rows + minted-plateau flag ─────────────
dem_cache = {}
def dem_of(i):
    if i not in dem_cache:
        r = pins[i]; dem_cache[i] = dem_at(r["lat"], r["lon"])
    return dem_cache[i]
full = []
for r in rows:
    if r["aU"] is None or r["aL"] is None: continue
    dL = dem_of(r["aL"]); dU = dem_of(r["aU"])
    full.append({"i": r["i"], "gap": round(r["gap"], 3), "i_class": tier_class(r["i"]),
                 "aL": r["aL"], "aL_class": tier_class(r["aL"]), "aL_z": pins[r["aL"]]["z"], "aL_dem": dL,
                 "aL_over_dem": None if dL is None else round(pins[r["aL"]]["z"] - dL, 2),
                 "aL_pinner": who_pinned(r["aL"])[0].split(" <- ")[0],
                 "aU": r["aU"], "aU_class": tier_class(r["aU"]), "aU_z": pins[r["aU"]]["z"], "aU_dem": dU,
                 "aU_over_dem": None if dU is None else round(pins[r["aU"]]["z"] - dU, 2),
                 "aU_pinner": who_pinned(r["aU"])[0].split(" <- ")[0],
                 "senior": senior(r["aL"], r["aU"]), "hops": len(r["pathL"]) + len(r["pathU"]) - 2})
json.dump(full, open(outdir / "rows.json", "w"), indent=0)
def flag(v): return "MINTED(>5m over DEM)" if v is not None and abs(v) > 5 else "near-DEM"
g2 = collections.defaultdict(list)
for f_ in full:
    g2[(f_["aL_class"], flag(f_["aL_over_dem"]), f_["aU_class"], flag(f_["aU_over_dem"]), f_["senior"])].append(f_["gap"])
g2l = [{"high(L)": k[0], "L_dem": k[1], "low(U)": k[2], "U_dem": k[3], "senior": k[4], "n": len(g), "p50": round(statistics.median(g), 3), "max": round(max(g), 3)} for k, g in sorted(g2.items(), key=lambda kv: -len(kv[1]))]
json.dump(g2l, open(outdir / "groups_dem.json", "w"), indent=1)
for g in g2l[:16]: print("G2", g)
# station census
st = [i for i, r in pins.items() if any(x.startswith("apron_station") for x in r["roles"])]
over = [(i, pins[i]["z"] - dem_of(i)) for i in st if dem_of(i) is not None]
print("stations", len(st), ">5m over DEM", sum(1 for _, d in over if d > 5), ">10m", sum(1 for _, d in over if d > 10), "<-5m", sum(1 for _, d in over if d < -5))
lat_anchors = {r["aL"] for r in rows if r["aL"] is not None} | {r["aU"] for r in rows if r["aU"] is not None}
sa = [i for i in lat_anchors if i in set(st)]
print("station anchors", len(sa), ">5m over DEM", sum(1 for i in sa if dem_of(i) is not None and pins[i]["z"] - dem_of(i) > 5))

print("DONE")
