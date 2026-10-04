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


import numpy as np
import pytest


# ── Independent brute-force reference ────────────────────────────────────────


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


