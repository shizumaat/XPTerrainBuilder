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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
from auto_patch import flat_site_mode  # noqa: E402

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


# ══════════════════════════════════════════════════════════════════════
# R8-3 — one authority per tunnel: objects own, OSM yields
# ══════════════════════════════════════════════════════════════════════


