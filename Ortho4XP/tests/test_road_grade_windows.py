"""Twins for OWNER RULINGS 2026-11-18e -- THE ROAD ON WRONG GROUND
(``O4_Road_Grade``; ``O4_Vector_Utils.neighbourhood_road_profile``'s
``in_area`` / ``grade_change_per_m``)."""

import numpy
import O4_Cfg_Vars as CFGVARS
import O4_Road_Grade as RG
import O4_Vector_Utils as VECT

KW = dict(cap_inside=0.10, runout_m=100.0, budget_m=1.0, cap_ceiling=0.20,
          grade_change_per_m=0.01 / 3.0)


def _profile(s, dem, cap_class=0.15, band=None, area=None, **kw):
    n = len(s)
    band = numpy.zeros(n, bool) if band is None else band
    area = numpy.ones(n, bool) if area is None else area
    args = dict(KW, **kw)
    return VECT.neighbourhood_road_profile(s, dem, band, cap_class,
                                           in_area=area, **args)


def _bluff(n=60, step=20.0):
    """A gentle road over a DEM that saws 15 m up and down mid-way."""
    s = numpy.arange(n) * step
    dem = 30.0 + 0.02 * s
    for k in range(20, 40, 3):
        dem[k] += 15.0
    return s, dem


def _windows(rep):
    return [r for r in rep["runs"] if r.get("kind") == "dem_wrong"]


def test_identity_for_a_way_under_the_steep_cap():
    s = numpy.arange(40) * 20.0
    dem = 5.0 + 4.0 * numpy.sin(s / 90.0)          # never above ~4.5 %
    z, rep = _profile(s, dem)
    assert rep["scope"] == "terrain"
    assert rep["runs"] == []
    assert numpy.array_equal(z, dem)


def test_window_pins_meet_the_dem_exactly():
    s, dem = _bluff()
    z, rep = _profile(s, dem)
    wins = _windows(rep)
    assert rep["scope"] == "dem_wrong" and wins
    for r in wins:
        assert z[r["i0"]] == dem[r["i0"]]
        assert z[r["i1"]] == dem[r["i1"]]
    # outside the windows: the DEM, bit for bit
    inside = numpy.zeros(len(s), bool)
    for r in wins:
        inside[r["i0"]:r["i1"] + 1] = True
    assert numpy.array_equal(z[~inside], dem[~inside])


def test_a_window_never_enters_a_run():
    s, dem = _bluff()
    band = numpy.zeros(len(s), bool)
    band[:5] = True                       # a run over stations 0..9
    _z, rep = _profile(s, dem, band=band)
    runs = [r for r in rep["runs"] if r.get("kind") is None]
    wins = _windows(rep)
    assert runs and wins
    assert all(w["i0"] > runs[0]["i1"] for w in wins)


def test_the_window_holds_the_steep_cap_and_the_curve():
    s, dem = _bluff()
    z, rep = _profile(s, dem)
    g = numpy.abs(numpy.diff(z)) / numpy.diff(s)
    assert g.max() <= 0.20 + 1e-9
    assert RG._grade_change_excess(s, z, 0.01 / 3.0) <= 1e-6
    for r in rep["runs"]:
        assert r["cap_eff"] <= 0.20 + 1e-12


def test_an_infeasible_window_keeps_the_dem():
    # a 60 m cliff whose window spans ~220 m: 20 % cannot climb it
    s = numpy.arange(30) * 20.0
    dem = numpy.where(numpy.arange(30) < 15, 0.0, 60.0)
    z, rep = _profile(s, dem)
    assert numpy.array_equal(z, dem)
    assert rep["dem_kept"] and rep["dem_kept"][0]["reason"] == "pins"
    assert not _windows(rep)


def test_outside_the_area_nothing_triggers():
    s, dem = _bluff()
    z, rep = _profile(s, dem, area=numpy.zeros(len(s), bool))
    assert rep["scope"] == "terrain"
    assert numpy.array_equal(z, dem)


def test_the_curve_is_identity_on_a_smooth_profile():
    s = numpy.arange(20) * 15.0
    t = 0.05 * s
    out = RG._smooth_grade_changes(s, t, 0.20, 0.01 / 3.0, [0], [0.0])
    assert numpy.allclose(out, t, atol=1e-7)


def test_the_curve_takes_its_pins_and_caps():
    s = numpy.arange(30) * 10.0
    t = numpy.where(s < 150, 0.15 * s, 0.15 * (300 - s))   # a 15 % crest
    out = RG._smooth_grade_changes(s, t, 0.15, 0.01 / 3.0, [0, 29], [0.0, t[-1]])
    assert out is not None
    assert out[0] == 0.0 and out[-1] == t[-1]
    assert RG._grade_change_excess(s, out, 0.01 / 3.0) <= 1e-6
    assert (numpy.abs(numpy.diff(out)) / 10.0).max() <= 0.15 + 1e-9


def test_rail_takes_the_rail_cap_and_curve():
    law = CFGVARS.road_neighbourhood_law()
    cap, rate = RG.steep_limits("railway:rail", law)
    assert cap == law["rail_cap"] == 0.0125
    assert rate < RG.steep_limits("service", law)[1]
    assert RG.steep_limits("service", law)[0] == law["terrain_cap"] == 0.20


def test_a_pin_past_the_steep_cap_is_still_reached():
    # a join pin 25 m up, 100 m of run-out to the DEM: 25 % -- past the
    # steep cap, within the pin ceiling: the structure's level is fixed
    s = numpy.arange(0.0, 201.0, 20.0)
    dem = numpy.zeros(len(s))
    band = numpy.zeros(len(s), bool)
    band[:3] = True
    z, rep = VECT.neighbourhood_road_profile(
        s, dem, band, 0.15, pin_idx=[2], pin_val=[25.0], pin_ceiling=0.30,
        **KW)
    (run,) = rep["runs"]
    assert rep["refused"] is False
    assert run.get("pins_over_steep_cap") is True
    assert abs(z[2] - 25.0) <= 0.0101       # the pin quantum (_PIN_FEASIBILITY_TOL_M)
    assert 0.20 < run["cap_eff"] <= 0.30
