#!/usr/bin/env python3
"""AIRSIDE-ENCLOSED VOID census over an EMITTED patch.

A VOID is a bounded complement component of the airside∪building union —
an interior ring (hole) of exactly the geometry the ENCLAVE REGION LAW
publishes as ``layout.airside_enclaves``
(``auto_patch/enclaves.py``; owner G-ENCLAVE 2026-07-28, extended to bare
ground 2026-08-07).  This tool reads that topology back off a SHIPPED
patch and reports, per void:

  * area, perimeter, minimum-rotated-rect SHORT SIDE and the POCKET flag
    (short side ≤ the gap law's ``GAP_FILL_MAX_WIDTH_M`` — the class the
    ruled gap ring + spine treatment covers, and therefore the class the
    band keep-out is scoped to);
  * the ESCAPE clause: touching ``tunnel_ramp`` / ``tunnel_trench`` /
    ``bridge_*`` shapes.  A void with an escape is NOT an enclave;
  * what is INSIDE it — retaining walls (with way id, ref and area),
    every other role/ref class, whether the gap ring + spine treated it,
    and the BARE GROUND remainder that carries no shape at all;
  * groundside pavement inside no-escape voids: the population the
    enclave law re-verdicts to airside.

**It measures no law and produces no defect counts.**  Grade defects come
from ``tools/harness/census.py`` and nothing else; this tool answers
"what is the enclave topology of this patch, and what is sitting in it".

Frames.  The geometry is EMITTED geometry: post-decimation and post
``_separate_groundside_from_airside``, so a void reads slightly larger
than the in-build region and a groundside shape inside it reads pulled
back from the rim.  Two patches are comparable only when built from the
same tree; a real-DEM patch is never comparable with a constant-DEM one.

Roles and the escape set are IMPORTED from ``auto_patch.enclaves`` — the
engine's own vocabulary, never a hand-typed copy (the census-wrapper
precedent, ``tools/INDEX.md``).  The patch is parsed by the harness
library's own reader (``check_grade._parse_osm``) in the builder's anchor
frame from the axes sidecar, so this tool and the census read one
geometry.

Usage:
    tools/void_census.py PATCH.osm [PATCH.osm ...] [--json OUT]
                                   [--walls-only] [--top N]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "src"))

from shapely.geometry import Polygon                      # noqa: E402
from shapely.ops import unary_union                       # noqa: E402
from shapely.strtree import STRtree                       # noqa: E402

import check_grade as CG                                  # noqa: E402
from auto_patch.config import GAP_FILL_MAX_WIDTH_M        # noqa: E402
from auto_patch.enclaves import (                         # noqa: E402
    ENCLAVE_ESCAPE_CONTACT_M,
    ENCLAVE_ESCAPE_ROLES,
    ENCLAVE_SURROUND_ROLES,
)
from auto_patch.geom_safe import min_rotated_rect         # noqa: E402
from auto_patch.layout import ROLE_RETAINING_WALL         # noqa: E402

# The ruled treatment's own marker in an emitted patch.
GAP_FACE_REFS = ("gap_fill_spine",)
MIN_CONTENT_AREA_M2 = 0.01     # below this an overlap is ring noise


def _rings(path: Path):
    """``(rings, anchor_used)`` — every closed pavement ring of the patch
    as ``(way_id, polygon, role, ref, tags)`` in LAYOUT-LOCAL METRES."""
    nodes, ways = CG._parse_osm(path)
    anchor = None
    try:
        anchor = CG.law_context_from_sidecar(path).get("anchor")
    except FileNotFoundError:
        anchor = None
    ll_to_m = CG._ll_to_m_factory(nodes, anchor)
    out = []
    for way in ways:
        pts = [ll_to_m(*nodes[nid]) for nid in way.nids if nid in nodes]
        if len(pts) < 4:
            continue
        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            continue
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        out.append((way.wid, poly, way.role, way.ref, way.tags))
    return out, anchor


def _short_side(poly):
    try:
        ring = list(min_rotated_rect(poly).exterior.coords)
    except Exception:
        return None
    if len(ring) < 4:
        return None
    sides = [math.hypot(ring[i + 1][0] - ring[i][0],
                        ring[i + 1][1] - ring[i][1])
             for i in range(len(ring) - 1)]
    return float(min(sides[:2])) if len(sides) >= 2 else None


def census(path: Path) -> dict | None:
    """The void census for one patch (a plain dict, JSON-ready)."""
    rings, anchor = _rings(path)
    if not rings:
        return None
    surround = [p for _w, p, role, _r, _t in rings
                if role in ENCLAVE_SURROUND_ROLES]
    if len(surround) < 2:
        return None
    union = unary_union(surround)
    comps = ([union] if union.geom_type == "Polygon"
             else [g for g in getattr(union, "geoms", [])
                   if g.geom_type == "Polygon"])
    voids = []
    for comp in comps:
        for interior in comp.interiors:
            hole = Polygon(list(interior.coords))
            if hole.is_empty or hole.area <= 0.0:
                continue
            voids.append(hole)

    others = [(w, p, role, ref) for w, p, role, ref, _t in rings
              if role not in ENCLAVE_SURROUND_ROLES]
    otree = STRtree([p for _w, p, _role, _ref in others]) if others else None
    # ROLES ONLY.  The engine's escape test also honours the ``is_bridge``
    # SHAPE FLAG, which ``to_osm`` does not emit — so this reader can see
    # the four escape ROLES and no more, and an is_bridge-flagged
    # pavement piece reads here as a non-escape.  Stated rather than
    # papered over: it is a frame limit of reading a shipped patch, and
    # the in-build predicate (``enclaves._escape_shapes``) has both.
    escapes = [(w, p, role) for w, p, role, _ref, _tags in rings
               if role in ENCLAVE_ESCAPE_ROLES]
    etree = STRtree([p for _w, p, _role in escapes]) if escapes else None

    records = []
    for hole in voids:
        by_class = collections.Counter()
        area_by_class = collections.Counter()
        covered, walls, gap_treated = [], [], False
        if otree is not None:
            for i in otree.query(hole):
                wid, poly, role, ref = others[int(i)]
                try:
                    inter = poly.intersection(hole)
                except Exception:
                    continue
                if inter.is_empty or inter.area < MIN_CONTENT_AREA_M2:
                    continue
                key = f"{role}/{ref}"
                by_class[key] += 1
                area_by_class[key] += inter.area
                covered.append(inter)
                if role == ROLE_RETAINING_WALL:
                    walls.append({"way": wid, "ref": ref,
                                  "area_m2": round(inter.area, 2)})
                if ref in GAP_FACE_REFS:
                    gap_treated = True
        escape_hits = []
        if etree is not None:
            for i in etree.query(hole.buffer(ENCLAVE_ESCAPE_CONTACT_M)):
                wid, poly, role = escapes[int(i)]
                if poly.distance(hole) <= ENCLAVE_ESCAPE_CONTACT_M:
                    escape_hits.append({"way": wid, "role": role})
        occupied = unary_union(covered).area if covered else 0.0
        short = _short_side(hole)
        centroid = hole.centroid
        lat = lon = None
        if anchor:
            lat0, lon0 = anchor
            lat = lat0 + math.degrees(centroid.y / CG.R_EARTH)
            lon = lon0 + math.degrees(
                centroid.x / (CG.R_EARTH * math.cos(math.radians(lat0))))
        records.append({
            "area_m2": round(hole.area, 1),
            "perimeter_m": round(hole.length, 1),
            "short_side_m": None if short is None else round(short, 1),
            "pocket": bool(short is not None
                           and short <= GAP_FILL_MAX_WIDTH_M),
            "lat": None if lat is None else round(lat, 8),
            "lon": None if lon is None else round(lon, 8),
            "escapes": escape_hits,
            "no_escape": not escape_hits,
            "gap_treated": gap_treated,
            "bare_m2": round(hole.area - occupied, 1),
            "bare_frac": (round((hole.area - occupied) / hole.area, 4)
                          if hole.area > 0 else 0.0),
            "contents": {k: [by_class[k], round(area_by_class[k], 1)]
                         for k in sorted(by_class)},
            "walls": walls,
        })
    records.sort(key=lambda r: -r["area_m2"])
    no_escape = [r for r in records if r["no_escape"]]
    return {
        "patch": str(path),
        "anchor": list(anchor) if anchor else None,
        "gap_fill_max_width_m": GAP_FILL_MAX_WIDTH_M,
        "voids": len(records),
        "no_escape": len(no_escape),
        "pocket": sum(1 for r in records if r["pocket"]),
        "gap_treated": sum(1 for r in records if r["gap_treated"]),
        "walls_in_no_escape_voids": sum(len(r["walls"]) for r in no_escape),
        "voids_with_wall": sum(1 for r in no_escape if r["walls"]),
        "records": records,
    }


def _print(report: dict, walls_only: bool, top: int) -> None:
    name = os.path.basename(report["patch"])
    print(f"{name:<30} voids={report['voids']:<5} "
          f"no_escape={report['no_escape']:<5} "
          f"pocket={report['pocket']:<5} "
          f"gap_treated={report['gap_treated']:<5} "
          f"walls_in_no_escape_voids={report['walls_in_no_escape_voids']:<4} "
          f"voids_with_wall={report['voids_with_wall']}")
    rows = [r for r in report["records"] if r["no_escape"]]
    if walls_only:
        rows = [r for r in rows if r["walls"]]
    for rec in rows[:top]:
        flag = "pocket" if rec["pocket"] else "WIDE  "
        print(f"    {flag} {rec['area_m2']:>10.1f} m2 "
              f"short={str(rec['short_side_m']):>7} "
              f"bare={rec['bare_frac'] * 100:5.1f}% "
              f"gap={'Y' if rec['gap_treated'] else 'n'} "
              f"@ {rec['lat']},{rec['lon']}")
        if rec["walls"]:
            print(f"        walls: {rec['walls']}")
        if rec["contents"]:
            print(f"        contents: {rec['contents']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("patches", nargs="+", type=Path)
    ap.add_argument("--json", dest="json_out", type=Path)
    ap.add_argument("--walls-only", action="store_true",
                    help="print only voids that contain a retaining wall")
    ap.add_argument("--top", type=int, default=10,
                    help="how many voids to print per patch (default 10)")
    args = ap.parse_args(argv)
    reports = []
    for path in args.patches:
        report = census(path)
        if report is None:
            print(f"{path}: no airside geometry")
            continue
        reports.append(report)
        _print(report, args.walls_only, args.top)
    if args.json_out:
        args.json_out.write_text(json.dumps(reports, indent=1))
        print("wrote", args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
