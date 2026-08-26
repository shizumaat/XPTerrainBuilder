"""THE NODELESS-INTERIOR INSTRUMENT — §2 of
docs/specs/heca-apron-round2-spec.md (Fable spec, 2026-08-25).

WHAT IT MEASURES.  An apron-role polygon carrying an INTERIOR DISK of
radius greater than ``config.APRON_NODELESS_RADIUS_M`` inside which the
patch emits ZERO vertices.

WHY IT IS WORTH A LOUD LINE.  Such a region's membrane is uncontrolled:
its elevation is whatever the mesh interpolates between the ring
vertices that bound it, tens or hundreds of metres away.  Worse, it is
INVISIBLE to every instrument that judges the surface — the census
prices PAIRS OF EMITTED NODES, so no nodes means no rows, and the region
reads as perfectly compliant.  HECA's 215 x 430 m void (the taxiway J
feed gap, §1) passed three rounds of censuses at 1,679 while carrying a
visible cliff at 30.1289374, 31.4052385.

THIS IS REPORT-FIRST AND UNGATED.  It changes no build path and takes no
build down; promotion to a refusal is a later owner ruling.  The count
lands in the patch sidecar as ``nodeless_interiors`` (EVIDENCE, never
law input) and the census prints it — zero-of-zero visible, because a
line that only appears when something is wrong cannot distinguish "the
instrument found nothing" from "the instrument did not run".

THE DISK.  ``r(p) = min(distance to the polygon boundary, distance to
the nearest emitted vertex)`` maximised over the polygon's interior: the
largest disk that lies inside the shape AND contains no emitted vertex.
The search rejects almost every shape on the first test — a polygon
whose pole of inaccessibility is closer to its own boundary than the
radius cannot hold the disk at all — and grid-searches only the
survivors.
"""
from __future__ import annotations

import math

import O4_UI_Utils as UI

_GEOM_EXC = Exception


def _pole_of_inaccessibility(poly, tol):
    """``(point, boundary_distance)`` — the interior point furthest from
    the boundary.  Uses shapely's own ``polylabel``; falls back to the
    representative point when it is unavailable."""
    try:
        from shapely.ops import polylabel
        p = polylabel(poly, tolerance=max(1.0, float(tol)))
    except Exception:                                     # pragma: no cover
        try:
            p = poly.representative_point()
        except _GEOM_EXC:
            return None, 0.0
    try:
        return p, float(poly.exterior.distance(p))
    except _GEOM_EXC:                                     # pragma: no cover
        return None, 0.0


def _empty_radius_at(poly_boundary, tree, points, px, py):
    """``min(distance to boundary, distance to nearest emitted vertex)``
    at ``(px, py)`` — the radius of the largest empty disk centred
    there."""
    from shapely.geometry import Point
    p = Point(px, py)
    try:
        r = float(poly_boundary.distance(p))
    except _GEOM_EXC:                                     # pragma: no cover
        return 0.0
    if tree is not None and points:
        try:
            k = tree.nearest(p)
            qx, qy = points[int(k)]
            r = min(r, math.hypot(qx - px, qy - py))
        except Exception:                                 # pragma: no cover
            pass
    return r


def largest_nodeless_disk(poly, tree, points, radius_m):
    """``(centre_xy, radius)`` of the largest EMPTY interior disk of
    ``poly``, or ``None`` when no disk of at least ``radius_m`` exists.

    Coarse grid at ``radius_m / 2`` (a disk of the target radius cannot
    hide between samples that close), then three halving refinements
    around the best sample."""
    from shapely.geometry import Point
    try:
        boundary = poly.exterior
        minx, miny, maxx, maxy = poly.bounds
    except _GEOM_EXC:                                     # pragma: no cover
        return None
    # FAST REJECT: the furthest-from-boundary interior point bounds every
    # disk this polygon can hold.  Most shapes die here.
    _pole, _rb = _pole_of_inaccessibility(poly, radius_m / 4.0)
    if _rb < radius_m:
        return None
    step = max(1.0, radius_m / 2.0)
    best = None
    if _pole is not None:
        r0 = _empty_radius_at(boundary, tree, points, _pole.x, _pole.y)
        best = ((float(_pole.x), float(_pole.y)), r0)
    n_x = int((maxx - minx) / step) + 1
    n_y = int((maxy - miny) / step) + 1
    if n_x * n_y > 250_000:                # a pathological bbox: pole only
        n_x = n_y = 0
    for ix in range(n_x):
        px = minx + ix * step
        for iy in range(n_y):
            py = miny + iy * step
            try:
                if not poly.contains(Point(px, py)):
                    continue
            except _GEOM_EXC:                             # pragma: no cover
                continue
            r = _empty_radius_at(boundary, tree, points, px, py)
            if best is None or r > best[1]:
                best = ((px, py), r)
    if best is None:
        return None
    (bx, by), br = best
    h = step / 2.0
    for _ in range(3):
        for dx in (-h, 0.0, h):
            for dy in (-h, 0.0, h):
                px, py = bx + dx, by + dy
                try:
                    if not poly.contains(Point(px, py)):
                        continue
                except _GEOM_EXC:                         # pragma: no cover
                    continue
                r = _empty_radius_at(boundary, tree, points, px, py)
                if r > br:
                    bx, by, br = px, py, r
        h /= 2.0
    if br < radius_m:
        return None
    return (bx, by), br


def find_nodeless_interiors(shapes, vertices_xy, radius_m, *,
                            roles=("apron",), m_to_ll=None):
    """``[record]`` — one per shape holding an empty interior disk of at
    least ``radius_m``.  Each record names the shape (its ``shapeID``,
    i.e. its index in ``layout.shapes``, plus its ``ref``), the disk
    centre and the radius.

    ``vertices_xy`` — every EMITTED vertex, in local metres.  ``m_to_ll``
    — ``layout.m_to_ll``, so the centre is reported where the owner can
    fly to it; omitted in unit tests, which read the metre centre."""
    points = [(float(x), float(y)) for (x, y) in (vertices_xy or ())]
    tree = None
    if points:
        try:
            from shapely.geometry import Point
            from shapely.strtree import STRtree
            tree = STRtree([Point(x, y) for (x, y) in points])
        except Exception:                                 # pragma: no cover
            tree = None
    out: list = []
    for idx, s in enumerate(shapes or ()):
        if (getattr(s, "role", None) or "") not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        if getattr(poly, "geom_type", "") != "Polygon":
            continue
        hit = largest_nodeless_disk(poly, tree, points, float(radius_m))
        if hit is None:
            continue
        (cx, cy), r = hit
        rec = {"shapeID": idx,
               "ref": getattr(s, "ref", "") or "",
               "role": getattr(s, "role", "") or "",
               "centre_m": [round(cx, 2), round(cy, 2)],
               "radius_m": round(float(r), 2),
               "area_m2": round(float(getattr(poly, "area", 0.0)), 1)}
        if m_to_ll is not None:
            try:
                lat, lon = m_to_ll(cx, cy)
                rec["centre_ll"] = [round(float(lat), 7),
                                    round(float(lon), 7)]
            except Exception:                             # pragma: no cover
                pass
        out.append(rec)
    return out


def report_nodeless_interiors(layout, vertices_xy, *, icao: str = ""):
    """Run the instrument, publish ``layout._nodeless_interiors``, and
    print the LOUD line — at zero too, so an absent line means the
    instrument did not run rather than that it found nothing."""
    from . import config as _cfg
    radius = float(getattr(_cfg, "APRON_NODELESS_RADIUS_M", 80.0))
    try:
        recs = find_nodeless_interiors(
            getattr(layout, "shapes", None) or (), vertices_xy, radius,
            m_to_ll=getattr(layout, "m_to_ll", None))
    except Exception as exc:                              # pragma: no cover
        UI.vprint(1, f"  [nodeless-interior] {icao}: instrument FAILED "
                     f"({type(exc).__name__}: {exc}) — no reading this "
                     f"build")
        return []
    layout._nodeless_interiors = recs
    tag = f"{icao}: " if icao else ""
    if not recs:
        UI.vprint(1, f"  [nodeless-interior] {tag}0 apron shape(s) carry "
                     f"an interior disk of radius > {radius:g} m with no "
                     f"emitted vertex")
        return recs
    UI.vprint(1, f"  [nodeless-interior] {tag}{len(recs)} apron shape(s) "
                 f"carry an UNCONTROLLED, CENSUS-INVISIBLE interior — an "
                 f"empty disk of radius > {radius:g} m with ZERO emitted "
                 f"vertices (no nodes means no census rows):")
    for rec in sorted(recs, key=lambda r: -r["radius_m"]):
        where = rec.get("centre_ll") or rec["centre_m"]
        UI.vprint(1, f"      shapeID {rec['shapeID']} "
                     f"(ref {rec['ref'] or '-'}, {rec['area_m2']:g} m2): "
                     f"radius {rec['radius_m']:g} m at {where}")
    return recs
