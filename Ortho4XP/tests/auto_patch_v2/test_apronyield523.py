"""AN APRON FOLLOWS ITS RUNWAY WHERE THE RUNWAY EXCEEDS THE CAP (owner
RULINGS 2026-10-10j, issue #523; spec §50.8).

Where §50 yields a runway's longitudinal cap to its thresholds, an apron
TIED to that runway takes the runway's built grade as its cap — derived at
the taxi family's own site (``runway_yield.derive_taxi``), read through the
one reader (``precedence.taxi_cap_for``) — and still PREFERS 1 % (09k),
that preference priced under the taxi caps (``[design]
yielded_preference``) so it can no longer outrank a connector's cap.

The fixture is a runway, a parallel taxiway on two stubs, and a long apron
welded to the parallel's far edge: with the runway at 2.5 % and the apron
held to 1.5 % the parallel cannot follow the runway and the two stubs must
take the difference (the see-saw of issue #523 in small); a second
runway, flat, with its own stub and apron on a network of its own, is the
"beside a yielded one" control.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.apron import (PREFERENCE_RULING,
                                             YIELDED_PREFERENCE_RULING,
                                             apron_edge_portions,
                                             apron_within_shape)
from auto_patch_v2.constraints.precedence import face_cap
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import solve_design
from auto_patch_v2.solve.design import assemble
from auto_patch_v2.solve.design_report import DesignReport
from auto_patch_v2.solve.design_roles import (ruling_head,
                                              yielded_preference_rulings)

from test_routes import _rect

APRON_CAP = 0.015


class _Dem:
    """The ground the yielded runway lies on: 2.5 % along x."""

    provenance = {"synthetic": "plane 2.5 % in x"}

    def __init__(self, g: float) -> None:
        self.g = g

    def z(self, x: float, y: float) -> float:
        return 700.0 + self.g * (x + 600.0) if x < 1500.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _field(law, drop_m: float):
    """Runway 09/27 (``drop_m`` between its thresholds), its parallel on two
    stubs and apron ``apronA`` behind it; a FLAT runway 18/36 two km east
    with its own stub and apron ``apronB``."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)

    def ends(a, b, xa, xb, y, dz):
        return (RunwayEnd(a, (xa, y), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
                RunwayEnd(b, (xb, y), (60.5, -135.5), 0.0, 0.0, 700.0 + dz, "fixture"))

    rws = (Runway("09/27", 45.0, 1, ends("09", "27", -600.0, 600.0, 0.0, drop_m), 3, "D"),
           Runway("18/36", 45.0, 1, ends("18", "36", 2000.0, 3200.0, 0.0, 0.0), 3, "D"))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, rws, (), (), {}, (),
                      (), (), (), (), (), (), pack, _Dem(drop_m / 1200.0),
                      law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubW", _rect(-361.5, 22.5, -338.5, 100), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "stub", "stubE", _rect(338.5, 22.5, 361.5, 100), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apronA", _rect(-400, 123, 400, 223), (), None, None,
             "airside", "apron", {}),
        Cell(7, "primary_parallel", "taxiA", _rect(-400, 100, 400, 123), (),
             None, "D", "airside", "taxi", {}),
        Cell(4, "runway", "18/36", _rect(2000, -22.5, 3200, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(5, "stub", "stubB", _rect(2588.5, 22.5, 2611.5, 100), (), None, "D",
             "airside", "taxi", {}),
        Cell(6, "apron", "apronB", _rect(2400, 100, 2800, 200), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubW", ((-350.0, 0.0), (-350.0, 111.5))),
            CutLine("taxi_centerline", "stubE", ((350.0, 0.0), (350.0, 111.5))),
            CutLine("taxi_centerline", "taxiA", ((-400.0, 111.5), (400.0, 111.5))),
            CutLine("taxi_centerline", "stubB", ((2600.0, 0.0), (2600.0, 150.0))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, with_runway_chord(pm, law, airport)


@pytest.fixture(scope="module")
def yielded(law):
    return _field(law, 30.0)             # 2.5 % pin to pin against 1.5 %


@pytest.fixture(scope="module")
def lawful(law):
    return _field(law, 6.0)              # 0.5 %: nothing yields


def _faces(pm, ref):
    return [f for f in pm.faces.values() if f.ref == ref]


def _apron_rows(pm, law, airport):
    return (apron_within_shape(pm, law, airport)
            + apron_edge_portions(pm, law, airport))


def test_the_tied_apron_takes_the_runways_built_grade(yielded, law):
    airport, pm = yielded
    rc = pm.runway_caps["09/27"]
    assert rc.yielded and rc.cap > 0.025
    faces = _faces(pm, "apronA")
    assert faces
    for f in faces:
        rec = pm.taxi_caps.get(f.id)
        assert rec is not None, "the apron beside the yielded runway is not tied"
        assert rec.ref == "09/27" and rec.table == APRON_CAP
        assert rec.cap == pytest.approx(rc.cap)
        lon, tr = face_cap(law, f, pm)
        assert lon == pytest.approx(rc.cap)
        assert tr == role_cap(law, "apron").transverse      # longitudinal law only


def test_the_tied_aprons_rows_are_hard_at_that_cap_and_still_prefer_flat(yielded, law):
    airport, pm = yielded
    cap = pm.runway_caps["09/27"].cap
    own = {f"face:{f.id}" for f in _faces(pm, "apronA")}
    rows = [r for r in apron_within_shape(pm, law, airport)
            if own & set(r.source.inputs)]
    hard = [r for r in rows if r.soft is None]
    pref = [r for r in rows if r.soft is not None]
    assert hard and pref
    assert {round(r.cap, 9) for r in hard} == {round(cap, 9)}
    # the preference is still 1 %, under the head the solve prices low
    assert {r.cap for r in pref} == {0.010}
    assert {r.source.ruling for r in pref} == {YIELDED_PREFERENCE_RULING}
    assert ruling_head(pref[0]) in yielded_preference_rulings(law)


def test_an_apron_tied_to_the_runway_that_did_not_yield_is_unchanged(yielded, law):
    airport, pm = yielded
    assert not pm.runway_caps["18/36"].yielded
    for f in _faces(pm, "apronB") + _faces(pm, "stubB"):
        assert f.id not in pm.taxi_caps
    for f in _faces(pm, "apronB"):
        assert face_cap(law, f, pm)[0] == APRON_CAP
    own = {f"face:{f.id}" for f in _faces(pm, "apronB") + _faces(pm, "stubB")}
    bare = _dc.replace(pm, taxi_caps={})      # the map before any yield
    mine = [r for r in _apron_rows(pm, law, airport) if own & set(r.source.inputs)]
    was = [r for r in _apron_rows(bare, law, airport) if own & set(r.source.inputs)]
    assert mine and mine == was
    assert all(r.source.ruling != YIELDED_PREFERENCE_RULING for r in mine)


def test_with_no_yielded_runway_no_row_changes(lawful, law):
    airport, pm = lawful
    assert not any(rc.yielded for rc in pm.runway_caps.values())
    assert dict(pm.taxi_caps) == {}
    rows = _apron_rows(pm, law, airport)
    assert rows
    assert {r.cap for r in rows if r.soft is None} == {APRON_CAP}
    assert {r.source.ruling for r in rows if r.soft is not None} == {PREFERENCE_RULING}
    cs, _c, _w = generate(pm, law, airport)
    base = assemble(pm, cs, law, DesignReport())
    assert base.yielded_pref_i == []


def test_the_yielded_preference_is_priced_under_the_taxi_caps(yielded, law):
    airport, pm = yielded
    d = law.tables.emit.design
    assert 0.0 < d.yielded_preference < d.law
    cs, _c, _w = generate(pm, law, airport)
    base = assemble(pm, cs, law, DesignReport())
    assert base.yielded_pref_i
    heads = {ruling_head(base.one[i][2]) for i in base.yielded_pref_i}
    assert heads == set(yielded_preference_rulings(law))


def _stub_grade(pm, z, x: float) -> float:
    """The built grade of the stub's centreline at ``x``, from the runway's
    edge to the parallel taxiway (77.5 m)."""
    at = {(round(v.xy[0], 1), round(v.xy[1], 1)): k for k, v in pm.vertices.items()}
    return abs(z[at[(x, 100.0)]] - z[at[(x, 22.5)]]) / 77.5


def test_the_connectors_sit_inside_their_caps_once_the_apron_follows(yielded, law):
    """THE SEE-SAW: with the apron held to 1.5 % under a 2.5 % runway the
    parallel welded to it cannot follow the runway and the two stubs carry
    the difference; with the apron tied they do not."""
    airport, pm = yielded
    cap = pm.runway_caps["09/27"].cap
    cs, _c, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    worst = max(_stub_grade(pm, sol.z, -350.0), _stub_grade(pm, sol.z, 350.0))
    assert worst <= cap, f"a connector at {100 * worst:.2f} %"
    # the apron spends the wider cap, and never more than it
    grades = [abs(sol.z[r.a] - sol.z[r.b]) / r.d
              for r in apron_within_shape(pm, law, airport)
              if isinstance(r, Diff) and r.soft is None]
    assert APRON_CAP < max(grades) <= cap + 1e-4

    # the same field with the apron left at its table cap (the taxi family
    # alone yields, 30ah): the stubs stand far over their yielded cap
    aprons = {f.id for f in pm.faces.values() if f.role == "apron"}
    before = _dc.replace(pm, taxi_caps={k: v for k, v in pm.taxi_caps.items()
                                        if k not in aprons})
    cs0, _c, _w = generate(before, law, airport)
    sol0, _r0 = solve_design(before, cs0, law)
    worst0 = max(_stub_grade(before, sol0.z, -350.0), _stub_grade(before, sol0.z, 350.0))
    assert worst0 > cap + 0.01
