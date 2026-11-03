"""#1726 (KBWI, owner sim read 2026-11-03: "the terminal complex still has
some slight separation with skylights and some jetway elements
offset/floating maybe 1m").  Three general rules:

* the re-seated parts that ε-touch a TERRAIN-ADAPTED member of their own
  frame are named at the partition (``adapted_riders.touching_adapted``),
  carried on the plan, and their connected unit takes that member's zero —
  the mesh at the frame origin plus the row's lift
  (``footprint_unit._adapted_zero``), which ``root_zeros`` never moves;
* a footless own-ground piece of a file touching it takes it too
  (``open_frame_seat.group_zero``'s ``adapted_zero``);
* a multi-anchor row whose whole geometry hangs above its origin rides the
  unit its anchor stands in (``hung_rows``), unless a row at its origin
  stands on the ground."""
from __future__ import annotations

import json
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport.adapted_riders import (
    ADAPTED_SRC,
    frame_zero,
    member_zeros,
    touching_adapted,
)
from auto_patch_v2.airport.hung_rows import hung_rows
from auto_patch_v2.airport.placement_file import OWN_GROUND
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model.rebake import RebakePlan, Unit


def _part(pid):
    return types.SimpleNamespace(pid=pid, feet=((0.0, 0.0, 0.0),))


def _member(mid, *pids):
    return types.SimpleNamespace(id=mid, resource=mid + ".obj",
                                 parts=tuple(_part(q) for q in pids))


def test_only_parts_touching_an_adapted_member_of_their_own_frame_are_named():
    shell, inner = _member("shell", 1, 2), _member("inner", 3, 4)
    other = _member("other", 5)                   # another anchor family
    units = [types.SimpleNamespace(members=(shell, inner)),
             types.SimpleNamespace(members=(other,))]
    contacts = [(1, 3), (2, 5), (4, 4)]
    assert touching_adapted(units, {}, contacts, frozenset({"shell"})) == {3}


def test_the_adapted_zero_is_the_surface_at_the_origin_plus_the_lift():
    assert frame_zero(lambda la, lo: 42.58, (39.0, -76.0), 0.0) == 42.58
    assert frame_zero(lambda la, lo: 40.0, (39.0, -76.0), 1.5) == 41.5
    assert frame_zero(lambda la, lo: None, (39.0, -76.0), 0.0) is None


def test_every_piece_of_a_unit_touching_it_takes_the_adapted_zero():
    """KBWI ``fu:6:6`` (interior + skylights) stood at the pad's 42.80 minus
    its walls' base (-0.41) = 43.21 over a shell draped at 42.58."""
    pieces = [types.SimpleNamespace(id="fu:6:6/b0", pids={10, 11}),
              types.SimpleNamespace(id="fu:6:6/b1", pids={12})]
    frame_of = {10: ((39.0, -76.0), 0.0), 11: ((39.0, -76.0), 0.0),
                12: ((39.0, -76.0), 0.0)}
    memo: dict = {}
    for un in pieces:
        assert FU._adapted_zero(un, pieces, {12}, frame_of,
                                lambda la, lo: 42.58, memo) == 42.58
    lone = types.SimpleNamespace(id="fu:6:9", pids={20})
    assert FU._adapted_zero(lone, [lone], {12}, {20: ((39.0, -76.0), 0.0)},
                            lambda la, lo: 42.58, {}) is None


def test_root_zeros_reads_the_adapted_seat():
    plan = types.SimpleNamespace(
        units=(types.SimpleNamespace(id="unit:6", agl_m=0.0,
                                     members=(_member("inner", 1),)),),
        adapted_frame_pids=(1,))
    zs = OFS.root_zeros({1: ("fu:6:6", 42.58, "", ADAPTED_SRC)}, plan)
    assert zs["fu:6:6|unit:6"] == (42.58, 0.0)


def _body(i, zero, reason):
    a = AR.Anchor(AR.OTHER, 40.0, -3.0, 45.0 - zero, reason, 45.0,
                  offset=(0.0, 45.0 - zero, 0.0))
    return Body(i, AR.OTHER, (i,), a, f"objects/sky__b{i}.obj")


def test_a_loose_own_ground_piece_of_a_touching_file_takes_the_adapted_zero():
    """KBWI ``KBWI_WIndows.obj`` b6-b13: skylight panes with no carrier
    stood on the ground under them, 41.46 and 44.99 against 42.58."""
    m = types.SimpleNamespace(id="dsf:obj6074", resource="objects/sky.obj", zero_y=0.0)
    rec = Split(0, m.id, m.resource, "/x/" + m.resource, 40.0, -3.0, 0.0,
                (_body(0, 41.46, f"{OWN_GROUND}: no carrier"),
                 _body(1, 44.99, f"{OWN_GROUND}: no carrier"),
                 _body(2, 47.00, "carried by another file")))
    counts: dict = {}
    out = OFS.group_zero(rec, m, {}, {}, counts, "unit:6", adapted_zero=42.58)
    got = [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies]
    assert got == [42.58, 42.58, 47.0]
    assert counts["adapted_frame_loose_bodies"] == 2


def test_member_zeros_names_the_files_that_touch():
    plan = types.SimpleNamespace(
        units=(types.SimpleNamespace(anchor=(39.0, -76.0), agl_m=0.0,
                                     members=(_member("sky", 1), _member("cargo", 2))),),
        adapted_frame_pids=(1,))
    assert member_zeros(plan, lambda la, lo: 42.58) == {"sky": 42.58}


def _obj(path, ys):
    vt = "".join(f"VT {i} {y} 0 0 1 0 0 0\n" for i, y in enumerate(ys))
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(ys)} 0 0 3\n"
                    f"{vt}IDX 0 1 2\nTRIS 0 3\n", encoding="utf-8", newline="\n")


def _row(path, lat, lon):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=0.0,
                                 kind="OBJECT", elevation=None)


def test_a_row_hangs_only_when_its_whole_origin_point_hangs(tmp_path):
    """GateDoor (lowest vertex 3.0 m) hangs; a figure whose animated legs
    reach y = 0 never does; a sign panel at its post's origin stays with
    the post (KIAH's road signs)."""
    _obj(tmp_path / "door.obj", [3.0, 3.0, 4.0])
    _obj(tmp_path / "man.obj", [0.0, 1.7, 1.8])
    _obj(tmp_path / "post.obj", [0.0, 6.0, 6.0])
    _obj(tmp_path / "panel.obj", [6.4, 6.4, 7.0])
    rows = [_row("door.obj", 40.0, -3.0), _row("man.obj", 40.1, -3.0),
            _row("panel.obj", 40.2, -3.0), _row("post.obj", 40.2, -3.0),
            _row("lib/stock.obj", 40.3, -3.0)]
    ask = hung_rows(rows, str(tmp_path), 0.5)
    assert [ask(i) for i in range(len(rows))] == [True, False, False, False, False]
    assert hung_rows(rows, str(tmp_path), 0.0) is None


def test_a_hung_row_in_a_unit_box_takes_the_units_zero():
    rows = [_row("objects/door.obj", 40.0005, -2.9995),
            _row("objects/door.obj", 40.0008, -2.9992)]
    dump = types.SimpleNamespace(placements=rows)
    plan = types.SimpleNamespace(units=())
    box = [(40.0, -3.0, 40.001, -2.999, 42.58, ADAPTED_SRC)]
    counts: dict = {}
    got = FU.msl_seats_for_dump(dump, plan, box, lambda la, lo: 42.80, "",
                                frozenset(), counts=counts, hung=lambda i: True)
    assert [(s.elevation, s.why) for s in got] == [(42.58, "hung")] * 2
    assert FU.msl_seats_for_dump(dump, plan, box, lambda la, lo: 42.80, "",
                                 frozenset(), hung=lambda i: False) == ()


def test_the_plan_carries_the_adapted_parts():
    p = RebakePlan("ICAO", "pack", "/p", (Unit("unit:0", (1.0, 2.0), 0.0, ()),),
                   (), {}, adapted_frame_pids=(3, 7))
    assert RebakePlan.from_json(json.dumps(p.to_dict())).adapted_frame_pids == (3, 7)
    assert "adapted_frame_pids" not in RebakePlan("I", "p", "/p", (), (), {}).to_dict()
