"""THE reach band's grid half — a LOOKUP accelerator, never the metric.

Owner ruling 2026-07-29 (spec ``rod-compose-and-band-single-source-spec.md``
§B): *"airside reachability never rides service roads or groundside; the
taxi route graph is the metric"*.  The band at a point is therefore

    band(x) = route value at x's nearest ROUTE ATTACHMENT
              ± the local OFF-ROUTE LEG to that attachment

where the route value comes from
``building_feasibility.spine_value_fields`` — anchor values propagated along
NON-SERVICE spine routes at the applicable caps, the same route metric as
the pair-pricing oracle and the seats' reachability ruling.

WHAT THIS MODULE USED TO DO, AND WHY IT WAS WRONG.  It propagated the anchor
VALUES through the paved grid itself:

    ceiling(x) = min over anchors a ( value_a + cap · d_pavement(x, a) )

— a min-plus envelope in an AREA metric.  Reach then flowed across any
pavement, so a service route drawn over AIRSIDE pavement (HECA maps its
terminal fabric as giant aprons with routes through them) short-circuited
the real taxi route: measured on the U-fixture
(``tests/test_service_spine_feasibility_exclusion.py``) ceiling 101.485 vs
the route-metric 110.5 — an 8.7 m UNDER-credit that biases building seats
LOW.  Its role-based domain guard only kept reach off service-road
PAVEMENT; it never consulted ``service_spine_pairs`` at all.  Same
area-vs-route class as the burial's pair web, on the seat side.

Method now:

1. Rasterize the pavement-with-holes union into a boolean mask at
   ``RASTER_REACH_BAND_CELL_M``; erode conservatively by ½ cell so the
   discrete domain ⊆ the true pavement and discrete legs never
   UNDER-estimate the true in-pavement distance.
2. Paint a per-cell longitudinal ``cap`` field for the LEG: the taxi cap
   (1.5 %) as the base, the narrow code-A/B cap (3 %) inside narrow taxi
   corridors — the same per-letter credit the band has always given.
3. Snap every VALUED spine node (the service-excluded field's node set) to
   its nearest paved cell: these are the route ATTACHMENTS.
4. ONE multi-source Dijkstra over the masked grid
   (:func:`solve_attachment_field`) assigns every paved cell its nearest
   attachment and the leg cost to it.
5. ``band(x, y)`` reads the cell's attachment value ± leg; an off-mask
   point reads the nearest paved cell within a bounded radius (distance
   transform), widened by ``APRON_MAX_GRADE × offset``, else ``None``
   (off-net — the local within-shape law governs it).

There is ONE band engine, so there is no selector: the
``O4_RASTER_REACH_BAND`` gate was deleted with the legacy paths.
``config.REACH_NO_SERVICE_SPINES`` stays — it gates the LAW, not the
engine.  The solve and the validator both build the band through
``building_feasibility.reach_band_unified``, which is now a thin wrapper
over this module.
"""

from __future__ import annotations

import math
import os
from typing import Callable, Optional, Tuple

import numpy as np

# Per-cell cap sentinels are the real grade caps (rise/run); imported lazily in
# the builder so the module stays import-light.

_INF = float("inf")


def resolve_seed_cell(members, cxs, cys, cap):
    """The seed interval of ONE cell from its coincident attachments —
    ``(ceiling, floor, collapsed)`` (spec kill-prep §3, gate
    ``config.BAND_SEED_EXACT``).

    ``members`` are ``(x, y, ceiling, floor, row, col)`` in the walk's
    deterministic (node-key sorted) order; every member of one call shares
    the cell, so the row/col of the first is the cell's.

    A cell holding ONE attachment returns that attachment's own interval —
    identical to the collapsing path, which is why the gate only ever
    changes collapsed cells.  A cell holding SEVERAL is the defect: the grid
    treats them as coincident and prices the route leg BETWEEN them at zero,
    so a low ceiling from one and a high floor from another manufacture an
    inversion of up to cap × 3√2 ≈ 0.064 m at a 3 m cell (HEAZ: four of four
    observed inversions reproduced this way).  Here ONE attachment AUTHORS
    the cell — the one nearest the cell CENTRE, ties by walk order — so the
    seed remains a route value AT an attachment, and every other attachment
    keeps its constraint RELAXED by the local cell cap × its straight-line
    distance to the author.  Straight-line distance under-prices the true
    in-pavement route leg, so the relaxation is conservative: a residual
    inversion under this rule is a genuine node-value inconsistency, not a
    grid artifact.
    """
    first = members[0]
    if len(members) == 1:
        return first[2], first[3], False
    ri0, ci0 = first[4], first[5]
    cx, cy = float(cxs[ci0]), float(cys[ri0])
    author = min(members, key=lambda m: math.hypot(m[0] - cx, m[1] - cy))
    cell_cap = float(cap[ri0][ci0]) if isinstance(cap, list) \
        else float(cap[ri0, ci0])
    ceiling, floor = author[2], author[3]
    for m in members:
        if m is author:
            continue
        slack = cell_cap * math.hypot(m[0] - author[0], m[1] - author[1])
        ceiling = min(ceiling, m[2] + slack)
        floor = max(floor, m[3] - slack)
    return ceiling, floor, True


def _local_cap_grids(layout, cxs, cys, paved, taxi_cap):
    """Per-cell longitudinal cap field over the paved cells.

    ``cxs``/``cys`` are the 1-D cell-centre coordinate axes; ``paved`` is the
    ``[nrows, ncols]`` boolean mask.  The BASE cap is the taxi cap (1.5 %): the
    reach ceiling at any pavement point is the runway value plus the climb along
    the taxi ROUTE to it (taxi cap), which the legacy ``_band_via`` also credits
    — a per-cell apron discount (1 %) instead makes the min-plus envelope prefer
    cheap apron shortcuts and read a spuriously tight apron ceiling that shifts
    the solve fixpoint (measured at CYXY: apron-1 % steered the solve to +40
    route_band; taxi-cap base gave −57).  Narrow (code-A/B) taxi-centerline
    corridors are then painted at the narrow cap (3 %) — the same per-letter
    credit the legacy band gives.  ``O4_RASTER_APRON_CAP`` overrides the base cap
    (experiment knob).  Returns ``float64[nrows, ncols]`` (0.0 off-mask)."""
    import shapely as _sh
    from shapely.ops import unary_union
    from auto_patch.config import (
        TAXI_MAX_GRADE_NARROW, taxi_grade_cap_for_letter)

    nrows, ncols = paved.shape
    base_cap = float(os.environ.get("O4_RASTER_APRON_CAP", taxi_cap))
    cap = np.where(paved, base_cap, 0.0)

    # Mesh of paved cell centres for the vectorised contains tests.
    gx, gy = np.meshgrid(cxs, cys)                 # [nrows, ncols]
    flat_x = gx[paved]
    flat_y = gy[paved]
    paved_ij = np.argwhere(paved)                  # rows of (r, c)

    def _paint(geom, value):
        if geom is None or geom.is_empty:
            return
        try:
            _sh.prepare(geom)
            hit = _sh.contains_xy(geom, flat_x, flat_y)
        except Exception:                          # pragma: no cover
            return
        rr = paved_ij[hit, 0]
        cc = paved_ij[hit, 1]
        cap[rr, cc] = value

    # Narrow (code-A/B) taxi corridors: paint per-SEGMENT so a route that
    # changes width along its length credits 3 % only where it is narrow (the
    # same ``cl.size_at_arc`` cap the legacy band's foot climb reads).
    narrow_bufs = []
    half_w = 7.5                                   # taxiway half-width corridor
    for cl in (getattr(layout, "apt_taxi_centerlines", None) or []):
        line = getattr(cl, "line", None)
        if line is None or line.is_empty or getattr(cl, "is_service", False):
            continue
        coords = list(line.coords)
        acc = 0.0
        for i in range(len(coords) - 1):
            (x0, y0), (x1, y1) = coords[i], coords[i + 1]
            seg_len = math.hypot(x1 - x0, y1 - y0)
            mid = acc + 0.5 * seg_len
            acc += seg_len
            try:
                letter = cl.size_at_arc(mid)
            except Exception:                      # pragma: no cover
                letter = ""
            if taxi_grade_cap_for_letter(letter) != TAXI_MAX_GRADE_NARROW:
                continue
            seg = _sh.LineString([(x0, y0), (x1, y1)])
            narrow_bufs.append(seg.buffer(half_w))
    if narrow_bufs:
        try:
            _paint(unary_union(narrow_bufs), TAXI_MAX_GRADE_NARROW)
        except Exception:                          # pragma: no cover
            pass

    return cap


def _domain_geom(layout):
    """The reach-field PROPAGATION domain: the airside pavement the band governs
    (taxi rects, aprons, junctions, cross-connectors, stubs), the runway and its
    crossings, and building pads — buffered ½ m to bridge weld seams.  The runway
    IS included: measured across SPJC/CYXY the extra cross-runway connectivity
    lowers CYXY route_band by a further ~28 (−57 vs −29) with no SPJC change, and
    it lets the geodesic route through runway-crossing regions the way the legacy
    spine graph does.  Returns ``(prepared, raw)`` or ``(None, None)``."""
    from shapely.ops import unary_union
    from shapely.prepared import prep
    from auto_patch.elevation_per_surface.building_feasibility import _VIS_BUFFER_M
    from auto_patch.layout import (
        ROLE_APRON, ROLE_BUILDING, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
        ROLE_PRIMARY_PARALLEL, ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
        ROLE_SECONDARY_PARALLEL, ROLE_STUB)
    domain_roles = frozenset({
        ROLE_APRON, ROLE_JUNCTION, ROLE_PRIMARY_PARALLEL,
        ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
        ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_BUILDING})
    polys = [s.polygon for s in layout.shapes
             if s.role in domain_roles and s.polygon is not None
             and not s.polygon.is_empty]
    if not polys:
        return None, None
    try:
        raw = unary_union(polys).buffer(_VIS_BUFFER_M)
    except Exception:                                      # pragma: no cover
        try:
            raw = unary_union([p.buffer(0) for p in polys]).buffer(_VIS_BUFFER_M)
        except Exception:
            return None, None
    if raw.is_empty:
        return None, None
    return prep(raw), raw


def _grid_edges(paved, cap, cell, connectivity=8):
    """The masked pavement grid graph.

    Returns ``(rows, cols, data, n_paved, cell_id)``: one undirected edge per
    unique 8- (or 16-) neighbour offset between paved cells, weighted
    ``mean-cap · Euclidean-step · cell``; ``cell_id`` is the row-major rank
    of each paved cell (``-1`` off-mask).  Extracted so the propagation
    core has exactly ONE definition of the grid metric."""
    nrows, ncols = paved.shape
    cell_id = np.full((nrows, ncols), -1, dtype=np.int64)
    paved_flat = paved.ravel()
    n_paved = int(paved_flat.sum())
    if n_paved == 0:
        return (np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64),
                np.empty(0, dtype=float), 0, cell_id)
    cell_id.ravel()[paved_flat] = np.arange(n_paved, dtype=np.int64)

    offsets = [(0, 1, 1.0), (1, 0, 1.0),
               (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0))]
    knight = [(1, 2), (2, 1), (2, -1), (1, -2)]
    rows_all, cols_all, data_all = [], [], []

    def _add_edges(dr, dc, step, require_mids=None):
        rs = slice(max(0, -dr), nrows - max(0, dr))
        cs = slice(max(0, -dc), ncols - max(0, dc))
        src = cell_id[rs, cs]
        dst = cell_id[rs.start + dr:rs.stop + dr, cs.start + dc:cs.stop + dc]
        both = (src >= 0) & (dst >= 0)
        if require_mids is not None:
            for (mr, mc) in require_mids:
                both = both & paved[rs.start + mr:rs.stop + mr,
                                    cs.start + mc:cs.stop + mc]
        cap_s = cap[rs, cs][both]
        cap_d = cap[rs.start + dr:rs.stop + dr,
                    cs.start + dc:cs.stop + dc][both]
        rows_all.append(src[both])
        cols_all.append(dst[both])
        data_all.append(0.5 * (cap_s + cap_d) * (step * cell))

    for (dr, dc, step) in offsets:
        _add_edges(dr, dc, step)
    if int(connectivity) >= 16:
        for (dr, dc) in knight:
            step = math.sqrt(dr * dr + dc * dc)
            mids = [(int(np.sign(dr)) if abs(dr) == 2 else 0,
                     int(np.sign(dc)) if abs(dc) == 2 else 0),
                    (dr - (int(np.sign(dr)) if abs(dr) == 2 else 0),
                     dc - (int(np.sign(dc)) if abs(dc) == 2 else 0))]
            _add_edges(dr, dc, step, require_mids=mids)

    rows = (np.concatenate(rows_all) if rows_all
            else np.empty(0, dtype=np.int64))
    cols = (np.concatenate(cols_all) if cols_all
            else np.empty(0, dtype=np.int64))
    data = (np.concatenate(data_all) if data_all
            else np.empty(0, dtype=float))
    return rows, cols, data, n_paved, cell_id


def solve_attachment_field(paved, cap, seed_cells, cell, connectivity=8):
    """Nearest-ATTACHMENT assignment over the masked pavement grid.

    ROUTE METRIC, NOT AREA METRIC (owner ruling 2026-07-29; spec
    rod-compose-and-band-single-source §B).  The reach VALUE is propagated
    on the taxi route graph by
    ``building_feasibility.spine_value_fields`` — never here.  This grid
    answers only the two LOOKUP questions the band needs at a point:

        which route ATTACHMENT (spine node) serves this cell, and what
        does the LOCAL OFF-ROUTE LEG to it cost?

    The predecessor of this function propagated the anchor VALUES through
    the grid — a min-plus envelope in an AREA metric.  That is what let a
    service route drawn across apron pavement short-circuit a 700 m taxi
    route (U-fixture: ceiling 101.485 vs the route-metric 110.5, an 8.7 m
    UNDER-credit that biases building seats LOW — exactly HECA's shape).
    Assigning each cell to its NEAREST attachment cannot short-circuit:
    the route price is read off the graph, and the grid only pays for
    leaving the route.

    ``paved`` (``bool[nrows, ncols]``), ``cap`` (``float[nrows, ncols]``
    local longitudinal cap, 0 off-mask), ``seed_cells`` (iterable of paved
    cell ids — the attachments), ``cell`` (metres), ``connectivity``
    (8 or 16).

    Returns ``(leg, source)``: ``float64[nrows, ncols]`` leg cost (``inf``
    off-mask or unreachable from every attachment) and
    ``int64[nrows, ncols]`` the winning attachment's cell id (``-1`` where
    the leg is ``inf``)."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra

    nrows, ncols = paved.shape
    rows, cols, data, n_paved, cell_id = _grid_edges(
        paved, cap, cell, connectivity)
    leg = np.full(nrows * ncols, _INF)
    source = np.full(nrows * ncols, -1, dtype=np.int64)
    seeds = np.fromiter(sorted({int(c) for c in seed_cells}),
                        dtype=np.int64)
    if n_paved == 0 or seeds.size == 0:
        return leg.reshape(nrows, ncols), source.reshape(nrows, ncols)

    M = csr_matrix((data, (rows, cols)), shape=(n_paved, n_paved))
    # ``min_only`` settles ONE multi-source pass and reports, per node, the
    # SOURCE that reached it — the argmin the value lookup needs (a plain
    # super-source pass would give the distance but lose the identity).
    dist, _pred, src = dijkstra(M, directed=False, indices=seeds,
                               return_predecessors=True, min_only=True)
    paved_flat = paved.ravel()
    leg[paved_flat] = dist
    source[paved_flat] = src
    source[~np.isfinite(leg)] = -1
    return leg.reshape(nrows, ncols), source.reshape(nrows, ncols)


def build_raster_reach_band(layout, G) -> Optional[Callable[
        [float, float], "Tuple[float, float] | None"]]:
    """Build THE reach band ``band(x, y) -> (floor, ceiling) | None``.

    VALUE comes from the ROUTE metric
    (``building_feasibility.spine_value_fields``: anchor values propagated
    along NON-SERVICE spine routes at the applicable caps); this grid
    supplies only the LOOKUP — the nearest route attachment and the local
    off-route leg to it (:func:`solve_attachment_field`).

    Returns ``None`` when no field can be built (no anchors, no pavement,
    empty mask, or the grid exceeds ``RASTER_REACH_BAND_MAX_CELLS``).  There
    is no fallback engine to hand off to — the caller reports off-net."""
    from scipy.ndimage import distance_transform_edt
    import shapely as _sh
    from auto_patch.config import (
        APRON_MAX_GRADE, TAXI_MAX_GRADE, RASTER_REACH_BAND_CELL_M,
        RASTER_REACH_BAND_CONNECTIVITY, RASTER_REACH_BAND_OFFNET_RADIUS_M,
        RASTER_REACH_BAND_MAX_CELLS)
    from auto_patch.elevation_per_surface.building_feasibility import (
        spine_value_fields)

    if not getattr(G, "pos", None):
        return None
    # ROUTE-METRIC value fields, service-excluded.  A node reachable only
    # through ``service_spine_pairs`` gets no entry, so it never becomes an
    # attachment — the same filter the legacy value-field path honoured.
    ceil_val, floor_val = spine_value_fields(layout, G)
    if not ceil_val:
        return None

    # Pavement-with-holes PROPAGATION domain (runway interior excluded — see
    # :func:`_domain_geom`).
    _prep, geom = _domain_geom(layout)
    if geom is None or geom.is_empty:
        return None

    cell = float(RASTER_REACH_BAND_CELL_M)
    minx, miny, maxx, maxy = geom.bounds
    # Fixed grid origin (determinism): snap the origin DOWN to a cell multiple so
    # the same airport always rasterizes onto the same lattice.
    x0 = math.floor(minx / cell) * cell - cell
    y0 = math.floor(miny / cell) * cell - cell
    ncols = int(math.ceil((maxx - x0) / cell)) + 2
    nrows = int(math.ceil((maxy - y0) / cell)) + 2
    if ncols <= 0 or nrows <= 0:
        return None
    if ncols * nrows > RASTER_REACH_BAND_MAX_CELLS:
        try:
            import O4_UI_Utils as _UI
            _UI.vprint(1, f"  [raster-reach-band] grid {nrows}x{ncols} "
                          f"({nrows * ncols} cells) exceeds cap "
                          f"{RASTER_REACH_BAND_MAX_CELLS}; no band")
        except Exception:                          # pragma: no cover
            pass
        return None

    cxs = x0 + (np.arange(ncols) + 0.5) * cell
    cys = y0 + (np.arange(nrows) + 0.5) * cell

    # Raw paved mask: cell centre inside the union.  One vectorised call over the
    # whole grid (chunked to bound peak memory of the coordinate arrays).
    gx, gy = np.meshgrid(cxs, cys)                 # [nrows, ncols]
    try:
        _sh.prepare(geom)
        raw = _sh.contains_xy(geom, gx.ravel(), gy.ravel()).reshape(nrows, ncols)
    except Exception:                              # pragma: no cover
        return None
    if not raw.any():
        return None

    # Conservative ½-cell erosion (discrete domain ⊆ true pavement): a cell stays
    # paved only if the union still contains its centre after shrinking inward by
    # ½ cell.  A thin corridor (≥3 cells wide by construction) survives.
    try:
        eroded_geom = geom.buffer(-0.5 * cell)
    except Exception:                              # pragma: no cover
        eroded_geom = None
    if eroded_geom is not None and not eroded_geom.is_empty:
        try:
            _sh.prepare(eroded_geom)
            paved = raw & _sh.contains_xy(
                eroded_geom, gx.ravel(), gy.ravel()).reshape(nrows, ncols)
        except Exception:                          # pragma: no cover
            paved = raw
    else:
        paved = raw
    if not paved.any():
        paved = raw                                # erosion closed everything

    # Per-cell cap field.
    cap = _local_cap_grids(layout, cxs, cys, paved, TAXI_MAX_GRADE)

    # Contiguous paved-cell indexing (row-major, deterministic).
    cell_id = np.full((nrows, ncols), -1, dtype=np.int64)
    paved_flat = paved.ravel()
    n_paved = int(paved_flat.sum())
    cell_id.ravel()[paved_flat] = np.arange(n_paved, dtype=np.int64)

    # ATTACHMENT CELLS: every spine node that CARRIES a route value (the
    # service-excluded field's node set — a service-only node has no entry
    # and therefore never becomes an attachment), snapped to its nearest
    # paved cell.  ``distance_transform_edt`` gives, for EVERY cell, the
    # nearest paved cell, so a node landing just off the eroded mask still
    # attaches to the pavement it lies on.  Per cell the CEILING takes the
    # min value and the FLOOR the max — the tightest interval the
    # coincident attachments justify.
    inv = ~paved
    edt_cells, edt_idx = distance_transform_edt(
        inv, return_indices=True) if inv.any() else (
            np.zeros((nrows, ncols)), None)
    seed_ceil: dict = {}                           # cell_id -> min ceiling
    seed_floor: dict = {}                          # cell_id -> max floor
    n_seeded = 0
    # SEED-CELL EXACTNESS (config.BAND_SEED_EXACT, spec kill-prep §3): with
    # the gate on, the coincident attachments of one cell are resolved AFTER
    # the walk so the intra-cell route leg between them can be priced —
    # collapsing them here prices it at ZERO and manufactures inversions up
    # to cap × 3√2.  ``pending`` keeps the per-cell candidates in the same
    # deterministic node order the loop walks.
    from auto_patch.config import BAND_SEED_EXACT as _SEED_EXACT
    pending: dict = {}
    # WHICH ROUTE NODES SEED WHICH CELL — write-only provenance for the
    # ``band.attachment_at`` diagnostic below (cycle-5 instrument-fix item 4:
    # ``tools/trace_reach_route.py`` must answer "which attachment serves this
    # point" FROM the band, not by re-deriving the lookup).  Nothing in the
    # field reads it; ``seed_ceil`` / ``seed_floor`` / ``leg`` / ``source`` are
    # byte-identical with or without it.
    cell_nodes: dict = {}
    cell_rc: dict = {}
    for k in sorted(ceil_val):                     # sorted() for determinism
        p = G.pos.get(k)
        if p is None:
            continue
        cv = float(ceil_val[k])
        fv = float(floor_val.get(k, cv))
        ci = int(round((p[0] - x0) / cell - 0.5))
        ri = int(round((p[1] - y0) / cell - 0.5))
        if not (0 <= ri < nrows and 0 <= ci < ncols):
            continue
        if not paved[ri, ci]:
            if edt_idx is None:
                continue
            ri2 = int(edt_idx[0, ri, ci])
            ci2 = int(edt_idx[1, ri, ci])
            if not paved[ri2, ci2]:
                continue
            ri, ci = ri2, ci2
        cid = int(cell_id[ri, ci])
        if cid < 0:
            continue
        cell_nodes.setdefault(cid, []).append(int(k))
        cell_rc[cid] = (ri, ci)
        if _SEED_EXACT:
            pending.setdefault(cid, []).append(
                (float(p[0]), float(p[1]), cv, fv, ri, ci))
            n_seeded += 1
            continue
        seed_ceil[cid] = min(seed_ceil.get(cid, _INF), cv)
        seed_floor[cid] = max(seed_floor.get(cid, -_INF), fv)
        n_seeded += 1
    n_collapsed_cells = 0
    for cid, members in pending.items():
        cv, fv, collapsed = resolve_seed_cell(members, cxs, cys, cap)
        seed_ceil[cid] = cv
        seed_floor[cid] = fv
        n_collapsed_cells += int(collapsed)
    if _SEED_EXACT:   # loud is law (O4_RASTER_REACH_BAND_QUIET deleted)
        try:
            import O4_UI_Utils as _UIseed
            _UIseed.vprint(1,
                f"  [raster-reach-band] seed-exact: {n_collapsed_cells} of "
                f"{len(pending)} seeded cell(s) hold >1 attachment; their "
                f"intra-cell legs priced at the local cap.")
        except Exception:                          # pragma: no cover
            pass
    if not seed_ceil:
        return None

    # ONE grid pass: nearest attachment + its off-route leg cost.
    leg, source = solve_attachment_field(
        paved, cap, seed_ceil.keys(), cell,
        connectivity=int(RASTER_REACH_BAND_CONNECTIVITY))

    # band = route value AT the attachment ± the local off-route leg.
    sc = np.full(max(n_paved, 1), _INF)
    sf = np.full(max(n_paved, 1), -_INF)
    for cid, v in seed_ceil.items():
        sc[cid] = v
    for cid, v in seed_floor.items():
        sf[cid] = v
    ceiling = np.full((nrows, ncols), _INF)
    floor = np.full((nrows, ncols), -_INF)
    have = source >= 0
    if have.any():
        ceiling[have] = sc[source[have]] + leg[have]
        floor[have] = sf[source[have]] - leg[have]

    # Off-mask nearest-paved lookup (bounded radius) via the distance transform
    # already computed.  ``edt_cells`` is in CELL units.
    off_radius = float(RASTER_REACH_BAND_OFFNET_RADIUS_M)
    apron_cap = float(APRON_MAX_GRADE)

    def band(x, y):
        ci = int(round((x - x0) / cell - 0.5))
        ri = int(round((y - y0) / cell - 0.5))
        if not (0 <= ri < nrows and 0 <= ci < ncols):
            return None
        if paved[ri, ci]:
            c = ceiling[ri, ci]
            if not math.isfinite(c):
                return None                        # paved but unreachable → None
            return (float(floor[ri, ci]), float(c))
        if edt_idx is None:
            return None
        off = float(edt_cells[ri, ci]) * cell
        if off > off_radius:
            return None
        nr = int(edt_idx[0, ri, ci])
        nc = int(edt_idx[1, ri, ci])
        c = ceiling[nr, nc]
        if not math.isfinite(c):
            return None
        slack = apron_cap * off
        return (float(floor[nr, nc]) - slack, float(c) + slack)

    def attachment_at(x, y):
        """THE LOOKUP's own answer at ``(x, y)`` — read-only provenance.

        ``{"cell", "off_mask_m", "leg_m", "attachment_cell", "attachment_cid",
        "attachment_nodes", "ceiling_at_attachment", "floor_at_attachment"}``
        or ``None`` where :func:`band` itself answers ``None``.

        WHY IT IS HERE AND NOT IN THE TOOL (cycle-5 instrument-fix item 4).
        ``tools/trace_reach_route.py`` answers "which runway and spine bind
        this point" — and for a year it answered it by REPLAYING a retired
        nearest-visible-centerline engine, so it refused coordinates this band
        serves perfectly well (measured: it exits "point is not taxi-reachable
        from any runway contact" at a vertex whose band is (8.8941, 16.3459)).
        A tool that re-derives a lookup is a second engine; this hands out the
        one that ran.  It reads the closure's own arrays and mutates nothing.
        """
        ci0 = int(round((x - x0) / cell - 0.5))
        ri0 = int(round((y - y0) / cell - 0.5))
        if not (0 <= ri0 < nrows and 0 <= ci0 < ncols):
            return None
        off = 0.0
        ri, ci = ri0, ci0
        if not paved[ri, ci]:
            if edt_idx is None:
                return None
            off = float(edt_cells[ri, ci]) * cell
            if off > off_radius:
                return None
            ri = int(edt_idx[0, ri0, ci0])
            ci = int(edt_idx[1, ri0, ci0])
        cid = int(source[ri, ci])
        if cid < 0:
            return None
        return {
            "cell": (ri0, ci0),
            "query_cell_paved": bool(paved[ri0, ci0]),
            "off_mask_m": off,
            "leg_m": float(leg[ri, ci]),
            "attachment_cid": cid,
            "attachment_cell": cell_rc.get(cid),
            "attachment_nodes": list(cell_nodes.get(cid, ())),
            "ceiling_at_attachment": float(sc[cid]),
            "floor_at_attachment": float(sf[cid]),
            "cell_m": float(cell),
        }

    band.attachment_at = attachment_at              # type: ignore[attr-defined]

    # Diagnostics on the closure (opt-in probes; also read by the profile A/B).
    # The OFF-ROUTE LEG distribution is the honest measure of how much of the
    # band this grid is responsible for: a large leg means a cell far from any
    # route attachment, which is exactly where a route metric and an area
    # metric would disagree most.
    _finite_leg = leg[np.isfinite(leg)]
    if _finite_leg.size:
        _lq = [float(np.percentile(_finite_leg, q)) for q in (50, 95)]
        _lmax = float(_finite_leg.max())
    else:                                          # pragma: no cover
        _lq, _lmax = [0.0, 0.0], 0.0
    band.raster_meta = {                           # type: ignore[attr-defined]
        "nrows": nrows, "ncols": ncols, "cells": nrows * ncols,
        "paved_cells": n_paved, "cell_m": cell,
        "connectivity": int(RASTER_REACH_BAND_CONNECTIVITY),
        "anchors_seeded": n_seeded,
        "attachment_cells": len(seed_ceil),
        "unreached_paved_cells": int(n_paved - int(have.sum())),
        "leg_p50_m": _lq[0], "leg_p95_m": _lq[1], "leg_max_m": _lmax,
        "grid_bytes": int((ceiling.nbytes + floor.nbytes + paved.nbytes
                           + cap.nbytes + cell_id.nbytes)),
    }
    if True:       # loud is law (O4_RASTER_REACH_BAND_QUIET deleted)
        try:
            import O4_UI_Utils as _UI
            m = band.raster_meta
            _UI.vprint(1, f"  [reach-band] {nrows}x{ncols} @ {cell:.1f} m "
                          f"({n_paved} paved / {m['cells']} cells), "
                          f"{n_seeded} route attachment(s) in "
                          f"{m['attachment_cells']} cell(s), conn-"
                          f"{m['connectivity']}, off-route leg p50/p95/max "
                          f"{_lq[0]:.2f}/{_lq[1]:.2f}/{_lmax:.2f} m, "
                          f"{m['unreached_paved_cells']} paved cell(s) "
                          f"off-net, ~{m['grid_bytes'] // (1 << 20)} MB")
        except Exception:                          # pragma: no cover
            pass
    return band
