"""#1934 R3 (spec ``docs/specs/1934-R3.md`` §4): a structure's own floor is
no zone lip reference -- a pad or pavement edge ending on a ramp floor's
vertex is dropped from the zone law's references; every other edge of it
stays a reference.  MEASURED KLAX: a split-level building's lower-storey
corner on the north tunnel ramp held taxi F zone 2 on the taxiway bridge
3.7 m under its DEM (the owner's hole, 2026-11-16 14:32Z)."""
from __future__ import annotations

import types

from auto_patch_v2.constraints import zones as Z
from auto_patch_v2.law import Law


def _face(fid, role, ref):
    return types.SimpleNamespace(id=fid, role=role, ref=ref, code_number=None,
                                 code_letter=None)


def _view():
    law = Law.for_airport("ZZZZ")
    faces = [_face(1, "building", "b32"), _face(2, "tunnel_ramp", "tunnel_ramp"),
             _face(3, "junction", "pav10")]
    rings = {1: (10, 11, 12, 13), 2: (12, 13, 20, 21), 3: (30, 31, 32)}

    def faces_of_role(roles):
        return [f for f in faces if f.role in roles]
    return types.SimpleNamespace(law=law, faces_of_role=faces_of_role, rings=rings,
                                 holes={1: [], 2: [], 3: []})


def test_ramp_floor_vertices_are_read():
    assert Z._structure_floor_vertices(_view()) == frozenset({12, 13, 20, 21})


def test_an_edge_ending_on_a_ramp_floor_is_no_reference():
    keys = {(e[0], e[1]) for e in Z._pavement_edges(_view())}
    # the building's edges touching the ramp floor are gone, the rest stand
    assert (10, 11) in keys and (10, 13) not in keys
    assert (11, 12) not in keys and (12, 13) not in keys
    # the taxiway beside no ramp is untouched
    assert {(30, 31), (31, 32), (30, 32)} <= keys

