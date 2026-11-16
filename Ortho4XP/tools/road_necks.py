#!/usr/bin/env python3
"""ROAD NECKS, CONTROL AGAINST ARM (#1918 R4; promoted from the rv1918r4
review's ``necks_ab.py`` + ``necks_cls.py`` on their second use).

A NECK ROW of a patch: a road ring vertex (``service_road`` /
``service_junction``) facing a chord of its OWN ring with no vertex
opposite — the foot at least ``END_M`` inside the chord, ``MIN_M`` to
``LATERAL_M`` across, the midpoint inside the ring — and its level
difference to the chord's level at the foot.  Each CONTROL row is re-read
on the ARM's patch: the arm's level of the same vertex (canonical lat/lon
join) against the arm's kerb level at the same foot (the nearest road way
segment within ``FOOT_M``).

    venv/bin/python tools/road_necks.py CONTROL.osm ARM.osm --pad-roads SOLVED.pkl [--json OUT]

Prints, for the PAD ROADS (``PlanarMap.pad_roads`` of any pickle carrying
``pm``, e.g. a ``v2_solve_replay --solved-out``) and the OTHER ROADS: rows
over 0.2 / 0.5 m before and after, how many changed, how many grew; then
the pad-road rows by CLASS (who else carries the vertex and the facing
chord on the control patch: ``free`` = pad roads only, ``standing(...)``
= the other roles there).  Measures no law; the census is the law read.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

#: road roles a neck row is read on
ROLES = frozenset({"service_road", "service_junction"})
#: metres across: the widest neck (``[road_contact] pair_lateral_m``)
LATERAL_M = 6.0
#: metres: the narrowest neck, and the shortest chord read (x 2)
MIN_M = 0.5
#: metres: a foot this near a chord end is the end's, not the chord's
END_M = 1.0
#: metres: the arm's kerb segment searched around the control foot
FOOT_M = 0.6
#: the two bars counted
BARS = (0.2, 0.5)


def load(path: Path, origin: tuple[float, float] | None = None):
    """``({nid: (x, y, z, lat, lon)}, ways, origin)`` of a patch in a local
    metric frame about ``origin`` (default: the patch's own mean — no
    airport constant; read an ARM in its CONTROL's origin)."""
    from check_grade import _parse_osm
    ll, ways = _parse_osm(Path(path))
    lat0, lon0 = origin or (sum(v[0] for v in ll.values()) / max(len(ll), 1),
                            sum(v[1] for v in ll.values()) / max(len(ll), 1))
    k = 111120.0 * math.cos(math.radians(lat0))
    z: dict = {}
    for w in ways:
        for n, e in zip(w.nids, w.elevs, strict=True):
            if e is not None:
                z[n] = float(e)
    nodes = {n: ((lo - lon0) * k, (la - lat0) * 111120.0, z.get(n), la, lo)
             for n, (la, lo) in ll.items()}
    return nodes, ways, (lat0, lon0)


def neck_rows(nodes, ways) -> list[dict]:
    """The control's neck rows (module doc), the worst chord per vertex."""
    from shapely.geometry import Point, Polygon
    rows = []
    for w in ways:
        if w.role not in ROLES or w.nids[0] != w.nids[-1] or len(w.nids) < 4:
            continue
        ids = w.nids[:-1]
        pts = [nodes[r] for r in ids]
        if any(p[2] is None for p in pts):
            continue
        poly = Polygon([(p[0], p[1]) for p in pts])
        if not poly.is_valid:
            continue
        n = len(pts)
        for i, (x, y, z, la, lo) in enumerate(pts):
            best = None
            for j in range(n):
                k = (j + 1) % n
                if i in (j, k):
                    continue
                (ax, ay, az), (bx, by, bz) = pts[j][:3], pts[k][:3]
                L = math.hypot(bx - ax, by - ay)
                if L < 2 * MIN_M:
                    continue
                t = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L / L
                if t * L < END_M or (1 - t) * L < END_M:
                    continue
                fx, fy = ax + t * (bx - ax), ay + t * (by - ay)
                d = math.hypot(x - fx, y - fy)
                if not MIN_M <= d <= LATERAL_M or \
                        not poly.contains(Point((x + fx) / 2, (y + fy) / 2)):
                    continue
                dz = z - (az + t * (bz - az))
                if best is None or abs(dz) > abs(best["dz"]):
                    best = {"dz": dz, "d": d, "lat": la, "lon": lo, "ref": str(w.ref),
                            "role": w.role, "v": ids[i], "foot": (fx, fy),
                            "chord": frozenset((ids[j], ids[k]))}
            if best:
                rows.append(best)
    return rows


def reread(rows, nodes1, ways1) -> list[dict]:
    """Each control row with ``after``: the arm's vertex level minus the
    arm's kerb level at the same foot (rows the arm cannot read dropped)."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    at1 = {(round(v[3], 9), round(v[4], 9)): v[2] for v in nodes1.values()}
    segs, segz = [], []
    for w in ways1:
        if w.role not in ROLES:
            continue
        for a, b in zip(w.nids, w.nids[1:], strict=False):
            pa, pb = nodes1[a], nodes1[b]
            if pa[2] is None or pb[2] is None or pa[:2] == pb[:2]:
                continue
            segs.append(LineString([pa[:2], pb[:2]]))
            segz.append((pa[2], pb[2]))
    tree = STRtree(segs)
    out = []
    for r in rows:
        z1 = at1.get((round(r["lat"], 9), round(r["lon"], 9)))
        if z1 is None:
            continue
        P = Point(*r["foot"])
        k = tree.query_nearest(P, max_distance=FOOT_M)
        if len(k) == 0:
            continue
        s = segs[int(k[0])]
        t = s.project(P) / s.length
        za, zb = segz[int(k[0])]
        out.append({**r, "after": z1 - (za + t * (zb - za))})
    return out


def carriers(ways0) -> tuple[dict, dict]:
    """``({edge: {(role, ref)}}, {node: {(role, ref)}})`` of a patch."""
    eo, no = collections.defaultdict(set), collections.defaultdict(set)
    for w in ways0:
        lab = (w.role, str(w.ref))
        for a, b in zip(w.nids, w.nids[1:], strict=False):
            eo[frozenset((a, b))].add(lab)
        for a in w.nids:
            no[a].add(lab)
    return eo, no


def neck_class(r, eo, no, pad_roads) -> str:
    """``v KIND | chord KIND`` of a pad-road row (:func:`carriers`)."""
    me = (r["role"], r["ref"])

    def kind(labs):
        ks = {("padroad" if ref in pad_roads else "road") if role in ROLES else str(role)
              for role, ref in labs} - {"padroad"}
        return "standing(" + "+".join(sorted(ks)) + ")" if ks else "free"
    return f"v {kind(no[r['v']] - {me})} | chord {kind(eo[r['chord']] - {me})}"


def summary(read, pad_roads) -> dict:
    """``{group: counts}`` for PAD ROADS / OTHER ROADS (module doc)."""
    out = {}
    for name, sel in (("pad_roads", lambda r: r["ref"] in pad_roads),
                      ("other_roads", lambda r: r["ref"] not in pad_roads)):
        rr = [r for r in read if sel(r)]
        c = {"rows": len(rr), "changed_0.05": sum(abs(r["after"] - r["dz"]) > 0.05 for r in rr),
             "worse_0.05": sum(abs(r["after"]) > abs(r["dz"]) + 0.05 for r in rr),
             "worse_0.1": sum(abs(r["after"]) > abs(r["dz"]) + 0.1 for r in rr)}
        for b in BARS:
            c[f"control>{b}"] = sum(abs(r["dz"]) > b for r in rr)
            c[f"arm>{b}"] = sum(abs(r["after"]) > b for r in rr)
        c["worst_worse"] = [
            {"lat": round(r["lat"], 7), "lon": round(r["lon"], 7), "ref": r["ref"],
             "control": round(r["dz"], 3), "arm": round(r["after"], 3)}
            for r in sorted(rr, key=lambda r: abs(r["dz"]) - abs(r["after"]))[:6]
            if abs(r["after"]) > abs(r["dz"]) + 0.05]
        out[name] = c
    return out


def classes(read, ways0, pad_roads) -> dict:
    """``{class: [n, >0.2 ctl, >0.2 arm, >0.5 ctl, >0.5 arm]}`` of pad-road rows."""
    cnt: dict = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    eo, no = carriers(ways0)
    for r in read:
        if r["ref"] not in pad_roads:
            continue
        c = cnt[neck_class(r, eo, no, pad_roads)]
        c[0] += 1
        c[1] += abs(r["dz"]) > 0.2
        c[2] += abs(r["after"]) > 0.2
        c[3] += abs(r["dz"]) > 0.5
        c[4] += abs(r["after"]) > 0.5
    return dict(cnt)


def pad_roads_of(pkl: Path) -> set[str]:
    with open(pkl, "rb") as fh:
        rec = pickle.load(fh)
    return {str(r) for r in (getattr(rec["pm"], "pad_roads", None) or ())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("control", type=Path)
    ap.add_argument("arm", type=Path)
    ap.add_argument("--pad-roads", type=Path, required=True,
                    help="a pickle carrying pm (PlanarMap.pad_roads)")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    pads = pad_roads_of(a.pad_roads)
    n0, w0, origin = load(a.control)
    n1, w1, _o = load(a.arm, origin)
    read = reread(neck_rows(n0, w0), n1, w1)
    summ, cls = summary(read, pads), classes(read, w0, pads)
    for name, c in summ.items():
        print(f"{name}: rows {c['rows']} | >0.2 {c['control>0.2']} -> {c['arm>0.2']} | "
              f">0.5 {c['control>0.5']} -> {c['arm>0.5']} | changed {c['changed_0.05']} "
              f"worse>0.05 {c['worse_0.05']} worse>0.1 {c['worse_0.1']}")
        for w in c["worst_worse"]:
            print(f"    WORSE {w['control']:+.2f} -> {w['arm']:+.2f} "
                  f"at {w['lat']},{w['lon']} {w['ref']}")
    print("pad-road class (vertex | chord)                n | >0.2 ctl->arm | >0.5 ctl->arm")
    for c, r in sorted(cls.items(), key=lambda kv: -kv[1][3]):
        print(f"  {c:44s} {r[0]:5d} | {r[1]:4d} -> {r[2]:4d} | {r[3]:4d} -> {r[4]:4d}")
    if a.json:
        a.json.write_text(json.dumps({"summary": summ, "classes": cls}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
