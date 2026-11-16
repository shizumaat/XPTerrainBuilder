"""#2127 (LGAV owner sim read 2026-11-16, item 1): a taxi centreline that
runs over a structure's cut on a deck states no level on the cut.

The taxiway crossing a pack trench on a deck kept its centreline rows
across the trench floor and wall void, so the floor's pin (the trench
floor 66 m) pulled the taxiway on both banks down to it: the taxiway and
apron around the bridge solved 6-9 m under the DEM and the pack's deck.
``stretches.edge_cap`` is the one reader of a centreline edge's cap
(taxi centreline rows, the route graph, the transverse axes); an edge
bounded by a cut's faces alone is no law edge there.  The deck's end
lines (``constraints/edge_deck``) carry the route across.

And a frame shell that states no cut of its own (no footprint, not
hidden) may ride a deck piece of the frame (``planar/floor_decks``): LGAV
``Trench_01``'s bridges stood at the frame zero while the deck they carry
was seated by its end lines.
"""
from __future__ import annotations

import types

from shapely.geometry import Polygon

from auto_patch_v2.constraints import stretches as S
from auto_patch_v2.law import Law
from auto_patch_v2.planar import floor_decks as FD

LAW = Law.for_airport("ZZZZ")


def _pm(left: str, right: str | None):
    faces = {1: types.SimpleNamespace(role=left)}
    if right is not None:
        faces[2] = types.SimpleNamespace(role=right)
    edge = types.SimpleNamespace(left_face=1, right_face=2 if right is not None else None)
    return types.SimpleNamespace(edges={7: edge}, faces=faces)


def _st():
    item = types.SimpleNamespace(cap_l=0.015, cap_t=0.015)
    return types.SimpleNamespace(by_edge={7: 0}, items=[item])


def test_a_centreline_edge_over_a_cut_alone_is_no_law_edge():
    caps = {1: (0.10, 0.10), 2: (0.10, 0.10)}
    for left, right in (("tunnel_trench", "retaining_wall"), ("retaining_wall", None),
                        ("retaining_wall", "retaining_wall"), ("tunnel_ramp", "tunnel_trench")):
        assert S.edge_cap(_pm(left, right), LAW, _st(), 7, caps) is None, (left, right)


def test_a_centreline_edge_beside_pavement_keeps_its_stretch_cap():
    caps = {1: (0.015, 0.015), 2: None}
    got = S.edge_cap(_pm("primary_parallel", "retaining_wall"), LAW, _st(), 7, caps)
    assert got == (0.015, 0.015)


def test_a_shell_stating_no_cut_may_ride_and_a_cut_or_hidden_shell_never():
    cut = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    hidden = types.SimpleNamespace(object_id="hidden", hidden=True, footprint=Polygon())
    owner = types.SimpleNamespace(object_id="owner", hidden=False, footprint=cut)
    liner = types.SimpleNamespace(object_id="liner", hidden=False, footprint=Polygon())
    assert FD.stating_cut([liner, hidden, owner]) == {"hidden", "owner"}
