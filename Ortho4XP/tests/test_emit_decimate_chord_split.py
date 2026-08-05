"""Emit decimation: how an over-long span picks its split point.

``_ring_keep_set`` is Douglas-Peucker with the law's absolute band plus a
``MAX_CHORD_M`` cap.  A span that violates ONLY the cap has no deviation
to split at — on a perfectly straight, constant-altitude run (the common
case: adjacent-ground band rows, the boundary ribbon, the OLS cut rows)
EVERY intermediate deviates exactly 0.0.  The farthest-vertex search then
returned the FIRST intermediate, so the recursion peeled one vertex per
level from the left instead of bisecting, and a long straight carried
roughly 3x the nodes the cap requires (330 m / 61 nodes: 22 kept where 7
suffice).  Those spans now split at the arc-length MIDPOINT.

Headless and fixture-free — pure geometry, no DEM, no X-Plane install.
"""
import math

import pytest
from shapely.geometry import Polygon

from auto_patch.emit_decimate import (
    MAX_CHORD_M,
    XY_TOL_M,
    Z_TOL_BOUNDARY_M,
    _mid_index,
    _ring_keep_set,
    decimate_shape_group,
)

ROW_LEN_M = 330.0
ROW_NODES = 61                      # 5.5 m stations, like a band corridor
BAND_WIDTH_M = 8.0
ROW_ALT_M = 100.0
# What the cap alone requires of one row: ceil(len / cap) + 1.
CAP_FLOOR = math.ceil(ROW_LEN_M / MAX_CHORD_M) + 1


class FakeShape:
    """The surface ``decimate_shape_group`` touches on a layout shape."""

    def __init__(self, polygon, node_altitudes, role="apron"):
        self.polygon = polygon
        self.node_altitudes = node_altitudes
        self.role = role


def straight_band(length=ROW_LEN_M, n_per_row=ROW_NODES,
                  width=BAND_WIDTH_M, alt=ROW_ALT_M, bump=None):
    """A thin two-row band: ``n_per_row`` evenly spaced stations along
    y=0 eastbound, the same stations along y=width westbound.  ``bump``
    is an optional ``(index, dz)`` applied to the bottom row so a REAL
    deviation drives that span's split."""
    step = length / (n_per_row - 1)
    bottom = [(i * step, 0.0) for i in range(n_per_row)]
    top = [(i * step, width) for i in range(n_per_row - 1, -1, -1)]
    alts = [alt] * (len(bottom) + len(top))
    if bump is not None:
        idx, dz = bump
        alts[idx] += dz
    return FakeShape(Polygon(bottom + top), alts + [alts[0]]), step


def bottom_row_x(shape):
    return sorted(x for (x, y) in list(shape.polygon.exterior.coords)[:-1]
                  if y == 0.0)


def max_gap(xs):
    return max(b - a for a, b in zip(xs, xs[1:]))


class TestStraightRunSplitsAtTheMidpoint:
    def test_a_straight_row_decimates_to_near_the_cap_floor(self):
        """The regression: 22 of 61 kept per row before the midpoint
        split, where the cap needs 7.  Bisection lands on 9 — the price
        of even spacing — so hold the line well under the old count."""
        shape, _step = straight_band()
        removed = decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        assert removed > 0
        kept = bottom_row_x(shape)
        assert len(kept) <= CAP_FLOOR + 2, (
            f"{len(kept)} nodes kept on a straight {ROW_LEN_M:.0f} m row; "
            f"the {MAX_CHORD_M:.0f} m cap needs {CAP_FLOOR}")
        assert kept[0] == 0.0 and kept[-1] == pytest.approx(ROW_LEN_M)

    def test_the_max_chord_cap_still_holds(self):
        """Economy may not be bought by exceeding the cap the rule
        exists to enforce."""
        shape, _step = straight_band()
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        assert max_gap(bottom_row_x(shape)) <= MAX_CHORD_M + 1e-6

    def test_the_kept_stations_are_evenly_spread(self):
        """Peeling from one end leaves clusters of adjacent survivors
        (5.5 m apart) next to near-cap gaps; bisection does not."""
        shape, step = straight_band()
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        gaps = [b - a for a, b in zip(bottom_row_x(shape),
                                      bottom_row_x(shape)[1:])]
        assert min(gaps) > 2 * step, (
            f"adjacent stations survived together: {gaps}")

    def test_both_rows_of_a_band_keep_mirror_identical_stations(self):
        """The two rows trace the same chain in OPPOSITE directions.  An
        orientation-dependent split point makes each row keep a
        different set, the unanimity vote then keeps the UNION, and the
        economy is lost — so the midpoint tie-break must not depend on
        traversal direction."""
        shape, _step = straight_band()
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        ring = list(shape.polygon.exterior.coords)[:-1]
        bottom = sorted(round(x, 6) for (x, y) in ring if y == 0.0)
        top = sorted(round(x, 6) for (x, y) in ring if y == BAND_WIDTH_M)
        assert bottom == top

    def test_mid_index_is_the_same_from_either_end(self):
        """``_mid_index`` directly, on both even- and odd-length spans."""
        for n_inter in range(1, 12):
            ring = [(float(i), 0.0) for i in range(n_inter + 2)]
            n = len(ring)
            fwd = _mid_index(ring, 0, n - 1, n)
            # the same span walked the other way round the ring
            rev = _mid_index(ring[::-1], 0, n - 1, n)
            assert fwd == n - 1 - rev, (
                f"span of {n_inter} intermediates split at {fwd} "
                f"forward but {n - 1 - rev} backward")


class TestRealDeviationsStillDriveTheSplit:
    def test_an_out_of_band_bump_is_kept(self):
        """When a vertex genuinely leaves the Z band it must remain the
        split point — the midpoint rule applies only to spans that are
        in band and fail the cap alone."""
        idx = 23
        shape, step = straight_band(bump=(idx, 10.0 * Z_TOL_BOUNDARY_M))
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        kept = bottom_row_x(shape)
        assert pytest.approx(idx * step) in kept

    def test_an_in_band_wiggle_is_still_dropped(self):
        """The Z band is the smoothing knob: a wiggle inside it collapses
        whether or not the cap is what forced the split."""
        idx = 23
        shape, step = straight_band(bump=(idx, 0.5 * Z_TOL_BOUNDARY_M))
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        assert pytest.approx(idx * step) not in bottom_row_x(shape)

    def test_an_xy_corner_is_kept(self):
        """A real XY bend anchors regardless of the split rule."""
        shape, step = straight_band()
        ring = list(shape.polygon.exterior.coords)[:-1]
        idx = 30
        ring[idx] = (ring[idx][0], 50.0 * XY_TOL_M)
        alts = list(shape.node_altitudes[:-1])
        keep = _ring_keep_set(ring, alts, Z_TOL_BOUNDARY_M)
        assert idx in keep


class TestRemovedVerticesStayWithinBand:
    def test_every_dropped_station_is_within_tolerance_of_its_chord(self):
        """The decimation contract, re-checked against the FINAL kept
        chords: a dropped vertex must lie within XY_TOL_M / z_tol of the
        segment that replaced it."""
        shape, step = straight_band(bump=(23, 10.0 * Z_TOL_BOUNDARY_M))
        original = [(i * step, ROW_ALT_M) for i in range(ROW_NODES)]
        original[23] = (original[23][0],
                        ROW_ALT_M + 10.0 * Z_TOL_BOUNDARY_M)
        decimate_shape_group([shape], Z_TOL_BOUNDARY_M)
        ring = list(shape.polygon.exterior.coords)[:-1]
        alts = list(shape.node_altitudes[:-1])
        kept = sorted((x, a) for (x, y), a in zip(ring, alts) if y == 0.0)
        for x, z in original:
            seg = [i for i in range(len(kept) - 1)
                   if kept[i][0] <= x <= kept[i + 1][0]]
            assert seg, f"station {x} is outside the kept row"
            (xa, za), (xb, zb) = kept[seg[0]], kept[seg[0] + 1]
            t = (x - xa) / (xb - xa) if xb > xa else 0.0
            assert abs(z - (za * (1.0 - t) + zb * t)) <= \
                Z_TOL_BOUNDARY_M + 1e-9


# ── TERRACE PANEL-BOUNDARY STATIONS ARE FORCE-KEPT ──────────────────

def test_terrace_stations_survive_decimation():
    """A declared joint's station rows are invisible anchors.

    The apron is split into PANELS before the solve, so the joint's two
    station rows are the vertices the panels and the retaining-wall face
    share — but the face is minted AFTER this pass, so no ring in the
    decimator's vote can see that dropping a station re-opens the 0.6 m
    band as a tear.  Same class as the crown weld and the string ends.
    """
    from shapely.geometry import Polygon

    from auto_patch.emit_decimate import decimate_emit_nodes
    from auto_patch.layout import BuiltShape, PavementLayout

    def _panel(y0, y1, stations):
        # a flat panel whose long edge carries the station row: every
        # station is 3D-collinear, so the decimator would remove them all
        ring = ([(0.0, y0), (200.0, y0)]
                + [(x, y1) for x in reversed(stations)])
        s = BuiltShape(polygon=Polygon(ring + [ring[0]]), role="apron",
                       ref="panel")
        s.node_altitudes = [100.0] * len(ring) + [100.0]
        return s

    stations = [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0]
    layout = PavementLayout(icao="KFAKE", anchor=(40.0, -100.0))
    layout.shapes = [_panel(0.0, 100.0, stations)]

    bare = PavementLayout(icao="KFAKE", anchor=(40.0, -100.0))
    bare.shapes = [_panel(0.0, 100.0, stations)]
    decimate_emit_nodes(bare, "KFAKE")
    n_bare = len(list(bare.shapes[0].polygon.exterior.coords)) - 1
    assert n_bare < len(stations) + 2, (
        "the fixture is not decimatable — the twin would prove nothing")

    layout.apron_terrace_presolve = [{
        "shape_id": id(layout.shapes[0]), "ref": "panel",
        "joints": [{"hi": [(x, 100.0) for x in stations],
                    "lo": [(x, 99.4) for x in stations]}],
    }]
    decimate_emit_nodes(layout, "KFAKE")
    kept = {(round(x, 3), round(y, 3))
            for (x, y) in list(layout.shapes[0].polygon.exterior.coords)}
    for x in stations:
        assert (round(x, 3), 100.0) in kept, (
            f"station x={x} was decimated away — the panel and its wall "
            f"no longer share a vertex")
