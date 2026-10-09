"""surfspec probe — #333 MECHANISM TEST, DRY: does clipping EVERY draped
page to its part OFF apt.dat pavement at the one evidence gate
(``classify/evidence._dsf_pavements``) undo the SPJC junction re-kind, and
what does it move elsewhere?  Both arms re-run the CLASSIFY stage on this
tree over the captured ``Airport`` (``v2_solve_replay.reclassify``'s trick):

    CONTROL  today's gate (a page < 80 % on apt.dat joins the union WHOLE)
    ARM      the gate's overlay branch applied to every page that overlies
             apt.dat at all: only the parts off apt.dat (>= remainder_min_m2)
             are sources, under the remainder spelling ``dsf:pol<N>#<k>``

    venv/bin/python docs/briefs/surfspec/aptclip_probe.py ICAO=CAP.pkl [...]
        [--site LAT,LON ...]

Reports: cells / role-area delta; ground whose ROLE changed, in full and
restricted to apt.dat pavement; the cells under each site in both arms.
A scratch monkeypatch — nothing in the engine is edited.
"""
from __future__ import annotations

import argparse
import collections
import pickle
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Ortho4XP"
sys.path.insert(0, str(ROOT / "src"))

from shapely.geometry import Point, Polygon        # noqa: E402
from shapely.ops import unary_union                # noqa: E402
from shapely.strtree import STRtree                # noqa: E402


def _poly(outer, holes=()):
    try:
        p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def _arm_gate(evidence_mod):
    """``_dsf_pavements`` with the overlay branch for every overlapping page."""
    polygon_parts = evidence_mod.polygon_parts

    def gate(raw, apt_union, boundary, rules):
        dp = rules.dsf_pavement
        g = boundary.buffer(dp.boundary_buffer_m) if boundary is not None else None
        out, dropped = [], 0
        for pid, poly in raw:
            if g is not None:
                parts = polygon_parts(poly.intersection(g))
                if not parts:
                    dropped += 1
                    continue
                poly = max(parts, key=lambda q: q.area)
            if poly.area < dp.min_area_m2:
                dropped += 1
                continue
            if not apt_union.is_empty and poly.intersection(apt_union).area > 1.0:
                dropped += 1
                for k, q in enumerate(polygon_parts(poly.difference(apt_union))):
                    if q.area >= dp.remainder_min_m2:
                        out.append((f"{pid}#{k}", q))
                continue
            out.append((pid, poly))
        return out, dropped
    return gate


def run(icao, pkl, sites):
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.classify import evidence as E
    from auto_patch_v2.law import Law
    with open(pkl, "rb") as fh:
        cap = pickle.load(fh)
    a = cap["airport"]
    law, rules = Law.for_airport(icao), load_rules()
    to_xy, _ = a.frame.transformers()
    apt = unary_union([q for q in (_poly(p.outer, p.holes) for p in a.pavements
                                   if not p.id.startswith("dsf:")) if q is not None])
    orig = E._dsf_pavements
    t = time.perf_counter()
    ctl = classify(a, law, rules)
    E._dsf_pavements = _arm_gate(E)
    try:
        arm = classify(a, law, rules)
    finally:
        E._dsf_pavements = orig
    print(f"\n== {icao}: cells {len(ctl.cells)} -> {len(arm.cells)} ({time.perf_counter() - t:.0f} s both arms)")
    ca = [(c, _poly(c.ring, c.holes)) for c in ctl.cells]
    cb = [(c, _poly(c.ring, c.holes)) for c in arm.cells]
    ca = [(c, q) for c, q in ca if q is not None]
    cb = [(c, q) for c, q in cb if q is not None]
    ra, rb = collections.Counter(), collections.Counter()
    for cs, r in ((ca, ra), (cb, rb)):
        for c, q in cs:
            r[f"{c.role}/{c.side}"] += q.area
    delta = {k: round(rb[k] - ra[k]) for k in set(ra) | set(rb) if abs(rb[k] - ra[k]) > 0.5}
    print("   role area delta m2:", dict(sorted(delta.items(), key=lambda kv: -abs(kv[1]))) or "none")
    tree = STRtree([q for _c, q in cb])
    T, TA = collections.Counter(), collections.Counter()
    ex = collections.defaultdict(list)
    for c, q in ca:
        if c.role == "building":
            continue
        for j in tree.query(q):
            d, h = cb[int(j)]
            if d.role == c.role or d.role == "building":
                continue
            x = q.intersection(h)
            if x.area <= 1.0:
                continue
            k = (c.role, d.role)
            T[k] += x.area
            ex[k].append((str(c.ref), str(d.ref), round(x.area)))
            on = x.intersection(apt).area if not apt.is_empty else 0.0
            if on > 1.0:
                TA[k] += on
    print(f"   ROLE CHANGES, all ground: {sum(T.values()):,.0f} m2 in {len(T)} kinds")
    for k, v in T.most_common(8):
        print(f"     {v:9,.0f} m2 {k[0]:22s} -> {k[1]:22s} e.g. {sorted(ex[k], key=lambda t: -t[2])[:2]}")
    print(f"   ROLE CHANGES on apt.dat pavement: {sum(TA.values()):,.0f} m2")
    for k, v in TA.most_common(6):
        print(f"     {v:9,.0f} m2 {k[0]:22s} -> {k[1]:22s}")
    for lat, lon in sites:
        pt = Point(to_xy(lon, lat))
        ha = [(str(c.ref), c.role, round(q.area)) for c, q in ca if q.contains(pt)]
        hb = [(str(c.ref), c.role, round(q.area)) for c, q in cb if q.contains(pt)]
        print(f"   site {lat}, {lon}: control {ha}  arm {hb}")
    # the remainder cells the arm minted, by role
    rem = collections.Counter()
    for c, q in cb:
        if "#" in str(c.ref) and str(c.ref).startswith("dsf:pol"):
            rem[c.role] += q.area
    print("   arm remainder-ref cells by role m2:", {k: round(v) for k, v in rem.most_common()})


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+")
    ap.add_argument("--site", action="append", default=[])
    args = ap.parse_args()
    sites = [tuple(float(x) for x in s.split(",")) for s in args.site]
    for pair in args.pairs:
        icao, pkl = pair.split("=", 1)
        run(icao, pkl, sites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
