"""Tile-seam geometry contract for the adjacent-ground graded strip.

Owner ruling 2026-07-24:

    "It seems like maybe the adjacent ground is being applied after the cut,
     because it angles away from it rather than forming a clean line along
     the cut, and we need it to be clean and consistent so it transitions
     smoothly across the tile boundary."

Two mechanisms implement that, and this module pins both:

* ``adjacent_ground._seam_prolonged_ring`` — the corridor march runs off the
  UN-CUT pavement frontage (the cut-back run of a ring is spliced back out
  along its flanking edges, bounded by the pavement ``tile_cut`` actually
  dropped), so the tile cut — not the march — decides where the band ends.
  The strip's seam edge is then the cut line itself, COLLINEAR with the
  pavement's own cut-back edge, instead of a fan wrapping the cut corner.
* ``tile_cut._pin_terrain_piece_seam_edge`` — a graded strip's cut-back edge
  is DENSIFIED onto absolute stations and pinned to the DEM, the same seam
  contract every other role honours.  Because the pin is a pure function of
  (cut-back line, station spacing, DEM), the two halves of a seam agree
  without seeing each other.

Hermetic: synthetic layouts + a synthetic DEM in ``tmp_path`` terms — no
build, no network, no X-Plane install.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch import adjacent_ground as AG
from auto_patch import tile_cut as TC
from auto_patch.config import TILE_CUT_HALF_WIDTH_M
from auto_patch.layout import (
    BuiltShape, PavementLayout, R_EARTH, ROLE_GRADED_STRIP, ROLE_RUNWAY,
)


# ── helpers ──────────────────────────────────────────────────────────────

#: Anchor chosen so the integer meridian sits a short, exact distance west
#: of the local origin — the SPLP geometry class (a runway meeting lon -77).
ANCHOR_LAT = -12.16
ANCHOR_LON = -76.999


def _layout(shapes=()):
    lay = PavementLayout("TEST", (ANCHOR_LAT, ANCHOR_LON))
    lay.shapes = list(shapes)
    return lay


def _x_of_lon(lon: float) -> float:
    return (math.radians(lon - ANCHOR_LON) * R_EARTH
            * math.cos(math.radians(ANCHOR_LAT)))


X_SEAM = _x_of_lon(-77.0)
#: The cut-back line the current (+x, i.e. -77/-76) tile ends on.
X_CUTBACK = X_SEAM + TILE_CUT_HALF_WIDTH_M


class _FlatDEM:
    """A DEM whose altitude is an exact analytic function of position, so a
    pin can be asserted to the millimetre.  ``alt`` takes the tile-relative
    ``(lon - tile_lon, lat - tile_lat)`` offset ``_sample_dem`` passes."""

    nodata = -32768

    def __init__(self, tile_lat: int, tile_lon: int):
        self.tile_lat = tile_lat
        self.tile_lon = tile_lon

    def alt(self, node):
        dlon, dlat = node
        lat = self.tile_lat + dlat
        lon = self.tile_lon + dlon
        # A smooth ramp in latitude — every position has ONE value, and both
        # tiles' DEM objects return it for the same lat/lon (the real
        # airport-inset guarantee this test stands in for).
        return 100.0 + 1000.0 * (lat - ANCHOR_LAT)


def _oblique_runway_piece(sign: int):
    """One tile half of a runway crossing the meridian at ~18 deg, already
    cut: its ring carries a straight CUT-BACK run on ``X_CUTBACK`` (``sign``
    +1) or on the mirror line (``sign`` -1), flanked by the two long edges.

    Ring order (CCW): SE long edge inbound -> cut-back run -> NW long edge
    outbound, i.e. exactly what ``tile_cut`` leaves behind."""
    x_cut = X_SEAM + sign * TILE_CUT_HALF_WIDTH_M
    u = (sign * 0.309, sign * 0.951)          # along-axis, into the tile
    half = 23.0                               # runway half-width
    a = (x_cut, -480.0)                       # SE cut corner
    b = (x_cut, -480.0 + 2 * half / 0.951)    # NW cut corner
    far_a = (a[0] + u[0] * 600.0, a[1] + u[1] * 600.0)
    far_b = (b[0] + u[0] * 600.0, b[1] + u[1] * 600.0)
    ring = [far_a, a, (x_cut, 0.5 * (a[1] + b[1])), b, far_b]
    poly = Polygon(ring)
    if not poly.exterior.is_ccw:
        ring = ring[::-1]
        poly = Polygon(ring)
    return poly


def _offcut_of(sign: int, length_m: float = 600.0) -> Polygon:
    """The neighbour-tile half ``tile_cut`` would have dropped for
    :func:`_oblique_runway_piece`: the SAME runway continued backwards
    across the 10 m gap, ending on the neighbour's own cut-back line."""
    x_cut = X_SEAM + sign * TILE_CUT_HALF_WIDTH_M
    u = (sign * 0.309, sign * 0.951)
    half = 23.0
    a = (x_cut, -480.0)
    b = (x_cut, -480.0 + 2 * half / 0.951)
    back = 2.0 * TILE_CUT_HALF_WIDTH_M / abs(u[0])   # to the far cut-back
    a2 = (a[0] - u[0] * back, a[1] - u[1] * back)
    b2 = (b[0] - u[0] * back, b[1] - u[1] * back)
    a3 = (a2[0] - u[0] * length_m, a2[1] - u[1] * length_m)
    b3 = (b2[0] - u[0] * length_m, b2[1] - u[1] * length_m)
    poly = Polygon([a2, b2, b3, a3])
    return poly if poly.is_valid else poly.buffer(0)


# ── the geometry contract ────────────────────────────────────────────────

def test_prolongation_is_a_noop_without_recorded_offcuts():
    """Every single-tile airport: nothing was cut away, so nothing is
    prolonged and the ring objects come back IDENTICAL (not just equal)."""
    piece = _oblique_runway_piece(+1)
    lay = _layout()
    assert AG.seam_offcut_union(lay) is None
    coords = list(piece.exterior.coords)
    alts = [50.0] * len(coords)
    out_c, out_a, n = AG._seam_prolonged_ring(
        lay, coords, True, [alts], 75.0, None)
    assert n == 0
    assert out_c is coords and out_a[0] is alts


def test_cut_back_run_is_prolonged_along_its_flanking_edges():
    """The spliced ring continues BOTH flanking frontage edges by the same
    length, past the cut line, and keeps every real pavement vertex."""
    piece = _oblique_runway_piece(+1)
    lay = _layout()
    lay.tile_seam_offcuts = [_offcut_of(+1)]
    coords = list(piece.exterior.coords)
    ccw = bool(piece.exterior.is_ccw)
    alts = [50.0 + 0.01 * c[1] for c in coords]

    out_c, out_a, n = AG._seam_prolonged_ring(
        lay, coords, ccw, [alts], 75.0, AG.seam_offcut_union(lay))
    assert n == 1, "the cut-back run must be recognised and prolonged"
    assert len(out_a[0]) == len(out_c)
    # Every original NON-cut-back vertex survives.
    kept = {(round(x, 3), round(y, 3)) for x, y in out_c}
    for x, y in coords[:-1]:
        if abs(x - X_CUTBACK) > 0.2:
            assert (round(x, 3), round(y, 3)) in kept
    # New vertices lie BEYOND the cut line (they are the neighbour-tile
    # continuation the tile cut will trim off).
    beyond = [(x, y) for x, y in out_c if x < X_CUTBACK - 0.2]
    assert len(beyond) == 2
    assert Polygon(out_c).is_valid


def test_prolongation_never_exceeds_the_recorded_offcut():
    """The bound is REAL pavement: shrink the recorded offcut and the
    prolongation shrinks with it (it can never invent pavement)."""
    piece = _oblique_runway_piece(+1)
    lay_full = _layout()
    lay_full.tile_seam_offcuts = [_offcut_of(+1)]
    coords = list(piece.exterior.coords)
    ccw = bool(piece.exterior.is_ccw)
    alts = [50.0] * len(coords)

    def _prolonged_len(layout):
        out_c, _, n = AG._seam_prolonged_ring(
            layout, coords, ccw, [alts], 75.0,
            AG.seam_offcut_union(layout))
        if not n:
            return 0.0
        beyond = [(x, y) for x, y in out_c if x < X_CUTBACK - 0.2]
        # distance from the cut line along the prolongation
        return max(X_CUTBACK - x for x, _ in beyond)

    full = _prolonged_len(lay_full)
    assert full > 1.0

    lay_short = _layout()
    lay_short.tile_seam_offcuts = [_offcut_of(+1, length_m=5.0)]
    short = _prolonged_len(lay_short)
    assert short < full, (short, full)


def test_prolongation_is_identical_for_both_halves_of_one_seam():
    """CROSS-TILE DETERMINISM: the two tile builds see mirror-image inputs
    and must derive mirror-image prolongations — same length, same
    direction — without ever seeing each other."""
    lengths = []
    for sign in (+1, -1):
        piece = _oblique_runway_piece(sign)
        lay = _layout()
        lay.tile_seam_offcuts = [_offcut_of(sign)]
        coords = list(piece.exterior.coords)
        alts = [50.0] * len(coords)
        out_c, _, n = AG._seam_prolonged_ring(
            lay, coords, bool(piece.exterior.is_ccw), [alts], 75.0,
            AG.seam_offcut_union(lay))
        assert n == 1
        cut = X_SEAM + sign * TILE_CUT_HALF_WIDTH_M
        beyond = [abs(x - cut) for x, _ in out_c
                  if sign * (x - cut) < -0.2]
        lengths.append(round(max(beyond), 6))
    assert lengths[0] == lengths[1], lengths


# ── the elevation contract ───────────────────────────────────────────────

def _strip_across_the_line(y0: float, y1: float, alt: float):
    """A graded strip straddling the meridian, so the cut severs it."""
    ring = [(X_SEAM - 120.0, y0), (X_SEAM + 120.0, y0),
            (X_SEAM + 120.0, y1), (X_SEAM - 120.0, y1)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_GRADED_STRIP,
                      ref="adjacent_ground",
                      node_altitudes=[alt] * (len(ring) + 1))


def test_strip_seam_edge_is_densified_and_pinned_to_the_dem():
    """The cut leaves the strip ending ON the cut-back line; every node of
    that edge must sit at its OWN DEM altitude, not at the band value the
    polygon difference interpolated."""
    strip = _strip_across_the_line(-300.0, -60.0, alt=11.0)
    lay = _layout([strip])
    dem = _FlatDEM(-13, -77)
    TC.cut_layout_at_tile_boundaries(
        lay, current_tile_lat=-13, current_tile_lon=-77, dem=dem)
    pieces = [s for s in lay.shapes if s.role == ROLE_GRADED_STRIP]
    assert pieces, "the strip must survive on the current-tile side"
    n_on_line = 0
    for s in pieces:
        for (x, y), a in zip(list(s.polygon.exterior.coords),
                             s.node_altitudes):
            if abs(x - X_CUTBACK) > 0.2:
                continue
            n_on_line += 1
            lat, lon = lay.m_to_ll(x, y)
            want = dem.alt((lon - (-77), lat - (-13)))
            assert a == pytest.approx(want, abs=0.011), (x, y, a, want)
    # Densified: a ~240 m cut-back edge carries far more than the two
    # crossing vertices the difference() would leave.
    assert n_on_line >= 20, n_on_line


def test_seam_pin_gives_both_tiles_the_same_terrain_line():
    """The two independent builds land on the SAME terrain line: sample each
    tile's pinned seam edge at shared stations and compare."""
    profiles = {}
    for tile_lon, sign in ((-77, +1), (-78, -1)):
        strip = _strip_across_the_line(-300.0, -60.0, alt=11.0 + tile_lon)
        lay = _layout([strip])
        dem = _FlatDEM(-13, tile_lon)
        TC.cut_layout_at_tile_boundaries(
            lay, current_tile_lat=-13, current_tile_lon=tile_lon, dem=dem)
        cut = X_SEAM + sign * TILE_CUT_HALF_WIDTH_M
        pts = {}
        for s in lay.shapes:
            if s.role != ROLE_GRADED_STRIP:
                continue
            for (x, y), a in zip(list(s.polygon.exterior.coords),
                                 s.node_altitudes):
                if abs(x - cut) <= 0.2:
                    pts[round(y, 3)] = a
        profiles[tile_lon] = pts
    shared = set(profiles[-77]) & set(profiles[-78])
    assert len(shared) >= 10, sorted(shared)
    # The two cut-back lines are 10 m apart in longitude and the test DEM
    # varies only with latitude, so at a shared station the two tiles must
    # produce the SAME value — the cross-tile contract.
    for y in shared:
        assert profiles[-77][y] == pytest.approx(profiles[-78][y], abs=0.011)


def test_seam_pin_leaves_a_non_crossing_strip_untouched():
    """STRICT NO-OP away from a seam: a strip that never meets the cut band
    keeps its polygon and its altitudes byte-for-byte."""
    ring = [(X_SEAM + 200.0, -300.0), (X_SEAM + 400.0, -300.0),
            (X_SEAM + 400.0, -60.0), (X_SEAM + 200.0, -60.0)]
    strip = BuiltShape(polygon=Polygon(ring), role=ROLE_GRADED_STRIP,
                       ref="adjacent_ground",
                       node_altitudes=[11.0] * (len(ring) + 1))
    # A second shape DOES cross, so the cut runs (cut_lines is non-empty).
    crosser = _strip_across_the_line(-1000.0, -900.0, alt=9.0)
    lay = _layout([strip, crosser])
    before_ring = list(strip.polygon.exterior.coords)
    before_alts = list(strip.node_altitudes)
    TC.cut_layout_at_tile_boundaries(
        lay, current_tile_lat=-13, current_tile_lon=-77,
        dem=_FlatDEM(-13, -77))
    survivors = [s for s in lay.shapes if s is strip]
    assert survivors, "the untouched strip must survive as the same object"
    assert list(strip.polygon.exterior.coords) == before_ring
    assert strip.node_altitudes == before_alts


def test_tile_cut_records_the_neighbour_tile_offcut():
    """The prolongation's bound has to come from somewhere: the cut records
    the airside pieces it drops as out-of-tile."""
    runway = BuiltShape(
        polygon=_oblique_runway_piece(+1).union(
            _offcut_of(+1)).convex_hull,
        role=ROLE_RUNWAY, ref="02/20")
    lay = _layout([runway])
    TC.cut_layout_at_tile_boundaries(
        lay, current_tile_lat=-13, current_tile_lon=-77,
        dem=_FlatDEM(-13, -77))
    offcuts = getattr(lay, "tile_seam_offcuts", None)
    assert offcuts, "the dropped neighbour-tile half must be recorded"
    union = AG.seam_offcut_union(lay)
    assert union is not None and not union.is_empty
    # Everything recorded lies on the NEIGHBOUR side of the tile line.
    assert union.bounds[2] <= X_SEAM + 0.001, union.bounds


def test_strip_terminates_collinear_with_the_pavement_cut_back_edge():
    """The headline contract: after the cut a graded strip's seam-side edge
    is a straight line ON the cut-back line — the same line the pavement
    ends on — not an edge angling away from it."""
    strip = _strip_across_the_line(-300.0, -60.0, alt=11.0)
    lay = _layout([strip])
    TC.cut_layout_at_tile_boundaries(
        lay, current_tile_lat=-13, current_tile_lon=-77,
        dem=_FlatDEM(-13, -77))
    seam_len = 0.0
    worst_angle = 0.0
    for s in lay.shapes:
        if s.role != ROLE_GRADED_STRIP:
            continue
        ring = list(s.polygon.exterior.coords)
        for i in range(len(ring) - 1):
            (x0, y0), (x1, y1) = ring[i], ring[i + 1]
            on0 = abs(x0 - X_CUTBACK) <= 0.05
            on1 = abs(x1 - X_CUTBACK) <= 0.05
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 0.05:
                continue
            if on0 and on1:
                seam_len += length
                assert abs(x1 - x0) <= 1e-6      # exactly along the cut
            elif on0 or on1:
                worst_angle = max(worst_angle, math.degrees(
                    math.atan2(abs(x1 - x0), abs(y1 - y0))))
    assert seam_len == pytest.approx(240.0, abs=0.5), seam_len
    # The only edges that LEAVE the cut line here are the strip's own two
    # ends, square to it (the shape is a rectangle).
    assert worst_angle == pytest.approx(90.0, abs=0.5), worst_angle


def test_cutback_line_specs_cover_both_sides_of_every_cut_line():
    lines = [LineString([(X_SEAM, -1000.0), (X_SEAM, 1000.0)])]
    specs = TC._cutback_line_specs(lines, TILE_CUT_HALF_WIDTH_M)
    assert sorted(specs) == sorted([
        (0, X_SEAM - TILE_CUT_HALF_WIDTH_M),
        (0, X_SEAM + TILE_CUT_HALF_WIDTH_M)])


# ── the VALUE contract on a prolonged frontage ───────────────────────────
#
# Defect fixed 2026-07-25 (the stage-3 blocker on
# ``config.RUNWAY_SEAM_VERTEX_DEM_PIN``).  A prolonged edge carries NO
# interior vertices, so the band march's frozen-nearest host for a station
# on it is either the cut-back CORNER or the synthetic tip — up to a whole
# prolongation away in station.  The host is also the law corridor's
# altitude reference in
# ``solver_primitives._build_adjacent_ground_zone_constraints``, so the
# band 270 m up the prolonged frontage was anchored to the corner's
# altitude (measured SPLP -13/-078: 54.60 / 55.10 m between neighbours at
# 59.0 m).  The march therefore records, per zone-row point, BOTH the host
# and the station's own frontage altitude, and flags the points that sit
# on a prolonged edge.

def _flat_static():
    """A prepared static block far from the ring (no station is skipped)."""
    from shapely.prepared import prep
    return prep(Polygon([(-9e3, -9e3), (-8e3, -9e3), (-8e3, -8e3),
                         (-9e3, -8e3)]))


def _march_rows(coords, alts, prolonged_keys):
    """Zone rows for one CCW ring under a DEM high above the corridor (so
    every station emits a cut band)."""
    rows: list[dict] = []
    AG._derive_shape_stations_and_bands(
        coords, True, alts, None, 75.0, 100.0, 1.0,
        lambda d: 0.02 * d, lambda d: -0.015 * d, 5.0, _flat_static(), set(),
        lambda x, y: 500.0, zone_rows_out=rows,
        prolonged_keys=prolonged_keys)
    return rows


def _prolonged_ring():
    """One oblique runway half, its cut-back run spliced back out."""
    piece = _oblique_runway_piece(+1)
    lay = _layout()
    lay.tile_seam_offcuts = [_offcut_of(+1)]
    coords = list(piece.exterior.coords)
    ccw = bool(piece.exterior.is_ccw)
    if not ccw:                       # the march helper assumes CCW
        coords = coords[::-1]
    alts = [50.0 + 0.01 * c[1] for c in coords]
    out_c, out_a, n = AG._seam_prolonged_ring(
        lay, coords, True, [alts], 75.0, AG.seam_offcut_union(lay))
    assert n == 1
    real = {AG._vertex_key(x, y) for x, y in coords}
    pro = {AG._vertex_key(x, y) for x, y in out_c} - real
    assert pro, "the splice must have minted synthetic vertices"
    return out_c, out_a[0], real, pro


def test_zone_rows_carry_the_station_frontage_altitude():
    """``ref_alts`` is the array the band's own analytic surface is valued
    from — one entry per row point, aligned with ``pts``/``hosts``."""
    coords, alts, _real, pro = _prolonged_ring()
    rows = _march_rows(coords, alts, pro)
    assert rows
    for row in rows:
        assert len(row["ref_alts"]) == len(row["pts"])
        assert len(row["host_pro"]) == len(row["pts"])
        for v in row["ref_alts"]:
            assert v is None or 40.0 <= float(v) <= 70.0


def test_stations_on_a_prolonged_edge_are_flagged():
    """The flag is what tells the host repair which corridors must be
    re-referenced; without ``prolonged_keys`` every flag is False, so the
    march is byte-identical for a ring that was never prolonged."""
    coords, alts, _real, pro = _prolonged_ring()
    flagged = _march_rows(coords, alts, pro)
    assert any(any(r["host_pro"]) for r in flagged), \
        "no station was recognised as sitting on the prolonged frontage"
    plain = _march_rows(coords, alts, None)
    assert not any(any(r["host_pro"]) for r in plain)
    assert [r["pts"] for r in plain] == [r["pts"] for r in flagged], \
        "the flag must not move a single station"


def test_flagged_station_reference_is_not_the_cut_back_corner():
    """The defect in one assertion: on a prolonged frontage the station's
    own altitude differs from its frozen-nearest host's by metres, so
    anchoring the corridor on the host alone mis-values the band."""
    coords, alts, real, pro = _prolonged_ring()
    by_key = {}
    for (x, y), a in zip(coords, alts):
        if a is not None:
            by_key.setdefault(AG._vertex_key(x, y), float(a))
    worst = 0.0
    for row in _march_rows(coords, alts, pro):
        for (hx, hy), ref, flag in zip(row["hosts"], row["ref_alts"],
                                       row["host_pro"]):
            if not flag or ref is None:
                continue
            host_alt = by_key.get(AG._vertex_key(hx, hy))
            if host_alt is None:
                continue
            worst = max(worst, abs(float(ref) - host_alt))
    assert worst > 0.5, (
        "expected a metre-scale host/station altitude gap on the "
        f"prolonged frontage, got {worst:.3f} m")
