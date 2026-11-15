"""Spec 2068 A3 R3: A PROJECTED VERTEX IS NOT AN UNKNOWN (``constraints/
yard_edge``).  A fence yard's own vertex (no other face carries it) stands
on the fence-foot plane after the solve: the row across its stand-off, the
ceiling twin of that row and a road ramp row on it are withdrawn; a
single-vertex row of another family stays, and a vertex the yard shares
with another face keeps its rows."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.yard_edge import (
    projected_vertices,
    yard_exempt,
    yard_records,
    yard_runs,
)
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band, Diff, Source
from auto_patch_v2.model.registries import FLOOR_YARD, Registries

LAW = Law.for_airport("SYNT")


def _pm():
    faces = [("groundside_pavement", "fenceyard:0:building1", (0, 1, 2, 3)),
             ("apron", "dsf:pol96", (10, 11, 12, 13)),
             ("service_road", "road1", (2, 3, 20, 21))]      # shares 2, 3 with the yard
    return types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(faces)},
        ring_vertices=lambda ring: tuple(ring),
        registries=types.SimpleNamespace(landings={}))


def _src(gen):
    return Source(gen, f"{gen} ruling", ("face:1", "dsf:pol96"))


def test_only_the_yards_own_vertices_are_projected():
    assert projected_vertices(_pm(), LAW) == frozenset({0, 1})
    empty = types.SimpleNamespace(faces={}, ring_vertices=lambda r: tuple(r))
    assert projected_vertices(empty, LAW) == frozenset()


def test_rows_across_a_projected_vertex_are_withdrawn():
    cross = Diff(1, 10, 0.05, 1.8, _src("groundside_ramp"), soft="groundside")
    twin = Diff(1, 10, 0.05, 1.8, _src("pavement_ceiling"))
    ramp = Band(0, 30.0, 31.0, _src("road_ramp"))
    single = Band(0, None, 40.0, _src("zones"))
    shared = Diff(2, 20, 0.08, 3.0, _src("roads"))
    other = Diff(10, 11, 0.05, 5.0, _src("apron_grade"))
    counts: dict = {}
    out = yard_exempt([cross, twin, ramp, single, shared, other], _pm(), LAW, counts)
    assert out == [single, shared, other]
    assert counts["yard_rows_withdrawn"] == 3


def test_no_yard_withdraws_nothing():
    pm = _pm()
    pm.faces = {k: f for k, f in pm.faces.items() if k != 0}
    rows = [Diff(1, 10, 0.05, 1.8, _src("groundside_ramp"))]
    counts: dict = {}
    assert yard_exempt(rows, pm, LAW, counts) is rows and "yard_rows_withdrawn" not in counts


def test_a_record_with_no_yard_face_is_no_record_and_no_run():
    """Spec 2068 A4 F1' (b): a yard record stands only while a yard face of
    its pad stands in the map (KMCI building43: a held floor pad's record
    drove a road run with no yard face)."""
    rec = {"yard_plane": (0.2, 0.0, 0.0, 0.0, 0.0), "yard_hull": ((0, 0), (9, 0), (9, 9)),
           "y_p": 0.0}
    pm = _pm()
    pm.registries = Registries(held={"building2": {FLOOR_YARD: dict(rec)}},
                               landings={"u/p1": dict(rec, pad="building1")})
    assert sorted(yard_records(pm)) == ["u/p1"]           # building1 has its yard face
    pm.faces = {k: f for k, f in pm.faces.items() if k != 0}
    assert yard_records(pm) == {} and yard_runs(pm, LAW) == []
