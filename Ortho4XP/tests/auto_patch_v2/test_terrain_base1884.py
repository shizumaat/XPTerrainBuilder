"""#1884 round 2 (A): A WALLED BUILDING AUTHORED ON ITS AUTHOR'S TERRAIN
STANDS ON OURS (``airport/terrain_base``), at both sites — §16 (3)'s own
ground (``placement_file._own_ground_file``) and a footless unit's wall
base (``footprint_unit._wall_base``).

LOWS ``domiki_lows_14`` (47.74974, 13.00860): a hilltop house authored
33.6 m over its placement's zero, nothing under it, floated 33.6 m.
Synthetic and hermetic: one OBJ8 holding a walled house 60 m north of the
origin, authored 20 m up, read through the engine's own parser; the
surface is a hill under the house."""
from __future__ import annotations

import os
import types

import pytest

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport import terrain_base as TB
from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

from test_v2objsplit import _box, _write_obj  # noqa: E402

LAT, LON = 40.0, -3.0
ARGS = dict(split_tol_m=0.3, elevated_base_m=0.5, bind_ground_m=0.5,
            coarsen_reach_m=100.0, chain_min_height_m=2.5)
NORTH = 30.0 / 111000.0           # the hill starts 30 m north of the origin


def _prism(x0, z0, w, y0, y1):
    v, t = _box(x0, z0, side=w, h=1.0)
    return [(x, y0 + y * (y1 - y0), z) for x, y, z in v], t


def _obj(tmp_path, shapes):
    verts, tris = [], []
    for v, t in shapes:
        tris += [(a + len(verts), b + len(verts), c + len(verts)) for a, b, c in t]
        verts += v
    return _write_obj(tmp_path / "house.obj", verts, [("", tris)])


def _plan(path, lift=0.0):
    g = obj8.parse_obj8(str(path))
    ml, mo = AR._m_per_deg(LAT)
    parts = []
    for ci, c in enumerate(obj8.solid_components(g)):
        v = g.vertices[sorted({int(i) for i in c.tris.reshape(-1)})]
        x0, x1 = float(v[:, 0].min()), float(v[:, 0].max())
        z0, z1 = float(v[:, 2].min()), float(v[:, 2].max())
        y0, y1 = float(v[:, 1].min()), float(v[:, 1].max())
        box = (LAT - z1 / ml, LON + x0 / mo, LAT - z0 / ml, LON + x1 / mo)
        la, lo = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        feet = ((la, lo, y0),) if y0 <= 0.5 else ()
        parts.append(Part(pid=ci, comp=ci, lat=la, lon=lo, base_y=y0,
                          area_m2=(x1 - x0) * (z1 - z0), box=box, feet=feet,
                          height_m=y1 - y0))
    m = Member(id="dsf:obj1", resource="objects/house.obj", authored_path=str(path),
               live_path=str(path), heading_deg=0.0, parts=tuple(parts))
    return RebakePlan(icao="TEST", pack_name="pack", pack_root=os.path.dirname(str(path)),
                      units=(Unit("u0", (LAT, LON), lift, (m,)),), skipped=(), counts={})


def _hill(top):
    """10 m at the origin; north of ``NORTH`` the hill, ``top`` m rising
    0.1 m per metre further east (a slope under the house)."""
    def z(lat, lon):
        if lat < LAT + NORTH:
            return 10.0
        return top + (lon - LON) * AR._m_per_deg(LAT)[1] * 0.1
    return z


HOUSE = _prism(0.0, -68.0, 8.0, 20.0, 26.0)          # walled, 20 m up, 60-68 m north


def _house(ss):
    for s in ss.all:
        for b in s.bodies:
            if b.plan_box and b.plan_box[0] > LAT + NORTH:
                return b
    raise AssertionError("no house body")


def test_a_house_on_its_authors_hill_stands_on_ours(tmp_path):
    """The rigid row would bury it (10 + 20 under a 40 m hill): its base
    plane (y 20) stands on the ground at the low side."""
    ss = PP.build_splits(_plan(_obj(tmp_path, [HOUSE])), _hill(40.0), write=False, **ARGS)
    b = _house(ss)
    assert TB.TERRAIN_CARRIED in b.anchor.reason and "under this ground" in b.anchor.reason
    assert b.anchor.y_zero == pytest.approx(20.0, abs=1e-6)
    # the LOW SIDE: the ring's west edge (the slope rises east)
    assert b.anchor.surface_z == pytest.approx(40.0, abs=0.05)
    assert b.anchor.offset[1] == pytest.approx(20.0, abs=1e-6)
    assert ss.counts.get("terrain_carried_bodies") == 1
    assert not ss.counts.get("terrain_carried_over_ground")


def test_a_house_whose_rigid_base_clears_our_ground_stands_on_it_too(tmp_path):
    """RULINGS 2026-11-13y (2): no walled building with nothing under it
    stays in the air — the case is counted for the owner's read."""
    ss = PP.build_splits(_plan(_obj(tmp_path, [HOUSE])), _hill(12.0), write=False, **ARGS)
    b = _house(ss)
    assert TB.TERRAIN_CARRIED in b.anchor.reason and "over this ground" in b.anchor.reason
    assert b.anchor.y_zero == pytest.approx(20.0, abs=1e-6)
    assert ss.counts.get("terrain_carried_over_ground") == 1


def test_a_thin_piece_in_the_air_keeps_its_authored_y(tmp_path):
    """13y (3): no walled part — §16 (3)'s own ground, authored y kept."""
    plate = _prism(0.0, -68.0, 8.0, 20.0, 20.5)
    ss = PP.build_splits(_plan(_obj(tmp_path, [plate])), _hill(40.0), write=False, **ARGS)
    b = _house(ss)
    assert TB.TERRAIN_CARRIED not in b.anchor.reason
    assert b.anchor.y_zero == pytest.approx(0.0, abs=1e-9)
    assert not ss.counts.get("terrain_carried_bodies")


def test_a_lifted_frame_is_not_read(tmp_path):
    """Witness (2): a frame with an authored lift stands on its author's
    ground already (``_wall_base``'s R5 clause)."""
    ss = PP.build_splits(_plan(_obj(tmp_path, [HOUSE]), lift=5.0), _hill(40.0),
                         write=False, **ARGS)
    assert TB.TERRAIN_CARRIED not in _house(ss).anchor.reason


def test_disarmed_without_the_wall_height(tmp_path):
    args = dict(ARGS, chain_min_height_m=0.0)
    ss = PP.build_splits(_plan(_obj(tmp_path, [HOUSE])), _hill(40.0), write=False, **args)
    assert _house(ss).anchor.y_zero == pytest.approx(0.0, abs=1e-9)


def _p(pid, base, h, box, feet=(), line=False):
    return types.SimpleNamespace(pid=pid, base_y=base, height_m=h, box=box, rings=(),
                                 feet=feet, line=line, scatter=False, lat=box[0], lon=box[1])


BOX = (LAT + 0.0006, LON, LAT + 0.0007, LON + 0.0001)
FR = ((LAT, LON), 0.0)


def _law(parts, surface):
    plan = types.SimpleNamespace(
        authored_seats=(),
        units=(types.SimpleNamespace(anchor=FR[0], agl_m=0.0, members=(
            types.SimpleNamespace(parts=tuple(parts)),)),))
    return TB.law_of(surface, plan, 2.5, 0.5, 0.3)


def test_a_structure_under_it_is_a_carrier():
    """Witness (4): an upper storey on its own ground floor (LOWS
    ``domiki_lows_34``) is carried by that floor, never dropped onto the
    terrain through it."""
    upper = _p(1, 3.8, 5.0, BOX)
    floor = _p(2, 0.0, 11.0, BOX, feet=((BOX[0], BOX[1], 0.0),))
    law = _law([upper, floor], _hill(40.0))
    assert TB._supported([upper], 3.8, FR, {1}, law)
    assert TB.seat([upper], None, FR[0], 0.0, law, {}) is None
    # a roof ABOVE it is no carrier, nor is a slab whose top stays under it
    roof = _p(3, 9.0, 0.5, BOX)
    slab = _p(4, 0.0, 0.2, BOX, feet=((BOX[0], BOX[1], 0.0),))
    law = _law([upper, roof, slab], _hill(40.0))
    assert not TB._supported([upper], 3.8, FR, {1}, law)
    # another frame overlapping is doubt (13r)
    other = types.SimpleNamespace(pid=9, base_y=50.0, height_m=0.0, box=BOX, rings=(),
                                  feet=(), line=False, scatter=False)
    plan = types.SimpleNamespace(authored_seats=(), units=(
        types.SimpleNamespace(anchor=FR[0], agl_m=0.0, members=(
            types.SimpleNamespace(parts=(upper,)),)),
        types.SimpleNamespace(anchor=(LAT + 1e-3, LON), agl_m=0.0, members=(
            types.SimpleNamespace(parts=(other,)),))))
    assert TB._supported([upper], 3.8, FR, {1}, TB.law_of(_hill(40.0), plan, 2.5, 0.5, 0.3))


def test_site1_a_footless_unit_stands_on_its_walls_base():
    """``_wall_base``'s footless branch: an unlifted unit with no foot and
    walls at y 33.6 takes base 33.6 (LOWS fu:1:263 floated 31.95 m)."""
    walls = {1: _p(1, 33.6, 6.0, BOX), 2: _p(2, 34.0, 3.0, BOX)}
    un = types.SimpleNamespace(id="fu:1:263", pids=frozenset({1, 2}))
    frame_of = {1: FR, 2: FR}
    law = _law(list(walls.values()), _hill(50.0))   # rigid base 43.6 under a 50 m hill
    counts: dict = {}
    assert FU._wall_base(un, [un], walls, 2.5, {}, frame_of,
                         (law, {}, counts)) == pytest.approx(33.6)
    assert counts == {"terrain_carried_units": 1}
    # no terrain law: the pre-round reading (0.0, the zero on the ground)
    assert FU._wall_base(un, [un], walls, 2.5, {}, frame_of) == 0.0
    # a unit with a foot anywhere is not footless: unchanged
    footed = dict(walls)
    footed[3] = _p(3, 0.0, 1.0, BOX, feet=((BOX[0], BOX[1], 0.0),))
    un3 = types.SimpleNamespace(id="fu:1:264", pids=frozenset({1, 2, 3}))
    assert FU._wall_base(un3, [un3], footed, 2.5, {}, {**frame_of, 3: FR},
                         (law, {}, {})) == 0.0
    # a lifted frame keeps R5's reading
    lifted = {1: ((LAT, LON), 5.0), 2: ((LAT, LON), 5.0)}
    assert FU._wall_base(un, [un], walls, 2.5, {}, lifted, (law, {}, {})) == 0.0
