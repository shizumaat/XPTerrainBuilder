"""THE TAXI BODY'S DATUM (owner RULINGS 2026-09-10p, closing the 10o
attribution; spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §8.4;
lane ``v2taxidatum``).

10o measured CYXY's parallel taxiway ``pav28``: a 1,664 m taxi body with NO
LEVEL — the per-body datum was apron-only (09p (3)) and the taxi profile is
a second-difference row with RHS 0 (curvature, no level) — so its level was
extrapolated from its far contact at the apron end while the ground rose
under it, and it cut 6.2 m into the hill.  The owner ruled every TAXI body
carries the SAME weak mean row an apron body carries.

Three readings, all synthetic:

* a lone 1 km parallel over ground its far contact stands 8 m below sits at
  its OWN terrain mean, and its designed shape (the taxi profile's own
  vertical-curve bound) survives;
* a taxi body TOUCHING a runway keeps the runway contact exactly — the
  final projection absorbs the conflict into non-runway vertices;
* a map with a runway and nothing else is BYTE-IDENTICAL: the runway family
  is not in the datum.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import runway_vertical_curve_bound
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import (apron_roles, datum_roles, design_law,
                                        taxi_body_roles)
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot
from tests.auto_patch_v2.test_v2cyxy import _ridge_z, _runway_frame

RUN_LEN = 1200.0
TAXI_LEN = 1000.0          # the parallel's length (the 10o site is 1,664 m)
CONTACT_DROP = 8.0         # its far contact stands this far below its ground


class _StepDem:
    """The 10o shape: the apron's bench, then the ground the parallel runs
    over standing ``CONTACT_DROP`` above it.  The runway keeps the apron's
    level, so the taxiway's every contact is low and its own ground is not."""

    provenance = {"synthetic": "apron bench, the parallel's ground 8 m above"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + CONTACT_DROP * min(1.0, max(0.0, (y - 120.0) / 60.0))

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


class _PlaneDem:
    """A gentle plane — the runway's own ground."""

    provenance = {"synthetic": "plane"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.002 * x

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _airport(law, dem):
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", r((RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key), r


def _solve(law, airport, cells, cuts=()):
    pm, _st = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return pm, np.asarray(sol.z, float), rep


def _taxi_datums(rep):
    return [r for r in rep.body_datums if r["kind"] == "taxi"]


# ── the fixture: an apron body and a SEPARATE parallel taxi body ────────

@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def apron_and_parallel(law):
    """An apron on the bench beside the runway and, 8 m up the step, a
    1 km parallel taxiway whose only contacts (its two link stubs) reach
    DOWN to the apron's level — the 10o geometry.  The apron and the
    parallel are two bodies: nothing but the stubs joins them."""
    airport, r = _airport(law, _StepDem())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronW", _rect(r, -520.0, 60.0, -320.0, 110.0), (),
             None, "D", "airside", "apron", {}),
        Cell(2, "primary_parallel", "pavT",
             _rect(r, -TAXI_LEN / 2, 200.0, TAXI_LEN / 2, 223.0), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "stub", "linkW", _rect(r, -431.5, 110.0, -408.5, 200.0), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "pavT",
                    (r((-TAXI_LEN / 2, 211.5)), r((TAXI_LEN / 2, 211.5)))),
            CutLine("taxi_centerline", "linkW",
                    (r((-420.0, 110.0)), r((-420.0, 211.5)))))
    pm, z, rep = _solve(law, airport, cells, cuts)
    return pm, z, rep, airport, r


def _parallel_body(pm, law, z):
    """The parallel's own vertices: the ring vertices of the ``pavT``
    faces (the body the datum row is taken over)."""
    roles = taxi_body_roles(law)
    vs: set[int] = set()
    for f in pm.faces.values():
        if f.role in roles and f.ref == "pavT":
            vs.update(v for ring in (f.ring, *f.holes)
                      for v in pm.ring_vertices(ring))
    return sorted(v for v in vs if pm.vertices[v].dem_z is not None)


def test_the_datum_roles_are_the_apron_and_the_taxi_families(law):
    """The ruling's scope: apron AND taxi, never the runway family, and the
    two are separate partitions."""
    kinds = dict(datum_roles(law))
    assert set(kinds) == {"apron", "taxi"}
    assert kinds["apron"] == apron_roles(law)
    assert kinds["taxi"] and not (kinds["taxi"] & kinds["apron"])
    rwy = set(law.tables.precedence.runway_family.members)
    assert not (rwy & (kinds["apron"] | kinds["taxi"])), \
        "the runway family carries its chord and its pins, never a datum"


def test_the_parallel_sits_on_its_own_terrain_mean(apron_and_parallel, law):
    """10p: the taxi body's MEAN z is the mean production DEM under it —
    the level 10o found missing.  Its far contact stands 8 m below that
    ground and no longer sets the body's level."""
    pm, z, rep, _airport, _r = apron_and_parallel
    taxi = _taxi_datums(rep)
    assert taxi, "the parallel is a taxi body and carries a datum row"
    vs = _parallel_body(pm, law, z)
    assert len(vs) > 3, "the parallel must be a real body"
    mean_z = sum(float(z[v]) for v in vs) / len(vs)
    mean_dem = sum(float(pm.vertices[v].dem_z) for v in vs) / len(vs)
    # THE BAR (lane deviation, reported): the datum is a WEAK row, so it
    # trades against the bending and the laws exactly as an apron body's
    # does — the 09p (3) twin's own reading, 0.5 m, not the solver's
    # active-set tolerance.  Measured here: the row's residual is 0.075 m
    # against the 8 m the body used to be out by.
    assert abs(mean_z - mean_dem) <= 0.5, \
        (f"the parallel's mean z {mean_z:.3f} stands {mean_z - mean_dem:+.3f} m "
         f"off its terrain mean {mean_dem:.3f}")
    # and the ROW's own reading, which the report publishes per body
    assert all(abs(r["residual_m"]) <= 0.5 for r in taxi), \
        f"a taxi body's published datum residual is out: {taxi}"
    # and the contact it used to take its level from IS 8 m below that mean
    apron_z = min(float(z[v]) for v in vs)
    assert mean_dem - apron_z > 0.5 * CONTACT_DROP, \
        "the fixture must put the body's contact well below its own ground"


def test_the_parallel_keeps_its_designed_shape(apron_and_parallel, law):
    """The datum sets the LEVEL, never the shape: the centreline's second
    differences stay inside the law's own vertical-curve bound (the taxi
    profile's pattern), so the body is not dragged into the terrain."""
    pm, z, _rep, _airport, _r = apron_and_parallel
    bl = next(b for b in pm.breaklines.values()
              if b.kind == "taxi_centerline" and b.ref == "pavT")
    ch = bl.vertices(pm)
    assert len(ch) > 4, "the centreline must have interior stations"
    worst = 0.0
    for k in range(1, len(ch) - 1):
        a, m, c = ch[k - 1], ch[k], ch[k + 1]
        (ax, ay), (mx, my), (cx, cy) = (pm.vertices[i].xy for i in (a, m, c))
        dp, dn = math.hypot(mx - ax, my - ay), math.hypot(cx - mx, cy - my)
        if dp <= 1e-6 or dn <= 1e-6:
            continue
        change = abs((float(z[c]) - float(z[m])) / dn
                     - (float(z[m]) - float(z[a])) / dp)
        bound = runway_vertical_curve_bound(law, 0.5 * (dp + dn), 3, "D")
        assert bound is not None
        worst = max(worst, change / bound)
    assert worst <= 1.0, \
        f"the parallel's profile bends {worst:.2f}x the law's own curve bound"


class _StepDemAt:
    """:class:`_StepDem` with the parallel's bench at an arbitrary height —
    the intervention the contact twin makes."""

    provenance = {"synthetic": "apron bench, the parallel's ground above it"}

    def __init__(self, rise: float) -> None:
        self.rise = rise

    def z(self, x: float, y: float) -> float:
        return 700.0 + self.rise * min(1.0, max(0.0, (y - 120.0) / 60.0))

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _runway_touching(law, dem):
    airport, r = _airport(law, dem)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "pavT",
             _rect(r, -TAXI_LEN / 2, 200.0, TAXI_LEN / 2, 223.0), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "linkR", _rect(r, -11.5, HALF_WIDTH, 11.5, 200.0), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "pavT",
                    (r((-TAXI_LEN / 2, 211.5)), r((TAXI_LEN / 2, 211.5)))),
            CutLine("taxi_centerline", "linkR",
                    (r((0.0, HALF_WIDTH)), r((0.0, 211.5)))),)
    pm, z, rep = _solve(law, airport, cells, cuts)
    return pm, z, rep, airport


def _runway_vertices(pm, law):
    rwy = set(law.tables.precedence.runway_family.members)
    vs: set[int] = set()
    for f in pm.faces.values():
        if f.role in rwy:
            vs.update(v for ring in (f.ring, *f.holes)
                      for v in pm.ring_vertices(ring))
    return sorted(vs)


def test_a_taxi_body_touching_a_runway_keeps_the_contact(law):
    """The ruling's guard: a taxi body may TOUCH the runway, and however
    far its own ground stands above the runway's, the CONTACT is the
    runway's own surface — its crown edge under the ridge, its hard rows
    held to their tolerance by the final projection.  The conflict is
    absorbed into the body's non-runway vertices.

    MEASURED at twice this fixture's step (16 m of ground over 60 m, a 27 %
    hillside no airport has): one contact rises 0.25 m above the ridge — the
    crown row at a shoulder vertex is a TARGET, not one of the hard rows, so
    a violent datum can lift it.  Reported by the lane, not fixed here."""
    pm, z, rep, airport = _runway_touching(law, _StepDemAt(CONTACT_DROP))
    assert _taxi_datums(rep), "the parallel and its stub carry a taxi datum"
    hold = float(design_law(law).hard_tol_m)
    assert rep.hard_settled, "the runway's hard set must settle"
    assert rep.hard_max_violation_m <= hold, \
        f"a runway hard row is out by {rep.hard_max_violation_m:.4f} m"
    assert rep.runway_projection.after_family_m <= hold, \
        "the final projection must hold the runway family's own rows"
    rwy = set(law.tables.precedence.runway_family.members)
    taxi = taxi_body_roles(law)
    contacts = [v for v, vx in pm.vertices.items()
                if any(pm.faces[f].role in rwy for f in vx.incident_faces)
                and any(pm.faces[f].role in taxi for f in vx.incident_faces)]
    assert contacts, "the stub must touch the runway"
    ax, ay, ux, uy = _runway_frame(airport)
    crown = float(law.tables.common.runway_crown_transverse)
    for v in contacts:
        dx, dy = pm.vertices[v].xy[0] - ax, pm.vertices[v].xy[1] - ay
        s, off = dx * ux + dy * uy, -dx * uy + dy * ux
        ridge = _ridge_z(pm, law, airport, z, s)
        drop = ridge - float(z[v])
        assert -hold <= drop <= crown * abs(off) + hold, \
            (f"a runway contact stands {drop:+.3f} m under its ridge — the "
             f"taxi body's datum took the contact off the runway's crown")


def test_a_lone_runway_is_byte_identical(law):
    """The runway family is NOT in the datum: a map with nothing but a
    runway solves to exactly the surface it solved to before the ruling —
    asserted as the ABSENCE of any datum row, the mechanism's own claim."""
    airport, r = _airport(law, _PlaneDem())
    cells = (Cell(0, "runway", "09/27",
                  _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2, HALF_WIDTH),
                  (), 3, "D", "airside", "runway", {}),)
    pm, z, rep = _solve(law, airport, cells)
    assert rep.body_datum_rows == 0 and rep.taxi_datum_rows == 0, \
        "a runway takes no per-body datum"
    assert not rep.body_datums
    # and the surface is its chord: flat between two equal thresholds, to
    # the runway family's own held tolerance
    hold = float(design_law(law).hard_tol_m)
    zs = [float(z[v]) for v in _runway_vertices(pm, law)]
    assert max(zs) - min(zs) <= float(law.tables.common.runway_crown_transverse) \
        * HALF_WIDTH + hold, "the lone runway is its chord plus its crown"
