"""#2072 / #1902: the airside on a hard deck's walls stands outside its
trench, and the deck's own ground always has a level (KIAH obj24551)."""
from __future__ import annotations

import types

from auto_patch_v2.constraints import edge_deck as ED
from auto_patch_v2.constraints import walled_plate as WP
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import airside_stage_roles
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.model.structures import DECK_GROUND_REF
from auto_patch_v2.solve import design_ground as DG

LAW = Law.for_airport("KIAH")
RING = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


def _pm(roles):
    return types.SimpleNamespace(
        decks=(types.SimpleNamespace(ring=RING, cut="bank"),),
        vertices={v: types.SimpleNamespace(xy=(5.0, 5.0)) for v in roles},
        roles_at=lambda v: roles[v])


def test_a_deck_station_on_the_wall_is_the_airsides_not_the_trenchs():
    """KIAH replay: the taxi deck's stations stood on the trench walls and
    counted inside the trench, so the taxiway's rows to the floor were kept
    and the floor and the deck pulled each other (2.89 m at obj24551)."""
    roles = {1: ("tunnel_ramp",), 2: ("retaining_wall", "junction"),
             3: ("tunnel_ramp", "junction"), 4: ("retaining_wall", "runway"),
             5: ("retaining_wall",)}
    floor, trench = ED.deck_floor(_pm(roles), airside_stage_roles(LAW))
    assert floor == {1, 3}
    assert trench == {1, 3, 4, 5}            # the station (2) is not the trench's
    # no airside roles given: as before, every wall vertex is the trench's
    assert ED.deck_floor(_pm(roles))[1] == {1, 2, 3, 4, 5}


def test_the_airside_row_to_the_floor_is_withdrawn_and_the_trench_law_kept():
    roles = {1: ("tunnel_ramp",), 2: ("retaining_wall", "junction"), 6: ("tunnel_ramp",)}
    floor, trench = ED.deck_floor(_pm(roles), airside_stage_roles(LAW))
    taxi = Diff(2, 1, 0.015, 20.0, Source("taxi", "x", ()))
    own = Diff(1, 6, 0.05, 20.0, Source("structures", "x", ()))
    out = WP.release_across([taxi, own], None, None, {}, under=floor, inside=trench,
                            keep=frozenset({"structures", ED.GEN}), key="k")
    assert out == [own]


def _ground_pm(xy_of, faces):
    vx = {v: types.SimpleNamespace(xy=xy, dem_z=1.0, incident_faces=tuple(
        fid for fid, (_r, _ref, ring) in faces.items() if v in ring))
        for v, xy in xy_of.items()}
    fs = {fid: types.SimpleNamespace(id=fid, role=role, ref=ref, ring=tuple(ring), holes=())
          for fid, (role, ref, ring) in faces.items()}
    return types.SimpleNamespace(
        decks=(types.SimpleNamespace(ring=RING),), vertices=vx, faces=fs,
        ring_vertices=lambda ring: tuple(ring), roles_at=lambda v: ("graded_strip",))


def test_a_deck_ground_vertex_a_zone_face_shares_outside_the_ring_keeps_its_datum():
    """KIAH obj24551: a deck-ground corner outside the ring that bounds a
    zone face had no span row and no datum; bending stood it 21.9 m up."""
    xy = {1: (5.0, 5.0), 2: (-3.0, 5.0), 3: (-3.0, 6.0), 4: (-6.0, 5.0), 5: (5.0, 1.0)}
    faces = {10: ("graded_strip", f"{DECK_GROUND_REF}:dsf:obj1", (1, 2, 3, 5)),
             11: ("graded_strip", "adjacent_ground:taxi:F:zone2#1", (2, 3, 4)),
             12: ("graded_strip", "adjacent_ground:taxi:F:zone2#2", (1, 5, 4))}
    got = DG._deck_ground_vertices(_ground_pm(xy, faces), {10, 11, 12})
    # 2, 3: outside the ring and shared with a zone face -> the zone's datum;
    # 1, 5: under the deck -> follow the deck even where a zone face shares them
    assert got == {1, 5}


def test_the_decks_own_ground_beyond_the_trench_reach_is_spanned():
    """A deck-ground face wider than the final trenches' reach: its vertices
    there still take the span pair to the nearest seat."""
    xy = {1: (0.0, 0.0), 2: (10.0, 0.0), 7: (-2.5, 5.0), 8: (-2.0, 6.0)}
    faces = {20: ("graded_strip", f"{DECK_GROUND_REF}:dsf:obj1", (7, 8, 1)),
             21: ("graded_strip", f"{DECK_GROUND_REF}:dsf:obj1#1", (7, 8, 2))}
    pm = _ground_pm(xy, faces)
    deck = types.SimpleNamespace(ring=RING)
    es = [types.SimpleNamespace(terms=((1, 1.0),), deck=deck, depth=7.0),
          types.SimpleNamespace(terms=((2, 1.0),), deck=deck, depth=7.0)]
    ends = [(e.terms, e.depth) for e in es]
    rows = ED._span_rows(pm, "dsf:obj1", es, (), set(), ends, 0.04)
    held = {r.terms[0][0] for r in rows if r.terms[0][1] > 0.0}
    assert {7, 8} <= held
