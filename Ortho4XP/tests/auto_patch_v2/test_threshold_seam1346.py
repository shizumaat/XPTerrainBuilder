"""THE TILE SEAM OUTRANKS A CIFP THRESHOLD (owner RULINGS 2026-10-26b,
issue #1346; ``constraints/threshold_seam``).

The owner, verbatim: "Like SPLP, or any airport on a tile boundary, the
tile boundary has to trump everything to ensure a smooth edge, so it would
allow cifp to move if required".

PANC's class, in synthetic form.  A 1,200 m runway crosses a meridian, and
its 09 displaced threshold lies 9 m from the seam band's edge.  The
threshold's CIFP value stands 0.5 m above the flat ground the §38 seam
pins hold.  Under the old precedence the two pins, and the vertical-curve
and transverse laws between them, have no common solution.  Under 26b the
threshold YIELDS: the solve releases it, the runway settles, and the
yield is published.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, roads
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.threshold_seam import (RULING_HEAD,
                                                      seam_thresholds,
                                                      yield_records)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.emit_stage import with_threshold_yield
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.design_roles import ruling_head
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS

GROUND = 700.0
CONFLICT_M = 0.5
#: the frame origin's longitude: lon -136.0 crosses the runway ~27 m west of x = 0
SEAM_LON = -135.9995
FAR_LON = -135.5


class _FlatDem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return GROUND

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, lon0: float, displaced_m: float):
    frame = Frame("ZZZZ", origin=(60.5, lon0), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, lon0), displaced_m, 0.0,
                      GROUND + CONFLICT_M, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, lon0), 0.0, 0.0, GROUND, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, GROUND, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _FlatDem(), law.ruleset_key)


def _map(law, lon0: float):
    # the meridian's frame x on this frame, so the threshold lands 9 m east
    # of the band edge whatever the projection does
    probe = _airport(law, lon0, 0.0)
    to_xy, _ = probe.frame.transformers()
    x_seam = to_xy(-136.0, 60.5)[0]
    half = float(law.tables.emit.seam.half_width_m)
    displaced = (x_seam + half + 9.0) + 600.0 if lon0 == SEAM_LON else 584.0
    airport = _airport(law, lon0, displaced)
    cells = (Cell(0, "runway", "09/27", ((-600.0, -22.5), (600.0, -22.5),
                                         (600.0, 22.5), (-600.0, 22.5)), (), 3, "D",
                  "airside", "runway", {}),)
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    return airport, with_runway_chord(pm, law, airport)


@pytest.fixture(scope="module")
def seamed(law):
    return _map(law, SEAM_LON)


@pytest.fixture(scope="module")
def solved(law, seamed):
    from auto_patch_v2.solve import Status, solve_design
    airport, pm = seamed
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    return airport, pm, cs, sol, rep


def test_the_threshold_near_the_seam_is_seam_yielding(seamed, law):
    airport, pm = seamed
    assert pm.seam_vertices, "the fixture's runway crosses no seam"
    st = seam_thresholds(pm, law, airport)
    assert [r.end for r in st.values()] == ["09"]
    (rec,) = st.values()
    # the pin sits at the profile station nearest the threshold point
    assert rec.seam_d_m < 15.0 < rec.reach_m
    assert rec.cifp_m == pytest.approx(GROUND + CONFLICT_M)


def test_only_the_seam_yielding_pin_carries_the_yielding_head(seamed, law):
    airport, pm = seamed
    cs, _c, _w = generate(pm, law, airport)
    st = seam_thresholds(pm, law, airport)
    heads = {p.v: ruling_head(p) for p in cs.pins if p.source.generator == "runway_profile"}
    assert {v for v, h in heads.items() if h == RULING_HEAD} == set(st)
    assert RULING_HEAD in law.tables.emit.design.yielding_pin_rulings


def test_the_cap_does_not_yield_to_a_seam_yielding_threshold(seamed):
    _airport_, pm = seamed
    assert not pm.runway_caps["09/27"].yielded


def test_the_threshold_yields_and_the_runway_settles(solved, law):
    airport, pm, cs, sol, rep = solved
    (v,) = seam_thresholds(pm, law, airport)
    z = np.asarray(sol.z, float)
    assert abs(z[v] - (GROUND + CONFLICT_M)) > 0.3, "the threshold did not yield"
    assert any(int(r["v"]) == v and r.get("ruling") == RULING_HEAD
               for r in rep.pin_yield)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    rows = census(surf, law, publication(pm, law, airport, sol.z),
                  roads.road_law_caps(pm, law))
    got = {k: len(rows[k]) for k in DEFECT_KEYS}
    assert got == {k: 0 for k in DEFECT_KEYS}, got
    # the seam pins hold exactly: the seam outranks the threshold
    for s in pm.seam_vertices:
        assert z[s] == pytest.approx(pm.vertices[s].dem_z, abs=1e-6)


def test_the_yield_is_published(solved, law):
    airport, pm, _cs, sol, rep = solved
    lines: list[str] = []
    pm2 = with_threshold_yield("ZZZZ", pm, law, airport, sol, rep.pin_yield, lines.append)
    (v,) = seam_thresholds(pm, law, airport)
    cifp, built, d, end = pm2.threshold_seam_yield[v]
    assert cifp == pytest.approx(GROUND + CONFLICT_M) and d < 15.0
    assert built == pytest.approx(float(sol.z[v]))
    assert end == "09/27 RWY 09"
    assert len(lines) == 1 and "THRESHOLD YIELDS TO THE TILE SEAM" in lines[0]
    pub = publication(pm2, law, airport, sol.z)
    (row,) = pub["threshold_seam_yield"]
    assert row[2] == pytest.approx(cifp) and row[5] == end


def test_a_runway_on_one_tile_keeps_its_cifp_pin(law):
    airport, pm = _map(law, FAR_LON)
    assert not pm.seam_vertices
    assert seam_thresholds(pm, law, airport) == {}
    cs, _c, _w = generate(pm, law, airport)
    heads = {ruling_head(p) for p in cs.pins if isinstance(p, Pin)}
    assert RULING_HEAD not in heads
    assert yield_records(pm, law, airport, [{"v": 0, "z_m": 1.0}]) == {}
