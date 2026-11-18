"""The road side banks (owner RULINGS 2026-11-18d, ``O4_Road_Bank``)."""
import math

import numpy
import pytest

import O4_Geo_Utils as GEO
import O4_Road_Bank as RB
import O4_Vector_Utils as VECT

LANE = 4.0
M = GEO.lat_to_m


class _Roads:
    def __init__(self, ways):
        self.ways = ways


@pytest.fixture(autouse=True)
def _scalx():
    old = VECT.scalx
    VECT.scalx = math.cos(math.radians(0.5))
    yield
    VECT.scalx = old


def _road(z=50.0, length_m=200.0):
    """A straight road due east at y = 0.5 deg, level at ``z``."""
    x = numpy.linspace(0.5, 0.5 + length_m / (M * VECT.scalx), 11)
    pts = numpy.column_stack([x, numpy.full_like(x, 0.5)])
    return {"points": pts, "alt": numpy.full(len(pts), z)}


def _ground(left, right):
    """A DEM: ``left(d)`` north of the road, ``right(d)`` south of it, with
    ``d`` the plan distance in metres from the centreline."""
    def alt_vec(way):
        dy = (numpy.asarray(way)[:, 1] - 0.5) * M
        return numpy.where(dy >= 0.0, left(numpy.abs(dy)),
                           right(numpy.abs(dy)))
    return alt_vec


def _step(drop):
    return lambda d: numpy.where(d < LANE + 0.5, 50.0, 50.0 - drop)


def test_bank_where_it_fits_face_where_it_does_not():
    # left: a 3 m drop beyond the ribbon edge (a 1:2 bank reaches it 6 m
    # out); right: a 40 m cliff (a 1:2 bank would run 80 m, past the cap)
    w = _road()
    rep = RB.assign_bank_runs(_Roads([w]), _ground(_step(3.0), _step(40.0)),
                              LANE)
    (run_l, run_r), (foot_l, foot_r) = w["bank_run"], w["bank_foot_m"]
    assert numpy.all(run_l == RB.BANK_RUN)
    assert numpy.allclose(foot_l, 6.0)
    assert numpy.all(run_r == RB.FACE_RUN)
    assert numpy.allclose(foot_r, RB.BANK_MAX_WIDTH_M)
    assert rep["bank_m"] == pytest.approx(200.0, rel=0.01)
    assert rep["face_m"] == pytest.approx(200.0, rel=0.01)


def test_banks_only_where_the_profile_was_graded():
    # RULINGS 2026-11-18e (g): a station outside every run and DEM-wrong
    # window (a terrain station, not answering) is never banked
    w = _road()
    n = len(w["points"])
    w["answers"] = numpy.zeros(n, dtype=bool)
    rep = RB.assign_bank_runs(_Roads([w]), _ground(_step(3.0), _step(40.0)),
                              LANE)
    assert numpy.all(numpy.asarray(w["bank_foot_m"]) == 0.0)
    assert rep == {"bank_m": 0.0, "face_m": 0.0}
    w = _road()
    w["answers"] = numpy.arange(n) < n // 2
    RB.assign_bank_runs(_Roads([w]), _ground(_step(3.0), _step(40.0)), LANE)
    foot_l = numpy.asarray(w["bank_foot_m"][0])
    assert numpy.all(foot_l[w["answers"]] > 0.0)
    assert numpy.all(foot_l[~w["answers"]] == 0.0)


def test_small_step_is_not_banked():
    w = _road()
    rep = RB.assign_bank_runs(
        _Roads([w]), _ground(lambda d: 50.0 - 0.2 * d,
                             lambda d: 50.0 + 0.2 * d), LANE)
    assert numpy.all(numpy.asarray(w["bank_foot_m"]) == 0.0)
    assert rep == {"bank_m": 0.0, "face_m": 0.0}
    assert RB.bank_foot_lines(_Roads([w]), LANE).is_empty


def _payload(w):
    return {"lane_width_m": LANE, "ways": [{
        "lat": w["points"][:, 1].tolist(), "lon": w["points"][:, 0].tolist(),
        "alt": list(w["alt"]),
        "bank_run": [list(map(float, s)) for s in w["bank_run"]],
        "bank_foot_m": [list(map(float, s)) for s in w["bank_foot_m"]]}]}


def test_field_cuts_and_fills_to_the_bank_and_keeps_the_dem_past_the_foot():
    w = _road()
    RB.assign_bank_runs(_Roads([w]), _ground(_step(3.0), _step(40.0)), LANE)
    x_mid = float(w["points"][5, 0])
    d = numpy.array([2.0, 4.0, 30.0])           # metres past the edge
    xy = numpy.column_stack([numpy.full(6, x_mid),
                             numpy.r_[0.5 + (LANE + d) / M,
                                      0.5 - (LANE + d) / M]])
    zv = numpy.r_[47.0, 47.0, 47.0, 10.0, 10.0, 10.0]
    (sel, z) = RB.bank_field(_payload(w), 0, 0, xy, zv)
    got = dict(zip(sel.tolist(), z.tolist()))
    assert got[0] == pytest.approx(50.0 - 2.0 / RB.BANK_RUN, abs=0.05)
    assert got[1] == pytest.approx(50.0 - 4.0 / RB.BANK_RUN, abs=0.05)
    assert 2 not in got                          # past the foot: the DEM
    assert got[3] == pytest.approx(50.0 - 2.0 / RB.FACE_RUN, abs=0.05)
    assert got[4] == pytest.approx(50.0 - 4.0 / RB.FACE_RUN, abs=0.05)
    assert 5 not in got                          # past the cap: the DEM


def test_foot_lines_stand_at_the_foot():
    w = _road()
    RB.assign_bank_runs(_Roads([w]), _ground(_step(3.0), lambda d: 50.0 + 0 * d),
                        LANE)
    lines = RB.bank_foot_lines(_Roads([w]), LANE)
    assert len(lines.geoms) == 1
    ys = numpy.asarray(lines.geoms[0].coords)[:, 1]
    assert numpy.allclose((ys - 0.5) * M, LANE + 6.0, atol=0.05)
