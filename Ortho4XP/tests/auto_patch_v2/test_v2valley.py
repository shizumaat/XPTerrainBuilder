"""SPEC §61 — THE TAXIWAY EDGE TAKES ITS CENTRELINE'S LEVEL, AND THE SOLVE
IS REPRODUCIBLE (owner RULINGS 2026-10-09e).

The finding: a taxi-family vertex off a SHORT centreline chain carried
bending only, a valley of the objective, so a constraint the surface already
SATISFIED moved hundreds of them (KCLT 506-615 vertices up to 0.81 m).  The
twins here are the stability bar at fixture scale — a NULL CHANGE moves
nothing — and the rows that make it so.
"""
from __future__ import annotations

import dataclasses as dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band, Source
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import DesignReport, assemble
from auto_patch_v2.solve.rows import _level_row_columns
from tests.auto_patch_v2 import test_v2taxidatum as T

#: the stability bar (§61 (6) 5): no vertex moves by this under a null change
BAR_M = 0.02


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def stub_problem(law):
    """The §8.6 stub fixture (an apron, a 1 km parallel and the 101 m link
    stub joining them — ``test_v2taxidatum.apron_and_parallel``) as the
    problem the solve is handed, before any solve."""
    airport, r = T._airport(law, T._RampDem())
    from auto_patch_v2.classify.roles import Cell, CutLine
    from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -T.RUN_LEN / 2, -HALF_WIDTH,
                                         T.RUN_LEN / 2, HALF_WIDTH), (), 3,
             "D", "airside", "runway", {}),
        Cell(1, "apron", "apronW", _rect(r, -520.0, 60.0, -320.0, 110.0), (),
             None, "D", "airside", "apron", {}),
        Cell(2, "primary_parallel", "pavT",
             _rect(r, -T.TAXI_LEN / 2, 200.0, T.TAXI_LEN / 2, 223.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(3, "stub", "linkW", _rect(r, -431.5, 110.0, -408.5, 200.0), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "pavT",
                    (r((-T.TAXI_LEN / 2, 211.5)), r((T.TAXI_LEN / 2, 211.5)))),
            CutLine("taxi_centerline", "linkW",
                    (r((-420.0, 110.0)), r((-420.0, 211.5)))))
    pm, _st = build(airport, Classification(cells, cuts, {}, ()), law)
    pm = with_taxi_trend(with_runway_chord(pm, law, airport), law, airport)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


def _z(pm, cs, law):
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return np.asarray(sol.z, float), rep


def _satisfied_ceilings(pm, z, n=12, margin=0.05):
    """``n`` ``Band`` ceilings ``margin`` ABOVE the surface's own level on
    apron / taxi-family vertices, by a fixed seed: constraints the surface
    already satisfies — a null change."""
    roles = {"apron", "junction", "primary_parallel", "stub", "cross_connector"}
    vs = sorted({v for f in pm.faces.values() if f.role in roles
                 for v in pm.ring_vertices(f.ring)})
    pick = np.random.default_rng(3).choice(len(vs), size=min(n, len(vs)),
                                           replace=False)
    src = Source("null_probe", "spec §61 null-change ceiling", ())
    return tuple(Band(vs[i], None, float(z[vs[i]]) + margin, src) for i in pick)


def test_the_stub_edge_is_named_by_its_centreline(stub_problem, law):
    """The rows exist where §61 puts them: the stub's side vertices carry a
    ``taxi_xsec`` row and no column of the taxi sheet is left with bending
    alone."""
    pm, cs = stub_problem
    rep = DesignReport()
    bp = assemble(pm, cs, law, rep)
    owners = [o for o in bp.rows.owner if o and o[0] == "taxi_xsec"]
    assert rep.taxi_xsec_rows == len(owners) > 0
    named = {int(bp.red.col[o[1]]) for o in owners}
    assert not ({o[1] for o in owners} & set(pm.taxi_trend_z)), \
        "a vertex with a trend row takes no cross-section row"
    lev = _level_row_columns(bp.rows, bp.body, bp.red.n_cols)
    taxi = set(law.tables.precedence.taxi_family.members)
    membrane = {int(bp.red.col[o[1]]) for o in bp.rows.owner
                if o and o[0] == "free_membrane"}
    for v, vx in pm.vertices.items():
        col = int(bp.red.col[v])
        if col < 0 or not any(pm.faces[f].role in taxi
                              for f in vx.incident_faces):
            continue
        assert lev[col] or col in named or col in membrane, \
            f"taxi-family vertex {pm.vertices[v].key} is held by bending alone"


def test_a_satisfied_ceiling_moves_nothing(stub_problem, law):
    """THE STABILITY BAR (§61 (6) 5): the same problem plus ceilings 0.05 m
    above its own answer is the same surface."""
    pm, cs = stub_problem
    z0, rep0 = _z(pm, cs, law)
    assert rep0.taxi_xsec_rows > 0
    bands = _satisfied_ceilings(pm, z0)
    z1, _rep1 = _z(pm, dc.replace(cs, bands=tuple(cs.bands) + bands), law)
    d = np.abs(z1 - z0)
    assert int((d > BAR_M).sum()) == 0, \
        f"{int((d > BAR_M).sum())} vertices moved under a null change, worst {d.max():.4f} m"
    assert d.max() < 0.005


def test_the_qp_exit_is_a_law_value(law):
    """§61 (4): the exit is ``[design] qp_rel_tol``, in the table."""
    d = law.tables.emit.design
    assert d.qp_rel_tol == 1e-12
    assert d.taxi_xsec == d.free_membrane == d.bend_taxi == 1.0
