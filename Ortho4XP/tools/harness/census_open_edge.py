"""THE OPEN EDGE IN A BOX (``census.py --open-edge-box LAT,LON,R``): the
metres of the patch's OPEN boundary — an edge no other patch face lies
across, where the patch meets the mesh's raw ground — within ``R`` metres of
a site that stand more than ``off`` metres off the DEM.

WHY (owner RULINGS 2026-11-03e, #1093): "no OPEN patch edge more than 0.5 m
off DEM (not the corner vertex)".  The census prices pairs of values; an
open edge standing 5 m over the ground beside it is a cliff the mesh draws
and no law row sees.  Promoted from lane lramp2's scratch read on its
second use (lane l1093r3).

The edge is sampled every ``step`` metres at the midpoints of its
sub-intervals (never at a vertex: the bar is the edge, not the corner), the
patch level read linearly between the edge's two emitted levels, the ground
off the build's DEM (``pad_edge_read.capture_dem``, a capture pickle — the
emitted patch carries no DEM).  A sample is OPEN when it lies on the
boundary of the union of every patch ring AND no patch face lies across
the STAND-OFF beyond it (``constraints/pad_ramp.stand_off_m``, three
identity cells): the last stage's arrangement notches a follower's node
off a standing edge by up to that much, and the stand-off between two
faces is read as a pair across it (``v2_late_read.standoff_pairs``), never
as raw ground.  Geometry comes from the harness library
(``check_grade._parse_osm``), never re-parsed.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

__all__ = ["open_edge_box", "parse_box", "format_open_edge", "stand_off_m"]

#: metres per degree of latitude on the local sphere (the box is a few
#: hundred metres: an equirectangular frame is exact to millimetres)
_M_PER_DEG = 6371008.8 * math.pi / 180.0


def stand_off_m() -> float:
    """The law's stand-off (``constraints/pad_ramp.stand_off_m``), read
    from the v2 law tables — never a literal here."""
    import sys
    from pathlib import Path
    src = str(Path(__file__).resolve().parents[2] / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from auto_patch_v2.constraints.pad_ramp import stand_off_m as _so
    from auto_patch_v2.law import Law
    return float(_so(Law.load()))


def parse_box(spec: str) -> tuple[float, float, float]:
    """``LAT,LON,R`` -> ``(lat, lon, r)``."""
    parts = [float(x) for x in str(spec).split(",")]
    if len(parts) != 3 or parts[2] <= 0.0:
        raise ValueError(f"--open-edge-box wants LAT,LON,R (R > 0), got {spec!r}")
    return parts[0], parts[1], parts[2]


def open_edge_box(nodes: dict, ways: list, dem: Callable[[float, float], float],
                  lat0: float, lon0: float, r: float, *, off: float = 0.5,
                  step: float = 0.5, ring_ll: Optional[list] = None,
                  standoff: float = 0.0) -> dict:
    """``{"open_m", "off_m", "refs": [{ref, role, open_m, off_m, worst}]}``
    for the open boundary within ``r`` metres of ``(lat0, lon0)`` — or,
    given ``ring_ll`` (``[(lat, lon), ...]``), inside that ring instead (a
    run-out's own box).  ``standoff``: a boundary sample with a patch face
    within that distance beyond it (outward of its own ring) is bridged,
    not open (module docstring)."""
    from shapely import STRtree
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    kx = _M_PER_DEG * math.cos(math.radians(lat0))

    def xy(nid):
        la, lo = nodes[nid]
        return (lo - lon0) * kx, (la - lat0) * _M_PER_DEG

    def ll(x, y):
        return lat0 + y / _M_PER_DEG, lon0 + x / kx
    site = (Polygon([((lo - lon0) * kx, (la - lat0) * _M_PER_DEG) for la, lo in ring_ll])
            if ring_ll else Point(0.0, 0.0).buffer(r))
    reach = site.buffer(200.0)
    polys, near = [], []
    for w in ways:
        if any(n not in nodes for n in w.nids):
            continue
        pts = [xy(n) for n in w.nids]
        if len(set(pts)) < 3:
            continue
        q = Polygon(pts)
        q = q if q.is_valid else q.buffer(0)
        if q.is_empty or not q.intersects(reach):
            continue
        polys.append(q)
        if q.intersects(site):
            near.append((w, pts))
    if not polys:
        return {"open_m": 0.0, "off_m": 0.0, "refs": []}
    cover = unary_union(polys)
    edge = cover.boundary
    tree = STRtree([edge])
    by: dict[str, dict] = {}
    tot_open = tot_off = 0.0
    for w, pts in near:
        ref = str(w.ref or w.wid)
        own = Polygon(pts)
        own = own if own.is_valid else own.buffer(0)
        for i in range(len(pts) - 1):
            za, zb = w.elevs[i], w.elevs[i + 1]
            if za is None or zb is None:
                continue
            (xa, ya), (xb, yb) = pts[i], pts[i + 1]
            seg = LineString([(xa, ya), (xb, yb)])
            if seg.length <= 0.0 or not seg.intersects(site):
                continue
            n = max(1, int(math.ceil(seg.length / step)))
            dl = seg.length / n
            for k in range(n):
                t = (k + 0.5) / n
                px, py = xa + t * (xb - xa), ya + t * (yb - ya)
                p = Point(px, py)
                if not site.contains(p) or not tree.query(p, predicate="dwithin",
                                                          distance=0.05).size:
                    continue
                if standoff > 0.0 and _bridged(p, xb - xa, yb - ya, seg.length, own,
                                               cover, standoff):
                    continue
                z = float(za) + t * (float(zb) - float(za))
                la, lo = ll(px, py)
                dz = z - float(dem(la, lo))
                rec = by.setdefault(ref, {"ref": ref, "role": w.role, "open_m": 0.0,
                                          "off_m": 0.0, "worst": None})
                rec["open_m"] += dl
                tot_open += dl
                if abs(dz) > off:
                    rec["off_m"] += dl
                    tot_off += dl
                if rec["worst"] is None or abs(dz) > abs(rec["worst"][2]):
                    rec["worst"] = (round(la, 7), round(lo, 7), round(dz, 2))
    refs = sorted(by.values(), key=lambda q: (-q["off_m"], q["ref"]))
    for q in refs:
        q["open_m"], q["off_m"] = round(q["open_m"], 1), round(q["off_m"], 1)
    return {"lat": lat0, "lon": lon0, "r_m": r, "off": off, "open_m": round(tot_open, 1),
            "off_m": round(tot_off, 1), "refs": refs}


def _bridged(p, ex: float, ey: float, L: float, own, cover, standoff: float) -> bool:
    """A face lies within ``standoff`` beyond the edge sample ``p`` (edge
    direction ``(ex, ey)``, length ``L``), on the side away from ``own``."""
    from shapely.geometry import LineString, Point
    nx, ny = -ey / L, ex / L
    if own.contains(Point(p.x + 0.05 * nx, p.y + 0.05 * ny)):
        nx, ny = -nx, -ny
    probe = LineString([(p.x + 0.05 * nx, p.y + 0.05 * ny),
                        (p.x + standoff * nx, p.y + standoff * ny)])
    return probe.intersects(cover)


def format_open_edge(rep: dict, top: Optional[int] = None) -> list[str]:
    """The report's lines: the box total, then each ref with metres off."""
    out = [f"OPEN EDGE in {rep.get('r_m', 0):.0f} m of {rep.get('lat')},{rep.get('lon')}: "
           f"{rep['off_m']:.1f} m of {rep['open_m']:.1f} m stand > {rep.get('off', 0.5)} m "
           f"off the DEM"]
    for q in [q for q in rep["refs"] if q["off_m"] > 0.0][:top]:
        la, lo, dz = q["worst"]
        out.append(f"  {q['ref']:<32} {q['role']:<20} {q['off_m']:6.1f} of "
                   f"{q['open_m']:6.1f} m  worst {dz:+.2f} m at {la},{lo}")
    return out
