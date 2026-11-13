"""ONE FRAME SEAT FOR A STOREY SHELL (#2062 R2, spec
``2062-storey-shell-spec`` §1 "Frame"; ``airport/storey_seat``): the
shell's own frame and every frame lying half inside its plan are written
whole at the building's zero plus each row's lift; a frame outside keeps
today's path.  Synthetic: no pack, no airport."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import storey_seat as SS
from shapely.geometry import box


def _row(oid, xy, lift, bbox, heading=0.0):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=f"/p/{oid}.obj",
                                 xy=xy, heading_deg=heading, agl_m=lift, plan_bbox=bbox)


def _shell():
    plan = box(0, 0, 40, 30)
    return types.SimpleNamespace(id="a", member_ids=("a", "a2"), plan=tuple(plan.exterior.coords),
                                 pad_ref="blk", levels=(0.0, 6.0), block=0)


def _pm(z=29.0):
    face = types.SimpleNamespace(ref="blk", ring=(0, 1, 2, 3), holes=())
    xy = {0: (0, 0), 1: (40, 0), 2: (40, 30), 3: (0, 30)}
    pm = types.SimpleNamespace(faces={0: face}, ring_vertices=lambda r: r,
                               vertices={v: types.SimpleNamespace(xy=p) for v, p in xy.items()})
    return pm, (lambda x, y: z)


def test_joined_frames_take_one_zero_plus_their_own_lift():
    objs = [_row("a", (20, 15), 0.0, box(0, 0, 40, 30)),
            _row("a2", (20, 15), 0.3, box(0, 0, 40, 30)),          # the shell's own frame
            _row("p", (30, 25), 6.2, box(28, 22, 34, 29)),         # people on its upper floor
            _row("p2", (30, 25), 11.0, box(29, 23, 33, 28)),       # ... their frame
            _row("x", (80, 15), 0.0, box(70, 5, 90, 25))]          # a frame outside
    pm, z_at = _pm()
    recs = SS.seat_records([_shell()], pm, z_at, objs, 1.0)
    got = {r["id"]: r["elevation"] for r in recs}
    assert got == {"a": 29.0, "a2": 29.3, "p": 35.2, "p2": 40.0}
    assert {r["seat"] for r in recs} == {SS.SEAT} and {r["zero"] for r in recs} == {29.0}


def test_a_frame_mostly_outside_the_shell_keeps_its_path():
    objs = [_row("a", (20, 15), 0.0, box(0, 0, 40, 30)),
            _row("c", (45, 15), 0.0, box(38, 0, 60, 30))]         # 2 of 22 m inside
    pm, z_at = _pm()
    assert [r["id"] for r in SS.seat_records([_shell()], pm, z_at, objs, 1.0)] == ["a"]


def test_no_solved_block_no_seat():
    pm, _z = _pm()
    assert SS.seat_records([_shell()], pm, lambda x, y: None,
                           [_row("a", (20, 15), 0.0, box(0, 0, 40, 30))], 1.0) == []


def test_the_seat_is_a_written_row_seat():
    from auto_patch_v2.airport import terrain_shaped as TS
    assert TS._WHY[SS.SEAT] == "storey_shell"
    assert SS.block_zero(_shell(), *_pm(31.5)) == pytest.approx(31.5)
