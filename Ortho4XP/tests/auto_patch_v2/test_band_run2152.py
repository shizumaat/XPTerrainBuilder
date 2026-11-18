"""#2152 / owner RULINGS 2026-11-18b: a road running ALONG inside a taxi zone
band grades with the band and descends where it leaves the run
(``airport/band_run``); the band beside the leaving road comes down to it;
the kerb past the run descends with the road (``terrace_profile``'s
``kerb_ground``).  Geometry twins on a hand-made map: the KEGE shape
(``small_roads:-311`` along taxiway ``dsf:pol93`` at 3 m, then off its
corner at 0.36 m/m)."""
from __future__ import annotations

import math
from types import SimpleNamespace as NS

import pytest
from auto_patch_v2.airport.band_run import ALONG_DEG, band_runs, ramp_banks
from auto_patch_v2.constraints.road_ramp import terrace_profile
from auto_patch_v2.law import Law

BAND = "adjacent_ground:taxi:E:zone2#1"


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _map(stations, offset, cut_route=False):
    """A route along x (station = x) with kerbs at y = -4 / +4 m, every
    road vertex on the taxi band's kerb; the feet stub answers the north
    kerb's distance to taxiway ``dsf:pol1`` as ``offset(s)`` (the south
    kerb 8 m farther)."""
    vertices, frame, d_of = {}, {}, {}
    faces = {0: NS(role="graded_strip", ref=BAND, id=0, ring=(), holes=()),
             1: NS(role="service_road", ref="small_roads:-1", id=1, ring=(), holes=())}
    vid = 0
    for s_ in stations:
        for t_ in (-4.0, 4.0):
            vertices[vid] = NS(xy=(float(s_), t_), incident_faces=(0, 1), dem_z=100.0)
            frame[vid] = (7, float(s_), t_)
            d_of[(float(s_), t_)] = offset(s_) + (0.0 if t_ < 0 else 8.0)
            vid += 1
    yield_ = (NS(kerb=frozenset({0})),) if cut_route else ()
    pm = NS(vertices=vertices, faces=faces, road_yield=yield_,
            ring_vertices=lambda cyc: ())

    def feet(p, refs=None):
        return {"dsf:pol1": (d_of[tuple(p)], 0, 0, 0.0, (0.0, 1.0))}
    feet.role_of = {"dsf:pol1": "primary_parallel"}
    return pm, frame, feet


def _kege(s_):
    """3 m held to s = 80, then off the corner at 0.36 m/m."""
    return 3.0 + max(0.0, s_ - 80.0) * 0.36


def _runs(law, pm, frame, feet):
    return band_runs(pm, law, list(pm.vertices), frozenset(pm.vertices), frame, feet)


def test_along_the_band_is_the_run_and_the_turn_off_its_corner_is_not(law):
    pm, frame, feet = _map(range(0, 121, 4), _kege)
    run = _runs(law, pm, frame, feet)
    on = sorted({frame[v][1] for v in run})
    assert on and on[0] == 0.0
    # the descent starts within the offset window (two lanes) of the turn
    assert 72.0 <= on[-1] <= 84.0
    assert set(run.values()) == {"dsf:pol1"}


def test_a_road_parallel_within_the_angle_is_along(law):
    k = math.tan(math.radians(ALONG_DEG)) * 0.8
    pm, frame, feet = _map(range(0, 81, 4), lambda s_: 3.0 + k * s_)
    assert len(_runs(law, pm, frame, feet)) == len(pm.vertices)


def test_a_road_through_zone_2_gets_no_run(law):
    """2026-10-20c (39): a carriageway cut out of zone 2 follows its own
    ground -- the band run never lifts it."""
    pm, frame, feet = _map(range(0, 121, 4), _kege, cut_route=True)
    assert _runs(law, pm, frame, feet) == {}


def test_an_end_in_the_band_turning_into_the_taxiway_stays_on_the_run(law):
    """The road's END inside the band meets its pavement (within a lane of
    it): its offset falls fast (a mouth), and it is on the run -- never a
    bare exit off it.  An end that leaves (the turn above) is not."""
    pm, frame, feet = _map(range(0, 81, 4),
                           lambda s_: max(0.5, 3.0 - max(0.0, 12.0 - s_) * 0.5))
    run = _runs(law, pm, frame, feet)
    assert {frame[v][1] for v in run} >= {0.0, 4.0, 8.0}


def test_the_band_beside_the_leaving_road_banks_down_to_it_never_beside_the_run(law):
    pm, frame, feet = _map(range(0, 121, 4), _kege)
    run = _runs(law, pm, frame, feet)
    # two band GROUND vertices 2 m off the north kerb: one by the run, one by
    # the leaving road
    nb = len(pm.vertices)
    pm.faces[2] = NS(role="graded_strip", ref=BAND, id=2, ring=(), holes=())
    pm.vertices[nb] = NS(xy=(40.0, -6.0), incident_faces=(2,), dem_z=90.0)
    pm.vertices[nb + 1] = NS(xy=(112.0, -6.0), incident_faces=(2,), dem_z=90.0)
    pm.ring_vertices = lambda cyc: (nb, nb + 1)
    station = {v: (fr[0], fr[1]) for v, fr in frame.items()}
    banks = ramp_banks(pm, law, run, station)
    assert nb not in banks
    u, d = banks[nb + 1]
    assert frame[u][1] == 112.0 and d == pytest.approx(2.0)


def test_the_kerb_past_the_run_descends_with_the_road():
    """A kerb carries no §37 (6) target; on the bare exit it reads its
    ground and descends at the design grade with the road."""
    st = {i: (0, i * 10.0) for i in range(8)}
    foot = {v: (1000 + v, 1000 + v, 0.0, "pol") for v in (0, 1, 2)}
    lv = {1000 + v: 100.0 for v in (0, 1, 2)}
    floor = {v: 98.0 for v in (3, 5, 7)}
    out, _rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor,
                                0.08, design=0.05, lane=4.0,
                                kerb_ground={4: 98.0, 6: 98.0})
    for v in (3, 4, 5, 6, 7):
        assert out[v] == pytest.approx(max(98.0, 100.0 - 0.05 * (v - 2) * 10.0))
    out0, _r = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor,
                               0.08, design=0.05, lane=4.0)
    assert 4 not in out0 and 6 not in out0
