"""#1883 twins: a channel whose floor the pack states seats its frame at
the zero the floor was read at (``airport/channel_zero``), its witness
plate published by ``pipeline/rebake_inputs._channel_plates``."""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import channel_zero as CZ
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.pipeline import rebake_inputs as RI

FLOOR = 66.47


def _body(i, zero, reason):
    a = AR.Anchor(AR.BASIN, 37.93, 23.94, 70.0 - zero, reason, 70.0,
                  offset=(0.0, 70.0 - zero, 0.0))
    return Body(i, AR.BASIN, (i,), a, f"objects/liner__b{i}.obj")


def test_the_witness_plate_is_published_for_a_pack_floored_channel_only():
    axis = tuple((float(i), 0.0) for i in range(40))
    ch = types.SimpleNamespace(id="channel:3", datum_source="pack", axis=axis,
                               witness_ids=("dsf:obj7",))
    out: dict = {}
    RI._channel_plates(out, types.SimpleNamespace(channels=(ch,)), set())
    y, st, clear, kind = out["dsf:obj7"]
    assert (y, clear, kind) == (0.0, 0.0, "channel:3") and st
    out = {}
    RI._channel_plates(out, types.SimpleNamespace(channels=(
        types.SimpleNamespace(id="channel:3", datum_source="lidar", axis=axis,
                              witness_ids=("dsf:obj7",)),)), set())
    assert out == {}


def test_the_rim_seated_bodies_of_the_frame_take_the_floor_zero():
    """LGAV: the liner pieces on the channel's rim stood 58.6-68.8 against
    a 66.47 floor; the witness's deepest solid (y -11.24) on the floor puts
    the frame's zero at 77.71 and every rim body of THAT channel there."""
    w = types.SimpleNamespace(plate_kind="channel:0", plate_y=-11.24,
                              plate_stations=((37.92, 23.93), (37.93, 23.94)))
    zeros = CZ.channel_zeros([w, types.SimpleNamespace(plate_kind="edge")],
                             lambda la, lo: FLOOR)
    assert abs(zeros["0"] - (FLOOR + 11.24)) < 1e-9
    rim = _body(0, 69.84, "basin rim (channel_wall:0#1@199): the object's zero is the rim")
    other = _body(1, 69.84, "basin rim (channel_wall:2#0@5): the object's zero is the rim")
    foot = _body(2, 76.34, "low-side foot")
    assert [CZ.rim_channel(b) for b in (rim, other, foot)] == ["0", "2", None]
    rec = Split(0, "dsf:obj1", "objects/liner.obj", "/x/liner.obj", 37.93, 23.94, 0.0,
                (rim, other, foot))
    m = types.SimpleNamespace(resource="objects/liner.obj", zero_y=0.0)
    out = OFS.at_zero(rec, m, zeros["0"], lambda b: CZ.rim_channel(b) == "0", "floor zero")
    got = [round(b.anchor.surface_z - b.anchor.y_zero, 6) for b in out.bodies]
    assert got == [round(FLOOR + 11.24, 6), 69.84, 76.34]
