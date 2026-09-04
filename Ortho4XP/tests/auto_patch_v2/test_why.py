"""Twins for ``solve/why.py`` — WHAT BINDS THIS SHAPE (lane v2why).

A synthetic apron behind a parallel taxiway and a stub from a PINNED
runway, on a DEM that climbs steeply away from the runway: the apron
wants to be higher than the taxi chain allows, so ``why`` must trace a
chain of binding rows from the apron to the runway pin, name the taxi /
no-step families along it, and its relax-one-family numbers must sum
sanely.  The code-letter evidence reads apt.dat 1202 edges by geometry.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack, TaxiEdge, TaxiNode)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import why


class _SteepDem:
    """1 % along the runway, 4 % climbing away from it (y): the apron at
    y ≈ 100..250 wants 4..10 m above the runway, far more than a 1.5 %
    stub over 60 m and a 1 % apron can carry."""

    provenance = {"synthetic": "plane 1 % in x, 4 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + 0.04 * max(0.0, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def prepared(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    # apt.dat 1201/1202: taxiway "A" along the parallel taxiway, width class B
    nodes = {1: TaxiNode(1, (-400.0, 91.5), "both"), 2: TaxiNode(2, (400.0, 91.5), "both"),
             3: TaxiNode(3, (0.0, 0.0), "both"), 4: TaxiNode(4, (0.0, 130.0), "both")}
    edges = (TaxiEdge(1, 2, "A", False, False, "B"),
             TaxiEdge(3, 4, "B1", False, False, "A"))
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), nodes, edges,
                      (), (), (), (), (), (), pack, _SteepDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(-200, 103, 200, 250), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5))),
            # the stub's lane runs INTO the apron (an apron lane is apron, 09-03j)
            CutLine("taxi_centerline", "stubB", ((0.0, 0.0), (0.0, 130.0))))
    cl = Classification(cells, cuts, {}, ())
    pm, _stats = build(airport, cl, law)
    cs, counts, _w = generate(pm, law, airport)
    prob, res = why.solve_with_duals(pm, cs, DEFAULT_WEIGHTS)
    assert res.status == 0, res.message
    import numpy as np
    z = np.asarray(res.x[:prob.n], float)
    esc = {g: float(res.x[c]) for g, c in prob.soft_cols.items()}
    return why.Prepared("ZZZZ", airport, law, pm, cs, counts, DEFAULT_WEIGHTS,
                        prob, res, z, esc, {})


def _apron_face(prep) -> int:
    return next(f.id for f in prep.pm.faces.values() if f.role == "apron")


def test_apron_is_held_below_its_dem(prepared):
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    zd = prepared.z[verts] - prepared.dem[verts]
    assert float(zd.min()) < -1.0, "the fixture must make the taxi chain bind"


def test_chain_trace_reaches_the_runway_pin_through_the_taxi_families(prepared):
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    tr = why.chain_trace(prepared, verts)
    assert tr is not None, "the apron must be chained to something"
    # the chain ends AT THE RUNWAY: a CIFP pin, or a runway vertex the
    # objective holds (weight 20) when the profile between pins is slack
    term_roles = {prepared.pm.faces[f].role for f in prepared.pm.vertices[tr.terminal].incident_faces}
    assert "runway" in term_roles, (tr.terminal_kind, tr.terminal_note, term_roles)
    assert tr.terminal_kind in ("PIN", "FREE"), tr.terminal_kind
    if tr.terminal_kind == "PIN":
        assert "CIFP" in tr.terminal_note
    else:
        assert "fit weight 20" in tr.terminal_note
    fams = {s.family for s in tr.steps}
    assert fams & {"no_step_pairs", "taxi_within_shape", "taxi_centreline",
                   "apron_within_shape"}, fams
    # the bounds along the chain sum to the height difference
    assert tr.sum_dz == pytest.approx(prepared.z[tr.start] - prepared.z[tr.terminal], abs=1e-6)
    from auto_patch_v2.model.constraints import Diff
    for s in tr.steps:
        assert s.v != s.u, s
        if isinstance(s.row, Diff):          # a Diff step sits exactly on its bound
            assert s.dz == pytest.approx(s.bound_m, abs=1e-5), s


def test_bindings_have_zero_slack_and_name_successors(prepared):
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    bl = why.bindings(prepared, verts)
    n = sum(len(v) for v in bl.values())
    assert n > 0
    for v, lst in bl.items():
        for b in lst:
            assert b.v == v and b.slack_m <= why.BIND_TOL_M
            assert b.family
            if b.note not in ("PIN", "FLAT") and not b.note.startswith("BAND"):
                assert b.must_rise, b


def test_relax_one_family_numbers_sum_sanely(prepared):
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    bl = why.bindings(prepared, verts)
    fams = sorted({b.family for lst in bl.values() for b in lst} - {"runway_pins"})
    assert fams
    singles = {f: why.relax_family(prepared, f, verts) for f in fams}
    for f, r in singles.items():
        assert r.status == "optimal", (f, r)
        assert r.dz_min >= -1e-6, (f, r)            # relaxing never lowers a held-down apron
        assert r.dz_median <= r.dz_max + 1e-9
    # all binding families together: the ceiling no single arm exceeds
    rows = [r for r in prepared.cs.rows() if why.family_of(r) not in set(fams)]
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.solve.highs import solve
    sol = solve(prepared.pm, ConstraintSet.from_rows(rows), prepared.weights)
    import numpy as np
    z2 = np.asarray(sol.z, float)
    ceiling = float(np.median(z2[verts] - prepared.z[verts]))
    assert ceiling > 0.5
    for f, r in singles.items():
        assert r.dz_median <= ceiling + 1e-6, (f, r.dz_median, ceiling)
    # at least one family, relaxed alone, lets the apron rise materially
    assert max(r.dz_median for r in singles.values()) > 0.05


def test_code_letter_evidence_reads_1202_by_geometry(prepared):
    fid = _apron_face(prepared)
    lines = why.taxi_letters(prepared, fid)
    assert lines, "the stub's lane runs into the apron"
    joined = "\n".join(lines)
    assert "B1 ['A']" in joined, joined           # the 1202 edge along the stub lane
    assert "stub/D@1.5%" in joined, joined


def test_family_labels_cover_every_row(prepared):
    seen = {why.family_of(r) for r in prepared.cs.rows()}
    assert seen <= {lbl for _g, _k, lbl in why._FAMILY_KEYS} | {"structures", "contiguity"}, seen


def test_resolve_faces_by_coordinate_and_by_id(prepared):
    fid = _apron_face(prepared)
    faces, how = why.resolve_faces(prepared, shape=fid)
    assert faces == [fid] and "face" in how
    _to_xy, to_ll = prepared.airport.frame.transformers()
    lat, lon = to_ll(0.0, 180.0)
    faces, how = why.resolve_faces(prepared, at=(lat, lon))
    assert faces == [fid], how
    faces, how = why.resolve_faces(prepared, shape=10_000)
    assert faces == [] and "no face" in how


def test_report_renders_every_section(prepared):
    fid = _apron_face(prepared)
    text = why.report(prepared, fid, max_relax=2)
    for key in ("== face", "binding rows", "chain trace", "relax one family",
                "code-letter evidence", "terminal"):
        assert key in text, key
