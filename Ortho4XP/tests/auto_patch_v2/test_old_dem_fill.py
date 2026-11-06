"""THE DEM OLDER THAN THE AIRPORT IS FILL (owner RULINGS 2026-11-06a (2),
2026-11-06b (4)/(5); #1915; ``airport/old_dem_fill``, ``planar/fill_bank``,
``constraints/fill_bank``).

One synthetic runway, 1,200 m along x, pins 700 / 700 m: its west half
crosses a valley the DEM falls into (0.2 m/m from x = -300 m, 60 m under
the west end), its east half stands on the plane.  Read every way the
spec's twins (§6) name: the fill covers the high end only, its toe is on
the DEM, a road across the valley holds its lower rim as a terrace and
sets the end area back above it, an airport with no fill station is
returned untouched, and the airside ceiling cuts the old hill."""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest
from auto_patch_v2.airport import old_dem_fill as F
from auto_patch_v2.law import Law
from auto_patch_v2.law.reference_code import runway_status
from auto_patch_v2.law.tables import runway_safety_area_length_m, snap_margin_m
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from shapely.geometry import Point

HALF = 600.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Coarse:
    """A coarse-class sampler (``source_pixel_m``: the base tier)."""

    provenance = {"synthetic": "old dem"}

    def __init__(self, fn):
        self.fn = fn

    def z(self, x: float, y: float) -> float:
        return float(self.fn(x, y))

    def z_many(self, xs, ys):
        return np.vectorize(self.fn, otypes=[float])(np.asarray(xs, float), np.asarray(ys, float))

    def source_pixel_m(self):
        return (None, "base_tier")


def _valley(x, y):
    """The plane at 700 m, falling 0.2 m/m west of x = -300 m into a valley
    whose floor rises 0.05 m/m either side of y = 0."""
    return 700.0 - 0.2 * max(0.0, -300.0 - x) + 0.05 * abs(y) * float(x < -300.0)


def _airport(dem, roads=(), elev=702.0, pins=(700.0, 700.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-HALF, 0.0), (60.5, -135.5), 0.0, 0.0, pins[0], "fixture"),
            RunwayEnd("27", (HALF, 0.0), (60.5, -135.5), 0.0, 0.0, pins[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    a = Airport("ZZZZ", "Synthetic", frame, elev, (rw,), (), (), {}, (), (), (), (), (), (),
                (), pack, dem, Law.for_airport("ZZZZ").ruleset_key)
    return _dc.replace(a, osm_ways=tuple(roads))


def _road(x, y0=-600.0, y1=600.0, wid=-7):
    return OsmWay(wid, "airport_small_roads", ((x, y0), (x, y1)), False, {"highway": "service"})


def test_the_fill_covers_the_old_valley_and_its_toe_is_on_the_dem(law):
    """(a) the footprint holds the west end and not the east; the ground
    there reads the pins' level, the old DEM is 60 m under it; (d) the toe
    stands on the DEM, never above it."""
    dem = _Coarse(_valley)
    airport, recs, lines = F.attach(_airport(dem), law)
    assert isinstance(airport.dem, F.FillDem) and lines and lines[0].startswith("OLD-DEM FILL")
    model = F.fill_model_of(airport)
    assert model.footprint.contains(Point(-HALF, 0.0))
    assert not model.footprint.contains(Point(HALF - 50.0, 0.0))
    assert airport.dem.z(-HALF, 0.0) == pytest.approx(700.0, abs=0.01)
    assert dem.z(-HALF, 0.0) == pytest.approx(640.0)
    assert airport.dem.z(HALF - 50.0, 0.0) == pytest.approx(700.0)      # the plane, untouched
    # the toe: the footprint's ring stands on the DEM (the fill met it)
    xs, ys = np.asarray(model.footprint.exterior.coords).T
    toe = airport.dem.z_many(xs, ys) - dem.z_many(xs, ys)
    assert float(np.max(toe)) < 0.5
    # beside the runway the ground falls at the fill slope from the crest
    lo, hi = airport.dem.z(-450.0, 120.0), airport.dem.z(-450.0, 130.0)
    assert (lo - hi) == pytest.approx(10.0 * model.grade, abs=0.05)
    assert any(r["kind"] == "run" for r in recs)


def test_a_road_across_the_fill_holds_its_lower_rim_and_sets_the_end_area_back(law):
    """2026-11-06b (4): a road 250 m past the west end crosses the buried
    valley; its rims stand at 620 m (the valley floor 590 m under it) —
    it is a terrace at 620 m, and the end area stops where the embankment
    from the end's level reaches it at the fill slope."""
    dem = _Coarse(_valley)
    airport, _recs, lines = F.attach(_airport(dem, roads=(_road(-HALF - 250.0),)), law)
    model = F.fill_model_of(airport)
    (t,) = model.terraces
    assert t.way_id == -7 and min(t.level) == pytest.approx(620.0, abs=0.5)
    assert max(t.level) == pytest.approx(620.0, abs=0.5)
    assert airport.dem.z(-HALF - 250.0, 0.0) == pytest.approx(620.0, abs=0.5)   # DEM 590
    rw = airport.runways[0]
    rsa = runway_safety_area_length_m(law, rw.code_number, rw.code_letter, runway_status(rw))
    half = t.half_m
    standoff = float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)
    want = 250.0 - half - standoff - (700.0 - 620.0) / model.grade
    assert want < rsa
    assert model.end_area_m["09/27"][0] == pytest.approx(want, abs=5.0)
    assert model.end_area_m["09/27"][1] == pytest.approx(rsa)
    assert any("terrace road -7" in ln for ln in lines)
    # beyond the road (seen from the crest) the ground is the terrace's,
    # falling from it — the crest's cone never buries the road
    assert airport.dem.z(-HALF - 280.0, 0.0) < 620.0


def test_an_airport_with_no_fill_station_is_returned_untouched(law):
    """(e): the plane under both pins — nothing to fill, the same object back."""
    a = _airport(_Coarse(lambda x, y: 700.0 + 0.001 * x))
    got, recs, lines = F.attach(a, law)
    assert got is a and recs == [] and lines == []


def test_a_sampler_of_no_stated_class_is_no_witness(law):
    """end_pins' own rule: an authored sampler (no class) judges nothing."""

    class _Bare:
        def z(self, x, y):
            return _valley(x, y)

    a = _airport(_Bare())
    assert F.attach(a, law)[0] is a


def test_the_airside_ceiling_cuts_the_old_hill(law):
    """2026-11-06b (5): with a fill, the ground inside the airside envelope
    stands no higher than the field elevation + the class tolerance."""
    def hill(x, y):
        return _valley(x, y) + 40.0 * max(0.0, 1.0 - abs(x - 300.0) / 200.0)
    airport, _r, _l = F.attach(_airport(_Coarse(hill), elev=702.0), law)
    model = F.fill_model_of(airport)
    assert model.cap_m == pytest.approx(702.0 + 12.0)
    assert airport.dem.z(300.0, 0.0) == pytest.approx(714.0)                 # the hill: 740
    assert airport.dem.z(300.0, 400.0) == pytest.approx(hill(300.0, 400.0))  # off airside


def test_the_fill_crosses_to_a_worker_with_its_model(law):
    """``dem_shared``: a wrapped sampler crosses as the wrapper."""
    from auto_patch_v2.airport import dem_shared
    airport, _r, _l = F.attach(_airport(_Coarse(_valley)), law)
    shared, token = dem_shared.share(airport.dem)
    back = dem_shared.revive(token)
    assert isinstance(back, F.FillDem)
    assert back.z(-HALF, 0.0) == pytest.approx(airport.dem.z(-HALF, 0.0))
    assert shared is None
    assert math.isfinite(back.z(0.0, 0.0))
