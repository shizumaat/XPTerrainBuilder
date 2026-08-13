#!/usr/bin/env python3
"""ARM SITE READ — the same named sites, read across two arms.

    venv/bin/python tools/arm_site_read.py CTL.osm ARM.osm \\
        [--site NAME=LAT,LON ...] [--radius M] \\
        [--rows CTL.rows.json ARM.rows.json] [--seats] [--welds] [--json OUT]

Run it from ``Ortho4XP/``.

THE QUESTION an A/B leaves open.  `harness/census.py --rows-json` itemises a
patch's law-true rows and `census_rows_diff.py` joins two dumps class by
class — but neither can be asked about a PLACE, and a round's acceptance is
written in places ("the wall at 35.2077303,-80.9290869", "the ramp corridor's
three coordinates").  `osm_site.py` answers what geometry is at a coordinate;
it does not carry law rows or pad seats.  This tool is the join: per named
site, per arm, the law-true rows within a radius and their worst grade — and,
with ``--seats``, the BUILDING PAD seats that moved between the two arms,
which is the channel this repo's HECA airside attribution ran through (a pad
seat welds into the apron ring, so a seat that moves moves airside).

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  Rows are read verbatim out of
`census.py --rows-json` dumps — the census remains the only instrument that
produces defect counts (the census-wrapper precedent, RULINGS `7e90032`) —
and geometry/altitudes are read through the harness library's own parser
(`check_grade._parse_osm`), so this tool and the census read one file the
same way.  A missing input is reported as SKIPPED, never as zero.

``--welds`` answers the OTHER acceptance question a place can be asked —
IS THIS SEAM JOINED?  (corridor-joins round, spec ruling 4(a): "count of
shared node refs between road-family and airside ways per mouth, with the
max |Δalt| across each seam".)  Row absence cannot answer it: a census row
exists only BETWEEN PAIRED GEOMETRY, so an UNWELDED road↔taxiway seam is
SILENT in every census — which is exactly how two acceptance claims passed
on a 0.999 m gap that no node could bridge.  Per site, per arm, this reports
the node ids shared between the two families, the worst altitude difference
carried at a shared node, the nearest unwelded approach when there are none,
and the retaining walls standing at the site.

THE FRAMES, both stated on the report:
* rows are located by the census's own row lat/lon, which for a within-shape
  pair is the PAIR's position — a long chord's row can therefore sit far from
  either endpoint's geometry (measured: 400 m+ apron chords at HECA), so a
  site radius selects rows NEAR THE PAIR, not rows whose shape touches the
  site;
* seats join by the building's ``ref`` tag across the two arms — way ids and
  shapeIDs are arm-dependent and are never joined on.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

__all__ = ["rows_near", "seat_moves", "seam_welds", "load_rows",
           "SiteReadRefusal", "ROAD_FAMILY_ROLES", "AIRSIDE_SEAM_ROLES"]

#: The two families a corridor MOUTH joins.  Road side: the census's own
#: ``check_grade._ROAD_FAMILY_ROLES``, read from it at call time (never a
#: second literal).  Airside: every role the census treats as airside that a
#: road can physically meet — the aircraft movement area.
ROAD_FAMILY_ROLES = ("service_road", "service_junction")
AIRSIDE_SEAM_ROLES = ("apron", "junction", "primary_parallel",
                      "secondary_parallel", "stub", "cross_connector",
                      "runway", "runway_crossing")

_ROOT = Path(__file__).resolve().parents[1]
_M_PER_DEG = 111320.0


class SiteReadRefusal(RuntimeError):
    """A question this tool will not answer with a guess."""


def _check_grade():
    sys.path.insert(0, str(_ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "arm_site_read_check_grade", _ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _dist_m(lat_a, lon_a, lat_b, lon_b) -> float:
    return math.hypot((lat_a - lat_b) * _M_PER_DEG,
                      (lon_a - lon_b) * _M_PER_DEG
                      * math.cos(math.radians(lat_a)))


def load_rows(path) -> list:
    """A census ``--rows-json`` dump's row list, verbatim."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SiteReadRefusal(f"cannot read rows dump {path}: {exc}") from exc
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SiteReadRefusal(
            f"{path} is not a census --rows-json dump (no 'rows' key)")
    return rows


def rows_near(rows, lat, lon, radius_m: float) -> dict:
    """Law-true rows within ``radius_m`` of a site, and their worst grade."""
    hits = []
    for r in rows:
        rlat, rlon = r.get("lat"), r.get("lon")
        if rlat is None or rlon is None:
            continue
        d = _dist_m(rlat, rlon, lat, lon)
        if d <= radius_m:
            hits.append((round(d, 1), r))
    hits.sort(key=lambda t: t[0])
    return {
        "n_rows": len(hits),
        "worst_grade_pct": max((h[1].get("grade_pct") or 0.0 for h in hits),
                               default=0.0),
        "worst_magnitude_m": max((h[1].get("magnitude_m") or 0.0
                                  for h in hits), default=0.0),
        "families": sorted({f'{h[1]["family"]}::{h[1]["roles"]}'
                            for h in hits}),
        "worst": [{"d_m": d, "family": r["family"], "roles": r["roles"],
                   "magnitude_m": r["magnitude_m"],
                   "grade_pct": r["grade_pct"], "way_a": r.get("way_a")}
                  for (d, r) in sorted(
                      hits, key=lambda t: -(t[1].get("magnitude_m") or 0))[:3]],
    }


def _seats(cg, patch) -> dict:
    """``{building ref: flat seat}`` read verbatim from the patch."""
    nodes, ways = cg._parse_osm(Path(patch))
    out = {}
    for w in ways:
        if w.role != "building" or not w.ref:
            continue
        alts = [a for a in (w.elevs or []) if a is not None]
        if not alts:
            tag = (w.tags or {}).get("altitude")
            if tag:
                alts = [float(tag)]
        if alts:
            pts = [nodes[n] for n in w.nids if n in nodes]
            out[w.ref] = (min(alts),
                          sum(p[0] for p in pts) / len(pts) if pts else None,
                          sum(p[1] for p in pts) / len(pts) if pts else None)
    return out


def seat_moves(cg, ctl_patch, arm_patch, *, floor_m: float = 0.01) -> dict:
    """Building pad seats that moved between the two arms, joined by ``ref``."""
    ctl, arm = _seats(cg, ctl_patch), _seats(cg, arm_patch)
    common = sorted(set(ctl) & set(arm))
    moved = [{"ref": r, "ctl_m": ctl[r][0], "arm_m": arm[r][0],
              "delta_m": round(arm[r][0] - ctl[r][0], 3),
              "lat": arm[r][1], "lon": arm[r][2]}
             for r in common if abs(arm[r][0] - ctl[r][0]) > floor_m]
    moved.sort(key=lambda d: -abs(d["delta_m"]))
    mags = sorted(abs(m["delta_m"]) for m in moved)
    return {
        "pads_joined": len(common),
        "pads_moved": len(moved),
        "floor_m": floor_m,
        "median_abs_delta_m": (mags[len(mags) // 2] if mags else 0.0),
        "max_abs_delta_m": (mags[-1] if mags else 0.0),
        "worst": moved[:10],
    }


#: Two shared nodes belong to the same MOUTH when they lie within this of
#: each other — one corridor width (``config.SERVICE_ROAD_WIDTH_M`` = 6 m)
#: with margin, i.e. "the same crossing", not "the same airport".  A
#: reporting choice, printed with every table: two runs at two windows are
#: two populations.
MOUTH_CLUSTER_M = 12.0


def seam_welds(cg, patch, lat=None, lon=None, radius_m=None) -> dict:
    """The SEAM-WELD table at one site: is the road↔airside seam JOINED?

    Reads the patch through the harness library's own parser, so this tool
    and the census read one file one way.  Reported, all within
    ``radius_m`` of the site:

    * ``shared_nodes`` — node ids carried by BOTH a road-family way and an
      airside way.  A shared node IS the weld: one node, one position, and
      (with per-way altitudes) one value per way at it.
    * ``max_seam_dalt_m`` — the worst altitude difference two ways carry at
      a SHARED node.  0.00 is the construction the ruling demands (the
      solver grades one node); anything else is a torn weld.
    * ``nearest_unwelded_m`` — when nothing is shared, the closest approach
      between the two families' nodes.  This is the number that says
      "unweldable" (0.999 m at the KCLT sites, against a 0.5 m weld
      tolerance) where a census reports silence.
    * ``walls`` — ``retaining_wall`` ways at the site, with their refs: the
      "wall gone both sides" half of the same acceptance claim.
    * ``mouths`` — the shared nodes clustered at ``MOUTH_CLUSTER_M``, so
      "≥2 shared nodes PER MOUTH" is answerable rather than a patch total.

    ``lat``/``lon``/``radius_m`` omitted ⇒ the WHOLE PATCH (the reading for
    an airport with no owner-named site).

    Pure read: no law, no defect counts (those are the census's alone).
    """
    nodes, ways = cg._parse_osm(Path(patch))
    road_roles = set(getattr(cg, "_ROAD_FAMILY_ROLES", ROAD_FAMILY_ROLES))
    air_roles = set(AIRSIDE_SEAM_ROLES)
    whole = lat is None or lon is None or radius_m is None

    def _near(w):
        if whole:
            return True
        for nid in w.nids:
            p = nodes.get(nid)
            if p is not None and _dist_m(p[0], p[1], lat, lon) <= radius_m:
                return True
        return False

    road_ways = [w for w in ways if w.role in road_roles and _near(w)]
    air_ways = [w for w in ways if w.role in air_roles and _near(w)]
    walls = [w for w in ways if w.role == "retaining_wall" and _near(w)]

    def _alts(group):
        out: dict = {}
        for w in group:
            for nid, a in zip(w.nids, (w.elevs or [])):
                if a is not None:
                    out.setdefault(nid, []).append((w.wid, float(a)))
        return out

    road_alt, air_alt = _alts(road_ways), _alts(air_ways)
    road_nids = {nid for w in road_ways for nid in w.nids}
    air_nids = {nid for w in air_ways for nid in w.nids}
    shared = sorted(nid for nid in (road_nids & air_nids)
                    if nid in nodes
                    and (whole or _dist_m(nodes[nid][0], nodes[nid][1],
                                          lat, lon) <= radius_m))
    worst = 0.0
    worst_nid = None
    for nid in shared:
        vals = [v for (_w, v) in road_alt.get(nid, [])
                + air_alt.get(nid, [])]
        if len(vals) >= 2 and (max(vals) - min(vals)) > worst:
            worst, worst_nid = max(vals) - min(vals), nid
    nearest = None
    if not shared and road_nids and air_nids:
        nearest = min(
            (_dist_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
             for a in road_nids if a in nodes
             for b in air_nids if b in nodes),
            default=None)
    # MOUTH CLUSTERS: shared nodes within ``MOUTH_CLUSTER_M`` of one another
    # are one crossing (single-link, the same connected-components rule the
    # census's site clustering uses, at this tool's own stated window).
    pts = [(nid, nodes[nid][0], nodes[nid][1]) for nid in shared]
    parent = {nid: nid for (nid, _la, _lo) in pts}

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, (na, la, lo) in enumerate(pts):
        for (nb, lb, ob) in pts[i + 1:]:
            if _dist_m(la, lo, lb, ob) <= MOUTH_CLUSTER_M:
                ra, rb = _find(na), _find(nb)
                if ra != rb:
                    parent[rb] = ra
    groups: dict = {}
    for (nid, la, lo) in pts:
        groups.setdefault(_find(nid), []).append((la, lo))
    mouths = sorted(
        ({"lat": round(sum(p[0] for p in g) / len(g), 7),
          "lon": round(sum(p[1] for p in g) / len(g), 7),
          "shared_nodes": len(g)} for g in groups.values()),
        key=lambda d: -d["shared_nodes"])
    return {
        "road_ways": len(road_ways), "airside_ways": len(air_ways),
        "shared_nodes": len(shared),
        "shared_nids": shared[:20],
        "mouths": len(mouths),
        "mouths_ge2_nodes": sum(1 for m in mouths if m["shared_nodes"] >= 2),
        "mouth_cluster_m": MOUTH_CLUSTER_M,
        "mouth_list": mouths[:12],
        "max_seam_dalt_m": round(worst, 4),
        "max_seam_dalt_nid": worst_nid,
        "nearest_unwelded_m": (round(nearest, 4)
                               if nearest is not None else None),
        "walls": len(walls),
        "wall_refs": sorted({w.ref for w in walls if w.ref})[:8],
        "wall_wids": sorted(w.wid for w in walls)[:8],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("control", help="control arm patch .osm")
    ap.add_argument("arm", help="the arm under test, patch .osm")
    ap.add_argument("--site", action="append", default=[],
                    metavar="NAME=LAT,LON")
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--rows", nargs=2, metavar=("CTL.rows.json",
                                                "ARM.rows.json"))
    ap.add_argument("--seats", action="store_true")
    ap.add_argument("--welds", action="store_true",
                    help="per site, the road↔airside seam-weld table "
                         "(shared nodes, max seam |Δalt|, walls)")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)

    sites = {}
    try:
        for spec in args.site:
            name, coord = spec.split("=", 1)
            lat, lon = (float(v) for v in coord.split(","))
            sites[name] = (lat, lon)
    except ValueError:
        print("REFUSED: --site wants NAME=LAT,LON", file=sys.stderr)
        return 2

    out: dict = {"control": args.control, "arm": args.arm,
                 "radius_m": args.radius}
    print(f"=== arm site read\n  control {args.control}\n  arm     {args.arm}")
    print(f"  frame: rows are located by the CENSUS's own row lat/lon (a "
          f"within-shape pair's position, which for a long chord is far from "
          f"either endpoint); seats join by building ref, never by way id")
    if args.rows:
        try:
            ctl_rows, arm_rows = (load_rows(args.rows[0]),
                                  load_rows(args.rows[1]))
        except SiteReadRefusal as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        out["sites"] = {}
        for name, (lat, lon) in sites.items():
            c = rows_near(ctl_rows, lat, lon, args.radius)
            a = rows_near(arm_rows, lat, lon, args.radius)
            out["sites"][name] = {"control": c, "arm": a}
            print(f"  {name:24s} rows {c['n_rows']:4d} → {a['n_rows']:4d}   "
                  f"worst grade {c['worst_grade_pct']:7.2f}% → "
                  f"{a['worst_grade_pct']:7.2f}%   worst |de| "
                  f"{c['worst_magnitude_m']:6.2f} → "
                  f"{a['worst_magnitude_m']:6.2f} m")
    elif sites:
        print("  SKIPPED site rows: no --rows dumps given (a census "
              "--rows-json dump per arm is this read's only row source)")
    if args.welds:
        cg = _check_grade()
        out["welds"] = {}
        scope = (sites if sites
                 else {"WHOLE PATCH": (None, None)})
        print(f"  SEAM WELDS (road family {'/'.join(ROAD_FAMILY_ROLES)} ↔ "
              f"airside; a shared NODE is the weld, row absence is not "
              f"evidence; mouth cluster {MOUTH_CLUSTER_M:g} m"
              + (f", r={args.radius:g} m" if sites else ", whole patch")
              + ")")
        for name, (lat, lon) in scope.items():
            rad = args.radius if sites else None
            c = seam_welds(cg, args.control, lat, lon, rad)
            a = seam_welds(cg, args.arm, lat, lon, rad)
            out["welds"][name] = {"control": c, "arm": a}
            for label, r in (("ctl", c), ("arm", a)):
                gap = ("—" if r["nearest_unwelded_m"] is None
                       else f"{r['nearest_unwelded_m']:.3f} m")
                print(f"    {name:22s} {label}  shared "
                      f"{r['shared_nodes']:4d}  mouths {r['mouths']:3d} "
                      f"({r['mouths_ge2_nodes']} with ≥2)  max seam |Δalt| "
                      f"{r['max_seam_dalt_m']:6.3f} m  nearest unwelded "
                      f"{gap:>9s}  walls {r['walls']:3d}")
    if args.seats:
        cg = _check_grade()
        out["seats"] = seat_moves(cg, args.control, args.arm)
        s = out["seats"]
        print(f"  PAD SEATS: {s['pads_moved']} of {s['pads_joined']} moved "
              f"> {s['floor_m']} m; median |Δ| {s['median_abs_delta_m']:.2f} m,"
              f" max {s['max_abs_delta_m']:.2f} m")
        for m in s["worst"][:5]:
            print(f"      {m['ref']:16s} {m['ctl_m']:8.2f} → {m['arm_m']:8.2f}"
                  f"  Δ{m['delta_m']:+.2f} m")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"  -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
