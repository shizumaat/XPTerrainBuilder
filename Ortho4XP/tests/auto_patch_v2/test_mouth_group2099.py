"""#2099 (owner ruling 2026-11-15T16:07Z: "Like other areas, tunnel mouths
made of multiple touching pieces need to be treated as an object group";
spec ``docs/specs/2099-mouth-groups.md``).

* ``airport/mouth_group``: the wing witness (W1-W3), one hop, the seat (S1 a
  plate, S2 a whole-row record), the mouths the readers took (M1-M3);
* the two general bugs found on the way: ``geom/foot_planes.floor_plane``
  over NaN candidates, and ``pack_partition`` over NaN anchors.
"""
from __future__ import annotations

import math
import types

import pytest
from auto_patch_v2.geom.foot_planes import floor_plane, ground_plane
from auto_patch_v2.law import Law

LAW = Law.for_airport("")


def test_floor_plane_leaves_a_nan_candidate_out():
    zs = [10.0] * 30 + [math.nan] * 5
    assert floor_plane(zs) == 10.0
    assert floor_plane([math.nan, math.nan]) is None
    assert ground_plane([math.nan, 4.0, 4.0]) == 4.0
    assert ground_plane([math.nan]) is None


def test_a_cold_dem_partition_is_refused_and_a_partial_one_is_said():
    from auto_patch_v2.airport.pack_partition import _refuse_groundless
    _refuse_groundless({"placements": 10, "unresolved": 2}, "XXXX")      # none: silent
    with pytest.raises(ValueError, match="cold"):
        _refuse_groundless({"placements": 10, "unresolved": 2, "no_ground": 8}, "XXXX")
    _refuse_groundless({"placements": 10, "unresolved": 2, "no_ground": 3}, "XXXX")


# ── the mouth group (spec §1-§2) ────────────────────────────────────────

def _cuboid(path, x0, x1, y0, y1, z0, z1, hard=False):
    """An OBJ8 cuboid (12 solid triangles); ``hard`` flags its top
    ATTR_hard_deck."""
    vs = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    top = (2, 3, 7, 6)
    side = [f for f in q if f != top]
    idx = [i for a, b, c, d in side for i in (a, b, c, a, c, d)]
    idx += [i for a, b, c, d in (top,) for i in (a, b, c, a, c, d)]
    vt = "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in vs)
    ix = "".join(f"IDX {i}\n" for i in idx)
    body = ("TRIS 0 30\n" + ("ATTR_hard_deck concrete\n" if hard else "") + "TRIS 30 6\n")
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(vs)} 0 0 {len(idx)}\n"
                    f"{vt}{ix}{body}", encoding="utf-8", newline="\n")
    return str(path)


def _placed(oid, path, xy, hdg=0.0):
    return types.SimpleNamespace(id=oid, path=path, resolved=path, xy=xy, heading_deg=hdg)


def _partition(members, contacts, line=()):
    """A load partition of one member per placement, part id = index."""
    units = tuple(types.SimpleNamespace(members=(types.SimpleNamespace(
        id=oid, resource=path, parts=(types.SimpleNamespace(pid=i, line=oid in line),)),))
        for i, (oid, path) in enumerate(members))
    mo = {(i, 0): (oid, path) for i, (oid, path) in enumerate(members)}
    return types.SimpleNamespace(units=units, member_object=mo, contacts=tuple(contacts))


def _cache():
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    return ResourceCache(LAW.tables.structures.basin.min_solid_thickness_m, _fe.quantum(LAW))


def test_a_touching_wall_at_its_own_anchor_is_a_wing(tmp_path):
    """W1-W3 and ONE HOP: a deck box over a cut (floor y -7.5) and five
    touchers at their own anchors -- a wing wall running 40 m out, a wall
    chained to it, a slab (no wall), a post (no wall's height, runs nowhere)
    and a fence (a LINE part joins nothing)."""
    from auto_patch_v2.airport import mouth_group as M
    box = _cuboid(tmp_path / "box.obj", -10, 10, -7.5, 0.5, -10, 10, hard=True)
    wall = _cuboid(tmp_path / "wall.obj", -0.3, 0.3, -1.0, 7.2, 0.0, 40.0)
    slab = _cuboid(tmp_path / "slab.obj", -5, 5, 0.0, 3.0, 0.0, 10.0)
    post = _cuboid(tmp_path / "post.obj", -0.2, 0.2, 0.0, 1.2, -0.2, 0.2)
    objs = [_placed("box", box, (0.0, 0.0)), _placed("w1", wall, (10.3, -10.0)),
            _placed("w2", wall, (10.3, -50.2)), _placed("slab", slab, (-15.0, -10.0)),
            _placed("post", post, (0.0, -10.2)), _placed("fence", wall, (-10.3, -10.0))]
    part = _partition([(o.id, o.path) for o in objs],
                      [(0, 1), (1, 2), (0, 3), (0, 4), (0, 5)], line={"fence"})
    groups, notes = M.mouth_groups(part, objs, [M.Mouth("box", -7.5, "test")], _cache(), LAW)
    assert [(g.mouth.object_id, [w for w, _r in g.wings]) for g in groups] == \
        [("box", ["w1", "w2"])]
    why = " ".join(notes)
    assert "slab" in why and "no wall" in why and "post" in why and "fence" not in why
    # a toucher another rule seats is no candidate (one authority per row)
    taken, _n = M.mouth_groups(part, objs, [M.Mouth("box", -7.5, "test")], _cache(), LAW,
                               taken={"w1"})
    assert taken == []          # w2 reaches the box only through w1


def test_a_wing_rides_its_mouths_seat_at_the_floor():
    from auto_patch_v2.airport import mouth_group as M
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT
    g = M.MouthGroup(M.Mouth("box", -7.5, "test"), (("w1", "Objects/w.obj"),))
    st = [(1.0, 2.0)]
    assert M.wing_plates([g], {"box": (0.25, st, 0.0, "deck")}) == \
        {"w1": (7.75, st, 0.0, "deck")}
    assert M.wing_plates([g], {"box": (0.25, st, 0.0, "deck", 170.0)})["w1"][4] == 162.5
    assert M.wing_plates([g], {}) == {}
    recs = [{"id": "box", "seat": PORTAL_SEAT, "elevation": 170.0},
            {"id": "other", "seat": PORTAL_SEAT, "elevation": 1.0, "led_by": "box"}]
    got = M.wing_records([g], recs, PORTAL_SEAT)
    assert got == [{"id": "w1", "resource": "Objects/w.obj", "datum": M.MOUTH_DATUM,
                    "seat": PORTAL_SEAT, "elevation": 162.5, "led_by": "box"}]


def test_the_mouths_are_the_readers_decks_portals_and_entrances():
    from auto_patch_v2.airport import mouth_group as M
    pm = types.SimpleNamespace(
        decks=(types.SimpleNamespace(object_id="d", bottom_y=-7.5),),
        structures=(types.SimpleNamespace(portal="p", portal_seat=("r", 170.0), mouth_z=170.0),
                    types.SimpleNamespace(portal="e", portal_seat=("r", 171.0, (0, 0), 4.0),
                                          mouth_z=168.5),
                    types.SimpleNamespace(portal="", portal_seat=(), mouth_z=0.0)))
    assert [(m.object_id, m.floor_y, m.reader) for m in M.mouths_of(pm)] == \
        [("d", -7.5, "hard-deck bridge"), ("e", -2.5, "entrance face"),
         ("p", 0.0, "roofed portal")]


def test_the_deck_raster_is_the_same_grid_a_chunk_at_a_time(monkeypatch):
    """#2099 (found on the closing tile, CYSN's 827k-face fence): the plan
    trace is sampled a chunk of faces at a time -- the same grid, bounded
    memory."""
    import numpy as np
    from auto_patch_v2.airport import deck_signature as D
    rng = np.random.default_rng(7)
    xz = rng.uniform(0.0, 60.0, size=(500, 3, 2))
    whole = D._raster(xz, 0.5)
    monkeypatch.setattr(D, "_RASTER_POINTS", 37)
    chunked = D._raster(xz, 0.5)
    assert np.array_equal(whole[0], chunked[0]) and whole[2] == chunked[2]
