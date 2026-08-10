"""Round 8 — VHHH close-out twins (docs/specs/round8-vhhh-closeout-spec.md).

Three laws, one lane.  Synthetic fixtures only: no X-Plane install, no
CIFP, no network, no DEM download, no build, no write anywhere.

* **R8-1** the flat-site substitution ALSO covers the airport's claimed
  object placements — ONE constant inset PER CLUSTER (hull ⊕ the flat
  margin), never one grown bbox, so the open water between an airport and
  an offshore reclamation stays sea; sub-5 strays are ignored.
* **R8-2** no solved value leaves its reach band: the writeback clamps,
  and every clamp mints a counted finding.  The equivalence pin asserts
  an in-band solve is untouched (this law must be inert where it has
  nothing to fix).
* **R8-3** one authority per tunnel — where a CLASSIFIED object tunnel
  owns ground AND cut a trench there, the OSM tunnel chain yields.  A
  classified body with NO trench (the ``tunnel4_done`` class) owns
  nothing, and an OSM-only tunnel is untouched.
"""
from __future__ import annotations

import math
import os
import sys
import types

import numpy as np
import pytest
from shapely.geometry import Polygon

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
from auto_patch import bridges, config, flat_site_mode  # noqa: E402
from auto_patch.elevation_per_surface import solver_primitives as SP  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    ROLE_APRON, ROLE_RUNWAY, ROLE_TUNNEL_TRENCH, BuiltShape,
)

R_EARTH = 6378137.0
TILE_LAT, TILE_LON = 0, 0
ANCHOR = (0.5, 0.5)              # (lat, lon)


def _lonlat(east_m: float, north_m: float) -> tuple[float, float]:
    """``(longitude, latitude)`` at a local-metre offset from ANCHOR."""
    cos0 = math.cos(math.radians(ANCHOR[0]))
    return (ANCHOR[1] + math.degrees(east_m / (R_EARTH * cos0)),
            ANCHOR[0] + math.degrees(north_m / R_EARTH))


# ══════════════════════════════════════════════════════════════════════
# R8-1 — the flat extent covers the airport's claimed object placements
# ══════════════════════════════════════════════════════════════════════
def _placement_block(centre_east_m, centre_north_m, count, spread_m=80.0):
    """``count`` placements scattered inside a ``spread_m`` box."""
    out = []
    side = max(1, int(math.ceil(math.sqrt(count))))
    for index in range(count):
        row, column = divmod(index, side)
        out.append(_lonlat(
            centre_east_m + (column - side / 2.0) * (spread_m / side),
            centre_north_m + (row - side / 2.0) * (spread_m / side)))
    return out


def test_two_placement_clusters_emit_two_boxes_and_the_channel_stays_clear():
    """R8-1: two clusters + a gap ⇒ TWO boxes, and the water between them
    is inside NEITHER — the spec's whole reason for per-cluster insets."""
    airport = _placement_block(0.0, 0.0, 12)
    # 2 km east: the "island".  Well clear of 2 x FLAT_SITE_MARGIN_M so
    # the gap is unambiguous.
    island = _placement_block(2000.0, 0.0, 20)

    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        airport + island, ANCHOR, TILE_LAT, TILE_LON)

    assert len(boxes) == 2, boxes
    assert sorted(box["placements"] for box in boxes) == [12, 20]

    def covers(box, longitude, latitude):
        x0, y0, x1, y1 = box["extent_deg"]
        return (x0 <= longitude - TILE_LON <= x1
                and y0 <= latitude - TILE_LAT <= y1)

    channel_lon, channel_lat = _lonlat(1000.0, 0.0)     # mid-gap
    assert not any(covers(box, channel_lon, channel_lat) for box in boxes)
    # ...and each cluster IS covered by one of them.
    for longitude, latitude in (airport[0], island[0]):
        assert any(covers(box, longitude, latitude) for box in boxes)


def test_sub_five_placement_strays_are_ignored():
    """R8-1: "clusters with < 5 placements ignored (streetlight strays)"."""
    real = _placement_block(0.0, 0.0, 9)
    strays = _placement_block(3000.0, 0.0, 4)

    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        real + strays, ANCHOR, TILE_LAT, TILE_LON)

    assert len(boxes) == 1
    assert boxes[0]["placements"] == 9


def test_a_chain_of_placements_within_the_join_stays_one_cluster():
    """Single-linkage: a bridge deck's placements every 200 m are ONE
    structure, not one cluster per span."""
    chain = [(index * 200.0, 0.0) for index in range(12)]
    clusters = flat_site_mode.cluster_placements_m(chain)
    assert len(clusters) == 1 and len(clusters[0]) == 12

    # ...and a break WIDER than the join splits them.
    split = ([(index * 200.0, 0.0) for index in range(6)]
             + [(2000.0 + index * 200.0, 0.0) for index in range(6)])
    assert len(flat_site_mode.cluster_placements_m(split)) == 2


def test_a_cluster_inside_the_apt_dat_extent_adds_no_inset():
    """The common case — every placement on the apron — must emit exactly
    the insets it emitted before this law."""
    from shapely.geometry import Point

    inside = Point(0.0, 0.0).buffer(3000.0)
    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(0.0, 0.0, 12), ANCHOR, TILE_LAT, TILE_LON,
        inside=inside)
    assert boxes == []


class _FakeDEM:
    """The surface ``_bake_one_inset`` reads from a working grid."""

    def __init__(self, constant=0.0, n=241):
        self.lat, self.lon = TILE_LAT, TILE_LON
        self.nxdem = self.nydem = int(n)
        self.x0 = self.y0 = 0.0
        self.x1 = self.y1 = 1.0
        self.nodata = -32768.0
        self.elevation_level = "auto"
        self.source_path = "<synthetic>"
        self.alt_dem = np.full((self.nydem, self.nxdem), float(constant),
                               dtype=np.float32)


def test_each_cluster_bakes_its_own_constant_inset_and_the_gap_is_untouched(
        monkeypatch):
    """R8-1 end to end: the overlay bakes one ``_ConstantInset`` per
    cluster; the water between airport and island keeps its real DEM."""
    dem = _FakeDEM(constant=0.0)
    tile = types.SimpleNamespace(
        lat=TILE_LAT, lon=TILE_LON, dem=dem,
        airport_elevation_inset_feather_m=60.0)

    airport_box = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(0.0, 0.0, 12), ANCHOR, TILE_LAT, TILE_LON)[0]
    island_box = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(2000.0, 0.0, 20), ANCHOR, TILE_LAT, TILE_LON)[0]

    monkeypatch.setattr(
        flat_site_mode, "flat_site_substitutions",
        lambda tile_, dico_airports=None, xplane_root=None: [{
            "icao": "TEST",
            "verdict": "flat_candidate",
            "z0_m": 4.0,
            "extent_deg": airport_box["extent_deg"],
            "extent_area_km2": airport_box["extent_area_km2"],
            "object_clusters": [island_box],
            "record": {"verdict": "flat_candidate"},
        }])

    INSETS.overlay_flat_site_insets(tile)

    stamped = dem.synthetic_flat_site_provenance
    kinds = [entry["kind"] for entry in stamped]
    assert kinds.count("synthetic_flat_site") == 1
    assert kinds.count("synthetic_flat_site_object_cluster") == 1
    cluster_entry, = [entry for entry in stamped
                      if entry["kind"] == "synthetic_flat_site_object_cluster"]
    assert cluster_entry["claimed_placements"] == 20
    assert cluster_entry["z0_m"] == 4.0

    def sample(longitude, latitude):
        column = int(round((longitude - TILE_LON) * (dem.nxdem - 1)))
        row = int(round((1.0 - (latitude - TILE_LAT)) * (dem.nydem - 1)))
        return float(dem.alt_dem[row, column])

    # Both cluster centres were lifted to Z0...
    assert sample(*_lonlat(0.0, 0.0)) == pytest.approx(4.0, abs=0.2)
    assert sample(*_lonlat(2000.0, 0.0)) == pytest.approx(4.0, abs=0.2)
    # ...and the open channel between them is still the real surface.
    assert sample(*_lonlat(1000.0, 0.0)) == pytest.approx(0.0, abs=1e-6)


# ══════════════════════════════════════════════════════════════════════
# R8-2 — no solved value leaves its reach band
# ══════════════════════════════════════════════════════════════════════
class _CanonicalPoints:
    """The registry surface ``_read_corner_elevs`` uses."""

    def get_or_add(self, x, y):
        return (round(float(x), 3), round(float(y), 3))

    def get(self, x, y):
        return (round(float(x), 3), round(float(y), 3))


def _square_layout(role=ROLE_APRON, node_altitudes=None):
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)]
    shape = BuiltShape(polygon=Polygon(ring + [ring[0]]), role=role,
                       ref="test", node_altitudes=node_altitudes)
    layout = types.SimpleNamespace(shapes=[shape],
                                   canonical_points=_CanonicalPoints())
    bucket_to_idx = {(float(x), float(y)): index
                     for index, (x, y) in enumerate(ring)}
    return layout, shape, bucket_to_idx


def test_a_floor_side_escape_is_clamped_and_counted():
    """R8-2, the VHHH shape: solved -12.5 m against a [4.6, 9.4] band."""
    layout, shape, bucket_to_idx = _square_layout()
    elev = [-12.5] * 4

    SP._writeback(layout, elev, bucket_to_idx, band=lambda x, y: (4.6, 9.4))

    assert shape.node_altitudes == [4.6, 4.6, 4.6, 4.6, 4.6]
    findings = layout.band_clamp_findings
    assert len(findings) == 4
    assert {finding[4] for finding in findings} == {"floor"}
    assert all(finding[3] == pytest.approx(17.1) for finding in findings)
    assert {finding[1] for finding in findings} == {ROLE_APRON}


def test_a_ceiling_side_escape_is_clamped_with_a_negative_delta():
    layout, shape, bucket_to_idx = _square_layout()

    SP._writeback(layout, [20.0] * 4, bucket_to_idx,
                  band=lambda x, y: (4.6, 9.4))

    assert shape.node_altitudes == [9.4, 9.4, 9.4, 9.4, 9.4]
    assert {finding[4] for finding in layout.band_clamp_findings} == {"ceil"}
    assert all(finding[3] == pytest.approx(-10.6)
               for finding in layout.band_clamp_findings)


def test_in_band_values_are_untouched_and_mint_no_finding():
    """THE EQUIVALENCE PIN: where the solve is already lawful this law
    must be inert — same altitudes, zero findings."""
    layout, shape, bucket_to_idx = _square_layout()

    SP._writeback(layout, [6.0, 6.5, 7.0, 6.25], bucket_to_idx,
                  band=lambda x, y: (4.6, 9.4))

    assert shape.node_altitudes == [6.0, 6.5, 7.0, 6.25, 6.0]
    assert layout.band_clamp_findings == []


def test_an_off_net_vertex_band_none_is_never_clamped():
    """``band(x, y) -> None`` is "the within-shape law governs here",
    not "clamp to nothing"."""
    layout, shape, bucket_to_idx = _square_layout()

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx,
                  band=lambda x, y: None)

    assert shape.node_altitudes == [-12.5, -12.5, -12.5, -12.5, -12.5]
    assert layout.band_clamp_findings == []


def test_sub_materiality_excess_is_left_alone():
    """The convergence guards' 0.01 m floor: a 5 mm dip is noise."""
    layout, shape, bucket_to_idx = _square_layout()

    SP._writeback(layout, [4.595] * 4, bucket_to_idx,
                  band=lambda x, y: (4.6, 9.4))

    assert layout.band_clamp_findings == []


def test_the_runway_datum_is_not_clamped():
    """Runway altitudes are CIFP-hard and the band checker exempts them;
    clamping one could only fight the datum."""
    layout, shape, bucket_to_idx = _square_layout(
        role=ROLE_RUNWAY, node_altitudes=[0.0] * 5)

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx,
                  band=lambda x, y: (4.6, 9.4))

    assert shape.node_altitudes == [-12.5, -12.5, -12.5, -12.5, -12.5]
    assert layout.band_clamp_findings == []


def test_a_layout_with_no_buildable_band_degrades_to_the_old_writeback():
    """The PRODUCTION call signature (``band`` omitted): the writeback
    builds the band itself, and where it cannot, the pass is exactly the
    pre-change writeback — never a crash, never a silent clamp."""
    layout, shape, bucket_to_idx = _square_layout()

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx)

    assert shape.node_altitudes == [-12.5, -12.5, -12.5, -12.5, -12.5]
    assert layout.band_clamp_findings == []


def test_findings_accumulate_across_both_writebacks():
    """``_writeback`` runs twice per build (solve exit, final projection)
    and both passes' clamps are evidence about the same surface."""
    layout, _shape, bucket_to_idx = _square_layout()
    band = lambda x, y: (4.6, 9.4)                      # noqa: E731

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx, band=band)
    SP._writeback(layout, [-12.5] * 4, bucket_to_idx, band=band)

    assert len(layout.band_clamp_findings) == 8


# ══════════════════════════════════════════════════════════════════════
# R8-3 — one authority per tunnel: objects own, OSM yields
# ══════════════════════════════════════════════════════════════════════
def _frame_square(half_m: float):
    return Polygon([(-half_m, -half_m), (half_m, -half_m),
                    (half_m, half_m), (-half_m, half_m)])


def _fake_tunnel(east_m: float, half_m: float = 30.0):
    """A classified tunnel record as the body-outline reader sees it."""
    longitude, latitude = _lonlat(east_m, 0.0)
    return types.SimpleNamespace(
        deck_footprint=_frame_square(half_m),
        roof_footprint=None,
        solid_outline_footprint=None,
        frame_origin_longitude_latitude=(longitude, latitude),
    )


def _tunnel_layout(monkeypatch, tunnels, trench_centres_m):
    """A layout carrying ``tunnels`` classified, with an emitted trench
    floor pan over each centre in ``trench_centres_m``."""
    monkeypatch.setattr(config, "OBJECT_BRIDGE_TERRAIN", True, raising=False)
    monkeypatch.setattr(bridges._CFG, "OBJECT_BRIDGE_TERRAIN", True,
                        raising=False)
    shapes = [
        BuiltShape(
            polygon=Polygon([(east - 20.0, -20.0), (east + 20.0, -20.0),
                             (east + 20.0, 20.0), (east - 20.0, 20.0)]),
            role=ROLE_TUNNEL_TRENCH, ref="object_tunnel_trench",
            altitude=-6.0)
        for east in trench_centres_m
    ]
    layout = types.SimpleNamespace(anchor=ANCHOR, shapes=shapes)
    setattr(layout, bridges._OBJECT_BRIDGE_CLASSIFICATION_ATTRIBUTE,
            types.SimpleNamespace(tunnels=list(tunnels)))
    return layout


def test_only_a_body_with_an_emitted_trench_owns_ground(monkeypatch):
    """R8-3: the predicate is the EMITTED plate, not the classification.
    The uncovered ``tunnel4_done`` class (body, no trench) owns nothing,
    so its OSM ramps survive."""
    with_trench = _fake_tunnel(0.0)
    without_trench = _fake_tunnel(1000.0)                # tunnel4 class
    layout = _tunnel_layout(monkeypatch, [with_trench, without_trench],
                            trench_centres_m=[0.0])

    union = bridges._object_trench_body_union(layout)

    assert union is not None
    assert union.contains(Polygon([(-5, -5), (5, -5), (5, 5), (-5, 5)]))
    assert not union.intersects(
        Polygon([(995, -5), (1005, -5), (1005, 5), (995, 5)]))


def test_no_trench_anywhere_means_no_yield_region(monkeypatch):
    """A classification with no emitted floor pan at all leaves the OSM
    chain exactly as it is today."""
    layout = _tunnel_layout(monkeypatch, [_fake_tunnel(0.0)],
                            trench_centres_m=[])
    assert bridges._object_trench_body_union(layout) is None


def test_an_osm_only_tunnel_has_no_classification_and_is_untouched(
        monkeypatch):
    monkeypatch.setattr(bridges._CFG, "OBJECT_BRIDGE_TERRAIN", True,
                        raising=False)
    layout = types.SimpleNamespace(anchor=ANCHOR, shapes=[])
    assert bridges._object_trench_body_union(layout) is None

    ramp = Polygon([(0, 0), (10, 0), (10, 5), (0, 5)])
    assert bridges._yield_piece_to_object_trench(
        ramp, None, corner_shared=True) is ramp


def test_a_ramp_quad_inside_a_body_is_dropped_whole():
    """A ramp quad SHARES its cross-edge corners with its neighbours, so
    it drops or survives whole — a clip would mint a third value on
    those shared nodes."""
    body = Polygon([(-50, -50), (50, -50), (50, 50), (-50, 50)])
    inside = Polygon([(-10, -5), (10, -5), (10, 5), (-10, 5)])
    stats: dict = {}

    assert bridges._yield_piece_to_object_trench(
        inside, body, corner_shared=True, stats=stats) is None
    assert stats == {"dropped": 1}


def test_a_ramp_quad_mostly_outside_a_body_survives_whole():
    body = Polygon([(-50, -50), (0, -50), (0, 50), (-50, 50)])
    quad = Polygon([(-5, -5), (95, -5), (95, 5), (-5, 5)])
    stats: dict = {}

    kept = bridges._yield_piece_to_object_trench(
        quad, body, corner_shared=True, stats=stats)

    assert kept is quad
    assert stats == {}


def test_a_grazing_wall_band_is_clipped_not_dropped():
    """A wall band is FLAT at one altitude and shares no value with its
    neighbours, so the part outside the body survives."""
    body = Polygon([(-50, -50), (0, -50), (0, 50), (-50, 50)])
    wall = Polygon([(-5, -2), (95, -2), (95, 2), (-5, 2)])
    stats: dict = {}

    kept = bridges._yield_piece_to_object_trench(
        wall, body, corner_shared=False, stats=stats)

    assert kept is not None and kept is not wall
    assert kept.area == pytest.approx(95.0 * 4.0, rel=1e-6)
    assert not kept.intersects(Polygon([(-4, -1), (-1, -1), (-1, 1),
                                        (-4, 1)]))
    assert stats == {"clipped": 1}


def test_the_yield_margin_is_the_spec_two_metres():
    assert bridges._OBJECT_TRENCH_YIELD_MARGIN_M == 2.0
