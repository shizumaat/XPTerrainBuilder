"""11-05a THE TAXI ROUTE EXCEPTION (owner RULINGS 2026-11-05a, issue #1893):
"It should be 1.5% everywhere that's physically possible, allowing
exceptions up to 2% when there's no other way and spreading it across the
largest possible distance."

Fixture: two parallel runways 400 m apart at levels ``drop`` apart, one
connector between them (``test_taxiyield135``'s builder).  The connector's
1.5 % grants about 5.3 m over the ~355 m between the runway edges.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.stretches import stretches
from auto_patch_v2.constraints.taxi_route_yield import TaxiRoute, route_lines
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from test_routes import _RampDem, _rect


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _pair(law, drop_m: float):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)

    def rwy(ref, a, b, y, z):
        return Runway(ref, 45.0, 1, (
            RunwayEnd(a, (-600.0, y), (60.5, -135.5), 0.0, 0.0, z, "fixture"),
            RunwayEnd(b, (600.0, y), (60.5, -135.5), 0.0, 0.0, z, "fixture")), 3, "D")
    rws = (rwy("09L/27R", "09L", "27R", 0.0, 700.0),
           rwy("09R/27L", "09R", "27L", 400.0, 700.0 - drop_m))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, rws, (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09L/27R", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "runway", "09R/27L", _rect(-600, 377.5, 600, 422.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(2, "cross_connector", "taxiC", _rect(-11.5, 22.5, 11.5, 377.5), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiC", ((0.0, 0.0), (0.0, 400.0))),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return with_runway_chord(pm, law, airport)


def _caps(pm, law, ref="taxiC"):
    return {round(s.cap_l, 6) for s in stretches(pm, law).items if s.ref == ref}


def test_a_route_its_letter_joins_does_not_yield(law):
    pm = _pair(law, 3.0)
    assert pm.taxi_routes == ()
    assert _caps(pm, law) == {0.015}


def test_a_route_its_letter_cannot_join_takes_the_smallest_uniform_grade(law):
    pm = _pair(law, 6.5)
    assert len(pm.taxi_routes) >= 1
    r = pm.taxi_routes[0]
    assert isinstance(r, TaxiRoute) and not r.over_ceiling
    assert 0.015 < r.needed < 0.02 and r.cap == pytest.approx(r.needed + 0.0002)
    assert r.high_z - r.low_z == pytest.approx(6.5, abs=0.05)
    # the whole connector carries it, end to end: one cap on every stretch
    assert _caps(pm, law) == {round(r.cap, 6)}
    assert "raised to" in route_lines("ZZZZ", pm.taxi_routes)[0]


def test_a_route_beyond_the_ceiling_is_held_there_and_reported(law):
    pm = _pair(law, 12.0)
    r = pm.taxi_routes[0]
    ceiling = law.ruleset.taxi.longitudinal_exception_max
    assert r.over_ceiling and r.needed > ceiling and r.cap == pytest.approx(ceiling)
    assert _caps(pm, law) == {round(ceiling, 6)}
    assert "NOT MET" in route_lines("ZZZZ", pm.taxi_routes)[0]
    assert r.as_dict()["over_ceiling"] is True


def _via_apron(law, drop_m: float):
    """Runway, stub up, an APRON, stub up, runway: the route crosses the
    apron (owner 2026-11-05 06:01Z, option a: the apron shares the route's
    exception)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)

    def rwy(ref, a, b, y, z):
        return Runway(ref, 45.0, 1, (
            RunwayEnd(a, (-600.0, y), (60.5, -135.5), 0.0, 0.0, z, "fixture"),
            RunwayEnd(b, (600.0, y), (60.5, -135.5), 0.0, 0.0, z, "fixture")), 3, "D")
    rws = (rwy("09L/27R", "09L", "27R", 0.0, 700.0),
           rwy("09R/27L", "09R", "27L", 400.0, 700.0 - drop_m))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, rws, (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09L/27R", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "runway", "09R/27L", _rect(-600, 377.5, 600, 422.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(2, "stub", "stubS", _rect(-11.5, 22.5, 11.5, 150), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apronM", _rect(-60, 150, 60, 250), (), None, None,
             "airside", "apron", {}),
        Cell(4, "stub", "stubN", _rect(-11.5, 250, 11.5, 377.5), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubS", ((0.0, 0.0), (0.0, 150.0))),
            CutLine("taxi_centerline", "stubN", ((0.0, 250.0), (0.0, 400.0))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return with_runway_chord(pm, law, airport)


def test_the_route_s_own_apron_pairs_rise_and_the_face_does_not(law):
    """Owner 2026-11-05 13:02Z: only the portion of the apron the taxi
    route passes through steepens — per ROW, never the whole face."""
    from auto_patch_v2.constraints.apron import apron_within_shape
    from auto_patch_v2.constraints.precedence import face_cap
    from auto_patch_v2.constraints.taxi_route_yield import route_pair_caps
    from auto_patch_v2.model.constraints import Diff
    pm = _via_apron(law, 7.0)
    assert pm.taxi_routes, "no route yielded"
    r = max(pm.taxi_routes, key=lambda x: x.cap)
    assert not r.over_ceiling and 0.015 < r.cap <= 0.02
    assert r.apron_pairs and _caps(pm, law, "stubS") == {round(r.cap, 6)}
    aprons = [f for f in pm.faces.values() if f.role == "apron"]
    assert aprons and all(face_cap(law, f, pm)[0] == 0.015 for f in aprons)
    lifted = route_pair_caps(pm)
    hard = [x for x in apron_within_shape(pm, law, None)
            if isinstance(x, Diff) and x.soft is None]
    on = [x for x in hard if (min(x.a, x.b), max(x.a, x.b)) in lifted]
    off = [x for x in hard if (min(x.a, x.b), max(x.a, x.b)) not in lifted]
    assert on and all(x.cap > 0.015 for x in on)
    assert off and all(x.cap == pytest.approx(0.015) for x in off)


def test_an_apron_off_any_failing_route_keeps_its_cap(law):
    from auto_patch_v2.constraints.precedence import face_cap
    pm = _via_apron(law, 3.0)
    assert pm.taxi_routes == ()
    assert all(face_cap(law, f, pm)[0] == 0.015 for f in pm.faces.values() if f.role == "apron")
