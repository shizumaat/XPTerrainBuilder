#!/usr/bin/env python3
"""WHAT THE OBJECT STAGE MADE OF THIS COORDINATE.

You have a lat/lon from an owner's sim read and the question is what the
build put there — not what the OSM patch says (that is ``osm_site.py``),
and not one law's defect count (that is ``harness/census.py``).  Three
products of ONE build, read at ONE point, in one process:

* the emitted DESIGN SURFACE's faces covering or near it — role, ref,
  side, z range and median (``<ICAO>.graded.json``);
* the DSF ROWS standing on it — ``OBJECT`` / ``OBJECT_MSL`` with the
  resource and, for an MSL row, its written elevation (a DSFTool TEXT
  dump; pass the PRISTINE one, ``<dsf>.anchor_bak…text``, when you want
  the pack as installed rather than as this repo last wrote it);
* the PLAN BODIES whose plan box reaches it — body id, §6 class, its
  footprint unit, its surface z and zero, and the ANCHOR REASON in the
  stage's own words.

**It measures nothing and derives no law.**  Every value is read verbatim
out of a product; the distances are plan distances in a local metric
frame.  Nothing is written.

    venv/bin/python tools/site_read.py LAT LON [R_M] --patch-dir DIR
        [--graded PATH] [--plan PATH] [--dsf-dump PATH]
        [--show faces,dsf,bodies] [--max N]

``--patch-dir`` resolves ``<ICAO>.graded.json`` and
``o4_v2_placement_<ICAO>.json`` (or ``<ICAO>.rebake.json``'s sibling
``o4_v2_placement_*``) by glob, so a build's own output directory is the
only argument most reads need; any of the three can be pointed at
explicitly instead.

Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the
scratchpad reader written for the 14g HECA attribution and re-written for
the 14bl LEMD one (scouts `v2heca331`, `v2lemd336o`) and used a third time
by lane `v2leafframe` — three copies of one question, already drifted in
their hard-coded paths.  Twin: ``tests/auto_patch_v2/test_v2leafframe.py``.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import typing as _t

#: metres per degree of latitude (the plan frame's own constant)
M_PER_DEG_LAT = 110540.0


def m_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def point_in_ring(lat: float, lon: float,
                  ring: _t.Sequence[tuple[float, float]]) -> bool:
    """Even-odd, on ``(lat, lon)`` pairs."""
    inside = False
    n = len(ring)
    for i in range(n):
        la1, lo1 = ring[i]
        la2, lo2 = ring[(i + 1) % n]
        if (la1 > lat) != (la2 > lat):
            if lon < (lo2 - lo1) * (lat - la1) / (la2 - la1) + lo1:
                inside = not inside
    return inside


def _box_distance_m(lat: float, lon: float, box, mlon: float) -> float:
    dla = max(box[0] - lat, lat - box[2], 0.0) * M_PER_DEG_LAT
    dlo = max(box[1] - lon, lon - box[3], 0.0) * mlon
    return math.hypot(dla, dlo)


def graded_faces_near(graded: dict, lat: float, lon: float, radius_m: float
                      ) -> list[dict]:
    """Every face of the design surface containing the point or within
    ``radius_m`` of one of its ring vertices, nearest first (a containing
    face reads distance 0)."""
    mlon = m_per_deg_lon(lat)
    verts = {v[0]: (v[1], v[2], v[3]) for v in graded["vertices"]}
    out = []
    for f in graded["faces"]:
        pts = [verts[i] for i in f["ring"] if i in verts]
        if len(pts) < 3:
            continue
        ring = [(p[0], p[1]) for p in pts]
        d = min(math.hypot((p[0] - lat) * M_PER_DEG_LAT, (p[1] - lon) * mlon)
                for p in pts)
        inside = point_in_ring(lat, lon, ring)
        if not inside and d > radius_m:
            continue
        zs = sorted(p[2] for p in pts)
        out.append({"id": f["id"], "role": f["role"], "ref": f.get("ref"),
                    "side": f.get("side"), "inside": inside,
                    "distance_m": 0.0 if inside else d,
                    "z_min": zs[0], "z_max": zs[-1], "z_med": zs[len(zs) // 2],
                    "nodes": len(pts)})
    out.sort(key=lambda r: r["distance_m"])
    return out


def dsf_rows_near(dump_path: str, lat: float, lon: float, radius_m: float
                  ) -> list[dict]:
    """``OBJECT`` / ``OBJECT_MSL`` / ``OBJECT_AGL`` rows of a DSFTool TEXT
    dump within ``radius_m``, nearest first.  Read verbatim: the row's
    own resource (its ``OBJECT_DEF``) and, where it has one, the written
    elevation."""
    mlon = m_per_deg_lon(lat)
    defs: list[str] = []
    out = []
    with open(dump_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("OBJECT_DEF "):
                defs.append(line[11:].strip())
                continue
            if not line.startswith("OBJECT"):
                continue
            tok = line.split()
            kind = tok[0]
            if kind == "OBJECT" and len(tok) >= 5:
                di, rlon, rlat, elev = int(tok[1]), float(tok[2]), float(tok[3]), None
            elif kind in ("OBJECT_MSL", "OBJECT_AGL") and len(tok) >= 6:
                di, rlon, rlat = int(tok[1]), float(tok[2]), float(tok[3])
                elev = float(tok[4])
            else:
                continue
            d = math.hypot((rlat - lat) * M_PER_DEG_LAT, (rlon - lon) * mlon)
            if d > radius_m:
                continue
            out.append({"kind": kind, "distance_m": d, "lat": rlat,
                        "lon": rlon, "elevation": elev,
                        "resource": defs[di] if di < len(defs) else f"def{di}"})
    out.sort(key=lambda r: r["distance_m"])
    return out


def plan_bodies_near(plan: dict, lat: float, lon: float, radius_m: float
                     ) -> list[dict]:
    """Every split body whose PLAN BOX reaches within ``radius_m``,
    nearest first, with its unit, class, zero and anchor reason."""
    mlon = m_per_deg_lon(lat)
    out = []
    for sp in plan.get("splits", ()):
        for b in sp.get("bodies", ()):
            box = b.get("plan_box")
            if not box:
                continue
            d = _box_distance_m(lat, lon, box, mlon)
            if d > radius_m:
                continue
            out.append({"distance_m": d,
                        "resource": sp["placement"]["resource"],
                        "body_id": b.get("body_id"), "class": b.get("class"),
                        "unit_of": b.get("unit_of"),
                        "surface_z": b.get("surface_z"),
                        "y_zero": b.get("y_zero"),
                        "anchor_reason": b.get("anchor_reason")})
    out.sort(key=lambda r: r["distance_m"])
    return out


def _resolve(patch_dir: str, pattern: str, explicit: str) -> str:
    if explicit:
        return explicit
    if not patch_dir:
        return ""
    hits = sorted(glob.glob(os.path.join(patch_dir, pattern)))
    return hits[0] if hits else ""


def main(argv: _t.Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("radius_m", type=float, nargs="?", default=40.0)
    ap.add_argument("--patch-dir", default="", help="a build's output dir; "
                    "<ICAO>.graded.json and o4_v2_placement_<ICAO>.json are "
                    "resolved inside it")
    ap.add_argument("--graded", default="")
    ap.add_argument("--plan", default="", help="o4_v2_placement_<ICAO>.json or "
                    "an obj8_split_report --json dump (both carry `splits`)")
    ap.add_argument("--dsf-dump", default="", help="a DSFTool TEXT dump; pass "
                    "the PRISTINE <dsf>.anchor_bak...text for the pack as "
                    "installed")
    ap.add_argument("--show", default="faces,dsf,bodies")
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--json", default="", help="write what was printed here")
    a = ap.parse_args(argv)

    show = {s.strip() for s in a.show.split(",") if s.strip()}
    graded_p = _resolve(a.patch_dir, "*.graded.json", a.graded)
    plan_p = _resolve(a.patch_dir, "o4_v2_placement_*.json", a.plan)
    doc: dict = {"lat": a.lat, "lon": a.lon, "radius_m": a.radius_m}

    if "faces" in show and graded_p:
        faces = graded_faces_near(json.load(open(graded_p)), a.lat, a.lon,
                                  a.radius_m)
        doc["faces"] = faces
        print(f"== graded faces containing / within {a.radius_m:.0f} m "
              f"({os.path.basename(graded_p)})")
        for r in faces[:a.max]:
            print(f"  shape {r['id']:<6d} {r['role']:<20s} "
                  f"{str(r['ref'])[:26]:<26s} side={str(r['side']):<10s} "
                  f"inside={str(r['inside']):<5s} d={r['distance_m']:6.1f} m  "
                  f"z {r['z_min']:.2f}..{r['z_max']:.2f} "
                  f"(med {r['z_med']:.2f}) n={r['nodes']}")
        print(f"  faces: {len(faces)}")

    if "dsf" in show and a.dsf_dump:
        rows = dsf_rows_near(a.dsf_dump, a.lat, a.lon, a.radius_m)
        doc["dsf_rows"] = rows
        print(f"== DSF rows within {a.radius_m:.0f} m "
              f"({os.path.basename(a.dsf_dump)})")
        for r in rows[:a.max]:
            e = "-" if r["elevation"] is None else f"{r['elevation']:.2f}"
            print(f"  {r['distance_m']:6.1f} m {r['kind']:<11s} "
                  f"{r['resource'].split('/')[-1][:62]:<62s} "
                  f"{r['lat']:.7f},{r['lon']:.7f}  elev={e}")
        print(f"  rows: {len(rows)} "
              f"{dict(collections.Counter(r['kind'] for r in rows))}")

    if "bodies" in show and plan_p:
        bodies = plan_bodies_near(json.load(open(plan_p)), a.lat, a.lon,
                                  a.radius_m)
        doc["bodies"] = bodies
        print(f"== plan bodies within {a.radius_m:.0f} m "
              f"({os.path.basename(plan_p)})")
        for r in bodies[:a.max]:
            sz = "-" if r["surface_z"] is None else f"{r['surface_z']:.2f}"
            print(f"  {r['distance_m']:6.1f} m "
                  f"{r['resource'].split('/')[-1][:46]:<46s} "
                  f"{str(r['body_id']):<5s} {str(r['class']):<12s} "
                  f"unit={str(r['unit_of']):<24s} surf={sz:<8s} "
                  f"zero={r['y_zero']:.2f} {str(r['anchor_reason'])[:110]}")
        print(f"  bodies: {len(bodies)}")
        print("  units:",
              dict(collections.Counter(str(r["unit_of"]) for r in bodies)))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        print(f"\nsite -> {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
