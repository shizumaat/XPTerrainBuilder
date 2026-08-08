"""FRONTAGE-CLASS SPLIT — which building pad does a defect row belong to,
and is that pad FRONTING an apron or DETACHED.

PROMOTED 2026-08-08 (fabricA, THE FABRIC MODEL Phase A) from the frontweld
lane scratchpad ``tmp/frontweld/frontage_split.py`` on its SECOND use —
promote-on-reuse, RULINGS ``7e90032``.  Its first use produced the
frontage-weld round's Job-1 table (RULINGS 2026-08-08 "Frontage weld:
measured ALREADY-TRUE": 79 fronting pads at HECA, the 1,373-row fronting
class); its second is this round's acceptance read of that same class on
the sparse arm.  The lane copy's own note asked for the axis to land as a
``census.py`` flag instead; that is a bigger change to the harness's core
instrument than this round's charter carries, so it lands here as a tool
and the census-flag question is left to Phase B.  ONE copy exists — do not
re-fork the lane file.

Why it is not already the census (tools/INDEX.md consulted first): the
census reports every law family, the side split, the magnitude bands, the
row itemisation and the site clustering.  The ONE axis it does not carry
is pad membership and the fronting/detached verdict.

It DERIVES NO LAW and RE-IMPLEMENTS NO CHECK.  Every row comes from
``check_grade.run_checks_law_true`` (THE harness library), the side from
``check_grade.row_side``, the magnitude from ``check_grade.row_magnitude``,
the excess from ``check_grade.row_excess_m``, the adjudication split from
``check_grade.adjudication``, the site clustering from
``census.cluster_sites`` and the weld tolerance from
``check_grade.LAW_TRUE_KNOBS['proximity_m']``.  A private re-count is the
census-wrapper defect.

THE TWO PREDICATES, stated so the split can be audited:

* FRONTING (the production predicate, replicated in the EMITTED frame):
  ``route_profile.anchors.build_building_seats`` calls a building edge a
  FRONTAGE edge when BOTH its endpoints are ring vertices of a SOFT
  pavement shape — role ``apron`` / ``junction`` / ``service_junction``
  (its ``apron_keys`` set, which is deliberately not apron-only: under the
  global slice the face a building fronts is usually a junction).  Here the
  same test runs on emitted node IDENTITY (``to_osm`` writes one node per
  welded vertex, so a shared ring vertex is the SAME nid — no proximity
  join, memory ``canonical-identity-join``).  Reported alongside two
  sensitivity variants: TOUCH (>=1 shared node) and NEAR (any ring vertex
  within the near-miss frontage reach of soft pavement).
* THE CLASS: a law-true row belongs to building B when either endpoint is a
  ring vertex of B, at the census's OWN canonical-node tolerance
  (``LAW_TRUE_KNOBS['proximity_m']`` = 0.5 m, the solver weld radius) —
  the same predicate ``census --sites`` uses to decide two rows are one
  node.  A row touching both a fronting and a detached pad is reported in
  its own BOTH column, never double-counted.

    venv/bin/python tools/frontage_split.py PATCH.osm [PATCH.osm ...]
        [--json OUT.json] [--seats CTL ARM]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "src", ROOT / "tools" / "harness"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_grade as cg          # noqa: E402
import census as H                # noqa: E402

#: The soft-pavement roles ``build_building_seats`` builds ``apron_keys``
#: from.  IMPORTED, never re-typed: the role literals are law input.
from auto_patch.layout import (        # noqa: E402
    ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION)

SOFT_ROLES = frozenset({ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION})
BUILDING_ROLE = "building"


def _grid_key(x, y, cell):
    return (int(math.floor(x / cell)), int(math.floor(y / cell)))


def _chord_bucket(row):
    """The retrospective's chord-length split, re-read on the row's own
    endpoints (the CHORD the law priced, in layout-local metres)."""
    a, b = H.row_points(row)
    if a is None or b is None:
        return "?"
    d = math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
    return "<10m" if d < 10 else ("10-50m" if d < 50 else ">=50m")


def classify_buildings(ways, nodes, ll_to_m, near_m):
    """``(fronting, detached, variants)`` — sets of building way ids.

    FRONTING = has a ring EDGE both of whose endpoints are soft-pavement
    ring vertices (the production ``_frontage_box`` predicate).
    """
    soft_nids = set()
    soft_pts = []
    for w in ways:
        if w.role in SOFT_ROLES:
            soft_nids.update(w.nids)
            for nid in w.nids:
                if nid in nodes:
                    soft_pts.append(ll_to_m(*nodes[nid]))
    cell = max(near_m, 1.0)
    grid = defaultdict(list)
    for (x, y) in soft_pts:
        grid[_grid_key(x, y, cell)].append((x, y))

    fronting, touch, near = set(), set(), set()
    buildings = [w for w in ways if w.role == BUILDING_ROLE]
    for w in buildings:
        ns = w.nids
        if any(n in soft_nids for n in ns):
            touch.add(w.wid)
        for i in range(len(ns) - 1):
            if ns[i] in soft_nids and ns[i + 1] in soft_nids:
                fronting.add(w.wid)
                break
        if w.wid not in fronting:
            hit = False
            for nid in ns:
                if nid not in nodes:
                    continue
                x, y = ll_to_m(*nodes[nid])
                gx, gy = _grid_key(x, y, cell)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for (sx, sy) in grid.get((gx + dx, gy + dy), ()):
                            if math.hypot(sx - x, sy - y) <= near_m:
                                hit = True
                                break
                        if hit:
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                near.add(w.wid)
    detached = {w.wid for w in buildings} - fronting
    return fronting, detached, {"touch": touch, "near_only": near,
                                "n_buildings": len(buildings)}


def build_pad_index(ways, nodes, ll_to_m, fronting, tol):
    """``(grid, cell)`` — a lookup from a point to the building wids whose
    ring carries a vertex within ``tol``."""
    cell = max(tol, 0.5)
    grid = defaultdict(list)
    for w in ways:
        if w.role != BUILDING_ROLE:
            continue
        for nid in w.nids:
            if nid not in nodes:
                continue
            x, y = ll_to_m(*nodes[nid])
            grid[_grid_key(x, y, cell)].append((x, y, w.wid))
    return grid, cell


def pads_at(pt, grid, cell, tol):
    if pt is None:
        return set()
    x, y = float(pt[0]), float(pt[1])
    gx, gy = _grid_key(x, y, cell)
    out = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for (px, py, wid) in grid.get((gx + dx, gy + dy), ()):
                if math.hypot(px - x, py - y) <= tol:
                    out.add(wid)
    return out


def analyse(patch: Path) -> dict:
    fam: dict = {}
    ctx = cg.law_context_from_sidecar(patch)
    cg.run_checks_law_true(patch, family_out=fam, quiet=True, top_n=0)
    keys = [k for k in fam if not str(k).startswith("_")]

    # The census's own step exemption, from the law register (never a copy).
    rows_by_family = {}
    for key, _title, _bucket in cg.LAW_FAMILIES:
        rows = fam.get(key, [])
        if key in cg.STEP_EXEMPT_FAMILIES:
            rows = [s for s in rows if not cg.step_exempt(s)]
        rows_by_family[key] = rows
    all_rows = [(k, r) for k, rs in rows_by_family.items() for r in rs]
    all_rows.sort(key=lambda kr: -cg.row_magnitude(kr[1]))

    nodes, ways = cg._parse_osm(patch)
    ll_to_m = cg._ll_to_m_factory(nodes, anchor=ctx.get("anchor"))
    tol = float(cg.LAW_TRUE_KNOBS["proximity_m"])
    # The near-miss frontage REACH, from the law's own constant (never a
    # literal here): auto_patch.config.BUILDING_FRONTAGE_NEAR_MISS_M, the
    # same one ``check_grade._check_frontage_near_miss`` judges with.
    near_m = float(cg._BUILDING_FRONTAGE_NEAR_MISS_M)

    fronting, detached, variants = classify_buildings(
        ways, nodes, ll_to_m, near_m)
    grid, cell = build_pad_index(ways, nodes, ll_to_m, fronting, tol)

    adj_all = cg.adjudication(all_rows)

    def _is_adjudicated(key, row):
        return (key not in cg.VERSION_DEFERRED_FAMILIES
                and not getattr(row, "out_of_scope", None))

    buckets = {"fronting": [], "detached": [], "both": [], "none": []}
    per_class_ways = {"fronting": set(), "detached": set()}
    for key, row in all_rows:
        a, b = H.row_points(row)
        pads = pads_at(a, grid, cell, tol) | pads_at(b, grid, cell, tol)
        if not pads:
            buckets["none"].append((key, row))
            continue
        f = pads & fronting
        d = pads & detached
        per_class_ways["fronting"] |= f
        per_class_ways["detached"] |= d
        if f and d:
            buckets["both"].append((key, row))
        elif f:
            buckets["fronting"].append((key, row))
        else:
            buckets["detached"].append((key, row))

    def _summary(rows):
        adj = [(k, r) for (k, r) in rows if _is_adjudicated(k, r)]
        sides = Counter(cg.row_side(r) for _k, r in adj)
        fams = Counter(k for k, _r in rows)
        worst = max((cg.row_magnitude(r) for _k, r in rows), default=0.0)
        excess = 0.0
        for k, r in adj:
            try:
                excess += float(cg.row_excess_m(r, k) or 0.0)
            except Exception:
                pass
        sites = H.cluster_sites(rows, cg) if rows else None
        return {
            "rows": len(rows),
            "adjudicated": len(adj),
            "adj_airside": sides.get("airside", 0) + sides.get("mixed", 0),
            "adj_groundside": sides.get("groundside", 0),
            "worst_m": round(worst, 3),
            "excess_m": round(excess, 3),
            "sites": (sites["sites"] if sites else 0),
            "actionable_sites": (sites["sites_actionable"] if sites else 0),
            "families": dict(fams.most_common(8)),
            "role_pairs": dict(Counter(
                "|".join(cg.row_roles(r)) for _k, r in rows).most_common(8)),
            "chord_len_split": dict(Counter(
                _chord_bucket(r) for _k, r in rows).most_common()),
        }

    out = {
        "patch": str(patch),
        "law_true_rows": len(all_rows),
        "adjudicated_total": adj_all["adjudicated_total"],
        "adjudicated_airside": (adj_all["adjudicated_by_side"].get("airside", 0)
                                + adj_all["adjudicated_by_side"].get("mixed", 0)),
        "buildings": {
            "total": variants["n_buildings"],
            "fronting": len(fronting),
            "detached": len(detached),
            "touch_only_no_edge": len(variants["touch"] - fronting),
            "near_but_not_touching": len(variants["near_only"]),
            "near_m": near_m,
        },
        "class": {k: _summary(v) for k, v in buckets.items() if k != "none"},
        "ways_carrying_rows": {k: len(v) for k, v in per_class_ways.items()},
        "rows_touching_no_pad": len(buckets["none"]),
        "proximity_m": tol,
    }
    return out


def seat_read(patch: Path) -> dict:
    """``{pad_identity: record}`` — every building pad's EMITTED level and
    the WELDED value at its face, on one patch.

    ``pad_identity`` is the pad's own FOOTPRINT — the sorted tuple of its
    11-decimal ring coordinates — which is DEM-independent and identical
    across two arms of the same tree, so two arms join EXACTLY (never by
    proximity, memory ``canonical-identity-join``).  ``weld_m`` is the
    median solved altitude carried by the pad's FRONTAGE nodes as the
    SOFT-PAVEMENT ways see them: the same nid, read off the apron /
    junction way rather than off the pad, which is what makes
    "seat == welded value" a check and not a tautology.
    """
    nodes, ways = cg._parse_osm(patch)
    alt: dict = {}
    soft_alt: dict = {}
    for w in ways:
        n_open = len(w.nids) - 1 if (len(w.nids) > 1
                                     and w.nids[0] == w.nids[-1]) \
            else len(w.nids)
        for idx in range(n_open):
            v = w.elevs[idx] if idx < len(w.elevs) else None
            if v is None:
                continue
            if w.role in SOFT_ROLES:
                soft_alt.setdefault(w.nids[idx], []).append(float(v))
            alt.setdefault(w.nids[idx], []).append(float(v))
    soft_nids = set(soft_alt)
    out: dict = {}
    for w in ways:
        if w.role != BUILDING_ROLE:
            continue
        ring = w.nids[:-1] if (len(w.nids) > 1
                               and w.nids[0] == w.nids[-1]) else w.nids
        key = tuple(sorted(f"{nodes[n][0]:.11f},{nodes[n][1]:.11f}"
                           for n in ring if n in nodes))
        vals = [float(v) for v in w.elevs if v is not None]
        face = [soft_alt[n] for n in ring if n in soft_nids]
        face_vals = sorted(v for grp in face for v in grp)
        med = None
        if face_vals:
            m = len(face_vals)
            med = (face_vals[m // 2] if m % 2
                   else 0.5 * (face_vals[m // 2 - 1] + face_vals[m // 2]))
        fronting = any(
            ring[i] in soft_nids and ring[(i + 1) % len(ring)] in soft_nids
            for i in range(len(ring))) if ring else False
        out[key] = {
            "wid": w.wid, "ref": w.ref,
            "level_m": (round(sum(vals) / len(vals), 3) if vals else None),
            "spread_m": (round(max(vals) - min(vals), 3) if vals else None),
            "weld_m": (None if med is None else round(med, 3)),
            "face_nodes": len(face),
            "fronting": fronting,
        }
    return out


def print_seats(a: Path, b: Path) -> None:
    ra, rb = seat_read(a), seat_read(b)
    common = [k for k in ra if k in rb]
    print(f"\n=== SEAT READ  {a.name} -> {b.name}   "
          f"({len(common)} pad(s) joined by footprint identity; "
          f"{len(ra) - len(common)} only in A, {len(rb) - len(common)} "
          f"only in B)")
    rows = []
    for k in common:
        x, y = ra[k], rb[k]
        if x["level_m"] is None or y["level_m"] is None:
            continue
        rows.append((y["level_m"] - x["level_m"], x, y))
    rows.sort(key=lambda r: -abs(r[0]))
    print(f"  {'ref':<16}{'front':>6}{'A level':>10}{'B level':>10}"
          f"{'move':>9}{'A |seat-weld|':>15}{'B |seat-weld|':>15}"
          f"{'B flat?':>9}")
    for (d, x, y) in rows[:24]:
        ga = ("-" if x["weld_m"] is None
              else f"{abs(x['level_m'] - x['weld_m']):.3f}")
        gb = ("-" if y["weld_m"] is None
              else f"{abs(y['level_m'] - y['weld_m']):.3f}")
        print(f"  {str(y['ref'])[:15]:<16}{('Y' if y['fronting'] else 'n'):>6}"
              f"{x['level_m']:>10.3f}{y['level_m']:>10.3f}{d:>+9.3f}"
              f"{ga:>15}{gb:>15}{y['spread_m']:>9.3f}")
    fr = [(x, y) for (_d, x, y) in rows if y["fronting"]]
    for label, sel, idx in (("A", fr, 0), ("B", fr, 1)):
        gaps = [abs(p[idx]["level_m"] - p[idx]["weld_m"])
                for p in sel if p[idx]["weld_m"] is not None]
        if gaps:
            print(f"  FRONTING |seat - welded face| in {label}: "
                  f"n={len(gaps)} max={max(gaps):.4f} m "
                  f"mean={sum(gaps) / len(gaps):.4f} m")
    moved = [d for (d, _x, y) in rows if y["fronting"]]
    if moved:
        print(f"  fronting pads moved: "
              f"{sum(1 for d in moved if abs(d) > 0.01)} of {len(moved)} "
              f"(>0.01 m), worst {max(moved, key=abs):+.3f} m")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patches", nargs="+")
    ap.add_argument("--json", default=None)
    ap.add_argument("--seats", action="store_true",
                    help="A/B the pads' emitted levels against the welded "
                         "value at their face (needs exactly 2 patches)")
    args = ap.parse_args(argv)
    if args.seats:
        if len(args.patches) != 2:
            ap.error("--seats needs exactly two patches (control, arm)")
        print_seats(Path(args.patches[0]), Path(args.patches[1]))
        return 0

    reports = []
    for p in args.patches:
        rep = analyse(Path(p))
        reports.append(rep)
        b = rep["buildings"]
        print(f"\n=== {rep['patch']}")
        print(f"  law-true {rep['law_true_rows']}  adjudicated "
              f"{rep['adjudicated_total']}  (airside "
              f"{rep['adjudicated_airside']})")
        print(f"  buildings {b['total']}: FRONTING {b['fronting']} / "
              f"DETACHED {b['detached']}  "
              f"(touch-no-edge {b['touch_only_no_edge']}, "
              f"near<= {b['near_m']:.1f} m not touching "
              f"{b['near_but_not_touching']})")
        print(f"  {'class':<10} {'rows':>6} {'adj':>6} {'adjAIR':>7} "
              f"{'sites':>6} {'act':>5} {'worst_m':>8} {'excess_m':>9}  ways")
        for k in ("fronting", "detached", "both"):
            s = rep["class"][k]
            print(f"  {k:<10} {s['rows']:>6} {s['adjudicated']:>6} "
                  f"{s['adj_airside']:>7} {s['sites']:>6} "
                  f"{s['actionable_sites']:>5} {s['worst_m']:>8.3f} "
                  f"{s['excess_m']:>9.3f}  "
                  f"{rep['ways_carrying_rows'].get(k, '-')}")
            print(f"             families:  {s['families']}")
            print(f"             role pairs:{s['role_pairs']}")
            print(f"             chords:    {s['chord_len_split']}")
        print(f"  rows touching NO pad: {rep['rows_touching_no_pad']}")
    if args.json:
        Path(args.json).write_text(json.dumps(reports, indent=1))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
