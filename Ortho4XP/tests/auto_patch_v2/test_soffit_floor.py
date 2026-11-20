"""20g (3) / 20s (``constraints/soffit_floor``): the trench floor under a
pack soffit is tied to the SOLVED surface under the group's seat witness --
the ground under the anchor stands 0.3 m higher and the floor stands 0.3 m
higher with it (the seat rides that ground, the soffit with the seat); a vertex stage 1 solves or a rigid / airside face shares is
never tied; the half prefix is the planner's.  A synthetic field built and
solved end to end (``test_viaduct_road``'s airport)."""
from __future__ import annotations

import dataclasses as dc

import pytest
from auto_patch_v2.airport import crossing_seat as cs
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Boundary, OsmWay
from test_soffit_road import GROUND, _rec

BOX = ((-2000.0, -2000.0), (2000.0, -2000.0), (2000.0, 2000.0), (-2000.0, 2000.0))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, bump: float):
    """Flat ground at 100 m, ``bump`` higher under the anchor building; a
    service road along y = 0 under the deck."""
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame

    class _Dem:
        provenance = {"synthetic": "flat, a bump under the anchor"}

        def z(self, x: float, y: float) -> float:
            return GROUND + (bump if -70.0 <= x <= -30.0 and -20.0 <= y <= 20.0 else 0.0)

        def bounds(self):
            return (-5000.0, -5000.0, 5000.0, 5000.0)

    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, GROUND, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, GROUND, "fixture"))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    road = OsmWay(1, "big_roads", ((-600.0, 0.0), (0.0, 0.0), (600.0, 0.0)), False,
                  {"highway": "service"})
    ap = Airport("ZZZZ", "Synthetic", frame, GROUND, (Runway("09/27", 45.0, 1, ends, 3, "D"),),
                 (), (), {}, (), (), (Boundary("b", BOX, ()),), (), (road,), (), (),
                 pack, _Dem(), law.ruleset_key)
    rec = _rec(2.5, 4.2, "highway=service", "1")
    rec["parts"][0]["vote"] = rec["vote_anchor"] = GROUND + bump
    to_ll = frame.transformers()[1]
    rec["parts"][0]["feet"] = [(*to_ll(x, y), yy) for x, y, yy in rec["parts"][0]["fxy"]]
    return dc.replace(ap, elevated_crossings=(rec,))


def _solve(law, bump: float):
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.soffit_floor import HALF_PREFIX, STATS
    from auto_patch_v2.constraints.structures import ramp_faces_of, ramp_groups
    from auto_patch_v2.constraints.structures import structures as structure_rows
    from auto_patch_v2.model.constraints import Linear
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.planar.soffit_road import ID_PREFIX
    from auto_patch_v2.solve import Status, solve_design
    assert HALF_PREFIX == f"{ID_PREFIX}:"
    airport = _airport(law, bump)
    run = Cell(0, "runway", "09/27", ((-600.0, 500.0), (600.0, 500.0), (600.0, 545.0),
                                      (-600.0, 545.0)), (), 3, "D", "airside", "runway", {})
    pm, stats = build(airport, Classification((run,), (), {}, ()), law)
    halves = [t for t in pm.structures if t.id.startswith(ID_PREFIX)]
    assert len(halves) == 2, stats.structures.refused
    rows = [r for r in structure_rows(pm, law, airport)
            if isinstance(r, Linear) and "elevated.clearance_margin_m" in r.source.ruling]
    assert rows and not STATS.get("soffit_floor_absolute"), STATS
    ramps = ramp_faces_of(pm, halves)
    floor = {v for t in halves for f in ramps[t.id] for s, vs in ramp_groups(pm, t, f)
             for v in vs if s <= t.profile[1][0] - 0.5}
    cs_, _c, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs_, law)[0]
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    return pm, rows, floor, sol


def test_the_floor_rides_the_solved_witness(law):
    from auto_patch_v2.constraints.soffit_floor import planar_ground, witness_terms
    got = {}
    for bump in (0.0, 0.3):
        pm, rows, floor, sol = _solve(law, bump)
        airport = _airport(law, bump)
        _g, _n, fx = planar_ground(pm, law, airport.dem)
        terms, mean_y = witness_terms(fx, airport.frame.entry(),
                                      airport.elevated_crossings[0]["parts"][0]["feet"])
        seat = sum(w * sol.z[v] for v, w in terms) - mean_y
        want = seat + 2.5 - 4.2 - cs.margin_m(law)
        assert floor and all(sol.z[v] == pytest.approx(want, abs=0.02) for v in floor)
        # R3: no row is led by a vertex an airside or rigid face shares
        assert not any(pm.faces[f].role in ("runway", "building")
                       for r in rows for f in pm.vertices[r.terms[0][0]].incident_faces)
        got[bump] = sum(sol.z[v] for v in floor) / len(floor)
    assert got[0.3] - got[0.0] == pytest.approx(0.3, abs=0.05)
