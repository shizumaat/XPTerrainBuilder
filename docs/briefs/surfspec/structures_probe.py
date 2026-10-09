"""surfspec probe — WHERE THE OTHH ARM PIECES STAND AGAINST THE BUILT
STRUCTURES: the arm pieces (``admit_probe.py --pieces-out``) intersected
with the sweep sidecar's tunnel-object corridors (``tunnel_objects``:
axis_ll buffered by width/2 + ramp length along the axis), the basin
facilities' ramp rings (``basin_facilities.ramp_rings_ll``), the stand-zone
plateaus (``plateau_rings``) and the terrace joints (``terrace_joints``).

    venv/bin/python docs/briefs/surfspec/structures_probe.py PIECES.json SIDECAR.axes.json
"""
from __future__ import annotations

import json
import math
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


def main(pieces_path, sidecar_path):
    pieces = json.load(open(pieces_path))
    sc = json.load(open(sidecar_path))
    lat0 = pieces[0]["ring_ll"][0][0]
    kx = 111_320.0 * math.cos(math.radians(lat0))
    ky = 110_540.0

    def xy(lat, lon):
        return ((lon) * kx, (lat) * ky)

    def ring(ll):
        p = Polygon([xy(la, lo) for la, lo in ll])
        return p if p.is_valid else p.buffer(0)

    P = [(p["ref"], p["m2"], p.get("class_est"), ring(p["ring_ll"])) for p in pieces]
    # tunnel corridors: axis + half width (+ the ramp beyond the walls)
    corr = []
    for t in sc.get("tunnel_objects", []):
        ax = t.get("axis_ll") or []
        if len(ax) < 2:
            continue
        w = float(t.get("width_m") or 10.0)
        line = LineString([xy(la, lo) for la, lo in ax])
        corr.append((t.get("id"), t.get("kind"), line.buffer(0.5 * w + 2.0, cap_style=2)))
    ramps = []
    for b in sc.get("basin_facilities", []):
        for r in b.get("ramp_rings_ll") or []:
            if len(r) >= 3:
                ramps.append((b.get("witness_id"), ring(r)))
    plat = []
    for k, v in (sc.get("plateau_rings") or {}).items():
        rings = v if isinstance(v, list) else [v]
        for r in rings:
            if isinstance(r, list) and len(r) >= 3 and isinstance(r[0], list):
                plat.append((k, ring(r)))
    joints = []
    for j in sc.get("terrace_joints", []):
        pts = j.get("points") or []
        if len(pts) >= 2:
            joints.append((j.get("kind"), LineString([xy(la, lo) for la, lo in pts]), j.get("step_m")))
    print(f"pieces {len(P)}; corridors {len(corr)}; basin ramp rings {len(ramps)}; plateaus {len(plat)}; joints {len(joints)}")
    for name, items in (("CORRIDOR", [(i, k, g) for i, k, g in corr]),
                        ("BASIN RAMP", [(i, "ramp", g) for i, g in ramps]),
                        ("PLATEAU", [(i, "plateau", g) for i, g in plat])):
        hits = []
        for ref, m2, cls, q in P:
            for i, k, g in items:
                x = q.intersection(g).area
                if x > 1.0:
                    hits.append((ref, m2, cls, i, k, round(x)))
                elif q.distance(g) < 5.0:
                    hits.append((ref, m2, cls, i, k, 0))
        print(f"\n{name}: {len(hits)} piece/structure pairs within 5 m")
        for h in sorted(hits, key=lambda t: -t[5])[:15]:
            print("  ", h)
    jh = []
    for ref, m2, cls, q in P:
        for k, line, step in joints:
            if q.distance(line) < 5.0:
                jh.append((ref, m2, cls, k, step, round(q.distance(line), 1)))
    print(f"\nTERRACE JOINTS within 5 m: {jh[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
