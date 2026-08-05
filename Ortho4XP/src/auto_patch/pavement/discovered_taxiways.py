"""Medial-axis (skeleton) extraction from raw pavement geometry.

What this module IS today: three medial-axis primitives —
``_medial_segments`` / ``_flatten_lines`` / ``_prune`` — used by
``pavement/service_roads.py`` to extend a 1206 truck route along a narrow
apt.dat strip's own medial axis (CYXY "New Taxiway 40").

Method (shapely only — no scipy/skimage):
  1. Densify the pavement boundary and take its Voronoi diagram; the Voronoi
     edges interior to the polygon approximate the medial axis.
  2. Keep medial edges whose clearance to the boundary is in a given
     half-width band (so apron cores, which have large clearance, drop out).
  3. Merge edges into polylines and prune short spurs.

Why a medial axis (not rectangle fitting): lanes form a connected *web*;
fitting one rectangle per residue blob collapses the web into a single
low-fill shape.  The medial axis follows each lane individually, bends and
all, and splits naturally at junctions.

── RETIREMENT RECORD: ``discover_unreferenced_centerlines`` ────────────────
The module's original public entry point synthesised taxiway centerlines for
lane-width pavement carrying NO apt.dat row-1201/1202 edge and NO OSM
``aeroway=taxiway`` way.  It was UNWIRED on 2026-07-31 and DELETED in the
dead-code round; the retirement record is kept here because ``pipeline.py``,
``config.py`` and ``junction_repair.py`` all point at this header.

Its two consumers — ``_build_taxi_rects`` and ``junction_spine`` — were
deleted by d4f61d6 on 2026-07-29, and the docstring written that day ("the
discovered centerlines join the global-slice spine downstream exactly like a
referenced taxiway") was an ASSERTION, not a wiring: the slice takes its
spine from ``layout.apt_taxi_centerlines``, which ``pipeline`` snapshots
BEFORE discovery ran (deliberately — that snapshot is junction_repair's
apt.dat-only route model), never from the local list discovery appended to.
Measured 2026-07-31: 595 discovered centerlines at HECA, 27 at SPJC, ZERO
spine nodes from either, and a byte-identical patch body with the call site
gone.  Removing it took phase 3 from 16.71 to 6.02 s at HECA and 4.7 to
3.08 s at SPJC.

There WAS a planned successor consumer and it was never built:
``docs/curve_native_spine_v2_plan.md`` **Phase 5 — coverage fallback**
("synthesize a spine from the discovered/``TX`` edge-skeleton centerline
(reuse the existing discovered-taxiway extractor) and cut with it").  That
plan's Phase 6 — retire the straight rects — is what shipped on 2026-07-29,
with Phase 5 still outstanding, so the extractor lost its consumer before
its replacement existed.

Rebuilding it would be a SPINE-COMPOSITION change, not a repair: ~595
synthetic lanes would enter the route model that the grade solve, the
reachability law and junction_repair's reclassification all read.  It needs
an owner / design ruling and its own measurement — and P7 has since measured
the medial axis as NOT covering the spine-coverage defect it would be the
obvious candidate for (ruling (b3), docs/specs/taut-string-
implementation-plan.md).
"""
from __future__ import annotations

from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import voronoi_diagram
from shapely import segmentize

_GEOM_EXC = (ValueError, ZeroDivisionError, AttributeError, TypeError)

_MAX_BOUNDARY_PTS = 40000   # perf guard for very large airports


def _flatten_lines(geom) -> list[LineString]:
    out: list[LineString] = []
    stack = [geom]
    while stack:
        g = stack.pop()
        if g is None or g.is_empty:
            continue
        if g.geom_type == "LineString":
            out.append(g)
        elif hasattr(g, "geoms"):
            stack.extend(g.geoms)
    return out


def _key(pt) -> tuple[float, float]:
    return (round(pt[0] * 2) / 2, round(pt[1] * 2) / 2)


def _medial_segments(P, hw_min: float, hw_max: float, sample: float):
    """Voronoi medial-axis segments of ``P`` whose clearance is in band."""
    bnd = P.boundary
    perim = bnd.length
    step = sample
    if perim / step > _MAX_BOUNDARY_PTS:
        step = perim / _MAX_BOUNDARY_PTS
    dense = segmentize(bnd, step)
    coords: list[tuple[float, float]] = []
    for g in (dense.geoms if dense.geom_type.startswith("Multi") else [dense]):
        coords += list(g.coords)
    if len(coords) < 4:
        return []
    try:
        vor = voronoi_diagram(MultiPoint(coords), edges=True)
    except _GEOM_EXC:
        return []
    except Exception:  # shapely GEOS can raise base Exception subclasses
        return []
    segs: list[LineString] = []
    for ln in _flatten_lines(vor):
        cc = list(ln.coords)
        for i in range(len(cc) - 1):
            a, b = cc[i], cc[i + 1]
            mid = Point((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            if not P.contains(mid):
                continue
            if not (hw_min <= mid.distance(bnd) <= hw_max):
                continue
            if not (P.contains(Point(a)) and P.contains(Point(b))):
                continue
            segs.append(LineString([a, b]))
    return segs


def _prune(polylines: list[LineString], prune_len: float) -> list[LineString]:
    """Drop short spurs: a polyline with a degree-1 (free) endpoint and length
    < ``prune_len`` is removed; iterate until stable."""
    pls = list(polylines)
    changed = True
    while changed:
        changed = False
        deg: dict[tuple[float, float], int] = {}
        for p in pls:
            for end in (_key(p.coords[0]), _key(p.coords[-1])):
                deg[end] = deg.get(end, 0) + 1
        keep = []
        for p in pls:
            free = (deg[_key(p.coords[0])] == 1
                    or deg[_key(p.coords[-1])] == 1)
            if free and p.length < prune_len:
                changed = True
                continue
            keep.append(p)
        pls = keep
    return pls


# Max corner-angle deviation from 90° for a KEEPABLE discovered taxi rect.
# A clean free-strip lane on regular pavement yields a near-rectangle; an
# apron-EMBEDDED lane gets snap-distorted by the rect builder (corners pulled
# onto the ragged apron boundary) and comes out sheared.  Discovery scopes
# itself to the free strips; sheared (apron-embedded) lanes are deferred to
# the narrow-neck apron-decomposition pass (Phase 2), which splits the apron
# into pads rather than ramming a rect through it.
_MAX_SHEAR_DEG = 10.0


