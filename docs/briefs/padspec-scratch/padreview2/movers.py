"""padreview2 A: the solve-owned airside movers of each arm (airside_value_delta --json, frame solve-owned) —
per arm: n / by family / worst; overlap with the FULL arm; share within D m of a building-face vertex of the
FULL arm's graded.json (a weld-vicinity mover) vs beyond (far-field); clusters at 50 m.
usage: movers.py FULL.graded.json D  arm=avd.json ..."""
import json, sys, math, collections
g = json.load(open(sys.argv[1])); D = float(sys.argv[2])
V = {v[0]: (v[1], v[2]) for v in g["vertices"]}
pad = [V[i] for f in g["faces"] if f["role"] == "building" for i in f["ring"] if i in V]
la0 = pad[0][0] if pad else 0.0
mlat = 111_320.0; mlon = 111_320.0 * math.cos(math.radians(la0))
cell = max(D, 50.0)
grid = collections.defaultdict(list)
for la, lo in pad:
    grid[(int(la * mlat // cell), int(lo * mlon // cell))].append((la * mlat, lo * mlon))
def near_pad(la, lo):
    x, y = la * mlat, lo * mlon; cx, cy = int(x // cell), int(y // cell)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for px, py in grid.get((cx + dx, cy + dy), ()):
                if math.hypot(px - x, py - y) <= D:
                    return True
    return False
def clusters(pts, r=50.0):
    cells = collections.defaultdict(list)
    for la, lo in pts:
        cells[(int(la * mlat // r), int(lo * mlon // r))].append((la, lo))
    seen = set(); n = 0
    for c in cells:
        if c in seen:
            continue
        n += 1; stack = [c]; seen.add(c)
        while stack:
            cx, cy = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    k = (cx + dx, cy + dy)
                    if k in cells and k not in seen:
                        seen.add(k); stack.append(k)
    return n
arms = {}
for spec in sys.argv[3:]:
    name, path = spec.split("=", 1)
    d = json.load(open(path))["frames"]["solve-owned"]
    arms[name] = {(m["lat"], m["lon"]): m for m in d["moved"]}
full = arms.get("F") or next(iter(arms.values()))
for name, mv in arms.items():
    fam = collections.Counter(m["family"] for m in mv.values())
    worst = {f: max((abs(m["dz_m"]) for m in mv.values() if m["family"] == f), default=0) for f in fam}
    nn = sum(1 for k in mv if near_pad(float(k[0]), float(k[1])))
    inter = len(set(mv) & set(full))
    big = sum(1 for m in mv.values() if abs(m["dz_m"]) > 0.3)
    far_big = [m for k, m in mv.items() if abs(m["dz_m"]) > 0.3 and not near_pad(float(k[0]), float(k[1]))]
    print(f"{name:4s} movers {len(mv):5d}  by family {dict(fam)}  worst {dict((f, round(w, 2)) for f, w in worst.items())}"
          f"  within {D:.0f} m of a pad rim {nn} ({100 * nn / max(1, len(mv)):.0f} %)  >0.3 m {big} (far-field {len(far_big)})"
          f"  shared with F {inter}  clusters@50m {clusters([(float(a), float(b)) for a, b in mv])}")
    for m in sorted(far_big, key=lambda m: -abs(m["dz_m"]))[:4]:
        print(f"       far-field {m['dz_m']:+.2f} at {m['lat']},{m['lon']} {m['roles']}")
