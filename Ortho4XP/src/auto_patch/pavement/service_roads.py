"""Ground-vehicle ``service_road`` network builder (session 47).

Builds a rect + junction network for ground-vehicle routes — apt.dat 1206
truck routes and OSM small roads — but ONLY where a route is a dedicated
strip OUTSIDE aircraft pavement.  Where a route instead crosses an
aircraft movement area (apron / taxiway / runway), nothing is emitted:
that surface's stricter aircraft grade rules already apply (per user
2026-05-24), and pavement is minted only where none exists, so existing
ribbons and aprons are never double-paved.

THE GRADE NUMBER IS ``config.SERVICE_ROAD_MAX_GRADE`` and nothing else
(``ROLE_GRADE_LIMITS`` maps both road roles to it).  This module states no
second number: the percentage this docstring used to quote, and the
different one grade_graph quoted, were both stale copies of a constant that
had since moved.

Most service roads have no apt.dat / DSF pavement polygon, so a standard
corridor width is synthesised (``config.SERVICE_ROAD_WIDTH_M``).  The
network mirrors the taxiway model: ``service_road`` rects along straight
runs (graded along their axis at the road cap) + ``service_junction`` fill
polygons at bends / intersections (all-direction, same cap).  Cars handle
steeper terrain than aircraft, so these also double as apron↔DEM
transition ramps.

SOURCE PRECEDENCE (owner ruling 2026-08-12b): apt.dat 1206 routes are
AUTHORITATIVE where present and OSM small roads complement them —
:func:`dedupe_service_sources` suppresses an OSM line that merely
re-spells a 1206 route, at CENTERLINE level, before anything is minted.
"""
from __future__ import annotations

import math
import os as _os

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import (LineString, MultiLineString, MultiPolygon,
                              Point, Polygon)
from shapely.ops import unary_union

from ..layout import ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION

_GEOM_EXC = (ValueError, TypeError, GEOSException, TopologicalError, IndexError)

# A route vertex within this distance of aircraft pavement counts as
# "on the movement area" and is excluded from the service-road network.
_PAV_CLEAR_TOL_M = 1.0
# MOUTH REACH — how far along its own axis a mouth fill may run from the
# corridor body's cut end toward the pavement it joins.  The gap it closes is
# ``_PAV_CLEAR_TOL_M`` measured along the buffer NORMAL, so a route meeting
# the edge obliquely needs more than the clearance itself; three times it
# spans an approach as shallow as ~20°.  The fill is additionally INTERSECTED
# with the buffered union, so this number can only ever shorten a fill that
# is already confined to the annulus — it can never reach pavement or open
# ground beyond it.
_MOUTH_REACH_M = 3.0 * _PAV_CLEAR_TOL_M
# Turn angle (deg) above which a polyline is split into a new straight run.
_BEND_ANGLE_DEG = 25.0
# Minimum service_junction fill-polygon area to keep (drop slivers).
_MIN_JUNCTION_AREA_M2 = 2.0


def _as_linestrings(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type == "MultiLineString":
        return [g for g in geom.geoms if not g.is_empty]
    return []


def _as_polygons(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return [g for g in geom.geoms if not g.is_empty]
    return []


def _max_chord_deviation(run: list[tuple[float, float]],
                         ex: float, ey: float) -> float:
    """Largest PERPENDICULAR distance from ``run``'s vertices to the chord
    ``run[0] → (ex, ey)`` — i.e. to the axis the rect would be built on."""
    ax, ay = run[0]
    dx, dy = ex - ax, ey - ay
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return 0.0
    worst = 0.0
    for px, py in run[1:]:
        d = abs((px - ax) * dy - (py - ay) * dx) / L
        if d > worst:
            worst = d
    return worst


def _split_at_bends(coords: list[tuple[float, float]],
                    width: float | None = None
                    ) -> list[list[tuple[float, float]]]:
    """Split a polyline into straight-ish runs.

    Two independent break tests, either of which closes the current run:

    * TURN ANGLE — a vertex whose turn exceeds ``_BEND_ANGLE_DEG`` (the
      original test; an L-bend).
    * CHORD DEVIATION (needs ``width``) — a run whose own vertices stray
      more than ``width / 2`` from its chord ``run[0] → candidate``.  A
      gently-curved road passes every per-vertex angle test yet bows well
      clear of the first-to-last chord the rect is built on
      (:func:`_rect_from_endpoints`), so ONE rect gets laid off the real
      road (CYXY "Barkley-Grow Crescent": 11 vertices, max turn 14.5°,
      sagitta 10.31 m against a 6 m corridor) and the corridor−rect
      residue is emitted as a bogus ribbon junction.  Half the width is
      the exact threshold at which the rect stops covering its own
      centerline.

    ``width=None`` (no caller-supplied corridor width) runs the turn test
    alone, exactly as before.  This is THE straightness definition: the
    rect builder stays a pure chord rect.
    """
    if len(coords) < 2:
        return []
    runs: list[list[tuple[float, float]]] = []
    cur = [coords[0], coords[1]]
    cos_tol = math.cos(math.radians(_BEND_ANGLE_DEG))
    half = None if width is None else width / 2.0
    for k in range(1, len(coords) - 1):
        ax, ay = coords[k - 1]
        bx, by = coords[k]
        cx, cy = coords[k + 1]
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        n1 = math.hypot(v1x, v1y)
        n2 = math.hypot(v2x, v2y)
        straight = (n1 > 1e-6 and n2 > 1e-6
                    and (v1x * v2x + v1y * v2y) / (n1 * n2) >= cos_tol)
        if straight and half is not None \
                and _max_chord_deviation(cur, cx, cy) > half:
            straight = False               # bows off its own chord
        if straight:
            cur.append((cx, cy))
        else:
            runs.append(cur)
            cur = [(bx, by), (cx, cy)]
    runs.append(cur)
    return runs


def _rect_from_endpoints(ax: float, ay: float, bx: float, by: float,
                         width: float) -> tuple[Polygon, LineString] | None:
    """A 4-corner rect of ``width`` centred on A→B, corners in canonical
    ``[hi-left, lo-left, lo-right, hi-right]`` order, plus its axis."""
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    h = width / 2.0
    try:
        poly = Polygon([
            (ax + nx * h, ay + ny * h),
            (bx + nx * h, by + ny * h),
            (bx - nx * h, by - ny * h),
            (ax - nx * h, ay - ny * h),
        ])
        axis = LineString([(ax, ay), (bx, by)])
    except _GEOM_EXC:
        return None
    if poly.is_empty or not poly.is_valid:
        return None
    return poly, axis


def _line_of(entry):
    """The LineString of a centerline entry.

    Entries are ``apt_dat_reader.TaxiCenterline`` in a built layout and
    ``(LineString, name)`` tuples in fixtures / the OSM small-road path —
    both dialects have always reached this module, so the reader is
    stated once here instead of at each loop head.
    """
    if hasattr(entry, "line"):
        return entry.line
    return entry[0]


def _name_of(entry) -> str:
    if hasattr(entry, "line"):
        return getattr(entry, "name", "") or ""
    return entry[1]


def _width_of(entry, default: float) -> float:
    """§F5: the corridor width THIS entry states, else ``default``.

    THE PER-WAY WIDTH CHANNEL (LEMD ramp/road fidelity spec Amendment 1,
    ruling 2).  The minter used ONE width for every route —
    ``config.SERVICE_ROAD_WIDTH_M`` = 6.0 m — while the source states a
    width per way: at the owner's LEMD item-3 probe the road feed's way
    -2096 is ``highway=service lanes=4`` (14.0 m) and the emitted rect
    measured 5.93 m, so half the real carriageway drapes on raw DEM.
    That draped half is what the owner read as "very bumpy"; it is the
    SAME defect as "about half the width", not a second one.

    A width reaches this module the way a name already does, in whichever
    dialect the caller speaks: a ``width_m`` attribute on a
    ``TaxiCenterline``-like object, or a third element on the
    ``(LineString, name)`` tuple.  Nothing else changes: an entry that
    states NO width takes ``default``, so an untagged network emits
    byte-identically to before this channel existed — which is the
    ruling's own condition.
    """
    stated = getattr(entry, "width_m", None)
    if stated is None and isinstance(entry, (tuple, list)) \
            and len(entry) >= 3:
        stated = entry[2]
    try:
        value = float(stated)
    except (TypeError, ValueError):
        return default
    return value if value > 0.0 else default


def dedupe_service_sources(
        apt_centerlines: list,
        osm_centerlines: list,
        *,
        width: float,
        min_frac: float = 0.5,
) -> tuple[list, int]:
    """Suppress OSM small-road lines that merely RE-SPELL a 1206 route.

    Owner ruling 2026-08-12b: apt.dat 1206 truck routes are an
    AUTHORITATIVE service-corridor source; OSM small roads COMPLEMENT
    them.  Two spellings of one physical corridor must not both mint —
    the downstream rect-overlap skip catches only the rects that
    actually collide, leaving two centerlines (and therefore two spines)
    for one road.

    The test is at CENTERLINE level, before minting: an OSM line whose
    own length lies more than ``min_frac`` inside the ``width``-wide
    corridor of the 1206 set is dropped.  Returns
    ``(kept_osm_entries, n_suppressed)``; entry objects are returned
    UNCHANGED (identity preserved — the caller's names/refs travel with
    them).
    """
    if not apt_centerlines or not osm_centerlines:
        return list(osm_centerlines), 0
    half = width / 2.0
    apt_bufs = []
    for entry in apt_centerlines:
        line = _line_of(entry)
        if line is None or line.is_empty:
            continue
        try:
            apt_bufs.append(line.buffer(half, cap_style=2, join_style=2))
        except _GEOM_EXC:
            continue
    if not apt_bufs:
        return list(osm_centerlines), 0
    try:
        apt_corridor = unary_union(apt_bufs)
    except _GEOM_EXC:
        return list(osm_centerlines), 0
    try:
        from shapely.prepared import prep
        apt_prep = prep(apt_corridor)
    except _GEOM_EXC:                                    # pragma: no cover
        apt_prep = None
    kept, dropped = [], 0
    for entry in osm_centerlines:
        line = _line_of(entry)
        if line is None or line.is_empty or line.length <= 0.0:
            kept.append(entry)
            continue
        if apt_prep is not None and not apt_prep.intersects(line):
            kept.append(entry)
            continue
        try:
            inside = line.intersection(apt_corridor).length
        except _GEOM_EXC:
            kept.append(entry)
            continue
        if inside / line.length > min_frac:
            dropped += 1
            continue
        kept.append(entry)
    return kept, dropped


def mouth_fills(centerlines: list, pav_union, pav_buf, *,
                width: float) -> list[Polygon]:
    """The MOUTH fills: corridor pavement reaching the aircraft-pavement
    EDGE ITSELF, at every axis crossing / terminus into that pavement.

    A MOUTH IS A CROSSING OR A TERMINUS INTO PAVEMENT — nothing else.  It
    is located by the route's own CONTACT with ``pav_union``: only the
    stretch within ``_MOUTH_REACH_M`` (along the route) of where the axis
    actually meets aircraft pavement is filled.  A road running ALONGSIDE
    an edge inside the 1 m clearance never contacts the union, so it gets
    no fill and keeps its clearance for its whole run — the alternative
    (filling the annulus wherever the corridor is near pavement) would
    spray metre-wide slivers down every edge-parallel road.

    RULING 1 (corridor-joins round, Fable spec 2026-08-12c, on the owner's
    in-sim refutation at KCLT).  The minter cuts the corridor back from all
    aircraft pavement by ``_PAV_CLEAR_TOL_M`` = 1.0 m, while
    ``conformance`` welds only within ``SHARED_VERTEX_TOL_M`` = 0.5 m — so
    every road↔taxiway seam was UNWELDABLE BY CONSTRUCTION (measured 0.999 m
    at both KCLT sites), the annulus was filled by a graded_strip carrying
    both claims, and no node anywhere was shared between the road family and
    the taxiway family.

    So at the mouths — and ONLY there — the corridor is carried across that
    annulus: for each piece of a route that lies inside ``pav_buf``, the
    stretch of it within ``_MOUTH_REACH_M`` of the buffer's own boundary is
    buffered to the corridor width and clipped to ``pav_buf − pav_union``.
    The result's boundary follows the PAVEMENT EDGE (the difference is taken
    against ``pav_union``, not the buffered union), so the corridor's own
    boundary nodes land ON the airside edge inside weld reach and
    ``enforce_conformance`` splices them into the airside ring: shared nodes,
    ONE altitude at the seam.

    CONFINED TO THE ANNULUS BY CONSTRUCTION.  Every fill is intersected with
    ``pav_buf`` and differenced against ``pav_union``, so a fill can neither
    overlay aircraft pavement (the double-paving ruling) nor escape into the
    open ground the corridor BODY already covers at its 1.0 m clearance —
    which is why the body's mid-run clearance is untouched by this pass.

    Returns the fill polygons (possibly empty); the caller unions them into
    the corridor before the rect/junction split, so they emit as ordinary
    ``service_junction`` fill under the road cap.
    """
    if pav_union is None or pav_buf is None:
        return []
    from shapely.ops import substring
    try:
        from shapely.prepared import prep
        pav_prep = prep(pav_union)
    except _GEOM_EXC:                                    # pragma: no cover
        pav_prep = None
    out: list[Polygon] = []
    for entry in centerlines:
        line = _line_of(entry)
        # §F5: the fill spans the clearance at the ROUTE's own width, so
        # a 14 m road's mouth is not carried across on a 6 m stub.
        half = _width_of(entry, width) / 2.0
        if line is None or line.is_empty or line.length <= 0.0:
            continue
        if pav_prep is not None and not pav_prep.intersects(line):
            continue                     # never reaches pavement → no mouth
        try:
            contact = line.intersection(pav_union)
        except _GEOM_EXC:
            continue
        stubs: list = []
        for piece in _as_linestrings(contact):
            if piece.is_empty:
                continue
            try:
                ss = sorted(line.project(Point(c))
                            for c in (piece.coords[0], piece.coords[-1]))
            except _GEOM_EXC:                            # pragma: no cover
                continue
            # …the run of route on EACH side of the contact, out to the
            # mouth reach: the stretch that actually spans the clearance.
            for (a, b) in ((ss[0] - _MOUTH_REACH_M, ss[0]),
                           (ss[1], ss[1] + _MOUTH_REACH_M)):
                a, b = max(0.0, a), min(line.length, b)
                if b - a <= 1e-9:
                    continue
                try:
                    stub = substring(line, a, b)
                except _GEOM_EXC:                        # pragma: no cover
                    continue
                if (stub is not None and not stub.is_empty
                        and stub.geom_type == "LineString"):
                    stubs.append(stub)
        for stub in stubs:
            try:
                fill = (stub.buffer(half, cap_style=2, join_style=2)
                        .intersection(pav_buf)
                        .difference(pav_union))
            except _GEOM_EXC:                            # pragma: no cover
                continue
            for poly in _as_polygons(fill):
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if (poly is None or poly.is_empty
                        or poly.geom_type != "Polygon"
                        or poly.area < _MIN_JUNCTION_AREA_M2):
                    continue
                out.append(poly)
    return out


def build_service_road_network(
        centerlines: list,
        pav_union: Polygon | None,
        *,
        width: float,
        min_len: float,
        mouth_join: bool | None = None,
        covered_span=None,
) -> tuple[list[tuple[Polygon, LineString, str, str]],
           list[tuple[Polygon, str, str]]]:
    """Build the ground-vehicle network from ``centerlines``
    (``TaxiCenterline`` objects, or ``(LineString_m, name)`` tuples).

    Returns ``(rects, junctions)``:
      * ``rects``     = ``[(rect, axis, ROLE_SERVICE_ROAD, name)]``
      * ``junctions`` = ``[(polygon, ROLE_SERVICE_JUNCTION, name)]``

    Only the portions of each route OUTSIDE aircraft pavement
    (``pav_union``) contribute.  Rects cover straight runs (trimmed back
    from bends / ends so they never overlap); junctions are the corridor
    residue (``corridor − rects``) at bends and intersections.  Width is
    the synthesised ``config.SERVICE_ROAD_WIDTH_M`` (most service roads
    have no pavement polygon).

    ``mouth_join`` (default ``config.SERVICE_CORRIDOR_MOUTH_JOIN``) adds the
    MOUTH fills of :func:`mouth_fills` to the corridor before the split, so
    the corridor JOINS aircraft pavement at its mouths (ruling 1) while its
    body keeps the 1.0 m clearance.  ``False`` restores the unweldable gap.

    ``covered_span`` (§T7) is the COVERED-SPAN MASK: the ground the
    mapped bores' roofed stretches occupy.  NEITHER a rect NOR a fill is
    minted inside it — a corridor synthesised over a roofed bore is a
    road on the tunnel's roof, and the measured population is 22 such
    pieces across two airports.  It is subtracted from the corridor
    exactly as ``pav_union`` is, so this pass has ONE way of saying
    "not here" rather than two.  Authored pavement never reaches this
    function, so the mask can only kill synthesis.
    """
    if mouth_join is None:
        from ..config import SERVICE_CORRIDOR_MOUTH_JOIN
        mouth_join = SERVICE_CORRIDOR_MOUTH_JOIN
    rects: list[tuple[Polygon, LineString, str, str]] = []
    junctions: list[tuple[Polygon, str, str]] = []
    if not centerlines:
        return rects, junctions

    covered = (covered_span
               if covered_span is not None and not covered_span.is_empty
               else None)
    pav_buf = None
    pav_prep = None
    if pav_union is not None and not pav_union.is_empty:
        try:
            from shapely.prepared import prep
            pav_buf = pav_union.buffer(_PAV_CLEAR_TOL_M)
            pav_prep = prep(pav_buf)
        except _GEOM_EXC:
            pav_buf = None
            pav_prep = None

    # External (off-pavement) centerline pieces.  Most service roads are
    # already entirely off aircraft pavement — skip the expensive
    # difference() unless the road actually touches it (prepared check).
    # §F5: each piece carries ITS OWN width from here on.  ``width`` is
    # the DEFAULT for a route that states none, which is every route in
    # an untagged network — so those emit byte-identically.
    ext: list[tuple[LineString, str, float]] = []
    for line, name, own_w in ((_line_of(c), _name_of(c),
                               _width_of(c, width)) for c in centerlines):
        if line is None or line.is_empty:
            continue
        if pav_buf is not None and pav_prep.intersects(line):
            g = line.difference(pav_buf)
        else:
            g = line
        if covered is not None:
            try:
                g = g.difference(covered)
            except _GEOM_EXC:                            # pragma: no cover
                pass
        for piece in _as_linestrings(g):
            if piece.length >= 1.0:
                ext.append((piece, name, own_w))
    if not ext:
        return rects, junctions

    # Corridor = per-route-width buffer of every external piece, clipped
    # to stay off aircraft pavement.  Flat caps / mitre joins keep it
    # tight to the routes.
    try:
        corridor = unary_union(
            [p.buffer(w / 2.0, cap_style=2, join_style=2)
             for p, _n, w in ext])
        if pav_buf is not None:
            corridor = corridor.difference(pav_buf)
        if covered is not None:
            corridor = corridor.difference(covered)
        if not corridor.is_valid:
            corridor = corridor.buffer(0)
    except _GEOM_EXC:
        return rects, junctions
    # MOUTH JOIN (ruling 1): carry the corridor across the clearance annulus
    # at its mouths only, so its boundary nodes land ON the airside edge.
    # The fills are confined to ``pav_buf − pav_union`` by construction, so
    # this can neither double-pave nor widen the body's clearance.
    if mouth_join and pav_buf is not None:
        fills = mouth_fills(centerlines, pav_union, pav_buf, width=width)
        if covered is not None and fills:
            fills = [f for f in fills
                     if f.intersection(covered).area <= 0.0]
        if fills:
            try:
                corridor = unary_union([corridor] + fills)
                if not corridor.is_valid:
                    corridor = corridor.buffer(0)
            except _GEOM_EXC:                            # pragma: no cover
                pass
    if corridor.is_empty:
        return rects, junctions

    # Rects on straight runs, trimmed back from each end by ``half`` so
    # adjacent runs / crossing roads don't overlap (the gap becomes
    # junction fill).  Skip a rect that would touch aircraft pavement or
    # an already-kept rect.
    kept_polys: list[Polygon] = []
    for piece, name, own_w in ext:
        half = own_w / 2.0
        coords = list(piece.coords)
        for run in _split_at_bends(coords, own_w):
            if len(run) < 2:
                continue
            ax, ay = run[0]
            bx, by = run[-1]
            seg_len = math.hypot(bx - ax, by - ay)
            if seg_len <= 2.0 * half:
                continue
            ux, uy = (bx - ax) / seg_len, (by - ay) / seg_len
            ax2, ay2 = ax + ux * half, ay + uy * half      # trim start
            bx2, by2 = bx - ux * half, by - uy * half      # trim end
            if math.hypot(bx2 - ax2, by2 - ay2) < min_len:
                continue
            built = _rect_from_endpoints(ax2, ay2, bx2, by2, own_w)
            if built is None:
                continue
            rect, axis = built
            try:
                if pav_buf is not None and rect.intersects(pav_buf):
                    continue                       # pokes into aircraft pavement
                if (covered is not None
                        and rect.intersection(covered).area > 0.0):
                    continue                       # stands on a bore's roof
                if any(rect.intersection(kp).area > 1.0 for kp in kept_polys):
                    continue                       # overlaps a kept rect
            except _GEOM_EXC:
                continue
            rects.append((rect, axis, ROLE_SERVICE_ROAD, name))
            kept_polys.append(rect)

    # Junctions = corridor − rects, keeping pieces above the sliver floor.
    try:
        residue = corridor
        if kept_polys:
            residue = corridor.difference(unary_union(kept_polys))
    except _GEOM_EXC:
        residue = corridor
    for poly in _as_polygons(residue):
        if poly.is_empty or not poly.is_valid:
            continue
        if poly.area >= _MIN_JUNCTION_AREA_M2:
            junctions.append((poly, ROLE_SERVICE_JUNCTION, "service"))

    return rects, junctions


# ──────────────────────────────────────────────────────────────────────
# (s79) ON-PAVEMENT road detection — docs/service_road_carve.md §2
# ──────────────────────────────────────────────────────────────────────
def detect_road_runs(
    routes: "list[tuple[LineString, str]]",
    pav_union,
    terminal_polys=None,
    runway_union=None,
    source_polys=None,
    *,
    max_width_m: float | None = None,
    terminal_clear_m: float | None = None,
    sample_m: float | None = None,
    min_run_m: float | None = None,
) -> "list[tuple[LineString, float, str]]":
    """Qualifying ROAD runs along apt.dat 1206 truck routes.

    ★ USER RULINGS (2026-06-11): roads are the 1206 LINES only; only
    pavement narrower than the cross-section cap is classified; nothing
    near a terminal.  A sample point on a merged route qualifies when

      (a) it lies ON pavement (``pav_union``),
      (b) EITHER the PERPENDICULAR pavement cross-section through it is
          ≤ ``ROAD_CARVE_MAX_WIDTH_M`` — a dedicated strip, not an apron
          interior (calibrated at the HECA #198 switchback: legs
          8.2-9.4 m / 12.2 m, the U-turn bulge 11-24 m stays junction
          territory) — OR the sample lies inside a NARROW SOURCE
          pavement polygon (mean width 2A/P ≤ the same cap): a road
          drawn as its own strip polygon that runs ALONG the edge of
          apron pavement blends into the fused union, so the chord
          reads road+apron (CYXY "New Taxiway 40" pav[1]: 11.5 m strip,
          chords 16-34 m — user-confirmed ROAD 2026-06-11),
      (c) it is ≥ ``ROAD_CARVE_TERMINAL_CLEAR_M`` from every terminal
          pad, and
      (d) it is outside the runway footprint + 3 m halo (the s69 carve
          lesson).

    Consecutive qualifying samples spanning ≥ ``ROAD_CARVE_MIN_RUN_M``
    become one run.  Returns ``[(run_centerline, median_width_m,
    route_name)]``; run centerlines are exact substrings of the input
    routes (bends preserved — the shared ``split_merged_centerline``
    downstream cuts them into straight rect axes + junction territory
    exactly like a taxiway).
    """
    from shapely.ops import substring
    from shapely.prepared import prep

    from ..config import (
        ROAD_CARVE_EDGE_HUG_MAX_M,
        ROAD_CARVE_MAX_WIDTH_M,
        ROAD_CARVE_MIN_RUN_M,
        ROAD_CARVE_SAMPLE_M,
        ROAD_CARVE_TERMINAL_CLEAR_M,
        ROAD_CARVE_TERMINAL_PARA_DEG,
        ROAD_CARVE_TERMINAL_RIM_M,
    )
    max_w = ROAD_CARVE_MAX_WIDTH_M if max_width_m is None else max_width_m
    term_clear = (ROAD_CARVE_TERMINAL_CLEAR_M
                  if terminal_clear_m is None else terminal_clear_m)
    step = ROAD_CARVE_SAMPLE_M if sample_m is None else sample_m
    min_run = ROAD_CARVE_MIN_RUN_M if min_run_m is None else min_run_m

    if pav_union is None or pav_union.is_empty or not routes:
        return []
    pav_prep = prep(pav_union)
    pav_boundary = pav_union.boundary

    # Terminal "ALONGSIDE" guard (user round 3): keep the terminal
    # polygons (not just a fused zone) so a flagged sample can compare
    # its route direction to the nearest terminal EDGE — only locally
    # parallel routes are curb roads to drop.
    term_list = [tp for tp in (terminal_polys or ())
                 if tp is not None and not tp.is_empty]
    term_zone = None
    if term_list:
        try:
            term_zone = unary_union(term_list).buffer(term_clear)
        except _GEOM_EXC:
            term_zone = None
    term_prep = prep(term_zone) if term_zone is not None \
        and not term_zone.is_empty else None

    def _alongside_terminal(p, dx, dy,
                            radius: float | None = None) -> bool:
        """True when ``p`` is within ``radius`` of a terminal AND the
        route runs locally parallel to the nearest terminal edge.
        Default radius = the close-in clear zone; mode C passes the
        larger TERMINAL_RIM radius (rim roads along the terminal row
        absorb into the apron — user round 4)."""
        if not term_list:
            return False
        if radius is None:
            if term_prep is None or not term_prep.contains(p):
                return False
        best_tp, best_d = None, float("inf")
        for tp in term_list:
            d9 = tp.exterior.distance(p)
            if d9 < best_d:
                best_d, best_tp = d9, tp
        if best_tp is None or (radius is not None and best_d > radius):
            return False
        # RADIAL test (robust on blobby pad rings, unlike a local ring
        # tangent): "alongside" = the route moves PERPENDICULAR to the
        # direction toward the terminal (i.e. parallel to its front).
        # A road heading at/away from the terminal (the HECA corner →
        # junction #168 section) is radial → keep.
        ring = best_tp.exterior
        q = ring.interpolate(ring.project(p))
        rx, ry = q.x - p.x, q.y - p.y
        rl = math.hypot(dx, dy) * math.hypot(rx, ry)
        if rl < 1e-9:
            return True          # degenerate: keep the old (drop) rule
        ang = math.degrees(math.acos(
            min(1.0, abs(dx * rx + dy * ry) / rl)))
        return ang >= (90.0 - ROAD_CARVE_TERMINAL_PARA_DEG)

    rwy_halo = None
    if runway_union is not None and not runway_union.is_empty:
        try:
            rwy_halo = runway_union.buffer(3.0)
        except _GEOM_EXC:
            rwy_halo = None
    rwy_prep = prep(rwy_halo) if rwy_halo is not None else None

    # Mode-B membership: NARROW source pavement polygons (a road drawn
    # as its own strip, mean width ≤ the cap).  Wide aprons never enter.
    narrow_srcs = []
    for sp in (source_polys or ()):
        if sp is None or sp.is_empty or sp.geom_type != "Polygon":
            continue
        try:
            if (sp.area >= 500.0
                    and 2.0 * sp.area / max(sp.boundary.length, 1e-9)
                    <= max_w):
                narrow_srcs.append((prep(sp), sp))
        except _GEOM_EXC:
            continue

    # Perpendicular probe half-length: a chord fully inside pavement
    # longer than 2*reach reads as "wide" regardless — keep reach just
    # above the width cap so the test stays cheap and unambiguous.
    reach = max_w + 4.0

    # APRON-CONNECTOR exemption (user 2026-06-26): a 1206 truck route that CONNECTS
    # the apron to a groundside lot is an SVC road CONNECTOR and must be carved (and
    # cut at both mouths), even where the alongside-terminal guard would drop it as a
    # curb road — "curbside is just groundside, it doesn't need its own class; a
    # truck route that never touches the apron just stays groundside."  A route is a
    # connector iff it CROSSES WIDE aircraft pavement (the apron: a perpendicular
    # chord through pavement ≫ a road width); a pure off-apron curb/parking road
    # never does, so it still drops to groundside.  The exemption only affects narrow
    # samples the terminal guard would otherwise drop (wide samples still fail the
    # width test), so it is safe.
    _connector_keep = _os.environ.get("O4_ROAD_CONNECTOR_KEEP", "1") == "1"
    _apron_reach = 1.5 * max_w + 4.0

    def _touches_apron(ls) -> bool:
        nn = max(1, int(ls.length // step))
        for tt in range(nn + 1):
            dd = min(tt * step, ls.length)
            pp = ls.interpolate(dd)
            if not pav_prep.contains(pp):
                continue
            a1 = ls.interpolate(max(dd - 2.0, 0.0))
            a2 = ls.interpolate(min(dd + 2.0, ls.length))
            adx, ady = a2.x - a1.x, a2.y - a1.y
            ah = math.hypot(adx, ady) or 1.0
            apx, apy = -ady / ah, adx / ah
            try:
                ac = LineString([(pp.x - _apron_reach * apx, pp.y - _apron_reach * apy),
                                 (pp.x + _apron_reach * apx, pp.y + _apron_reach * apy)])
                ai = ac.intersection(pav_union)
            except _GEOM_EXC:
                continue
            for pc in ([ai] if ai.geom_type == "LineString"
                       else [g for g in getattr(ai, "geoms", ())
                             if g.geom_type == "LineString"]):
                if pc.distance(pp) < 0.5 and pc.length > 1.5 * max_w:
                    return True
        return False

    out: "list[tuple[LineString, float, str]]" = []
    for ls, name in ((c.line, c.name) if hasattr(c, "line") else c
                     for c in routes):
        L = ls.length
        if L < min_run:
            continue
        connector = _connector_keep and _touches_apron(ls)
        n = max(1, int(L // step))
        flags: list[bool] = []
        widths: list[float] = []
        dists: list[float] = []
        offpav: list[bool] = []
        for t in range(n + 1):
            d0 = min(t * step, L)
            p = ls.interpolate(d0)
            p1 = ls.interpolate(max(d0 - 2.0, 0.0))
            p2 = ls.interpolate(min(d0 + 2.0, L))
            dx, dy = p2.x - p1.x, p2.y - p1.y
            ok = False
            w = float("inf")
            if (pav_prep.contains(p)
                    and (connector or not _alongside_terminal(p, dx, dy))
                    and (rwy_prep is None or not rwy_prep.contains(p))):
                h = math.hypot(dx, dy) or 1.0
                px, py = -dy / h, dx / h
                try:
                    chord = LineString([
                        (p.x - reach * px, p.y - reach * py),
                        (p.x + reach * px, p.y + reach * py)])
                    inter = chord.intersection(pav_union)
                except _GEOM_EXC:
                    inter = None
                pieces = []
                if inter is not None and not inter.is_empty:
                    pieces = ([inter] if inter.geom_type == "LineString"
                              else [g for g in getattr(inter, "geoms", ())
                                    if g.geom_type == "LineString"])
                for pc in pieces:
                    if pc.distance(p) < 0.5:
                        w = pc.length
                        ok = w <= max_w
                        break
                if not ok:
                    # Mode B: inside a narrow source strip polygon
                    # (edge-blended road — see docstring (b)).
                    for sprep, sp in narrow_srcs:
                        if sprep.contains(p):
                            w = min(w, 2.0 * sp.area
                                    / max(sp.boundary.length, 1e-9))
                            ok = True
                            break
                if not ok:
                    # Mode C: EDGE-HUGGING — near the airside rim the
                    # road is "not surrounded by apron" even when the
                    # cross-section blends wide (user round 3) — UNLESS
                    # it runs along the terminal row (rim radius test,
                    # user round 4: those absorb into the apron).
                    try:
                        gap = p.distance(pav_boundary)
                    except _GEOM_EXC:
                        gap = float("inf")
                    if (gap <= ROAD_CARVE_EDGE_HUG_MAX_M
                            and not _alongside_terminal(
                                p, dx, dy,
                                radius=ROAD_CARVE_TERMINAL_RIM_M)):
                        ok = True
                        w = min(w, max_w)
            dists.append(d0)
            flags.append(ok)
            widths.append(w)
            offpav.append(not pav_prep.contains(p))

        t0 = None
        for t in range(n + 2):
            on = t <= n and flags[t]
            if on and t0 is None:
                t0 = t
            elif not on and t0 is not None:
                d_start, d_end = dists[t0], dists[min(t - 1, n)]
                # CONNECTOR DEAD-END EXTENSION (user 2026-06-26): a connector run
                # that ends where the route exits pavement INTO the groundside
                # (the lot was subtracted from pav_union before the carve) stops ~a
                # road-width short, leaving a GAP to the groundside.  Extend the run
                # to the first off-pav sample (the groundside boundary) so the SVC
                # rect reaches it — the overlap-clip then makes the SVC road SHARE
                # an edge with the groundside (a cut, not a gap).  Only into off-pav
                # (the lot), never into a wide-apron interior.
                if connector:
                    if t <= n and offpav[t]:
                        d_end = dists[min(t, n)]
                    if t0 - 1 >= 0 and offpav[t0 - 1]:
                        d_start = dists[t0 - 1]
                if d_end - d_start >= min_run:
                    try:
                        run = substring(ls, d_start, d_end)
                    except _GEOM_EXC:
                        run = None
                    if run is not None and run.geom_type == "LineString" \
                            and run.length >= min_run:
                        ws = sorted(widths[t0:min(t - 1, n) + 1])
                        out.append((run, ws[len(ws) // 2] if ws else max_w, name))
                t0 = None

    # ── STRIP EXTENSION (user round 3): a 1206 road that ENTERS a
    # narrow apt.dat strip polygon continues as a road along the
    # strip's own medial axis even where the 1206 polyline stops
    # (CYXY "New Taxiway 40" ramp: 'Crew cars' drives ~97 m into the
    # 11.5 m strip and turns around; the ramp itself runs another
    # ~250 m).  Roads keep 1206 provenance — the strip must carry
    # ≥ 15 m of route to extend.
    if narrow_srcs:
        try:
            from .discovered_taxiways import (
                _flatten_lines, _medial_segments, _prune)
            from shapely.ops import linemerge
        except Exception:                              # pragma: no cover
            narrow_srcs = []
        run_union = None
        if out:
            try:
                run_union = unary_union([r for (r, _w, _n) in out])
            except _GEOM_EXC:
                run_union = None
        for sprep, sp in narrow_srcs:
            inside = 0.0
            touch_name = ""
            for ls, name in ((c.line, c.name) if hasattr(c, "line") else c
                             for c in routes):
                try:
                    li = ls.intersection(sp).length
                except _GEOM_EXC:
                    continue
                if li > inside:
                    inside, touch_name = li, name
            if inside < 15.0:
                continue
            mean_w = 2.0 * sp.area / max(sp.boundary.length, 1e-9)
            try:
                segs = _medial_segments(sp, 2.0, max_w / 2.0 + 2.0, 2.5)
                if not segs:
                    continue
                lanes = _prune(_flatten_lines(
                    linemerge(unary_union(segs))), 15.0)
            except _GEOM_EXC:
                continue
            if not lanes:
                continue
            merged9 = unary_union(lanes)
            try:
                merged9 = linemerge(merged9)
            except ValueError:
                pass                     # already a single LineString
            lane_cands = _flatten_lines(merged9)
            if not lane_cands:
                continue
            lane = max(lane_cands, key=lambda g: g.length)
            if lane.length < min_run:
                continue
            # drop the part already covered by a qualifying run
            ext = lane
            if run_union is not None:
                try:
                    rem = lane.difference(run_union.buffer(mean_w))
                    pieces9 = [g for g in _flatten_lines(rem)
                               if g.length >= min_run]
                    if not pieces9:
                        continue
                    ext = max(pieces9, key=lambda g: g.length)
                except _GEOM_EXC:
                    pass
            # terminal / runway guards still apply at the midpoint
            mid = ext.interpolate(0.5, normalized=True)
            c1 = ext.interpolate(max(ext.project(mid) - 2.0, 0.0))
            c2 = ext.interpolate(min(ext.project(mid) + 2.0, ext.length))
            if _alongside_terminal(mid, c2.x - c1.x, c2.y - c1.y):
                continue
            if rwy_prep is not None and rwy_prep.contains(mid):
                continue
            out.append((ext, mean_w, f"{touch_name}+strip"))
    return out


# ──────────────────────────────────────────────────────────────────────
# §F5 — THE STATED WIDTH, RE-ASSOCIATED TO A CORRIDOR COURSE
# ──────────────────────────────────────────────────────────────────────
#: §F5 gate (LEMD ramp/road fidelity spec Amendment 1, ruling 2).
#: DEFAULT ON.  OFF attaches no width to any course, and the minter then
#: takes ``config.SERVICE_ROAD_WIDTH_M`` for every route exactly as it did
#: before this channel existed — the byte-identical control arm.
_WAY_WIDTH_ENV = "O4_SERVICE_ROAD_WAY_WIDTH"

#: A corridor course must run within this of a tagged way to BE that way.
#: The courses are built from the feed's own geometry, so the match is
#: near-exact where it exists; this is the slack for the 1206 spelling of
#: the same road and for the linemerge that joins chains.
_WIDTH_ASSOCIATION_M = 8.0

#: Fraction of a course that must lie within :data:`_WIDTH_ASSOCIATION_M`
#: of the way before the way's width governs it.  A course that merely
#: touches a wide road at one end is not that road.
_WIDTH_ASSOCIATION_COVER = 0.5


def way_width_channel_enabled() -> bool:
    """§F5: does a corridor course carry the width its OSM way states?"""
    return _os.environ.get(_WAY_WIDTH_ENV, "1") == "1"


def attach_course_widths(courses: list, network, project, *,
                         default: float) -> list:
    """``[(line, name, width)]`` — each course paired with the width its
    own source way states, else ``default``.

    THE SOURCE IS THE PER-AIRPORT ROAD FEED (``osm_load.AirportRoadNetwork``,
    the same object ``bridges._load_tunnel_road_network`` merges for the
    tunnel walk), and the tag reader is the ENGINE's own
    ``bridges._carriageway_width_from_tags`` — imported, never re-spelled,
    so a ``lanes=`` or ``width=`` read here and one read at a portal can
    never disagree.  The courses themselves carry no tags (they are
    geometry stashed by the slice), so the association is GEOMETRIC, the
    same re-association ``bridges._mapped_osm_carriageway_width_m`` makes
    at a portal footprint: a way governs a course when at least
    :data:`_WIDTH_ASSOCIATION_COVER` of the course lies within
    :data:`_WIDTH_ASSOCIATION_M` of it, and the WIDEST such way wins.

    ``courses`` are ``(line, name)`` tuples in layout metres and
    ``project`` is the layout's own ``to_m(lon, lat)`` — using the
    layout's projection, never a private one, is what keeps the
    association in the frame the courses were built in.

    Returns the courses at ``default`` when the law is off, when there is
    no feed, or when nothing associates — so an airport whose feed states
    no width beyond the default emits BYTE-IDENTICALLY.
    """
    plain = [(line, name, default) for line, name in courses]
    if not way_width_channel_enabled() or not courses or network is None:
        return plain
    ways = getattr(network, "ways", None)
    nodes = getattr(network, "nodes", None)
    if not ways or not nodes:
        return plain
    try:
        from ..bridges import _carriageway_width_from_tags
    except ImportError:                                  # pragma: no cover
        return plain
    candidates = []
    for _wid, node_refs, tags in ways:
        if not tags or tags.get("highway") is None:
            continue
        stated = _carriageway_width_from_tags(tags.get("highway"), tags, 0.0)
        if stated <= 0.0 or abs(stated - default) < 1e-9:
            continue          # states nothing beyond what we already use
        pts = []
        for ref in node_refs:
            ll = nodes.get(ref)
            if ll is None:
                continue
            pts.append(project(ll[1], ll[0]))
        if len(pts) < 2:
            continue
        try:
            line = LineString(pts)
        except _GEOM_EXC:                                # pragma: no cover
            continue
        if line.is_empty:
            continue
        candidates.append((stated, line.buffer(
            _WIDTH_ASSOCIATION_M, cap_style=2, join_style=2)))
    if not candidates:
        return plain
    candidates.sort(key=lambda c: -c[0])                 # widest first
    out = []
    for line, name in courses:
        chosen = default
        if line is not None and not line.is_empty and line.length > 0.0:
            for stated, region in candidates:
                try:
                    covered = line.intersection(region).length
                except _GEOM_EXC:                        # pragma: no cover
                    continue
                if covered >= _WIDTH_ASSOCIATION_COVER * line.length:
                    chosen = stated
                    break                                # widest wins
        out.append((line, name, chosen))
    return out
