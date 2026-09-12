#!/usr/bin/env python3
"""THE SHARED-EDGE CENSUS: how many metres of a groundside shape's
boundary run along AIRSIDE PAVEMENT in an emitted patch.

The question §27 is accepted or refused on (owner RULINGS 2026-09-12c:
"shapeID 81 ... cannot be groundside because it shares a long edge with
an apron.  Something can only be groundside if it has no connection to
airside other than a service road").  No other instrument answers it:
`harness/census.py` prices PAIRS OF VALUES, so a lot welded flat along
800 m of apron breaks no grade law and reports ZERO rows;
`role_overlap_read.py` asks AREA overlap (what stands on what), which is
0 for two faces that merely share an edge; `osm_site.py` answers one
coordinate.  This is the BOUNDARY-LENGTH sweep, per shape, split by the
neighbour's side: airside pavement / service road / building.

It measures no law and counts no defects.  Geometry, roles and the
groundside partition come from the harness library
(`check_grade._parse_osm`, `effective_role`, `_GROUNDSIDE_ROLES`) — the
same code path the census and the pytest fixtures use — so a role here
is the role the law read.  Edges are joined on NODE IDENTITY (the 11-dp
canonical join, memory `canonical-identity-join`): a shared edge is two
shapes listing the same node pair, which is exactly what the planar
weld produces, never a proximity match.

    venv/bin/python tools/role_edge_census.py PATCH.osm [PATCH.osm ...]
        [--min-m 10] [--min-radius 1.0] [--detail] [--json OUT]

`--min-m` is §27's `[lot] airside_edge_min_m`; `--min-radius` its sliver
floor (area / perimeter, an emit artefact).  Several files are reported
separately — that is the arm-vs-arm read a before/after starts from.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_grade import (_GROUNDSIDE_ROLES, _parse_osm,  # noqa: E402
                         effective_role)

#: The airside PAVEMENT roles: every role the law sides airside except
#: `building` (§27 (1) — a pad is not pavement a lot can be part of).
AIRSIDE_PAVEMENT = ("runway", "runway_crossing", "primary_parallel",
                    "secondary_parallel", "stub", "cross_connector",
                    "junction", "apron")


def _shapes(path: Path):
    nodes, ways = _parse_osm(path)
    lat0 = (sum(v[0] for v in nodes.values()) / len(nodes)) if nodes else 0.0
    mlat, mlon = 111320.0, 111320.0 * math.cos(math.radians(lat0))

    def xy(nid):
        la, lo = nodes[nid][0], nodes[nid][1]
        return (lo * mlon, la * mlat)

    shapes: dict[str, dict] = {}
    for w in ways:
        sid = w.tags.get("shapeID")
        if sid is None:
            continue
        d = shapes.setdefault(sid, {"rings": [], "role": None, "cls": None,
                                    "ref": None})
        r = list(w.nids)
        if len(r) > 1 and r[0] == r[-1]:
            r = r[:-1]
        d["rings"].append(r)
        if d["role"] is None:
            d["role"] = effective_role(w)
            d["cls"] = w.tags.get("class")
            d["ref"] = w.tags.get("ref")
    return shapes, xy


def census(path: Path):
    shapes, xy = _shapes(path)

    def seg(a, b):
        ax, ay = xy(a)
        bx, by = xy(b)
        return math.hypot(ax - bx, ay - by)

    def ring_area(r):
        p = [xy(n) for n in r]
        s = 0.0
        for i in range(len(p)):
            x1, y1 = p[i]
            x2, y2 = p[(i + 1) % len(p)]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2

    edges: dict[frozenset, set] = defaultdict(set)
    for sid, d in shapes.items():
        for r in d["rings"]:
            for i in range(len(r)):
                edges[frozenset((r[i], r[(i + 1) % len(r)]))].add(sid)
    shared: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e, ss in edges.items():
        if len(ss) < 2:
            continue
        a, b = tuple(e)
        L = seg(a, b)
        for s in ss:
            for o in ss:
                if s != o:
                    shared[s][o] += L
    out = []
    for sid, d in shapes.items():
        role = d["role"]
        if role not in _GROUNDSIDE_ROLES:
            continue
        area = sum(ring_area(r) for r in d["rings"])
        per = 0.0
        for r in d["rings"]:
            per += sum(seg(r[i], r[(i + 1) % len(r)]) for i in range(len(r)))
        air = svc = bld = 0.0
        nb = []
        for o, L in shared[sid].items():
            orole = shapes[o]["role"]
            if orole in AIRSIDE_PAVEMENT:
                air += L
            elif orole in ("service_road", "service_junction"):
                svc += L
            elif orole == "building":
                bld += L
            nb.append((o, orole, shapes[o]["ref"], round(L, 1)))
        out.append(dict(shapeID=sid, ref=d["ref"], role=role, cls=d["cls"],
                        area_m2=area, perim_m=per, airside_pav_m=air,
                        service_m=svc, building_m=bld,
                        radius_m=(area / per if per else 0.0),
                        neighbours=sorted(nb, key=lambda t: -t[3])[:6]))
    out.sort(key=lambda o: -o["airside_pav_m"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patches", nargs="+", type=Path)
    ap.add_argument("--min-m", type=float, default=10.0)
    ap.add_argument("--min-radius", type=float, default=1.0)
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    dump = {}
    for p in a.patches:
        rows = census(p)
        dump[str(p)] = rows
        over = [r for r in rows if r["airside_pav_m"] >= a.min_m]
        sub = [r for r in over if r["radius_m"] >= a.min_radius]
        sliv = [r for r in over if r["radius_m"] < a.min_radius]
        lots = [r for r in sub if (r["cls"] or r["role"]) == "parking_lot"]
        print(f"=== {p.name}: groundside shapes {len(rows)}, "
              f"sharing >= {a.min_m:g} m with airside pavement {len(over)} "
              f"({sum(r['area_m2'] for r in over):,.0f} m2)")
        print(f"    SUBSTANTIVE (area/perimeter >= {a.min_radius:g} m): "
              f"{len(sub)} shapes, {sum(r['area_m2'] for r in sub):,.0f} m2"
              f"   [slivers excluded: {len(sliv)}]")
        print(f"    of them LOT-class (§27's population): {len(lots)} shapes, "
              f"{sum(r['area_m2'] for r in lots):,.0f} m2")
        if a.detail:
            print(f"    {'shape':>8} {'ref':<14} {'role':<20} {'class':<12} "
                  f"{'area':>10} {'perim':>8} {'r':>6} {'airside':>8} {'svc':>7}")
            for r in sub:
                print(f"    {r['shapeID']:>8} {str(r['ref']):<14} {r['role']:<20} "
                      f"{str(r['cls']):<12} {r['area_m2']:>10,.0f} "
                      f"{r['perim_m']:>8,.0f} {r['radius_m']:>6.1f} "
                      f"{r['airside_pav_m']:>8.1f} {r['service_m']:>7.1f}")
    if a.json:
        a.json.write_text(json.dumps(dump, indent=1))
        print(f"[json] {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
