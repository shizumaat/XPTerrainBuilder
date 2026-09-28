"""§39 (1) NO VERTEX BESIDE AN EDGE — the vector map nodes a vertex that
stands on another constrained edge's interior (issue #71).

NLWF -14.31235, -178.06844 (tile -15-179, lane ``nlwfends_t2``): the shore
weld (§39 (1)) PROJECTS patch-ring vertex n171 onto the coastline edge
n170 -> n2687, as the law says; the ring runs along the coast n170 -> n171
and turns inland n171 -> n172.  In the tile's ``.poly`` the sea edge
n170 -> n2687 reached Triangle4XP WHOLE, with n171 0.036 mm beside it and
the seawall end n3370 0.008 mm beside it (two such sites, four pairs), and
Triangle4XP filled the hairlines with a Steiner cascade — 1,368,039
triangles under 0.01 m^2 and the DSF point pools pushed to quadtree
level 14.  A synthetic ``insert_way`` of the same coordinates nodes them,
so the insertion route that left the edge whole is NOT attributed; the
cure sits at the one site every route arrives at.

THE CURE (``Vector_Map.node_vertices_on_edges``): after ``snap_to_grid``
every constrained edge whose interior passes within ``split_spacing_m`` of
a node it does not end at is SPLIT AT that node.  Nothing moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from O4_Vector_Utils import Vector_Map                        # noqa: E402

# the measured nodes, tile-relative (lon + 179, lat + 15), from
# /tmp/harness/tile_nlwfends_t2/Data-15-179.node (lane nlwfends, cb4c76b2)
N170 = (0.931340200, 0.687678200)       # ring vertex snapped onto the coast
N171 = (0.931544466, 0.687648669)       # the PROJECTED ring vertex
N172 = (0.932053919, 0.687714225)       # the ring turning inland
N2687 = (0.931899100, 0.687597400)      # the coastline's next vertex
N3370 = (0.931561048, 0.687646272)      # the seawall's end on the coast
N3371 = (0.931544429, 0.687644133)      # ... and its next vertex


def _map():
    vm = Vector_Map()
    vm.split_spacing_m = 0.010
    vm.weld_spacing_m = 0.0
    return vm


def _insert(vm, pts, marker):
    vm.insert_way(numpy.array([[p[0], p[1], 0.0] for p in pts]), marker,
                  check=True)


def _nid(vm, p):
    return vm.dico_nodes[p] if p in vm.dico_nodes else min(
        vm.nodes_dico, key=lambda i: (vm.nodes_dico[i][0] - p[0]) ** 2
        + (vm.nodes_dico[i][1] - p[1]) ** 2)


def _has_edge(vm, a, b):
    return (a, b) in vm.dico_edges or (b, a) in vm.dico_edges


def _fixture():
    """The arrangement AS IT REACHED THE ``.poly`` (tile -15-179, lane
    ``nlwfends_t2``): the ring along the coast, the whole sea edge beside
    it, the seawall end on it.  Built edge by edge (``create_edge``, no
    encroachment test): a synthetic ``insert_way`` of the same four
    coordinates DOES node them, so the route by which the tile's own
    insertion order left the sea edge whole is not reproduced here — the
    pass below is the one site every route has arrived at, which is why
    the cure sits there.  The tile build is the interventional witness:
    4 splits, 4 -> 0 UNMESHABLE, 1,368,039 -> 38 triangles under 0.01 m^2
    with the patch body unchanged."""
    vm = _map()
    ids = {p: vm.insert_node(p[0], p[1], 0.0)
           for p in (N170, N171, N172, N2687, N3370, N3371)}
    interp = Vector_Map.dico_attributes["INTERP_ALT"]
    sea = Vector_Map.dico_attributes["SEA"]
    for a, b, m in ((N170, N171, interp), (N171, N172, interp),
                    (N170, N2687, sea), (N3370, N3371, interp)):
        vm.create_edge(ids[a], ids[b], m)
    vm.snap_to_grid(9)
    return vm


def test_the_fixture_is_the_unnoded_nlwf_arrangement():
    """The sea edge spans n171 (0.036 mm beside it) and n3370 (0.008 mm)."""
    vm = _fixture()
    assert _has_edge(vm, _nid(vm, N170), _nid(vm, N2687))


def test_noding_splits_the_sea_edge_at_both_vertices_on_it():
    vm = _fixture()
    n = vm.node_vertices_on_edges(vm.split_spacing_m, -15)
    a, b, s, c = (_nid(vm, N170), _nid(vm, N171), _nid(vm, N3370),
                  _nid(vm, N2687))
    assert n == 2
    assert not _has_edge(vm, a, c), "the sea edge still spans n171"
    # the chain along the coast is now a -> b -> s -> c
    assert _has_edge(vm, a, b) and _has_edge(vm, b, s) and _has_edge(vm, s, c)
    # the stretch the ring shares with the coast is ONE segment, both markers
    e = vm.dico_edges.get((a, b), vm.dico_edges.get((b, a)))
    assert vm.data_edges[e] & Vector_Map.dico_attributes["SEA"]
    assert vm.data_edges[e] & Vector_Map.dico_attributes["INTERP_ALT"]


def test_noding_moves_nothing_and_reaches_a_fixed_point():
    vm = _fixture()
    before = dict(vm.nodes_dico)
    vm.node_vertices_on_edges(vm.split_spacing_m, -15)
    assert vm.nodes_dico == before, "noding must never move a node"
    assert vm.node_vertices_on_edges(vm.split_spacing_m, -15) == 0


def test_a_vertex_beyond_the_radius_is_not_noded():
    """20 mm beside the line is a genuine near-parallel run (the hairline
    census prices it), not an un-noded arrangement."""
    vm = _map()
    off = 0.020 / 111319.49
    far = (N171[0], N171[1] + off)
    ids = [vm.insert_node(p[0], p[1], 0.0) for p in (N170, far, N2687)]
    vm.create_edge(ids[0], ids[1], Vector_Map.dico_attributes["INTERP_ALT"])
    vm.create_edge(ids[0], ids[2], Vector_Map.dico_attributes["SEA"])
    vm.snap_to_grid(9)
    assert vm.node_vertices_on_edges(vm.split_spacing_m, -15) == 0
