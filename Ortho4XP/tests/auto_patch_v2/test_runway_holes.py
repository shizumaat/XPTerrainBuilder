"""A RUNWAY FACE WITH A HOLE PRICES EVERY VERTEX (lane ``rwyholes``; the
RULINGS 2026-09-13dd chip).

On lane v2roles' HECA arm (``frames.py list HECA`` → ``v2roles_HECA``) 8
of 33 runway faces were ANNULI — §40 shoulder ribbons wrapping their
``adjacent_ground:runway`` zone-strip islands — and their 490 hole
vertices, the runway's own (I5 lists the runway face at each), were
declared no crown drop and stated in no crown / transverse row, because
``crown_drops`` / ``runway_crown`` / ``runway_transverse`` read
``vw.rings[f.id]`` — the OUTER ring — while the census judged those
vertices at the runway's cap.

The fixture is that class: the crown fixture's runway with a
``graded_strip`` island cut into one half off the ridge (a pavement role
would be ABSORBED as a notch by §41 (1); a strip is not a shape role and
stays a hole).  The twins hold:

* the generators and the verifier read ONE vertex set per face through
  ONE accessor (``model.planar.face_vertex_ids`` ← ``View.face_vertices``
  / ``Shape.vertex_ids``), and agree on its count, face by face;
* every hole vertex carries a designed crown drop, a crown row and a
  transverse row; the built declaration covers it; the census's
  ``runway_transverse`` DEFECT family stays empty on the solved surface.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.constraints import generate, runway_profile
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.model.planar import face_vertex_ids
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.verify import census
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import crown_by_vertex
from tests.auto_patch_v2.test_crown import (HALF_WIDTH, Airport, Cell, Classification,
                                            CutLine, Frame, Runway, RunwayEnd,
                                            SceneryPack, _PlaneDem, _rect, _rot, build)

RUNWAY_FAMILY = runway_profile.RUNWAY_FAMILY


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def build_annulus(law):
    """The crown fixture's airport with a zone-strip ISLAND inside one
    runway half (x 150..190, y 4..16: off the ridge, inside the half
    width), so that half's face is a ring around a hole — HECA's
    05L/23R shoulder class."""
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", r((600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    island = _rect(r, 150, 4, 190, 16)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -600, -HALF_WIDTH, 600, HALF_WIDTH),
             (island,), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "graded_strip", "island1", island, (), None, None, "airside", "strip", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", (r((-400.0, 91.5)), r((400.0, 91.5)))),
            CutLine("taxi_centerline", "stubB", (r((0.0, HALF_WIDTH)), r((0.0, 91.5)))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


@pytest.fixture(scope="module")
def annulus(law):
    return build_annulus(law)


def _hole_vertices(pm, law) -> tuple[int, set[int]]:
    vw = view(pm, law)
    holed = [f for f in vw.faces_of_role(RUNWAY_FAMILY) if vw.holes[f.id]]
    assert len(holed) == 1, [(f.id, f.role) for f in holed]
    f = holed[0]
    return f.id, {v for h in vw.holes[f.id] for v in h}


def test_fixture_is_a_runway_annulus(annulus, law):
    airport, pm = annulus
    vw = view(pm, law)
    fid, hv = _hole_vertices(pm, law)
    assert len(hv) >= 3
    outer = {v for f in vw.faces_of_role(RUNWAY_FAMILY) for v in vw.rings[f.id]}
    ridge = {v for chs in runway_profile.ridge_chains(vw).values() for c in chs for v in c}
    assert not (hv & outer) and not (hv & ridge)
    island = [f for f in pm.faces.values() if f.ref == "island1"]
    assert [f.role for f in island] == ["graded_strip"]
    # the hole vertices ARE the runway face's (I5)
    assert all(fid in pm.vertices[v].incident_faces for v in hv)


def test_face_vertex_ids_is_outer_then_holes_each_once(annulus, law):
    assert face_vertex_ids([1, 2, 3], [[4, 5], [5, 6]]) == [1, 2, 3, 4, 5, 6]
    assert face_vertex_ids([7, 8, 9], []) == [7, 8, 9]
    _airport, pm = annulus
    vw = view(pm, law)
    for fid in pm.faces:
        ids = vw.face_vertices(fid)
        assert ids == face_vertex_ids(vw.rings[fid], vw.holes[fid])
        assert len(ids) == len(set(ids))
        assert set(ids) == set(vw.rings[fid]) | {v for h in vw.holes[fid] for v in h}


def test_generators_price_every_hole_vertex(annulus, law):
    airport, pm = annulus
    vw = view(pm, law)
    fid, hv = _hole_vertices(pm, law)
    designed = runway_profile.crown_drops(pm, law, airport)
    assert hv <= set(designed) and all(designed[v] > 0.0 for v in hv)
    crown = runway_profile.runway_crown(pm, law, airport)
    crowned = {r.terms[0][0] for r in crown if isinstance(r, Linear)}
    assert hv <= crowned
    trans = runway_profile.runway_transverse(pm, law, airport)
    bounded = {v for r in trans for v, c in r.terms if c == -1.0}
    assert hv <= bounded
    # ONE population: every off-ridge vertex of every runway-family face,
    # outer and hole rings alike, carries exactly one crown row and one
    # transverse row (no crossing here: nothing is exempt)
    ridge = {v for chs in runway_profile.ridge_chains(vw).values() for c in chs for v in c}
    every = {v for f in vw.faces_of_role(RUNWAY_FAMILY) for v in vw.face_vertices(f.id)}
    assert set(designed) == every
    assert crowned == every - ridge and len(crown) == len(crowned)
    assert bounded == every - ridge and len(trans) == len(bounded)


def test_census_and_generator_read_one_vertex_set(annulus, law):
    airport, pm = annulus
    vw = view(pm, law)
    fid, hv = _hole_vertices(pm, law)
    cs, _c, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    p = Patch.of(surf, law, pub)
    by_key = {sh.key: sh for sh in p.shapes}
    # face by face, the verifier's vertex set IS the generator's
    for f in pm.faces.values():
        assert set(by_key[f.id].vertex_ids) == set(vw.face_vertices(f.id))
        assert len(by_key[f.id].vertex_ids) == len(vw.face_vertices(f.id))
    sh = by_key[fid]
    assert len(sh.vertex_ids) == len(sh.ids) + len(hv) and hv <= set(sh.vertex_ids)
    # the BUILT declaration covers the hole vertices, and the census reads it
    declared = crown_by_vertex(p)
    assert hv <= set(declared)
    built = runway_profile.crown_drops(pm, law, airport, sol.z)
    assert set(built) == set(runway_profile.crown_drops(pm, law, airport))
    rows = census(surf, law, pub)
    assert rows["runway_transverse"] == []
    hole_xy = {tuple(round(c, 2) for c in p.xy[v]) for v in hv}
    on_holes = [r for r in rows["runway_crown"] if tuple(r["site_m"][0]) in hole_xy]
    assert on_holes == []
