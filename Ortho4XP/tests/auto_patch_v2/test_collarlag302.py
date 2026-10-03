"""THE COLLAR'S COVERAGE EDGE IS GROUND (issue #302, lane ``collarlag302``).

HECA ``building75#collar`` (rim v21675 at 30.12086521267, 31.41819005825)
alternated +4.14 / -2.22 m between sweeps sw1020 / sw1021 with the nearest
change 174 m away.  MEASURED on the replay: the vertex is a collar OUTER
vertex on the COVERAGE EDGE whose only rows were its ONE-WAY 1:3 bank rows
(the platform leads) — all SLACK, 23 m from the plate — plus a bending
stencil of Σc² 0.0098: a near-null column whose height was wherever the
solve path stopped (107.2 m through lag round 4, 102.7 m from round 6).  The
lag's "NOT SETTLED" was a co-symptom, not the cause.

The fix is at the single derivation site of "which vertex is ground"
(``solve/design_ground.ground_datum_vertices``): a collar's own coverage-edge
vertex takes the weak §23 DEM datum, so it EQUALS the natural ground where
its bank is slack and is cut to the law line where the bank binds.  The
fixture is ``test_unitplatform_platform``'s pad (ground falling 4 % across
x, the pad's north rim on the coverage edge) on a DEM that also FALLS
``RIM_FALL_M`` over the pad's last ``RIM_FALL_RUN_M`` toward that rim — the
HECA shape, a rim standing above a road's lower ground — so a rim the bank
leaves slack has a level the plate's stencil cannot reproduce.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.constraints import generate
from auto_patch_v2.model.constraints import Band, Source
from auto_patch_v2.solve import design_ground, solve_design
from auto_patch_v2.solve.design_ground import (coverage_edge_collar_vertices,
                                               ground_datum_vertices)

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.planar.build import build

from test_unitplatform_platform import _coverage_collar_vertices, _cells, law  # noqa: F401
from test_v2frontage import _airport

#: the fixture DEM's fall toward the pad's coverage-edge rim (y = 300)
RIM_FALL_M = 4.0
RIM_FALL_RUN_M = 20.0


class _Dem:
    provenance = {"synthetic": "falling 4 % across x and 4 m toward the north rim"}

    def z(self, x: float, y: float) -> float:
        t = min(1.0, max(0.0, (y - (300.0 - RIM_FALL_RUN_M)) / RIM_FALL_RUN_M))
        return 700.0 - 0.04 * x - RIM_FALL_M * t

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return pm, airport


def _arm(law, **over):
    d = _dc.replace(law.tables.emit.design, **over)
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit, design=d)))


@pytest.fixture(scope="module")
def problem(built, law):
    pm, airport = built
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


def _far_vertex(pm, cov):
    """A runway vertex as far from the collar as the fixture allows."""
    rw = {v for f in pm.faces.values() if f.role == "runway"
          for v in pm.ring_vertices(f.ring)}
    c = np.mean([pm.vertices[v].xy for v in cov], axis=0)
    return max(rw, key=lambda v: float(np.hypot(*(np.asarray(pm.vertices[v].xy) - c))))


def test_the_coverage_edge_collar_vertex_is_ground(built, law):
    """The population is #223's (the collar's own vertices on an edge with
    no face beyond), and every one of them carries the ground datum."""
    pm, _a = built
    cov = _coverage_collar_vertices(pm, "padU")
    assert cov
    got = ground_datum_vertices(pm, law)
    assert cov <= got
    assert cov <= coverage_edge_collar_vertices(pm)


def test_the_rim_level_is_path_independent(problem, law):
    """A slack-bank rim has a level of its own: the same problem solved
    under a 3-round and a 12-round lag, and again under a far perturbation
    (a 0.30 m ceiling on the runway vertex farthest from the collar), puts
    every coverage-edge collar vertex at the same height."""
    pm, cs = problem
    cov = sorted(_coverage_collar_vertices(pm, "padU"))
    z3 = np.asarray(solve_design(pm, cs, _arm(law, one_way_max_rounds=3))[0].z, float)
    z12 = np.asarray(solve_design(pm, cs, _arm(law, one_way_max_rounds=12))[0].z, float)
    far = _far_vertex(pm, cov)
    src = Source("collarlag302", "far perturbation twin", ())
    cs2 = _dc.replace(cs, bands=tuple(cs.bands) + (Band(far, None, float(z3[far]) - 0.30, src),))
    zp = np.asarray(solve_design(pm, cs2, _arm(law, one_way_max_rounds=3))[0].z, float)
    assert float(np.max(np.abs(z3[cov] - z12[cov]))) <= 0.01
    assert float(np.max(np.abs(z3[cov] - zp[cov]))) <= 0.01


def test_a_slack_rim_rests_on_the_ground(problem, law):
    """Where the 1:3 bank from the platform does not bind, the rim EQUALS
    the natural ground (the datum is the only term with a level) — never a
    level the bending stencil extrapolated off the plate."""
    pm, cs = problem
    from auto_patch_v2.constraints import platform
    cov = _coverage_collar_vertices(pm, "padU")
    z = np.asarray(solve_design(pm, cs, law)[0].z, float)
    bs = float(law.tables.emit.design.bank_slope)
    rows = [r for r in platform.platform_collar_rows(pm, law) if r.a in cov]
    slack = [v for v in cov
             if all(abs(pm.vertices[v].dem_z - z[r.b]) < bs * r.d - 0.05
                    for r in rows if r.a == v)]
    assert slack, "the fixture must carry a rim the bank leaves slack"
    for v in slack:
        assert abs(z[v] - pm.vertices[v].dem_z) <= 0.10, (v, z[v], pm.vertices[v].dem_z)


def test_the_datum_never_moves_the_rim_off_its_ground(problem, law, monkeypatch):
    """The before-arm, printed: with the collar's coverage edge out of the
    ground set the rim keeps only its bank and its stencil.  On THIS fixture
    the stencil is well conditioned (bending Σc² ~1 on the rim column), so
    the before-arm already sits near the DEM and the twin cannot show the
    near-null column HECA's sliver collar carried (Σc² 0.0098, measured on
    the replay, see the module docstring); it pins only that the datum
    brings the rim no FARTHER from its ground."""
    pm, cs = problem
    cov = sorted(_coverage_collar_vertices(pm, "padU"))
    z_fix = np.asarray(solve_design(pm, cs, law)[0].z, float)
    monkeypatch.setattr(design_ground, "coverage_edge_collar_vertices",
                        lambda planar: set())
    assert not set(cov) & ground_datum_vertices(pm, law)
    z_off = np.asarray(solve_design(pm, cs, law)[0].z, float)
    dem = np.array([pm.vertices[v].dem_z for v in cov])
    off = float(np.max(np.abs(z_off[cov] - dem)))
    on = float(np.max(np.abs(z_fix[cov] - dem)))
    print(f"collarlag302 twin: max |z - DEM| on the coverage rim: "
          f"without the datum {off:.3f} m, with it {on:.3f} m")
    assert on <= off + 1e-6
