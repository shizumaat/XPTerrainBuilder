"""padspec2 — §56 (3) THE SEAT WITHOUT THE COLLAR, probed on the EMITTED
design surface (swg_*.graded.json + the platforms sidecar): for every pad
whose hold is RESIDUAL (or whose collar carries relief), read the welded
frontage contacts (pad-rim vertices shared with an airside face) at their
SOLVED z, and ask: (1) FLAT seat: max |z_c - D| (reproduces the sidecar's
residual); (2) TILTED seat: the plane of gradient <= pad_slope_max whose
max |z_c - plane| is least (an LP, scipy linprog) — if that max is within
hard_tol the apron ALREADY reached values a tilted pad plane can weld to
within the caps, so a tilted seat is sufficient (a sufficiency proof: the
solved values were themselves reached under the caps).
usage: seat_probe.py ICAO GRADED.json AXES.json [REF ...]"""
import json, sys, math
import numpy as np
from scipy.optimize import linprog
icao, graded, axes = sys.argv[1], sys.argv[2], sys.argv[3]
want = set(sys.argv[4:])
G = json.load(open(graded)); A = json.load(open(axes))
plats = {r["ref"]: r for r in A.get("platforms", [])}
lat0 = G["vertices"][0][1]; ky = 111320.0; kx = ky * math.cos(math.radians(lat0))
V = {v[0]: ((v[2]) * kx, (v[1]) * ky, v[3]) for v in G["vertices"]}
AIR = {"apron", "taxiway", "runway", "junction", "taxi", "runway_shoulder", "cross_connector", "secondary_parallel", "graded_strip"}
air_v = set()
face_by_ref = {}
for f in G["faces"]:
    vs = set(f["ring"]) | {i for h in f.get("holes", []) for i in h}
    if f.get("side") == "airside" and f.get("role") != "building":
        air_v |= vs
    face_by_ref.setdefault(str(f.get("ref")), set()).update(vs)
PS = 0.01; TOL = 0.02
for ref, rec in sorted(plats.items()):
    if want and ref not in want: continue
    if rec.get("refused") or "datum" not in rec: continue
    rim = face_by_ref.get(ref + "#collar") or face_by_ref.get(ref) or set()
    contacts = sorted(v for v in rim if v in air_v)
    if len(contacts) < 3: continue
    D = float(rec["datum"])
    X = np.array([V[v][:2] for v in contacts]); Z = np.array([V[v][2] for v in contacts])
    c0 = X.mean(axis=0); Xc = X - c0
    flat = np.abs(Z - D).max()
    # LP: min t  s.t. |Z - (d + a x + b y)| <= t, |a|,|b| <= PS/sqrt2 (conservative box inside the disc)
    n = len(Z); g = PS / math.sqrt(2)
    # vars [d, a, b, t]
    A_ub = []; b_ub = []
    for (x, y), z in zip(Xc, Z):
        A_ub.append([1, x, y, -1]); b_ub.append(z)      # d+ax+by - t <= z
        A_ub.append([-1, -x, -y, -1]); b_ub.append(-z)  # -(d+ax+by) - t <= -z
    res = linprog([0, 0, 0, 1], A_ub=A_ub, b_ub=b_ub, bounds=[(None, None), (-g, g), (-g, g), (0, None)])
    resf = linprog([0, 0, 0, 1], A_ub=A_ub, b_ub=b_ub, bounds=[(None, None), (0, 0), (0, 0), (0, None)])
    span = float(np.ptp(X, axis=0).max())
    d, a, b, t = res.x; tf = resf.x[3]
    print(f"{icao} {ref:16s} verdict={rec.get('hold_verdict')} contacts={n} span={span:.0f}m  flat@datum max|miss|={flat:.3f}  "
          f"best FLAT max|miss|={tf:.3f}  best TILTED(<=1%) max|miss|={t:.3f} grad={100*math.hypot(a,b):.2f}%  "
          f"-> {'FLAT ok' if tf<=TOL else ('TILT ok' if t<=TOL else 'RESIDUAL')}  sidecar held_miss_max={rec.get('held_miss_max_m')} released={rec.get('released')}")
