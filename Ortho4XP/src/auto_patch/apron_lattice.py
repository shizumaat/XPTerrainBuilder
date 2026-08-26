"""THE APRON INTERIOR LATTICE — §1b of
docs/specs/heca-apron-round2-spec.md (Amendment 1, 2026-08-25).

WHY THIS AND NOT §1's ROUTE SYNTHESIS.  §1 bridges a FEED GAP: two taxi
routes that end unconnected across continuous apron pavement.  That
premise was REFUTED at HECA by measurement — apt.dat nodes 462 and 470
are CONNECTED (a 560.6 m network path against 252.7 m straight, a 2.2x
detour) and neither is a leaf (degree 3 and 2).  The routes go AROUND
the apron.  Synthesizing a centerline there would invent taxi geometry
the airport does not have, so §1 stays as landed — correct for true feed
gaps, inert here.

THE VOID IS REAL ALL THE SAME.  The §2 instrument measured 10 nodeless
apron interiors at HECA, worst 175.4 m empty radius over 499,938 m2, and
the owner's cliff line carries 247 m with NO emitted station, dropping
6.06 m, pricing ZERO census rows.  What that ground needs is ANCHORS.

So: an apron polygon whose §2 EMPTY-DISK RADIUS exceeds
``config.APRON_NODELESS_RADIUS_M`` gains a sparse interior vertex
LATTICE at ``config.APRON_LATTICE_SPACING_M``, minted as FREE SOLVER
NODES carrying within-shape law edges to their lattice and ring
neighbours, priced by the apron's OWN caps.  No new roles, no routes, no
frontage semantics.

ONE MEASUREMENT, NOT TWO.  The trigger is literally the §2 instrument
(``nodeless_interior.largest_nodeless_disk``) — the lattice fires on
exactly the shapes the instrument flags.  A second private notion of
"is this apron empty" is the census-wrapper defect in miniature.

DETERMINISM.  The lattice is laid on the shape's OWN LOCAL FRAME — the
axes of its minimum rotated rectangle, origin at that rectangle's first
corner — so it is a function of the polygon alone: no build order, no
global grid phase, no dependence on which apron was processed first.
Points are clipped to the polygon and held a clear margin off the ring
so no lattice point can intern into a ring vertex's bucket.
"""
from __future__ import annotations

import math

import O4_UI_Utils as UI

from .geom_safe import min_rotated_rect

_GEOM_EXC = Exception

#: How far a lattice point must stand off the ring.  The canonical
#: registry interns within 0.5 m; this is an order clear of that, so a
#: lattice point can never merge into a ring vertex's bucket (the
#: identity-adoption path stays a belt-and-braces case, never the rule).
LATTICE_RING_MARGIN_M = 6.0


def _local_frame(poly):
    """``(origin, ux, uy)`` — the shape's OWN axes, from its minimum
    rotated rectangle.  A function of the polygon alone, so two builds
    of the same apron lay the same lattice."""
    try:
        rect = min_rotated_rect(poly)
        pts = list(rect.exterior.coords)[:4]
    except _GEOM_EXC:                                     # pragma: no cover
        return None
    if len(pts) < 4:                                      # pragma: no cover
        return None
    (ax, ay), (bx, by), (_cx, _cy), (dx, dy) = pts[:4]
    ex, ey = bx - ax, by - ay
    fx, fy = dx - ax, dy - ay
    le = math.hypot(ex, ey)
    lf = math.hypot(fx, fy)
    if le < 1e-6 or lf < 1e-6:                            # pragma: no cover
        return None
    return (ax, ay), (ex / le, ey / le), (fx / lf, fy / lf)


def lattice_points(poly, spacing_m, *, margin_m=LATTICE_RING_MARGIN_M):
    """The interior lattice for one polygon: points on the shape's own
    axes at ``spacing_m``, inside the polygon and at least ``margin_m``
    from its boundary.  Deterministically ordered (along the first axis,
    then the second) so the emitted polylines are stable."""
    from shapely.geometry import Point
    frame = _local_frame(poly)
    if frame is None:                                     # pragma: no cover
        return []
    (ox, oy), (ux, uy), (vx, vy) = frame
    try:
        interior = poly.buffer(-float(margin_m))
        if interior.is_empty:
            return []
        minx, miny, maxx, maxy = poly.bounds
    except _GEOM_EXC:                                     # pragma: no cover
        return []
    span = math.hypot(maxx - minx, maxy - miny)
    n = int(span / float(spacing_m)) + 2
    out: list = []
    for i in range(-n, n + 1):
        row: list = []
        for j in range(-n, n + 1):
            x = ox + (i * spacing_m) * ux + (j * spacing_m) * vx
            y = oy + (i * spacing_m) * uy + (j * spacing_m) * vy
            if not (minx <= x <= maxx and miny <= y <= maxy):
                continue
            try:
                if not interior.contains(Point(x, y)):
                    continue
            except _GEOM_EXC:                             # pragma: no cover
                continue
            row.append((i, j, float(x), float(y)))
        out.extend(row)
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def _rows_and_columns(pts):
    """The lattice's own adjacency: consecutive members of each row
    (same ``i``) and each column (same ``j``).  Returned as POLYLINES —
    the emission leg writes one way per run, and the census prices each
    consecutive pair."""
    by_i: dict = {}
    by_j: dict = {}
    for (i, j, x, y) in pts:
        by_i.setdefault(i, []).append((j, x, y))
        by_j.setdefault(j, []).append((i, x, y))
    lines: list = []
    for key in sorted(by_i):
        members = sorted(by_i[key])
        run: list = []
        prev = None
        for (j, x, y) in members:
            if prev is not None and j != prev + 1:
                if len(run) >= 2:
                    lines.append(run)
                run = []
            run.append((x, y))
            prev = j
        if len(run) >= 2:
            lines.append(run)
    for key in sorted(by_j):
        members = sorted(by_j[key])
        run: list = []
        prev = None
        for (i, x, y) in members:
            if prev is not None and i != prev + 1:
                if len(run) >= 2:
                    lines.append(run)
                run = []
            run.append((x, y))
            prev = i
        if len(run) >= 2:
            lines.append(run)
    return lines


def construct_apron_lattice_presolve(layout, *, spacing_m=None,
                                     radius_m=None, roles=("apron",)):
    """Build ``layout.apron_lattice_presolve`` — one entry per apron
    whose largest EMPTY interior disk exceeds ``radius_m``.

    Entry: ``{"shape", "shapeID", "points" [(x, y)], "lines"
    [[(x, y), ...]], "radius_m", "centre"}``.

    Called in the pipeline's FREEZE WINDOW slot (1), beside the gap-fill
    spine construction and BEFORE ``geometry_freeze.freeze`` — the
    lattice is plan geometry, so it must exist before the plan is
    frozen and the one node list is built.

    Flag OFF: no store, and every downstream leg is vacuous —
    byte-identical.
    """
    from . import config as _cfg
    from .nodeless_interior import largest_nodeless_disk
    if not getattr(_cfg, "APRON_INTERIOR_LATTICE", False):
        layout.apron_lattice_presolve = []
        return []
    if spacing_m is None:
        spacing_m = float(getattr(_cfg, "APRON_LATTICE_SPACING_M", 50.0))
    if radius_m is None:
        radius_m = float(getattr(_cfg, "APRON_NODELESS_RADIUS_M", 80.0))
    # THE VERTEX POPULATION the disk is measured against: every vertex
    # the plan carries at this point, from EVERY shape — an apron whose
    # interior is crossed by another shape's ring is not empty.  Same
    # question the §2 instrument asks at emit, asked of the plan.
    pts_all: list = []
    for s in (getattr(layout, "shapes", None) or ()):
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            if poly.geom_type != "Polygon":
                continue
            pts_all.extend((float(x), float(y))
                           for x, y in poly.exterior.coords)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
    tree = None
    if pts_all:
        try:
            from shapely.geometry import Point
            from shapely.strtree import STRtree
            tree = STRtree([Point(x, y) for (x, y) in pts_all])
        except Exception:                                 # pragma: no cover
            tree = None
    entries: list = []
    for idx, s in enumerate(getattr(layout, "shapes", None) or ()):
        if (getattr(s, "role", None) or "") not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            if poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        hit = largest_nodeless_disk(poly, tree, pts_all, radius_m)
        if hit is None:
            continue
        (cx, cy), r = hit
        grid = lattice_points(poly, spacing_m)
        if len(grid) < 1:
            continue
        entries.append({
            "shape": s, "shapeID": idx,
            "points": [(x, y) for (_i, _j, x, y) in grid],
            "lines": _rows_and_columns(grid),
            "radius_m": round(float(r), 2),
            "centre": (round(cx, 2), round(cy, 2))})
    layout.apron_lattice_presolve = entries
    if entries:
        n_pts = sum(len(e["points"]) for e in entries)
        n_lines = sum(len(e["lines"]) for e in entries)
        UI.vprint(1, f"  [apron-lattice] {len(entries)} apron(s) with an "
                     f"empty interior disk > {radius_m:g} m gained an "
                     f"interior lattice at {spacing_m:g} m: {n_pts} free "
                     f"solver node(s) in {n_lines} polyline(s) — the "
                     f"membrane the census could not see")
    return entries


def lattice_node_indices(layout, bucket_to_idx):
    """The solver node indices of every lattice point, resolved through
    the canonical registry — the set the scaffold seed re-seats as
    INTERIOR nodes."""
    cps = layout.canonical_points
    out: set = set()
    for entry in (getattr(layout, "apron_lattice_presolve", None) or ()):
        for (x, y) in entry.get("points", ()):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None:
                out.add(i)
    return out


def build_apron_lattice_constraints(layout, bucket_to_idx, ctx):
    """The within-shape constraint entry per latticed apron, and the
    LAW EDGES the census will be handed.

    THE LAW IS THE APRON'S OWN.  Edges are built through
    ``_grade_graph_edges`` on a ring that is the apron's exterior WITH
    its lattice points appended, so ``classify_pair`` prices every
    lattice/ring and lattice/lattice pair by the apron's caps — one law,
    the same one the ring pairs are priced by.  A private cap here would
    be the second authority the round exists to remove.

    Returns ``(sc_entries, lattice_idx, edge_records)``; ``edge_records``
    is the sidecar publication: ``{"a": [lat, lon], "b": [lat, lon],
    "budget_m": float, "shapeID": int}`` per priced edge.
    """
    from .elevation_per_surface.solver_primitives import (
        _grade_graph_edges, _open_ring, _stage_of_shape, _STAGE_KEY)
    from . import config as _cfg
    entries = getattr(layout, "apron_lattice_presolve", None) or []
    if not entries or not getattr(_cfg, "APRON_INTERIOR_LATTICE", False):
        return [], set(), []
    cps = layout.canonical_points
    sc_out: list = []
    lattice_idx: set = set()
    edge_records: list = []
    for entry in entries:
        s = entry.get("shape")
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        lat_pts = [(float(x), float(y)) for (x, y) in entry["points"]]
        coords = list(ring) + lat_pts
        idx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
               for (x, y) in coords]
        first_lat = len(ring)
        for i in idx[first_lat:]:
            if i is not None:
                lattice_idx.add(i)
        try:
            edges = _grade_graph_edges(s, coords, idx, ctx)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        # Keep only the edges the LATTICE introduces: the apron's own
        # ring pairs are already constrained by the shape's ordinary
        # within-shape entry, and stating them twice would hand the POCS
        # sweep two copies of one law.
        lat_set = {i for i in idx[first_lat:] if i is not None}
        keep = [(a, b, bud) for (a, b, bud) in edges
                if a in lat_set or b in lat_set]
        if not keep:
            continue
        pos = {i: coords[p] for p, i in enumerate(idx) if i is not None}
        node_list = sorted({a for (a, _b, _c) in keep}
                           | {b for (_a, b, _c) in keep})
        sc_out.append({"nodes": node_list, "edges": keep, "flat": False,
                       "flat_pairs": (), "area": 0.0,
                       "role": getattr(s, "role", "") or "apron",
                       _STAGE_KEY: _stage_of_shape(s),
                       "ref": "apron_lattice"})
        for (a, b, bud) in keep:
            pa, pb = pos.get(a), pos.get(b)
            if pa is None or pb is None:                  # pragma: no cover
                continue
            try:
                la = layout.m_to_ll(pa[0], pa[1])
                lb = layout.m_to_ll(pb[0], pb[1])
            except _GEOM_EXC:                             # pragma: no cover
                continue
            edge_records.append({
                "a": [round(float(la[0]), 11), round(float(la[1]), 11)],
                "b": [round(float(lb[0]), 11), round(float(lb[1]), 11)],
                "budget_m": round(float(bud), 6),
                "shapeID": entry.get("shapeID")})
    return sc_out, lattice_idx, edge_records
