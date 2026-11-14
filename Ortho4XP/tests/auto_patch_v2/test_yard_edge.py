"""Spec 2068 A3 R3: A PROJECTED VERTEX IS NOT AN UNKNOWN (``constraints/
yard_edge``).  A fence yard's own vertex (no other face carries it) stands
on the fence-foot plane after the solve: the row across its stand-off, the
ceiling twin of that row and a road ramp row on it are withdrawn; a
single-vertex row of another family stays, and a vertex the yard shares
with another face keeps its rows."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.yard_edge import projected_vertices, yard_exempt
from auto_patch_v2.model.constraints import Band, Diff, Source


def _pm():
    faces = [("groundside_pavement", "fenceyard:0:building1", (0, 1, 2, 3)),
             ("apron", "dsf:pol96", (10, 11, 12, 13)),
             ("service_road", "road1", (2, 3, 20, 21))]      # shares 2, 3 with the yard
    return types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(faces)},
        ring_vertices=lambda ring: tuple(ring))


def _src(gen):
    return Source(gen, f"{gen} ruling", ("face:1", "dsf:pol96"))


def test_only_the_yards_own_vertices_are_projected():
    assert projected_vertices(_pm()) == frozenset({0, 1})
    empty = types.SimpleNamespace(faces={}, ring_vertices=lambda r: tuple(r))
    assert projected_vertices(empty) == frozenset()


def test_rows_across_a_projected_vertex_are_withdrawn():
    cross = Diff(1, 10, 0.05, 1.8, _src("groundside_ramp"), soft="groundside")
    twin = Diff(1, 10, 0.05, 1.8, _src("pavement_ceiling"))
    ramp = Band(0, 30.0, 31.0, _src("road_ramp"))
    single = Band(0, None, 40.0, _src("zones"))
    shared = Diff(2, 20, 0.08, 3.0, _src("roads"))
    other = Diff(10, 11, 0.05, 5.0, _src("apron_grade"))
    counts: dict = {}
    out = yard_exempt([cross, twin, ramp, single, shared, other], _pm(), counts)
    assert out == [single, shared, other]
    assert counts["yard_rows_withdrawn"] == 3


def test_no_yard_withdraws_nothing():
    pm = _pm()
    pm.faces = {k: f for k, f in pm.faces.items() if k != 0}
    rows = [Diff(1, 10, 0.05, 1.8, _src("groundside_ramp"))]
    counts: dict = {}
    assert yard_exempt(rows, pm, counts) is rows and counts["yard_rows_withdrawn"] == 0
