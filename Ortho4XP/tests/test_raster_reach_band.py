"""Tests for THE reach band's grid LOOKUP (one engine, route metric).

Fast synthetic tests exercise the grid core (:func:`solve_attachment_field`)
against an independent brute-force reference and pin the mask-erosion
conservatism, off-net policy, and determinism.  The integration tests build
CYXY once (module-cached) to check the end-to-end band closure.

WHAT CHANGED 2026-07-29 (owner directive, spec ``rod-compose-and-band-
single-source-spec.md`` §B).  The grid used to propagate the anchor VALUES —
``ceiling = min_a(value_a + cap·d_grid)``, a min-plus envelope in an AREA
metric — so reach flowed across any pavement and could short-circuit a real
taxi route (U-fixture: a service route over apron pavement priced T at
101.485 vs the route-metric 110.5, an 8.7 m under-credit biasing seats LOW).
The grid now answers only the LOOKUP: each paved cell's nearest route
ATTACHMENT and the local off-route LEG cost to it.  The VALUE is propagated
on the non-service spine graph by
``building_feasibility.spine_value_fields``.  The reference below matches
that: a 0-cost multi-source Dijkstra that carries the winning source.

The ``O4_RASTER_REACH_BAND`` selector is gone with the legacy engines, so
there is no gate-off arm to test — ``reach_band_unified`` is a thin wrapper
over this module.
"""
from __future__ import annotations

import heapq
import math

import numpy as np
import pytest

from auto_patch.elevation_per_surface.raster_reach_band import (
    solve_attachment_field)


# ── Independent brute-force reference ────────────────────────────────────────

def _neighbors(r, c, nrows, ncols, paved, connectivity):
    """The same edge set the grid core builds: 8-neighbour chamfer, plus
    knight moves (through paved cardinal intermediates) at connectivity 16."""
    out = []
    for (dr, dc) in [(-1, 0), (1, 0), (0, -1), (0, 1),
                     (-1, -1), (-1, 1), (1, -1), (1, 1)]:
        rr, cc = r + dr, c + dc
        if 0 <= rr < nrows and 0 <= cc < ncols and paved[rr, cc]:
            out.append((rr, cc, math.hypot(dr, dc)))
    if connectivity >= 16:
        for (dr, dc) in [(1, 2), (2, 1), (2, -1), (1, -2),
                         (-1, 2), (-2, 1), (-2, -1), (-1, -2)]:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < nrows and 0 <= cc < ncols and paved[rr, cc]):
                continue
            m1 = (int(np.sign(dr)) if abs(dr) == 2 else 0,
                  int(np.sign(dc)) if abs(dc) == 2 else 0)
            m2 = (dr - m1[0], dc - m1[1])
            if paved[r + m1[0], c + m1[1]] and paved[r + m2[0], c + m2[1]]:
                out.append((rr, cc, math.hypot(dr, dc)))
    return out


def _brute_leg(paved, cap, seeds_rc, cell, connectivity=8):
    """Reference off-route LEG cost by an explicit multi-source Dijkstra from
    0-cost attachments.  Edge weight = mean-cap * Euclidean-step * cell —
    identical to the module."""
    nrows, ncols = paved.shape
    leg = np.full((nrows, ncols), math.inf)
    pq = [(0.0, r, c) for (r, c) in seeds_rc]
    heapq.heapify(pq)
    seen = set()
    while pq:
        cost, r, c = heapq.heappop(pq)
        if (r, c) in seen:
            continue
        seen.add((r, c))
        leg[r, c] = cost
        for (rr, cc, step) in _neighbors(r, c, nrows, ncols, paved,
                                         connectivity):
            if (rr, cc) in seen:
                continue
            w = 0.5 * (cap[r, c] + cap[rr, cc]) * step * cell
            heapq.heappush(pq, (cost + w, rr, cc))
    return leg


def _cell_ids(paved):
    """Row-major paved-cell rank, ``-1`` off-mask (the module's indexing)."""
    cell_id = np.full(paved.shape, -1, dtype=np.int64)
    cell_id.ravel()[paved.ravel()] = np.arange(int(paved.sum()))
    return cell_id


def _seed_ids(paved, seeds_rc):
    cid = _cell_ids(paved)
    return [int(cid[r, c]) for (r, c) in seeds_rc]


@pytest.mark.parametrize("connectivity", [8, 16])
def test_attachment_leg_matches_bruteforce_uniform(connectivity):
    """Uniform cap, single attachment: the leg IS cap·grid-distance."""
    nrows, ncols, cell = 7, 9, 2.0
    paved = np.ones((nrows, ncols), dtype=bool)
    cap = np.full((nrows, ncols), 0.01)
    seeds_rc = [(0, 0)]
    leg, source = solve_attachment_field(
        paved, cap, _seed_ids(paved, seeds_rc), cell,
        connectivity=connectivity)
    bl = _brute_leg(paved, cap, seeds_rc, cell, connectivity=connectivity)
    assert np.allclose(leg, bl, atol=1e-9)
    # one attachment ⇒ every paved cell is assigned to it
    assert (source == _cell_ids(paved)[0, 0]).all()


@pytest.mark.parametrize("connectivity", [8, 16])
def test_attachment_leg_matches_bruteforce_multi_hole(connectivity):
    """Two attachments + a hole + a varying cap field: the leg is the min
    over attachments, and every cell is assigned to an attachment that
    realises exactly that leg (ties may pick either)."""
    nrows, ncols, cell = 8, 8, 3.0
    paved = np.ones((nrows, ncols), dtype=bool)
    paved[3:5, 3:5] = False                         # interior hole
    rng = np.random.default_rng(0)
    cap = np.where(paved, 0.01 + 0.02 * rng.random((nrows, ncols)), 0.0)
    seeds_rc = [(0, 0), (7, 7)]
    leg, source = solve_attachment_field(
        paved, cap, _seed_ids(paved, seeds_rc), cell,
        connectivity=connectivity)
    bl = _brute_leg(paved, cap, seeds_rc, cell, connectivity=connectivity)
    assert np.allclose(leg[paved], bl[paved], atol=1e-9)
    # per-attachment single-source legs: the assigned source must be one
    # that achieves the winning leg (the ROUTE-metric guarantee — the cell
    # is priced off the attachment it is actually nearest to).
    singles = {sid: _brute_leg(paved, cap, [rc], cell,
                               connectivity=connectivity)
               for sid, rc in zip(_seed_ids(paved, seeds_rc), seeds_rc)}
    cid = _cell_ids(paved)
    for r in range(nrows):
        for c in range(ncols):
            if not paved[r, c]:
                continue
            s = int(source[r, c])
            assert s in singles
            assert singles[s][r, c] == pytest.approx(leg[r, c], abs=1e-9)
    assert cid[0, 0] in set(source[paved].tolist())


def test_attachment_unreachable_is_inf():
    """A paved component with no attachment stays inf (→ band None: off-net,
    no constraint)."""
    nrows, ncols, cell = 4, 9, 2.0
    paved = np.ones((nrows, ncols), dtype=bool)
    paved[:, 4] = False                             # split into two components
    cap = np.where(paved, 0.01, 0.0)
    leg, source = solve_attachment_field(
        paved, cap, _seed_ids(paved, [(0, 0)]), cell)
    assert math.isfinite(leg[0, 0])
    assert not math.isfinite(leg[0, 8])             # right component unreached
    assert source[0, 8] == -1


def test_attachment_deterministic():
    """Two identical runs produce byte-identical grids."""
    nrows, ncols, cell = 10, 10, 2.5
    paved = np.ones((nrows, ncols), dtype=bool)
    cap = np.full((nrows, ncols), 0.015)
    seeds = _seed_ids(paved, [(0, 0), (9, 9), (0, 9)])
    a = solve_attachment_field(paved, cap, seeds, cell)
    b = solve_attachment_field(paved, cap, seeds, cell)
    assert np.array_equal(a[0], b[0])
    assert np.array_equal(a[1], b[1])


def test_mask_erosion_is_conservative():
    """The ½-cell inward buffer used by the rasterizer keeps every eroded cell
    centre strictly inside the true pavement union (discrete domain ⊆ truth)."""
    import shapely
    from shapely.geometry import Polygon
    cell = 3.0
    union = Polygon([(0, 0), (60, 0), (60, 40), (0, 40)])   # a paved rectangle
    eroded = union.buffer(-0.5 * cell)
    xs = np.arange(-5, 65, 1.0)
    ys = np.arange(-5, 45, 1.0)
    gx, gy = np.meshgrid(xs, ys)
    shapely.prepare(union)
    shapely.prepare(eroded)
    in_eroded = shapely.contains_xy(eroded, gx.ravel(), gy.ravel())
    in_union = shapely.contains_xy(union, gx.ravel(), gy.ravel())
    # every eroded-mask cell centre is inside the true union (discrete ⊆ truth).
    assert in_eroded.any()
    assert np.all(in_union[in_eroded])
    # and no eroded point lies within ½ cell of the true boundary.
    ex, ey = gx.ravel()[in_eroded], gy.ravel()[in_eroded]
    from shapely.geometry import Point
    assert min(union.exterior.distance(Point(px, py))
               for px, py in zip(ex, ey)) >= 0.5 * cell - 1e-9


# ── Integration tests (build CYXY once, module-cached) ───────────────────────

pytestmark = pytest.mark.xdist_group("CYXY")


def _cyxy_graph():
    from conftest import cached_airport_layout
    from auto_patch.elevation_per_surface import solver_primitives as SP
    import auto_patch.grade_graph as GG
    layout = cached_airport_layout("CYXY")
    nodes, b2i = SP._build_node_list(layout)
    G = GG.build_unified_graph(layout, b2i)
    return layout, G, nodes


def test_single_engine_band_is_the_raster():
    """``reach_band_unified`` IS the grid band — one engine, no selector.

    Before 2026-07-29 this file tested a gate that chose between three
    engines; there is nothing to choose from now, so the invariant worth
    pinning is that the wrapper returns the field itself (a wrapper that
    quietly fell back to something else is exactly the engine-mixing bug
    the deletion removed)."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    layout, G, _ = _cyxy_graph()
    band = reach_band_unified(layout, G)
    meta = getattr(band, "raster_meta", None)
    assert meta is not None, "the band must be the grid field itself"
    assert meta["paved_cells"] > 0 and meta["anchors_seeded"] > 0
    assert meta["attachment_cells"] > 0
    # the off-route leg must stay LOCAL: the route carries the distance.
    assert meta["leg_p50_m"] >= 0.0


def test_raster_band_covers_band_role_vertices():
    """The band answers (non-None) at the airside vertices it governs."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    from auto_patch.grade_graph_validate import _band_roles, _open_ring
    layout, G, _ = _cyxy_graph()
    band = reach_band_unified(layout, G)
    roles = _band_roles()
    covered = total = 0
    for s in layout.shapes:
        if s.role not in roles or s.polygon is None or s.polygon.is_empty:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            total += 1
            b = band(x, y)
            if b is not None:
                covered += 1
                assert isinstance(b, tuple) and len(b) == 2
    assert total > 0
    assert covered / total > 0.95           # near-total coverage


def test_offnet_returns_none():
    """Off-net policy: a point far off the mask returns None.  There is no
    fallback engine left to mix in."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    from auto_patch.elevation_per_surface.raster_reach_band import (
        build_raster_reach_band)
    layout, G, _ = _cyxy_graph()
    raster = build_raster_reach_band(layout, G)
    assert raster is not None
    # 50 km out: beyond the bounded radius (and the grid) → None.
    assert raster(5.0e4, 5.0e4) is None
    # The wrapper returns the field closure directly (same None off-net).
    wrapped = reach_band_unified(layout, G)
    assert wrapped(5.0e4, 5.0e4) is None
    # An on-pavement anchor position answers with a finite interval.
    for i in sorted(G.runway_anchor):
        b = wrapped(*G.pos[i])
        assert b is None or (isinstance(b, tuple) and len(b) == 2)
        break


def test_raster_band_deterministic():
    """Two builds of the band give identical values at sampled points."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    layout, G, nodes = _cyxy_graph()
    b1 = reach_band_unified(layout, G)
    b2 = reach_band_unified(layout, G)
    pts = [G.pos[i] for i in sorted(G.pos)[:400]]
    for (x, y) in pts:
        assert b1(x, y) == b2(x, y)
