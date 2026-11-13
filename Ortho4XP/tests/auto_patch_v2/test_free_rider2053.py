"""Owner RULINGS 2026-11-13r (#2053): a footed rider on NO surface of its
host stands on its own ground — only when certain.

SBRJ ``policeman4`` rode the floorless booth ``Guarita_Mil.obj`` (walls
authored to y -0.69) 0.69 m over the ground.  The twins: the booth frees
him; a terminal with a RAISED floor keeps its chairs (the named
``floor_fraction`` false positive); a rider half over a floor keeps his
group; feet outside the walls, an unreadable host and another member's
slab under him all keep the group.  Then the whole plan pass: the freed
rider is a unit of its own seated on the ground under it, and the host's
zero does not move.
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import rider_floor as RF
from auto_patch_v2.airport.contents import _poly
from auto_patch_v2.model.frame import m_per_deg_exact
from auto_patch_v2.model.rebake import Member, Part, Unit

LAT0, LON0 = -22.9, -43.1
ML, MO = m_per_deg_exact(LAT0)


def _ll(x: float, z: float) -> tuple[float, float]:
    """Authored (x, z) at heading 0 from the origin to (lat, lon)."""
    return LAT0 - z / ML, LON0 + x / MO


def _write_obj(path, quads) -> str:
    """An OBJ8 of quads, each four (x, y, z) corners."""
    vt, idx = [], []
    for q in quads:
        k = len(vt)
        vt += q
        idx += [k, k + 1, k + 2, k, k + 2, k + 3]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ")
                     + " ".join(str(i) for i in chunk))
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return str(path)


def _plate(x0, x1, z0, z1, y):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]


def _walls(h=1.0, lo=-0.69, hi=2.5):
    return [[(-h, lo, -h), (h, lo, -h), (h, hi, -h), (-h, hi, -h)],
            [(-h, lo, h), (h, lo, h), (h, hi, h), (-h, hi, h)],
            [(-h, lo, -h), (-h, lo, h), (-h, hi, h), (-h, hi, -h)],
            [(h, lo, -h), (h, lo, h), (h, hi, h), (h, hi, -h)]]


def _ring(x0, x1, z0, z1):
    return (_ll(x0, z0), _ll(x1, z0), _ll(x1, z1), _ll(x0, z1))


def _part(pid, x0, x1, z0, z1, base_y, height, feet_y=None):
    ring = _ring(x0, x1, z0, z1)
    la = [p[0] for p in ring]
    lo = [p[1] for p in ring]
    feet = () if feet_y is None else tuple(
        (*_ll(x, z), feet_y) for x, z in ((x0, z0), (x1, z1)))
    return Part(pid=pid, comp=0, lat=sum(la) / 4, lon=sum(lo) / 4,
                base_y=base_y, area_m2=(x1 - x0) * (z1 - z0),
                box=(min(la), min(lo), max(la), max(lo)), feet=feet,
                rings=(ring,), height_m=height)


def _member(mid, path, parts):
    return Member(id=mid, resource=mid + ".obj", authored_path=path,
                  live_path=path, heading_deg=0.0, parts=tuple(parts),
                  origin=(LAT0, LON0))


def _plan(tmp_path, host_quads, rider_box=(-0.2, 0.2, -0.2, 0.2),
          host_path=None, extra=(), walls_y=-0.69):
    hp = host_path or _write_obj(tmp_path / "host.obj", host_quads)
    host = _member("host", hp, [_part(0, -1.0, 1.0, -1.0, 1.0, walls_y,
                                      2.5 - walls_y, feet_y=walls_y)])
    rp = _write_obj(tmp_path / "rider.obj", [_plate(*rider_box, 1.7)])
    rider = _member("rider", rp, [_part(1, *rider_box, 0.0, 1.8, feet_y=0.0)])
    units = [Unit("unit:0", (LAT0, LON0), 0.0, (host,)),
             Unit("unit:1", (LAT0, LON0), 0.0, (rider,))]
    units += [Unit(f"unit:{2 + k}", (LAT0, LON0), 0.0, (m,))
              for k, m in enumerate(extra)]
    return types.SimpleNamespace(units=tuple(units), contacts=(),
                                 connectors=None, adapted_frame_pids=(),
                                 authored_seats=())


def _shim(member, ui, pid):
    p = member.parts[0]
    return types.SimpleNamespace(key=(ui, 0, 0), pids=frozenset({pid}),
                                 rings=p.rings, part_boxes=(p.box,))


def _free(plan) -> bool:
    shims = [_shim(u.members[0], ui, u.members[0].parts[0].pid)
             for ui, u in enumerate(plan.units)]
    w = RF.free_rider_witness(plan, shims,
                              lambda i: _poly(shims[i].rings,
                                              shims[i].part_boxes, ML, MO),
                              ML, MO, 1.0, 0.3)
    return w([1], 0)


def test_the_floorless_booth_frees_its_policeman(tmp_path):
    """Walls to y -0.69, a roof at 2.5 and a counter at 1.6 over him: no
    surface under his feet — certain."""
    q = _walls() + [_plate(-1, 1, -1, 1, 2.5), _plate(-0.3, 0.3, -0.3, 0.3, 1.61)]
    assert _free(_plan(tmp_path, q))


def test_a_raised_floor_terminal_keeps_its_chairs(tmp_path):
    """A floor 0.3 m over the walls' feet (``floor_fraction`` reads it as
    0: outside the contact band) is a surface under the chair."""
    q = _walls() + [_plate(-1, 1, -1, 1, 0.3), _plate(-1, 1, -1, 1, 2.5)]
    assert not _free(_plan(tmp_path, q))


def test_a_floor_wound_down_is_still_a_floor(tmp_path):
    q = _walls() + [list(reversed(_plate(-1, 1, -1, 1, 0.0)))]
    assert not _free(_plan(tmp_path, q))


def test_a_rider_half_over_a_floor_keeps_his_group(tmp_path):
    q = _walls() + [_plate(-1, 0.0, -1, 1, 0.0)]
    assert not _free(_plan(tmp_path, q))


def test_feet_outside_the_walls_keep_the_group(tmp_path):
    assert not _free(_plan(tmp_path, _walls(), rider_box=(0.8, 1.3, -0.2, 0.2)))


def test_walls_level_with_his_feet_keep_the_group(tmp_path):
    """Clause 4: the census found multi-file buildings' pieces (KBNA) and
    statues in a fence (KBUF) whose feet stand level with the host's walls
    — leaving lifts nothing, so they stay (and walls 0.2 m down: under
    ``split_tol_m``)."""
    q = _walls(lo=0.0) + [_plate(-1, 1, -1, 1, 2.5)]
    assert not _free(_plan(tmp_path, q, walls_y=0.0))
    q = _walls(lo=-0.2) + [_plate(-1, 1, -1, 1, 2.5)]
    assert not _free(_plan(tmp_path, q, walls_y=-0.2))


def test_an_unreadable_host_keeps_the_group(tmp_path):
    assert not _free(_plan(tmp_path, (), host_path=str(tmp_path / "gone.obj")))


def test_another_members_slab_under_him_keeps_the_group(tmp_path):
    sp = _write_obj(tmp_path / "slab.obj", [_plate(-1, 1, -1, 1, 0.0)])
    slab = _member("slab", sp, [_part(2, -1.0, 1.0, -1.0, 1.0, 0.0, 0.0)])
    assert not _free(_plan(tmp_path, _walls(), extra=(slab,)))


def _seats(plan, witness: bool):
    real = FU._rider_witness
    if not witness:
        FU._rider_witness = lambda *a, **k: None
    try:
        units, _c = FU.plan_units_and_connectors(plan, 0.5, 200.0, {}, 2.5,
                                                 0.95, 0.5)
    finally:
        FU._rider_witness = real
    z = FU.plan_unit_datums(units, plan, lambda la, lo: 10.0, (), 0.0, 0.0, 2.5)
    return {b: (u.id, z[u.id][0]) for u in units for b in u.bodies if u.id in z}


@pytest.mark.parametrize("floor", [False, True])
def test_the_plan_seats_the_freed_rider_on_its_ground(tmp_path, floor):
    q = _walls() + [_plate(-1, 1, -1, 1, 2.5)]
    if floor:
        q.append(_plate(-1, 1, -1, 1, 0.0))
    plan = _plan(tmp_path, q)
    before, after = _seats(plan, False), _seats(plan, True)
    assert before[(1, 0, 0)][1] == pytest.approx(10.69)        # 22b: on the walls
    assert after[(0, 0, 0)] == before[(0, 0, 0)]               # the host never moves
    if floor:
        assert after[(1, 0, 0)] == before[(1, 0, 0)]           # doubt: his group
    else:
        uid, zero = after[(1, 0, 0)]
        assert uid.endswith("/rider") and zero == pytest.approx(10.0)
