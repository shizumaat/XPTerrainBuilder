"""THE RUNWAY END BOX UNDER THE CURRENT ZONE LAW (owner RULINGS 2026-10-15c;
the master's two KBJC 12L bugs, fixed before the new law).

Measured at KBJC 12L (capture on main 32bcb6881, replayed on c075032f2):
the end band stood 1.5–7.5 m over a falling DEM and rose +0.88–1.09 m in
3 m beyond the blast pad against the FAA near-end rule.  The floor that
held it was NOT the end box's own: v7391 / v7395 / v918 — vertices of
12L's zone beyond its END, where 12L's own edges are not abeam — were
joined by the zone CLASS KEY (``("runway", 4, None)``) to the PARALLEL
runway 12R/30L (code 4B) 250–330 m away, whose clamped corridor floor
(lo −0.747 m at 22.9 m) sat 2.4–3.1 m over the nearest taxi class's
ceiling; the projection took the empty band's midpoint (1726.56 m).

The twins, on a synthetic pair of code-4 parallels (FAA: 4D and 4B) with
a junction across the 4D runway's end:

* the class join reaches no farther than a zone face can
  (``planar.zones.ZONE_MITRE_LIMIT`` half-widths): no zone row of a
  vertex beyond runway A's end names a vertex of runway B;
* in the end box the taxi class floors only (no ceiling row);
* the projection holds the end profile SENIOR: a zone floor above the
  end profile's ceiling yields to it (``solve.project.senior_band``).
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import strips, zones
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Linear, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.project import (END_PROFILE_HEAD, ZONE_GENERATOR,
                                         project_zone_bands, senior_band)

from tests.auto_patch_v2.test_v2zoneclamp import _base, _corridor, _x_of, _z_of

A_END = 1000.0          # runway A: x in [-A_END, A_END], y = 0, 4D
B_Y = 300.0             # runway B: parallel at y = B_Y, 4B, 2,100 m


class _FlatDem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 1700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


@pytest.fixture(scope="module")
def synthetic(law):
    frame = Frame("ZZZZ", origin=(39.9, -105.1), identity_dp=11)
    ll = (39.9, -105.1)
    ra = Runway("12L/30R", 30.0, 1,
                (RunwayEnd("12L", (-A_END, 0.0), ll, 0.0, 0.0, 1700.0, "fixture"),
                 RunwayEnd("30R", (A_END, 0.0), ll, 0.0, 0.0, 1700.0, "fixture")),
                4, "D")
    rb = Runway("12R/30L", 23.0, 1,
                (RunwayEnd("12R", (-1100.0, B_Y), ll, 0.0, 0.0, 1700.0, "fixture"),
                 RunwayEnd("30L", (A_END, B_Y), ll, 0.0, 0.0, 1700.0, "fixture")),
                4, "B")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 1700.0, (ra, rb), (), (), {}, (),
                      (), (), (), (), (), (), pack, _FlatDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "12L/30R", _rect(-A_END, -15.0, A_END, 15.0), (), 4,
             "D", "airside", "runway", {}),
        Cell(1, "runway", "12R/30L", _rect(-1100.0, B_Y - 11.5, A_END, B_Y + 11.5),
             (), 4, "B", "airside", "runway", {}),
        # a junction on runway A's side at its west end, reaching past the
        # end (the KBJC 12L junction pav1 beside the end edge)
        Cell(2, "junction", "pav1", _rect(-A_END - 100.0, 50.0, -A_END - 40.0, 75.0), (),
             None, "E", "airside", "taxi", {}),
    )
    cl = Classification(cells, (), {}, ())
    pm, _stats = build(airport, cl, law)
    return airport, pm


def _beyond_a_west(pm, law, airport):
    """The graded-strip vertices beyond runway A's west end (x < −A_END),
    laterally within its zone, not on pavement."""
    vw = view(pm, law)
    out = set()
    for f in vw.faces_of_role(("graded_strip",)):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                x, y = vw.xy[v]
                if x < -A_END - 1.0 and abs(y) < 120.0 and v not in vw.pavement_vertices:
                    out.add(v)
    return vw, out


def test_the_fixture_has_an_end_box_and_a_parallel(synthetic, law):
    airport, pm = synthetic
    vw, beyond = _beyond_a_west(pm, law, airport)
    assert beyond, "the fixture must carry strip vertices beyond runway A's end"
    rb = {v for f in vw.faces_of_role(("runway",)) if f.ref == "12R/30L"
          for v in vw.rings[f.id]}
    assert rb


def test_no_zone_row_beyond_an_end_reaches_the_parallel_runway(synthetic, law):
    """The class join (``("runway", 4, None)``) of a vertex beyond runway
    A's end never reaches runway B 300 m away — the KBJC 12L floor."""
    airport, pm = synthetic
    vw, beyond = _beyond_a_west(pm, law, airport)
    rb = {v for f in vw.faces_of_role(("runway",)) if f.ref == "12R/30L"
          for v in vw.rings[f.id]}
    bad = [r for r in zones.zone_bands(pm, law, airport)
           if r.follows in beyond and any(v in rb for v, _c in r.terms)]
    assert not bad, f"{len(bad)} zone rows beyond 12L's end name 12R/30L"


def test_the_end_box_takes_no_ceiling_from_a_taxi_class(synthetic, law):
    """In the end box (``strips.end_band_vertices``) the runway's end
    profile is the ceiling; the junction across the end floors only."""
    airport, pm = synthetic
    vw = view(pm, law)
    box = strips.end_band_vertices(vw, strips.runway_groups(vw, airport))
    assert box
    taxi = {v for f in vw.faces_of_role(("junction",)) for v in vw.rings[f.id]}
    rows = [r for r in zones.zone_bands(pm, law, airport)
            if r.follows in box and any(v in taxi for v, _c in r.terms)]
    assert rows, "the junction must band the end box (its floor)"
    assert all(r.hi is None and r.lo is not None for r in rows)
    # and the end profile's chord does carry a ceiling for every one
    ends = strips.end_corridor_longitudinal(pm, law, airport)
    capped = {r.follows for r in ends if isinstance(r, Linear)
              and r.source.ruling.startswith(END_PROFILE_HEAD) and r.hi is not None}
    assert {r.follows for r in rows} <= capped


def _end_chord(v, foot, lo, hi):
    return Linear(((v, 1.0), (foot, -1.0)), lo, hi,
                  Source("strips", END_PROFILE_HEAD + " (owner RULINGS 2026-10-12q (1))",
                         (f"vertex:{v}",)), follows=v)


def test_senior_band_lets_the_end_profile_win_a_conflict():
    inf = np.inf
    lo, hi = senior_band(np.array([-0.3]), np.array([0.14]),
                         np.array([2.0]), np.array([inf]))
    assert lo[0] == pytest.approx(0.14) and hi[0] == pytest.approx(0.14)
    # no conflict: the intersection
    lo, hi = senior_band(np.array([-0.3]), np.array([0.14]),
                         np.array([-0.1]), np.array([0.05]))
    assert (lo[0], hi[0]) == (pytest.approx(-0.1), pytest.approx(0.05))
    # no senior row: the zone band as it was (an empty one stays empty)
    lo, hi = senior_band(np.array([-inf]), np.array([inf]),
                         np.array([1.0]), np.array([0.5]))
    assert (lo[0], hi[0]) == (1.0, 0.5)


def test_the_projection_holds_the_end_profile_over_a_zone_floor(law):
    """v918's arithmetic: a zone floor 2.35 m over the end profile's
    ceiling.  The clamp lands ON the end ceiling, not at the midpoint."""
    # v0 ground, v1 runway end (0.0), v2 a far pavement (2.35 + 0.75)
    rows = [_end_chord(0, 1, -0.26, 0.14),
            _corridor(0, 2, -0.75, None)]
    base = _base(3, rows)
    z = [1.5, 0.0, 3.1]
    x, rep = project_zone_bands(None, law, base, _x_of(base, z))
    out = _z_of(base, x)
    assert out[0] == pytest.approx(0.14)
    assert ZONE_GENERATOR == "zones"
