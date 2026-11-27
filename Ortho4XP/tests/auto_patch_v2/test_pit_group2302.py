"""RULINGS 2026-11-27f (owner 2026-11-27T18:03Z, #2302 LEMD central pit): the
placements of a pit an object floor owns -- the floor, its covers (the
retaining walls) and the frame's placements standing in it -- are no channel's
wall or floor witness (``planar/object_floor_cells.pit_group``, read by
``planar/build.channels_after_basins`` as §45 (13) (d)'s exclusion).

LEMD ``channel:6``: road -1895 loops inside the Ground-FSX pit; the pit group
(LEMD85 floor, LEMD03 walls, LEMD36 contents) witnessed it, its flat floor was
the group's deepest solid (588.97) and its width the walls' reach (67.4 m), so
the channel stood the ground 5.94 m under LEMD03's outer foot (594.9) outside
the walls the object floor trims it back to."""
from __future__ import annotations

import importlib
import types

from auto_patch_v2.planar.object_floor_cells import pit_group
from shapely.geometry import box

_build = importlib.import_module("auto_patch_v2.planar.build")


def _floor(hidden=False):
    return types.SimpleNamespace(
        object_id="floor", covers=("walls",), hidden=hidden, footprint=box(0, 0, 100, 60),
        seats=(("floor", "f.obj", 596.0), ("walls", "w.obj", 596.0),
               ("inside", "i.obj", 596.0), ("elsewhere", "e.obj", 596.0),
               ("nobelow", "n.obj", 596.0)))


def _obj(oid, bg):
    return types.SimpleNamespace(id=oid, below_grade=bg)


_OBJECTS = [_obj("floor", box(0, 0, 100, 60)), _obj("walls", box(-2, -2, 102, 62)),
            _obj("inside", box(40, 20, 60, 40)), _obj("elsewhere", box(500, 500, 600, 600)),
            _obj("nobelow", None)]


def test_the_group_is_the_floor_its_walls_and_what_stands_in_it():
    assert pit_group([_floor()], _OBJECTS) == {"floor", "walls", "inside"}


def test_a_hidden_floor_names_no_group():
    """a floor owning no ground leaves its cut to the map's own laws (2026-11-06d (1))"""
    assert pit_group([_floor(hidden=True)], _OBJECTS) == frozenset()


def test_both_channel_reads_take_the_group(monkeypatch):
    seen = []

    def fake(airport, classification, law, objects, claimed, pit=frozenset(), *a, **k):
        seen.append(frozenset(pit))
        return [types.SimpleNamespace(witness_ids=("x",))], types.SimpleNamespace(notes=[])

    monkeypatch.setattr(_build, "identify_channels", fake)
    monkeypatch.setattr(_build, "build_structures", lambda *a, **k: (None, (), None))
    monkeypatch.setattr(_build, "build_basins",
                        lambda *a, **k: (None, [types.SimpleNamespace(member_ids=("b",))], None))
    _build.channels_after_basins(None, None, None, (), (), (), (), None, None, frozenset(),
                                 frozenset(), floor_group=frozenset({"g"}))
    assert seen == [frozenset({"g"}), frozenset({"g", "b"})]
