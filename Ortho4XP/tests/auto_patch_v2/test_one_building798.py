"""Owner RULINGS 2026-10-19u (#798 (a)): a multi-file building on pavement
seats on ONE shared datum (``footprint_unit._one_building_groups``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import one_building as OB

D = 1.0 / 111_320.0          # a metre of latitude


def _unit(uid, members, lat0, size_m=10.0):
    box = (lat0, -106.0, lat0 + size_m * D, -106.0 + size_m * D)
    return FU.PlanUnit(id=uid, bodies=(), pids=frozenset(), members=tuple(members),
                       boxes=(box,), area_m2=size_m * size_m)


def _run(units, pav, reach=2.5, span=200.0):
    out = {u.id: (100.0 + i, "", "ground") for i, u in enumerate(units)}
    return OB.one_building_groups(units, out, pav, reach, span)


def test_pieces_of_one_building_share_the_highest_datum():
    a = _unit("a", ["h1.obj", "h2.obj"], 39.0)
    b = _unit("b", ["h2.obj", "h3.obj"], 39.0 + 11 * D)       # 1 m apart
    got = _run([a, b], {"a": (101.5, frozenset({"h1.obj", "h2.obj"})),
                        "b": (100.4, frozenset())})
    assert got["a"] == (101.5, "", "one_building")
    assert got["b"] == (101.5, "", "one_building")


def test_one_walled_file_is_no_building():
    a = _unit("a", ["sign.obj", "kerb.obj"], 39.0)
    got = _run([a], {"a": (101.5, frozenset({"sign.obj"}))})
    assert got["a"] == (100.0, "", "ground")


def test_apart_or_unshared_units_keep_their_own_datum():
    a = _unit("a", ["h1.obj", "h2.obj"], 39.0)
    far = _unit("far", ["h2.obj", "h3.obj"], 39.0 + 20 * D)   # 10 m apart
    other = _unit("o", ["x.obj", "y.obj"], 39.0 + 11 * D)     # no shared file
    pav = {"a": (101.0, frozenset({"h1.obj", "h2.obj"})),
           "far": (103.0, frozenset({"h2.obj", "h3.obj"})),
           "o": (104.0, frozenset({"x.obj", "y.obj"}))}
    got = _run([a, far, other], pav)
    assert got["a"][0] == 101.0 and got["far"][0] == 103.0 and got["o"][0] == 104.0


def test_a_structure_past_the_connector_span_is_no_building():
    rail = _unit("r", ["pillar.obj", "base.obj"], 39.0, size_m=300.0)
    got = _run([rail], {"r": (101.0, frozenset({"pillar.obj", "base.obj"}))})
    assert got["r"] == (100.0, "", "ground")


def test_walled_files_reads_the_part_height():
    tall = types.SimpleNamespace(pid=1, height_m=6.0)
    low = types.SimpleNamespace(pid=2, height_m=0.3)
    plan = types.SimpleNamespace(units=[types.SimpleNamespace(members=[
        types.SimpleNamespace(resource="wall.obj", parts=[tall]),
        types.SimpleNamespace(resource="kerb.obj", parts=[low])])])
    assert OB.walled_files([tall, low], plan, 2.5) == frozenset({"wall.obj"})
    assert OB.walled_files([tall, low], plan, 0.0) == frozenset({"wall.obj", "kerb.obj"})
