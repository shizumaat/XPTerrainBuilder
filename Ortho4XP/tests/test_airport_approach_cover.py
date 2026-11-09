"""#1990 twins: ZL18 at airports follows the approaches — the boundary
plus a 3° glide-path corridor off each runway end, on a SYNTHETIC
two-runway airport (no corpus, no apt.dat on disk)."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Point, box

import O4_Airport_Approach_Cover as COVER
import O4_Geo_Utils as GEO
from auto_patch_v2.airport.apt_dat import AptRunway

LAT, LON = 30, 31                      # the synthetic tile
CLAT, CLON = 30.5, 31.5                # the synthetic airport's centre
KX, KY = GEO.lon_to_m(CLAT), GEO.lat_to_m


def _ll(east_m, north_m):
    """``(lat, lon)`` of a point ``east_m`` / ``north_m`` off the centre."""
    return CLAT + north_m / KY, CLON + east_m / KX


def _runway(a, b, width=45.0, disp_a=0.0, disp_b=0.0):
    (lat_a, lon_a), (lat_b, lon_b) = _ll(*a), _ll(*b)
    return AptRunway(width, 1, (("A", lat_a, lon_a, disp_a, 0.0),
                                ("B", lat_b, lon_b, disp_b, 0.0)))


#: 09/27 (3 km, threshold of the WEST end displaced 300 m) and 18/36
#: (2 km), crossing at the centre.
EW = _runway((-1500, 0), (1500, 0), disp_a=300.0)
NS = _runway((0, 1000), (0, -1000), width=30.0)
#: the airport boundary: a 3.4 x 2.4 km box round both runways
BOUNDARY = box((CLON - LON) - 1700 / KX, (CLAT - LAT) - 1200 / KY,
               (CLON - LON) + 1700 / KX, (CLAT - LAT) + 1200 / KY)


def _local(east_m, north_m):
    lat, lon = _ll(east_m, north_m)
    return Point(lon - LON, lat - LAT)


def test_corridor_length_follows_a_3_degree_glide_path():
    assert COVER.corridor_length_m(1000) == pytest.approx(5816, abs=2)
    assert COVER.corridor_length_m(500) == pytest.approx(2908, abs=1)
    assert COVER.corridor_length_m(0) == 0.0


def test_one_corridor_per_runway_end_none_at_zero():
    assert len(COVER.threshold_corridors([EW, NS], 2908.0)) == 4
    assert COVER.threshold_corridors([EW, NS], 0.0) == []


def test_corridor_starts_at_the_displaced_threshold_and_widens():
    region = COVER.cover_region(None, [EW], LAT, LON, 0.0, 500)
    # west end: displaced 300 m, so the corridor starts at -1200 m
    assert region.contains(_local(-1250, 0))
    assert not region.contains(_local(-1100, 0))
    # it reaches 2,908 m out from that threshold, not further
    assert region.contains(_local(-1200 - 2850, 0))
    assert not region.contains(_local(-1200 - 2960, 0))
    # east end (no displacement) starts at the runway end
    assert region.contains(_local(1550, 0))
    assert not region.contains(_local(1450, 0))
    # runway width at the threshold, ~1 km at the far end
    assert not region.contains(_local(1550, 60))
    assert region.contains(_local(1500 + 2850, 480))
    assert not region.contains(_local(1500 + 2850, 530))


def test_light_is_the_boundary_only():
    region = COVER.cover_region(BOUNDARY, [EW, NS], LAT, LON, 0.0, 0)
    assert region.equals(BOUNDARY)


def test_extent_widens_the_polygon_not_its_bounding_box():
    region = COVER.cover_region(BOUNDARY, [], LAT, LON, 1.0, 0)
    assert region.contains(_local(1700 + 950, 0))
    # a buffered box has round corners: 0.9 km diagonal off a corner is out
    assert not region.contains(_local(1700 + 900, 1200 + 900))


def _tile(cover_extent=1.0, approach_ft=1000, zl=18):
    return types.SimpleNamespace(lat=LAT, lon=LON, cover_zl=zl,
                                 cover_extent=cover_extent,
                                 cover_approach_ft=approach_ft)


def _squares(monkeypatch, **kw):
    monkeypatch.setattr(COVER, "airport_runways",
                        lambda code, root: (EW, NS) if code == "ZZZZ" else ())
    dico = {"ZZZZ": {"boundary": BOUNDARY}}
    return COVER.tile_cover_squares(_tile(**kw), dico, ["ZZZZ"],
                                    xplane_root="/nowhere")


def test_squares_meet_the_region_and_grow_with_the_preset(monkeypatch):
    light = _squares(monkeypatch, cover_extent=0.0, approach_ft=0)
    balanced = _squares(monkeypatch, cover_extent=0.0, approach_ft=500)
    sharper = _squares(monkeypatch, cover_extent=0.0, approach_ft=1000)
    assert light and light < balanced < sharper
    region = COVER.cover_region(BOUNDARY, [EW, NS], LAT, LON, 0.0, 1000)
    for sq in sharper:
        assert region.intersects(box(*COVER.square_bounds(*sq, 18, LAT, LON)))


def test_squares_are_not_the_bounding_box(monkeypatch):
    sharper = _squares(monkeypatch, cover_extent=0.0, approach_ft=1000)
    xs = sorted({x for x, _ in sharper})
    ys = sorted({y for _, y in sharper})
    full_box = (len(range(xs[0], xs[-1] + 1, 16))
                * len(range(ys[0], ys[-1] + 1, 16)))
    # a cross of four corridors fills well under half its bounding box
    assert len(sharper) < full_box / 2
    # the diagonal corner 5 km NE of the centre is not covered
    corner = GEO.wgs84_to_orthogrid(*_ll(5000, 5000), 18)
    assert corner not in sharper


def test_unknown_code_is_the_boundary_alone(monkeypatch):
    monkeypatch.setattr(COVER, "airport_runways", lambda code, root: ())
    dico = {("repr", 1): {"boundary": BOUNDARY}}
    got = COVER.tile_cover_squares(_tile(0.0, 1000), dico, [("repr", 1)],
                                   xplane_root="/nowhere")
    assert got == COVER.cover_squares(BOUNDARY, LAT, LON, 18)


def test_runways_reader_abstains_without_an_install():
    assert COVER.airport_runways("ZZZZ", None) == ()
    assert COVER.airport_runways(("repr", 1), "/nowhere") == ()


def test_presets_carry_the_corridor():
    import O4_Settings_Presets as PRESETS
    got = {p.key: p.as_dict()["cover_approach_ft"] for p in PRESETS.PRESETS}
    assert got == {"light_on_disk": "0", "balanced": "500",
                   "sharper_airports": "1000"}
