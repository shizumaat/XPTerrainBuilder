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
        [--pad-frontage [--near M] [--min-step M]]

`--min-m` is §27's `[lot] airside_edge_min_m`; `--min-radius` its sliver
floor (area / perimeter, an emit artefact).  Several files are reported
separately — that is the arm-vs-arm read a before/after starts from.

`--pad-frontage` is the SECOND question, on the same geometry and the
same joins: THE STEP a building PAD's neighbours stand at — *pad ->
neighbour -> shared edge m -> step m* — which is what owner RULINGS
2026-09-11ai-1 -> 2026-09-12r ("grade frontages only", spec §28) is
accepted on.  Again no other instrument answers it: the harness census
FORGIVES a declared terrace across a shape joint (`terrace_joints_ll`),
so a car park standing 3 m above the terminal it fronts reports ZERO
rows — and at LEMD the +3.03 m the owner read is not even a declared
joint (the patch carries 4, none of them `building4`'s).  Steps are read
across the NODE-IDENTITY join where the two shapes share nodes and, where
they do not, across the nearest facing vertex within `--near` (default
2.0 m): the pad-frontage relation is a PROXIMITY relation in the engine
too (`[design] pad_frontage_m` 3.0, owner RULINGS 2026-09-10ax (1)), and
`building4` / `pav124` share not one node while standing 0.71-1.50 m
apart.  `--min-step` (default 0.05 m) is the floor a neighbour is listed
at.  It prices no law and counts no defects.
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


#: The GROUNDSIDE roles §28 (1) names, in the emitted patch's own
#: vocabulary: `check_grade._GROUNDSIDE_ROLES` is the law's partition and
#: `parking_lot` reaches the patch as a `class` tag beside an
#: `oracle_role` of `groundside_pavement` (`precedence.toml`), so a lot is
#: already inside that set and the class tag is what NAMES it.
GROUNDSIDE_FRONTAGE_ROLES = tuple(sorted(_GROUNDSIDE_ROLES - {"tunnel_ramp"}))


def pad_frontage(path: Path, near: float = 2.0, min_step: float = 0.05):
    """PAD -> NEIGHBOUR -> SHARED EDGE m -> STEP m (module docstring).

    One row per (pad shape, neighbour shape) whose max |step| reaches
    ``min_step``: the neighbour's role and class, the metres of edge the
    two SHARE by node identity, the number of facing vertex pairs within
    ``near``, and the largest and mean signed step (neighbour minus pad,
    so a car park standing above its terminal reads POSITIVE).  Sorted by
    pad area, then by |step|."""
    import numpy as np
    from scipy.spatial import cKDTree

    shapes, xy = _shapes(path)
    nodes, ways = _parse_osm(path)
    zof: dict[str, float] = {}
    for w in ways:
        for n, e in zip(w.nids, w.elevs):
            if e is not None:
                zof[n] = float(e)

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
        for s_ in ss:
            for o in ss:
                if s_ != o:
                    shared[s_][o] += L

    allv = sorted({n for d in shapes.values() for r in d["rings"] for n in r})
    tree = cKDTree(np.array([xy(n) for n in allv]))
    of_shape: dict[str, set[str]] = defaultdict(set)
    for sid, d in shapes.items():
        for r in d["rings"]:
            for n in r:
                of_shape[n].add(sid)

    out = []
    for sid, d in shapes.items():
        if d["role"] != "building":
            continue
        area = sum(ring_area(r) for r in d["rings"])
        pv = sorted({n for r in d["rings"] for n in r})
        nb: dict[str, list[float]] = defaultdict(list)
        for n in pv:
            if n not in zof:
                continue
            for k in tree.query_ball_point(xy(n), near):
                o = allv[k]
                if o not in zof:
                    continue
                for osid in of_shape[o]:
                    if osid == sid:
                        continue
                    if shapes[osid]["role"] not in GROUNDSIDE_FRONTAGE_ROLES:
                        continue
                    nb[osid].append(zof[o] - zof[n])
        rows = []
        for osid, steps in nb.items():
            worst = max(steps, key=abs)
            if abs(worst) < min_step:
                continue
            rows.append(dict(shapeID=osid, ref=shapes[osid]["ref"],
                             role=shapes[osid]["role"], cls=shapes[osid]["cls"],
                             shared_edge_m=round(shared[sid].get(osid, 0.0), 1),
                             pairs=len(steps), step_m=round(worst, 2),
                             mean_step_m=round(sum(steps) / len(steps), 2)))
        if rows:
            rows.sort(key=lambda r: -abs(r["step_m"]))
            out.append(dict(shapeID=sid, ref=d["ref"], area_m2=area,
                            neighbours=rows))
    out.sort(key=lambda r: -r["area_m2"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patches", nargs="+", type=Path)
    ap.add_argument("--min-m", type=float, default=10.0)
    ap.add_argument("--min-radius", type=float, default=1.0)
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--pad-frontage", action="store_true",
                    help="the §28 read: pad -> neighbour -> shared edge m -> step m")
    ap.add_argument("--near", type=float, default=2.0,
                    help="facing-vertex horizon for the step read (m)")
    ap.add_argument("--min-step", type=float, default=0.05,
                    help="a neighbour is listed at this step or worse (m)")
    a = ap.parse_args(argv)
    dump = {}
    if a.pad_frontage:
        for p in a.patches:
            rows = pad_frontage(p, near=a.near, min_step=a.min_step)
            dump[str(p)] = rows
            worst = [abs(n["step_m"]) for r in rows for n in r["neighbours"]]
            print(f"=== {p.name}: PAD FRONTAGE — pads with a groundside step "
                  f">= {a.min_step:g} m: {len(rows)}; "
                  f"neighbour rows {len(worst)}; "
                  f"worst {max(worst) if worst else 0.0:.2f} m")
            for r in rows:
                print(f"  pad {r['shapeID']:>6} {str(r['ref']):<14} "
                      f"{r['area_m2']:>10,.0f} m2")
                for n in r["neighbours"]:
                    print(f"      -> {n['shapeID']:>6} {str(n['ref']):<12} "
                          f"{n['role']:<20} {str(n['cls']):<18} "
                          f"edge={n['shared_edge_m']:>7.1f} m "
                          f"pairs={n['pairs']:>4} "
                          f"step={n['step_m']:+.2f} mean={n['mean_step_m']:+.2f}")
        if a.json:
            a.json.write_text(json.dumps(dump, indent=1))
            print(f"[json] {a.json}")
        return 0
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
