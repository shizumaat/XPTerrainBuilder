"""AIRSIDE NEAREST-PAIR TABLE — the reading the AIRSIDE NO-STEP law
(RULINGS 2026-08-27) is stated in.

THE QUESTION.  "Is there a STEP here?" is not a question about one pair
of adjacent vertices — that is what every pointwise family already asks,
and the round-3 dip site passed all of them while carrying +1.07 m of
relief across 50-75 m.  It is a question about a NEIGHBOURHOOD: over a
local window, how far apart in z do two airside points get, against their
DIRECT distance?  This tool answers exactly that, per named site, per
arm, at several pair distances.

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  Geometry and altitudes are
read through the harness library's own ``check_grade._parse_osm``; the
cap printed beside each row is ``grade_law.TAXI_MAX_GRADE``, imported for
reading only; defect counts come from ``tools/harness/census.py`` and
nowhere else — a private re-count is the census-wrapper defect.  Quote it
ARM TO ARM on identical options, never as a verdict.

CONTIGUOUS PAVEMENT ONLY (spec ``airside-no-step-law-spec.md``
Amendment 1 ruling 2).  A chord that leaves the airside pavement union
crosses a GAP, and RULINGS 2026-08-24b is explicit that a step is lawful
exactly there.  The default therefore reports only pairs whose chord
stays inside the union of the patch's own airside ways;
``--allow-gap-chords`` restores the unfiltered read (the framing the
spec's own §0 used, and which Amendment 1 corrected).

TWO POPULATIONS, named rather than assumed.  ANCHORED = the
centerline-valued surfaces (the taxiway family and the round-3 apron
spine stations) — the "T pieces" the owner saw standing proud.
MEMBRANE = the apron surface and its interior lattice.  Both role sets
are IMPORTED from the engine (``airside_no_step.taxiway_family_roles``,
``layout.ROLE_*``), never re-spelled here.

    venv/bin/python tools/airside_pair_table.py A.osm [B.osm ...] \\
        --site dip=30.1290177,31.4055841 [--radius 200] [--dists 30,50,75]
        [--allow-gap-chords] [--json OUT.json]

Twin: ``tests/test_airside_pair_table.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as cg                                   # noqa: E402
from auto_patch.grade_law import TAXI_MAX_GRADE            # noqa: E402

#: The role-less FEATURE classes each population owns, as
#: ``layout.to_osm`` spells them (blast role-literal hazard: these are
#: emitted ``o4_feature`` values, and ``check_grade`` carries the same
#: two in ``_NO_STEP_POLYLINE_FEATURES``).
ANCHOR_FEATURES = ("apron_spine_station",)
MEMBRANE_FEATURES = ("apron_lattice",)


def anchor_roles():
    """The centerline-valued surfaces: the taxiway family plus the
    runway family.  Imported from the engine, never re-spelled."""
    from auto_patch.airside_no_step import taxiway_family_roles
    from auto_patch.layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING
    return frozenset(taxiway_family_roles()) | {ROLE_RUNWAY,
                                                ROLE_RUNWAY_CROSSING}


def membrane_roles():
    from auto_patch.layout import ROLE_APRON
    return frozenset({ROLE_APRON})


def _airside_union(nodes, ways, ll_to_m):
    """PREPARED union of the patch's own airside pavement, or ``None``.

    Built from the emitted rings of ``enclaves.ENCLAVE_AIRSIDE_ROLES`` —
    the same register the solve enumerates its airside nodes from, so
    this reader and the law scope the same pavement.
    """
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        from shapely.prepared import prep
        from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES
    except Exception:                                     # pragma: no cover
        return None
    polys = []
    for w in ways:
        if w.role not in ENCLAVE_AIRSIDE_ROLES:
            continue
        pts = [ll_to_m(*nodes[n]) for n in w.nids if n in nodes]
        if len(pts) < 4:
            continue
        try:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                polys.append(p)
        except Exception:                                 # pragma: no cover
            continue
    if not polys:
        return None
    try:
        u = unary_union(polys)
        return None if u.is_empty else prep(u)
    except Exception:                                     # pragma: no cover
        return None


def _points(nodes, ways, feats, roles, features, ll_to_m):
    """``{node_id: (x, y, z, way_id, role)}`` for one population."""
    out = {}
    pool = list(ways)
    for cls in features:
        pool += list(feats.get(cls, []))
    want_features = {id(w) for cls in features for w in feats.get(cls, [])}
    for w in pool:
        if id(w) not in want_features and w.role not in roles:
            continue
        for k, nid in enumerate(w.nids):
            if nid not in nodes:
                continue
            a = w.elevs[k] if k < len(w.elevs) else None
            if a is None:
                continue
            x, y = ll_to_m(*nodes[nid])
            out[nid] = (x, y, float(a), w.wid, w.role or "")
    return out


def _table(anchored, membrane, site_xy, site_r, dists, union=None):
    ax, ay = site_xy
    anc = [v for v in anchored.values()
           if math.hypot(v[0] - ax, v[1] - ay) <= site_r]
    mem = [v for v in membrane.values()
           if math.hypot(v[0] - ax, v[1] - ay) <= site_r + max(dists)]
    line = None
    if union is not None:
        from shapely.geometry import LineString as _LS
        line = _LS
    rows = []
    for d_max in dists:
        worst = None
        n_pairs = n_over = n_gap = 0
        for (x, y, z, wid, role) in anc:
            for (mx, my, mz, mwid, mrole) in mem:
                d = math.hypot(mx - x, my - y)
                if d < 1e-6 or d > d_max:
                    continue
                if union is not None and not union.covers(
                        line(((x, y), (mx, my)))):
                    n_gap += 1
                    continue        # a chord across a pavement GAP
                n_pairs += 1
                dz = abs(mz - z)
                if dz > TAXI_MAX_GRADE * d:
                    n_over += 1
                if worst is None or dz > worst[0]:
                    worst = (dz, d, wid, mwid, z, mz)
        rows.append({"dist_max_m": d_max, "pairs": n_pairs,
                     "over_cap": n_over, "gap_chords_skipped": n_gap,
                     "worst": None if worst is None else {
                         "de_m": round(worst[0], 3),
                         "distance_m": round(worst[1], 1),
                         "grade_pct": round(100.0 * worst[0] / worst[1], 2),
                         "anchor_way": worst[2], "membrane_way": worst[3],
                         "anchor_alt": worst[4], "membrane_alt": worst[5]}})
    return len(anc), len(mem), rows


def read(patch, sites, radius=200.0, dists=(30.0, 50.0, 75.0),
         allow_gap_chords=False):
    """The library entry.  ``sites`` is ``[(name, lat, lon), ...]``."""
    feats = {}
    nodes, ways = cg._parse_osm(Path(patch), feature_out=feats)
    ll_to_m = cg._ll_to_m_factory(nodes)
    anchored = _points(nodes, ways, feats, anchor_roles(), ANCHOR_FEATURES,
                       ll_to_m)
    membrane = _points(nodes, ways, feats, membrane_roles(),
                       MEMBRANE_FEATURES, ll_to_m)
    union = None if allow_gap_chords else _airside_union(nodes, ways,
                                                         ll_to_m)
    out = {"patch": str(patch), "cap_pct": 100.0 * TAXI_MAX_GRADE,
           "contiguous_pavement_only": union is not None,
           "anchored_nodes": len(anchored), "membrane_nodes": len(membrane),
           "sites": []}
    for (name, lat, lon) in sites:
        sx, sy = ll_to_m(lat, lon)
        n_a, n_m, rows = _table(anchored, membrane, (sx, sy), radius,
                                list(dists), union=union)
        out["sites"].append({"site": name, "lat": lat, "lon": lon,
                             "radius_m": radius, "anchored_in_reach": n_a,
                             "membrane_in_reach": n_m, "rows": rows})
    return out


def _print(res):
    print(f"\n=== {Path(res['patch']).name} ===")
    print(f"  anchored nodes {res['anchored_nodes']}  membrane nodes "
          f"{res['membrane_nodes']}  cap read at {res['cap_pct']:.2f}%  "
          + ("CONTIGUOUS PAVEMENT ONLY"
             if res["contiguous_pavement_only"]
             else "gap chords INCLUDED (--allow-gap-chords)"))
    for s in res["sites"]:
        print(f"  site {s['site']} @{s['lat']},{s['lon']} "
              f"r={s['radius_m']:g} m: {s['anchored_in_reach']} anchored / "
              f"{s['membrane_in_reach']} membrane in reach")
        for r in s["rows"]:
            if r["worst"] is None:
                print(f"    <={r['dist_max_m']:g} m: no pair"
                      + (f" ({r['gap_chords_skipped']} gap chord(s) skipped)"
                         if r["gap_chords_skipped"] else ""))
                continue
            w = r["worst"]
            print(f"    <={r['dist_max_m']:g} m: {r['pairs']:6d} pair(s), "
                  f"{r['over_cap']:5d} over cap x direct; worst |dz|="
                  f"{w['de_m']:.3f} m at {w['distance_m']:.1f} m = "
                  f"{w['grade_pct']:.2f}%  ({w['anchor_way']} "
                  f"{w['anchor_alt']:.2f} -> {w['membrane_way']} "
                  f"{w['membrane_alt']:.2f})"
                  + (f"  [{r['gap_chords_skipped']} gap chord(s) skipped]"
                     if r["gap_chords_skipped"] else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Airside nearest-pair table per named site, arm to "
                    "arm.  A MEASUREMENT: it prices no law and counts no "
                    "defects.")
    ap.add_argument("patches", nargs="+", help="emitted patch .osm")
    ap.add_argument("--site", action="append", required=True,
                    metavar="NAME=LAT,LON", help="repeatable")
    ap.add_argument("--radius", type=float, default=200.0)
    ap.add_argument("--dists", default="30,50,75")
    ap.add_argument("--allow-gap-chords", action="store_true",
                    help="include chords that leave the airside pavement "
                         "union (Amendment 1 ruling 2 excludes them)")
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args(argv)
    dists = [float(t) for t in a.dists.split(",") if t.strip()]
    if not dists:
        ap.error("--dists needs at least one distance")
    sites = []
    for spec in a.site:
        if "=" not in spec or "," not in spec:
            ap.error(f"--site wants NAME=LAT,LON, got {spec!r}")
        name, coord = spec.split("=", 1)
        lat, lon = (float(t) for t in coord.split(","))
        sites.append((name, lat, lon))
    results = []
    for p in a.patches:
        res = read(p, sites, radius=a.radius, dists=dists,
                   allow_gap_chords=a.allow_gap_chords)
        results.append(res)
        _print(res)
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
