#!/usr/bin/env python3
"""ARM SITE READ — the same named sites, read across two arms.

    venv/bin/python tools/arm_site_read.py CTL.osm ARM.osm \\
        [--site NAME=LAT,LON ...] [--radius M] \\
        [--rows CTL.rows.json ARM.rows.json] [--seats] [--json OUT]

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

__all__ = ["rows_near", "seat_moves", "load_rows", "SiteReadRefusal"]

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
