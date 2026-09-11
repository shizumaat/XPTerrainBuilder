"""THE GROUND'S OWN DATUM (owner RULINGS 2026-09-10av; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §23; lane
``v2grounddem``).

09b (3) made adjacent ground a pure LAW surface with no DEM term, and a
surface built only from one-sided rows has no LEVEL: CYXY's 14R/32L end
corridor cut 1.9 m into lawful natural ground and a 45 % bank climbed back
to a foot correctly on the DEM.  The owner's law: an adjacent-ground vertex
carries a WEAK per-vertex DEM datum while its law rows stay one-sided and
ONE-WAY — so the strip EQUALS the natural ground wherever the ground is
lawful, and is cut or filled only where a law row binds.

Readings: lawful ground (the strip IS the ground, and the pavement does not
move), ground above the zone ceiling (cut to the law line THERE and the DEM
elsewhere), ground falling faster than the law (filled at the law line), a
taxiway beside a law-bound strip (the bending channel, bounded), and the
derivation site itself (no pavement vertex, no interior pocket).
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.law.tables import zone_bounds
from auto_patch_v2.solve import design as _design
from auto_patch_v2.solve.design import DesignReport, assemble
from auto_patch_v2.solve.design_ground import ground_datum_vertices
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot  # noqa: F401
from tests.auto_patch_v2.test_v2smooth import RUN_LEN, _airport, law  # noqa: F401

#: the runway rectangle in the (identity) frame ``_rot(90)``
_X0, _X1 = -RUN_LEN / 2, RUN_LEN / 2
_Y0, _Y1 = -HALF_WIDTH, HALF_WIDTH
#: the parallel taxiway (the bending-channel fixture only), NORTH
_TAXI = (-400.0, 60.0, 400.0, 83.0)
#: ``rulesets.toml [common] runway_crown_transverse`` — the runway's EDGE
#: sits this far under its spine, so the corridor a ground vertex is judged
#: in starts from ``700 − crown·|y|``, never from the field elevation
_CROWN = 0.010
#: THE ONE LAWFUL UNIFORM SLOPE off a code-3 runway edge.  The corridor
#: accumulates: at ``d`` the ground must lie in ``[−0.15 − 0.03·(d−3),
#: −0.09 − 0.015·(d−3)]`` under the edge.  A UNIFORM fall is lawful only in
#: ``[0.0300, 0.0308]`` — steeper than the 3 % lip minimum, gentler than the
#: 75 m band ceiling — and a uniform fall is what the twin needs: it is
#: AFFINE along every ray, so the bending term (``bend_strip`` 30, ten times
#: the datum) has nothing to fight and the reading is the datum's alone.
_SLOPE = 0.0306


def _near(x: float, y: float) -> tuple[float, float]:
    return (min(max(x, _X0), _X1), min(max(y, _Y0), _Y1))


def _outside(x: float, y: float) -> float:
    px, py = _near(x, y)
    return float(np.hypot(x - px, y - py))


def _edge_z(x: float, y: float) -> float:
    """The runway's own EDGE level at the point governing ``(x, y)``."""
    return 700.0 - _CROWN * abs(_near(x, y)[1])


def _lawful_z(x: float, y: float) -> float:
    return _edge_z(x, y) - _SLOPE * _outside(x, y)


class _LawfulDem:
    """The crowned runway surface, and ground falling away from every edge
    at the one uniform rate the corridor admits: NO zone row binds."""

    provenance = {"synthetic": "lawful adjacent ground"}

    def z(self, x: float, y: float) -> float:
        return _lawful_z(x, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _MoundDem(_LawfulDem):
    """The lawful ground with a 2 m mound over one stretch of the south
    strip's outer ring: there, and only there, the ground stands ABOVE the
    corridor's ceiling (which at 75 m sits 1.13 m over the lawful field) and
    the law must cut it."""

    provenance = {"synthetic": "lawful ground + a mound over the ceiling"}
    MOUND = (-300.0, 300.0, -100.0, -50.0)    # x0, x1, y0, y1
    RISE = 2.0

    def z(self, x: float, y: float) -> float:
        base = super().z(x, y)
        x0, x1, y0, y1 = self.MOUND
        return base + self.RISE if x0 <= x <= x1 and y0 <= y <= y1 else base


class _CliffDem(_LawfulDem):
    """The lawful ground with a stretch of the south strip falling at 8 %
    — steeper than any corridor floor, so the law must FILL it."""

    provenance = {"synthetic": "lawful ground + an 8 % fall"}
    RUN = (-300.0, 300.0)

    def z(self, x: float, y: float) -> float:
        x0, x1 = self.RUN
        d = _outside(x, y)
        if x0 <= x <= x1 and y < _Y0 and d > 0.0:
            return _edge_z(x, y) - 0.08 * d
        return super().z(x, y)


def _runway_cells(r):
    return (Cell(0, "runway", "09/27", _rect(r, _X0, _Y0, _X1, _Y1), (), 3, "D",
                 "airside", "runway", {}),)


def _taxi_cells(r):
    return (*_runway_cells(r),
            Cell(1, "primary_parallel", "taxiA", _rect(r, *_TAXI), (), None, "D",
                 "airside", "taxi", {}),
            # the stub WELDS the taxiway to the runway: a taxi body carries
            # no datum of its own (10v), so a detached parallel is held by
            # bending alone and swings a metre — the fixture, not the law
            Cell(2, "stub", "stubB", _rect(r, -11.5, _Y1, 11.5, _TAXI[1]), (),
                 None, "D", "airside", "taxi", {}))


def _arm(law, dem, *, taxi: bool = False):                   # noqa: F811
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.solve import solve_design
    airport, r = _airport(law, dem, ())
    cells = _taxi_cells(r) if taxi else _runway_cells(r)
    cuts: tuple = ()
    if taxi:
        axis = tuple(r((x, 71.5)) for x in np.arange(_TAXI[0], _TAXI[2] + 0.1, 20.0))
        cuts = (CutLine("taxi_centerline", "taxiA", axis, "D"),)
    pm, _st = build(airport, Classification(cells, cuts, {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    if taxi:
        pm = with_taxi_trend(pm, law, airport, {})
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return pm, cs, sol, rep


def _no_datum_arm(law, dem, **kw):                           # noqa: F811
    """THE NO-DATUM ARM — the surface exactly as 09b (3) built it."""
    real = _design.ground_datum_vertices
    _design.ground_datum_vertices = lambda pm, lw: frozenset()
    try:
        return _arm(law, dem, **kw)
    finally:
        _design.ground_datum_vertices = real


@pytest.fixture(scope="module")
def lawful(law):                                             # noqa: F811
    return _arm(law, _LawfulDem())


@pytest.fixture(scope="module")
def lawful_no_datum(law):                                    # noqa: F811
    return _no_datum_arm(law, _LawfulDem())


def _ground(pm, law):                                        # noqa: F811
    return ground_datum_vertices(pm, law)


def _law_line(pm, law, v):                                   # noqa: F811
    """The corridor at ``v`` in metres of elevation: the runway EDGE level
    that governs it plus the signed ``zone_bounds`` offsets."""
    x, y = pm.vertices[v].xy
    lo, hi = zone_bounds(law, "runway", _outside(x, y), 3, "D")
    e = _edge_z(x, y)
    return (None if lo is None else e + lo, None if hi is None else e + hi)


def _pav(pm, *roles):
    return {v for v, vx in pm.vertices.items()
            if any(pm.faces[f].role in roles for f in vx.incident_faces)}


# ── (1) LAWFUL GROUND: the strip IS the ground ──────────────────────────

def test_the_strip_equals_the_natural_ground_where_the_ground_is_lawful(lawful, law):  # noqa: F811
    """The ruling's headline: where the ground already satisfies the zone
    law relative to its pavement, no row is active, the datum is the only
    term carrying a level, and the strip sits ON the DEM."""
    pm, _cs, sol, _rep = lawful[:4]
    z = np.asarray(sol.z, float)
    g = _ground(pm, law)
    assert g, "the fixture must have adjacent ground"
    off = [abs(z[v] - float(pm.vertices[v].dem_z)) for v in g]
    assert max(off) <= 0.05, f"worst {max(off):.3f} m off its DEM"


def test_the_datum_is_minted_for_every_adjacent_ground_vertex(lawful, law):  # noqa: F811
    """One row per adjacent-ground vertex, and the report counts them."""
    pm, cs, _sol, _rep = lawful[:4]
    rep = DesignReport()
    base = assemble(pm, cs, law, rep)
    minted = {own[1] for own in base.rows.owner if own and own[0] == "ground_datum"}
    assert minted == set(_ground(pm, law))
    assert rep.ground_datum_rows == len(minted) > 0


def test_the_pavement_does_not_move(lawful, lawful_no_datum, law):  # noqa: F811
    """THE ONE-WAY GUARANTEE (spec §23.3), measured.  The datum's row
    carries ONE column and that column is never a pavement vertex; every row
    coupling ground to pavement is ONE-WAY, so its pavement columns leave the
    matrix.  What is left is the shared bending stencil, which annihilates
    the affine field the datum gives a lawful strip — so the pavement here is
    identical to the no-datum arm to the solver's own tolerance, while the
    STRIP moves onto its ground."""
    pm, _cs, sol, _rep = lawful[:4]
    pm0, _cs0, sol0, _rep0 = lawful_no_datum[:4]
    z, z0 = np.asarray(sol.z, float), np.asarray(sol0.z, float)
    assert len(z) == len(z0)
    rwy = _pav(pm, "runway")
    assert rwy
    assert max(abs(z[v] - z0[v]) for v in rwy) <= 1.0e-3, "the runway moved"
    g = _ground(pm, law)
    assert max(abs(z0[v] - float(pm0.vertices[v].dem_z)) for v in g) > 0.20


# ── (2) GROUND ABOVE THE CEILING: cut to the law line, there only ───────

def test_ground_over_the_ceiling_is_cut_to_the_law_line_and_nowhere_else(law):  # noqa: F811
    """A 1 m mound over one stretch of the south strip: the corridor's
    CEILING binds there and the surface is cut to it; every vertex clear of
    the mound still equals its own DEM."""
    pm, _cs, sol, _rep = _arm(law, _MoundDem())[:4]
    z = np.asarray(sol.z, float)
    g = _ground(pm, law)
    x0, x1, y0, y1 = _MoundDem.MOUND
    on, off = [], []
    for v in g:
        x, y = pm.vertices[v].xy
        (on if x0 <= x <= x1 and y0 <= y <= y1 else off).append(v)
    assert on and off
    cuts = [float(pm.vertices[v].dem_z) - z[v] for v in on]
    assert min(cuts) > 0.5, f"the mound was not cut (min {min(cuts):.3f} m)"
    # held AT the ceiling: the law row is a one-sided PENALTY, so its
    # equilibrium against the datum leaves law/(law+ground_datum) of the
    # overshoot — 1 % of a metre — never a cut past the line
    over = [z[v] - _law_line(pm, law, v)[1] for v in on]
    assert max(over) <= 0.05, f"held {max(over):.3f} m over its ceiling"
    assert min(over) >= -0.10, f"cut {-min(over):.3f} m past its ceiling"
    clear = [v for v in off if not (x0 - 40.0 <= pm.vertices[v].xy[0] <= x1 + 40.0
                                    and pm.vertices[v].xy[1] < 0.0)]
    assert clear
    assert max(abs(z[v] - float(pm.vertices[v].dem_z)) for v in clear) <= 0.05


# ── (3) GROUND FALLING FASTER THAN THE LAW: filled at the law line ──────

def test_ground_falling_faster_than_the_law_is_filled_at_the_law_line(law):  # noqa: F811
    """An 8 % fall off the south edge: no corridor floor admits it, so the
    law FILLS to its floor — and the fill stops at the line."""
    pm, _cs, sol, _rep = _arm(law, _CliffDem())[:4]
    z = np.asarray(sol.z, float)
    g = _ground(pm, law)
    x0, x1 = _CliffDem.RUN
    on = [v for v in g if x0 <= pm.vertices[v].xy[0] <= x1
          and pm.vertices[v].xy[1] < _Y0 - 10.0]
    assert on
    fills = [z[v] - float(pm.vertices[v].dem_z) for v in on]
    assert min(fills) > 0.5, f"the fall was not filled (min {min(fills):.3f} m)"
    under = [_law_line(pm, law, v)[0] - z[v] for v in on]
    assert max(under) <= 0.10, f"held {max(under):.3f} m under its floor"
    assert min(under) >= -0.10, f"filled {-min(under):.3f} m past its floor"


# ── (4) THE BENDING CHANNEL, BOUNDED ────────────────────────────────────

def test_a_law_bound_strip_does_not_drag_the_taxiway_edge(law):  # noqa: F811
    """The one channel §23.3 cannot close by construction: a bending row
    centred on a pavement vertex carries its strip neighbours' columns.  The
    north strip here is judged against the TAXIWAY's edge while its ground
    is the runway's lawful field, so the datum and the law disagree over its
    whole length — the hardest case — and the taxiway's own edge still holds
    to the materiality floor."""
    dem = _LawfulDem()
    pm, _cs, sol, _rep = _arm(law, dem, taxi=True)[:4]
    pm0, _cs0, sol0, _rep0 = _no_datum_arm(law, dem, taxi=True)[:4]
    z, z0 = np.asarray(sol.z, float), np.asarray(sol0.z, float)
    assert len(z) == len(z0)
    moved = {r: max(abs(z[v] - z0[v]) for v in _pav(pm, r))
             for r in ("runway", "primary_parallel", "stub")}
    # MEASURED here: runway 0.027, primary_parallel 0.008, stub 0.061 — the
    # stub is 23 m wide with a law-bound strip on both sides in a two-ring
    # mesh, the coarsest geometry the channel can act through.  The real
    # bound is the airport bar (HECA per-role undulation within +5 % of
    # control); this twin holds the channel to a decimetre.
    assert max(moved.values()) <= 0.10, moved


# ── (5) THE DERIVATION SITE ─────────────────────────────────────────────

def test_no_pavement_vertex_carries_a_ground_datum(lawful, law):  # noqa: F811
    """08t (1): the designed surface keeps NO per-vertex DEM pull.  A vertex
    shared with pavement IS pavement."""
    pm, _cs, _sol, _rep = lawful[:4]
    pav = _pav(pm, "runway")
    for v in _ground(pm, law):
        assert v not in pav
        assert {pm.faces[f].role for f in pm.vertices[v].incident_faces} & {
            "graded_strip", "runway_clearance", "taxiway_clearance"}


@_dc.dataclass(frozen=True)
class _V:
    xy: tuple
    dem_z: float | None
    incident_faces: tuple


@_dc.dataclass(frozen=True)
class _E:
    left_face: int | None
    right_face: int | None


@_dc.dataclass(frozen=True)
class _F:
    id: int
    role: str
    ring: tuple
    holes: tuple = ()


class _Map:
    """The smallest map that states the enclosure rule: one OUTER strip face
    carrying an edge to the outside, and one strip face whose every edge
    borders pavement — an interior pocket."""

    def __init__(self):
        self.faces = {0: _F(0, "graded_strip", (0, 1)),      # outer
                      1: _F(1, "apron", (2, 3)),
                      2: _F(2, "graded_strip", (4, 5))}      # enclosed
        self.edges = {0: _E(0, None),                        # 0 -> outside
                      1: _E(0, 1),
                      2: _E(1, 2),                           # pocket <-> apron
                      3: _E(2, 1)}
        self.vertices = {v: _V((0.0, 0.0), 700.0, ()) for v in range(6)}

    def ring_vertices(self, cycle):
        return tuple(cycle)


def test_an_interior_pocket_takes_no_datum(law):             # noqa: F811
    """09g (1) stands: ground ENCLOSED by pavement is part of the design
    sheet with the DEM overridden there.  Only the strip face that reaches
    the patch's outer boundary carries datums."""
    assert ground_datum_vertices(_Map(), law) == frozenset({0, 1})
