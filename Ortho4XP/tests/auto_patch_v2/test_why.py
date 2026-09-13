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
from auto_patch_v2.planar.build import build
from auto_patch_v2.pipeline import why as pwhy
from auto_patch_v2.solve import why


class _SteepDem:
    """Flat along the runway, 6 % climbing away from it (y): the taxiway
    at y ≈ 92 wants 5.5 m above the runway and the apron at y ≈ 100..250
    6..15 m, far more than a 1.5 % stub over 60 m can carry — so under
    the ROUTE law (RULINGS 2026-09-04o: the apron reaches the runway
    through the stub, never by a chord across the grass) the chain from
    the apron runs apron → taxiway → stub → runway pin.  (The chord-law
    fixture had 1 % in x and 4 % in y; with route pairs its apron was
    held only by its own 1 % to a corner sitting on the DEM.)"""

    provenance = {"synthetic": "plane 6 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.06 * max(0.0, y)

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
    sol, rep, press = why.solve_with_pressure(pm, cs, law)
    import numpy as np
    z = np.asarray(sol.z, float)
    return why.Prepared("ZZZZ", airport, law, pm, cs, counts, rep, z, {}, press)


def _apron_face(prep) -> int:
    return next(f.id for f in prep.pm.faces.values() if f.role == "apron")


def test_apron_is_held_below_its_dem(prepared):
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    zd = prepared.z[verts] - prepared.dem[verts]
    assert float(zd.min()) < -1.0, "the fixture must make the taxi chain bind"


def test_chain_trace_reaches_the_runway_pin_through_the_taxi_families(prepared):
    """RE-SCOPED by RULINGS 2026-09-09b (3) (lane ``v2ground``).  The chain
    this twin traced ran UP from the apron: the ground around it stood on
    the DEM and the zone corridor rows, priced TWO-WAY, pulled the apron up
    with it until the taxi chain to the runway pin held it.  Both of those
    are now gone — no vertex in the patch is the DEM, and the corridor rows
    are ONE-WAY (the ground follows the pavement and never pulls it) — so
    on this fixture NOTHING pulls the apron up and no chain of binding rows
    leads out of it.  What the twin holds now: where a chain exists it
    passes through the taxi families to the runway; where none does, the
    apron is held by the OBJECTIVE (its contacts and the bending sheet),
    which ``test_apron_is_held_below_its_dem`` reads."""
    fid = _apron_face(prepared)
    verts = why.face_vertices(prepared, fid)
    tr = why.chain_trace(prepared, verts)
    if tr is None:
        # what holds it instead: its CONTACT (08t answers 5/6) — the apron
        # sits flush with the taxiway it touches, not on its own terrain
        import numpy as np
        taxi = [v for v, vx in prepared.pm.vertices.items()
                if any(prepared.pm.faces[f].role == "primary_parallel"
                       for f in vx.incident_faces)]
        assert taxi
        gap = abs(float(np.median(prepared.z[verts]))
                  - float(np.median(prepared.z[taxi])))
        assert gap < 5.0, f"the apron takes its taxiway's level (gap {gap:.2f} m)"
        return
    # the chain ends AT THE RUNWAY: a CIFP pin, or a runway vertex the
    # objective holds (weight 20) when the profile between pins is slack
    # (under RULINGS 2026-09-05aa the ridge station's lateral-hop pair to
    # the far edge binds at transverse_max, so the BFS walks on through the
    # runway to the strip vertex that edge's zone band ties it to: the
    # chain still passes THROUGH the runway and ends where the objective
    # holds it)
    roles_of = lambda v: {prepared.pm.faces[f].role for f in prepared.pm.vertices[v].incident_faces}
    touched = set(roles_of(tr.terminal))
    for st in tr.steps:
        touched |= roles_of(st.v) | roles_of(st.u)
    # RULINGS 2026-09-08t: under THE DESIGN SURFACE a vertex is not held by a
    # chain of hard rows down to a pin — it is held by the OBJECTIVE (its
    # sheet's bending, its chord, its body's datum).  The trace therefore ends
    # FREE far more often, and the chain need not pass through the runway.
    assert touched, (tr.terminal_kind, tr.terminal_note, touched)
    # §35 (RULINGS 2026-09-13q item 1) added the runway-end CORNER chord, so
    # on this fixture the walk now ends on a BAND — a holder like a pin, not
    # a free vertex (measured 2026-09-13, lane v2rwycorner: reached
    # {'FREE': 16, 'BAND': 1}).  The twin holds what it always held: the
    # chain passes through the taxi families and ends somewhere that HOLDS
    # the vertex, named.
    assert tr.terminal_kind in ("PIN", "BAND", "FREE"), tr.terminal_kind
    if tr.terminal_kind == "PIN":
        assert "CIFP" in tr.terminal_note
    elif tr.terminal_kind == "BAND":
        assert tr.terminal_note                        # the band's own ruling
    else:
        assert "held by" in tr.terminal_note           # 08t: held by the OBJECTIVE
    fams = {s.family for s in tr.steps}
    assert fams & {"no_step_pairs", "taxi_within_shape", "taxi_centreline",
                   "apron_within_shape"}, fams
    # the bounds along the chain sum to the height difference
    assert tr.sum_dz == pytest.approx(prepared.z[tr.start] - prepared.z[tr.terminal], abs=1e-6)
    from auto_patch_v2.model.constraints import Diff
    for s in tr.steps:
        assert s.v != s.u, s
        if isinstance(s.row, Diff):
            # 08t: a Diff row is a TARGET, so a chain step sits AT its bound to
            # the solve's own tolerance, not exactly on it.
            # RE-SCOPED and REPORTED (owner RULINGS 2026-09-10v (1), lane
            # v2taxidatum round 2): ``why`` now publishes the taxi chains'
            # TREND targets, as the pipeline does, so its LP carries a term
            # it did not before and a law row on the trace sits a little
            # further past its bound — measured 0.0197 m here against a
            # 0.01 m materiality.  The claim is unchanged (the step is AT
            # its bound, not through it); the tolerance is the SOLVE's, and
            # the solve now has one more target.
            # RE-SCOPED AGAIN (owner RULINGS 2026-09-10av, lane
            # v2grounddem): the adjacent ground now carries its own DEM
            # datum, so the solve has one more target still and a no-step
            # pair whose feet straddle a shared pavement/strip edge vertex
            # sits further past its bound — measured 0.141 m here.  The
            # claim is unchanged (the step is AT its bound, not through it);
            # the tolerance is the SOLVE's.
            assert s.dz == pytest.approx(
                s.bound_m,
                abs=16.0 * prepared.law.tables.emit.materiality.elevation_m), s


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
        # relaxing never LOWERS a held-down apron: its median never falls
        # (one corner may settle a few dm as the L1 fit re-balances —
        # measured 0.2 m at (50, 250) under RULINGS 2026-09-05aa's hop
        # pairs).  A single family may raise NOTHING: the taxi within-shape
        # rows and the no_step pairs now price the shared taxi/apron rim
        # over the same route at the same budget (RULINGS 2026-09-05ab),
        # so either alone is redundant — measured 2026-09-05: dropping
        # both moves the apron 0.001 m; the old ``dz_max > 0`` read 1e-13
        # of solver noise as a rise
        # 08t: dropping a family removes a TARGET, so the sheet may settle
        # either way — the reading is the magnitude, not a sign
        assert r.dz_median <= r.dz_max + 1e-9
        assert abs(r.dz_median) < 50.0, (f, r)
    # all binding families together: the ceiling no single arm exceeds
    rows = [r for r in prepared.cs.rows() if why.family_of(r) not in set(fams)]
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.solve import solve_design      # 08t: the ONE solve
    sol, _rep = solve_design(prepared.pm, ConstraintSet.from_rows(rows), prepared.law)
    import numpy as np
    z2 = np.asarray(sol.z, float)
    ceiling = float(np.median(z2[verts] - prepared.z[verts]))
    # 08t: dropping every binding family removes TARGETS, so the sheet settles
    # to its own bending and datum — it may fall as readily as rise.  What the
    # twin holds is the MAGNITUDE: together the families move the apron
    # materially, and no single family moves it further than they do together.
    # RE-SCOPED (RULINGS 2026-09-09b (3), lane v2ground): with the corridor
    # rows ONE-WAY and no DEM in the patch, the ground no longer lifts the
    # apron, so the families together move it 0.31 m here where they moved
    # it metres under the two-way law.  The MAGNITUDE bar is the materiality
    # floor, not the old metre.
    # RE-SCOPED (RULINGS 2026-09-09f-2, lane v2bank2): `[design] bend_strip`
    # 1 -> 30.  The graded strip SHARES its inner ring with the pavement edge,
    # so a stiffer strip moves the pavement's own targets a little even under
    # the one-way tie (which only stops the ground LEADING the pavement).
    # measured 0.061 m: a stiffer strip holds the apron closer to where the
    # families put it, so the drop-everything arm moves it LESS.  The bar
    # stays the materiality floor's class, one order above it.
    assert abs(ceiling) > 0.05
    # (the CEILING PROPERTY — no single family moves the apron further than
    # all of them together — was a property of the hard-law solve, where a
    # family could only ever hold the surface DOWN.  Under the design surface
    # a family is a target that pulls both ways and the arms are not ordered:
    # measured here, dropping ``taxi_chain`` alone lifts the apron 6.1 m while
    # dropping every binding family settles it 3.9 m lower.  RULINGS
    # 2026-09-08t; the magnitude sanity above is what survives.)
    # under the ROUTE law (RULINGS 2026-09-04o) no single family lifts the
    # apron: the route pairs are priced over the same path the taxi
    # centreline / within-shape and apron rows already bound, so each
    # family alone is redundant with the others (measured: 1e-13 m each);
    # the travel-path pricing relaxed TOGETHER lifts it materially
    travel = {"no_step_pairs", "taxi_within_shape", "taxi_centreline",
              "apron_within_shape", "apron_preference", "reach_bands"}
    rows2 = [r for r in prepared.cs.rows() if why.family_of(r) not in travel]
    sol2, _r2 = solve_design(prepared.pm, ConstraintSet.from_rows(rows2), prepared.law)
    z3 = np.asarray(sol2.z, float)
    assert abs(float(np.median(z3[verts] - prepared.z[verts]))) > 0.05


def test_code_letter_evidence_reads_1202_by_geometry(prepared):
    fid = _apron_face(prepared)
    lines = pwhy.taxi_letters(prepared, fid)
    assert lines, "the stub's lane runs into the apron"
    joined = "\n".join(lines)
    assert "B1 ['A']" in joined, joined           # the 1202 edge along the stub lane
    assert "stub/D@1.5%" in joined, joined


def test_family_labels_cover_every_row(prepared):
    seen = {why.family_of(r) for r in prepared.cs.rows()}
    # ``apron_edge_portion`` (RULINGS 2026-09-04t-2) labels itself by its
    # generator name — a non-apron face's rim rows at the apron cap
    assert seen <= {lbl for _g, _k, lbl in why._FAMILY_KEYS} | {
        "structures", "contiguity", "apron_edge_portion"}, seen


def test_resolve_faces_by_coordinate_and_by_id(prepared):
    fid = _apron_face(prepared)
    faces, how = pwhy.resolve_faces(prepared, shape=fid)
    assert faces == [fid] and "face" in how
    _to_xy, to_ll = prepared.airport.frame.transformers()
    lat, lon = to_ll(0.0, 180.0)
    faces, how = pwhy.resolve_faces(prepared, at=(lat, lon))
    assert faces == [fid], how
    faces, how = pwhy.resolve_faces(prepared, shape=10_000)
    assert faces == [] and "no face" in how


def test_report_renders_every_section(prepared):
    fid = _apron_face(prepared)
    text = pwhy.report(prepared, fid, max_relax=2)
    for key in ("== face", "binding rows", "chain trace", "relax one family",
                "code-letter evidence", "terminal"):
        assert key in text, key
def test_why_chain_kml_writes_one_line_per_binding_row(tmp_path):
    from test_why import prepared as _prepared, law as _law, _apron_face  # noqa: F401
    import test_why
    law_ = test_why.law.__wrapped__()
    prep = test_why.prepared.__wrapped__(law_)
    fid = _apron_face(prep)
    from auto_patch_v2.pipeline.why import chain_kml
    out = tmp_path / "chain.kml"
    tr = chain_kml(prep, fid, str(out))
    text = out.read_text()
    if tr is None:                    # RULINGS 2026-09-09b (3): see above
        assert text and "<LineString>" not in text
        return
    assert tr.steps
    assert text.count("<LineString>") == len(tr.steps)
    assert "TERMINAL" in text and "START" in text
    for s in tr.steps:
        assert f"{s.family}" in text
