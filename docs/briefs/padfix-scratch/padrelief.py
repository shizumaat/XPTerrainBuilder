"""padrelief.py GRADED.json SIDECAR.json [GRADED_B.json SIDECAR_B.json] — every pad (building faces by base ref):
vertices, how many are its OWN / welded to AIRSIDE pavement / welded to GROUNDSIDE pavement only, relief (max - min),
tilt over its extent, the sidecar's hold verdict; classes and counts over 0.05 m (a read; prices nothing)."""
import collections
import json
import math
import sys

AIR = {"apron", "cross_connector", "junction", "primary_parallel", "runway", "runway_crossing", "secondary_parallel", "stub"}
GS = {"groundside_pavement", "parking_lot", "service_junction", "service_road"}


def read(gp, sp):
    G = json.load(open(gp)); X = json.load(open(sp))
    V = {v[0]: v for v in G["vertices"]}
    held = {p["ref"]: p for p in X.get("platforms", []) if isinstance(p, dict) and "ref" in p}
    use = collections.defaultdict(set)
    for f in G["faces"]:
        for ring in (f["ring"], *f.get("holes", [])):
            for i in ring:
                use[i].add(f["role"])
    pads = collections.defaultdict(set)
    for f in G["faces"]:
        if f["role"] == "building":
            pads[f["ref"].split("#")[0]].update(f["ring"])
    out = {}
    for ref, vs in pads.items():
        air = [i for i in vs if use[i] & AIR]
        gs = [i for i in vs if not (use[i] & AIR) and use[i] & GS]
        own = len(vs) - len(air) - len(gs)
        zs = [V[i][3] for i in vs]
        lat = [V[i][1] for i in vs]; lon = [V[i][2] for i in vs]
        ext = math.hypot((max(lat) - min(lat)) * 111320, (max(lon) - min(lon)) * 111320 * math.cos(math.radians(lat[0])))
        cls = ("landing" if "/landing" in ref else
               "all-weld gs" if not own and not air else "all-weld air" if not own and not gs else
               "all-weld mixed" if not own else "own+air" if air else "own, landside")
        hp = held.get(ref)
        i0 = next(iter(vs))
        out[ref] = dict(cls=cls, n=len(vs), own=own, air=len(air), gs=len(gs), relief=round(max(zs) - min(zs), 2),
                        tilt=round(100 * (max(zs) - min(zs)) / max(ext, 1e-6), 2), ext=round(ext),
                        verdict=(hp.get("hold_verdict") if hp else None), ll=f"{V[i0][1]:.8f}, {V[i0][2]:.8f}")
    return out


def main(a):
    A = read(a[0], a[1])
    B = read(a[2], a[3]) if len(a) > 3 else None
    for name, R in (("A", A), ("B", B)):
        if R is None:
            continue
        c = collections.Counter(r["cls"] for r in R.values())
        over = collections.Counter(r["cls"] for r in R.values() if r["relief"] > 0.05)
        print(f"{name}: pads {len(R)}; by class (pads / with relief > 0.05 m): " +
              "; ".join(f"{k} {c[k]} / {over[k]}" for k in sorted(c)))
    for cls in sorted({r["cls"] for r in A.values()}):
        rows = sorted(((r["relief"], ref) for ref, r in A.items() if r["cls"] == cls and r["relief"] > 0.05), reverse=True)[:6]
        for rel, ref in rows:
            r = A[ref]
            b = f" | B relief {B[ref]['relief']}" if B and ref in B else ""
            print(f"   [{cls}] {ref}: relief {rel} m over {r['ext']} m ({r['tilt']} %), n {r['n']} own {r['own']} air {r['air']} gs {r['gs']}, {r['verdict']}, {r['ll']}{b}")


if __name__ == "__main__":
    main(sys.argv[1:])
