"""THE ZERO THE TERRAIN WAS ADAPTED FOR (owner sim read KMCI 1.0.480,
2026-11-10T15:47Z: "Looks like the art is at the right spot, and the
terminal is too low").

KMCI's terminal frame (``OBJECT_AGL`` +8.50 at 39.297902, -94.718822) holds
four terrain-adapted members (wall corridors, a sunken road) whose rows were
left AGL, so they -- and through #1726 every re-seated piece of the frame --
draped on OUR mesh at the origin: the pad's lower level, drawn at the lot,
gave 308.76 while the cuts were read for the DEM there plus the lift
(310.70) and the stand-side feet read 310.71.  Three general rules:

* the patch half records each lifted terrain-adapted row's rendered zero
  (``adapted_riders.seat_records``);
* the frame's zero is that record's where it names the frame's origin and
  lift (``frame_zero``), and the row is written there (``terrain_shaped.
  row_seats``; 14g (2) in ``placement_write``);
* a FOOTLESS member authored at the same origin with another lift
  (``CEILING-DECO`` +8.40) hangs in that frame (``member_zeros``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import terrain_shaped as TS
from auto_patch_v2.airport.adapted_riders import (
    authored_zeros,
    frame_zero,
    member_zeros,
    seat_records,
)

ORIGIN = (39.297901884, -94.718821527)


def _obj(oid, kind="OBJECT_AGL", agl=8.499, anchor_z=302.197, seated=False):
    return types.SimpleNamespace(id=oid, path=f"Airport/T/{oid}.obj", xy=(1.0, 2.0),
                                 kind=kind, agl_m=agl, ground_seated=seated,
                                 base_z=anchor_z + (0.0 if seated else agl))


def _to_ll(x, y):
    return ORIGIN


def _records():
    objs = [_obj("dsf:obj1"), _obj("dsf:obj2", kind="OBJECT", agl=0.0),
            _obj("dsf:obj3", seated=True), _obj("dsf:obj4")]
    return seat_records(objs, {"dsf:obj1", "dsf:obj2", "dsf:obj3"}, _to_ll)


def test_only_a_lifted_adapted_row_gets_a_record_at_its_rendered_zero():
    recs = _records()
    assert [r["id"] for r in recs] == ["dsf:obj1"]
    assert recs[0]["seat"] == TS.ADAPTED_SEAT
    assert recs[0]["elevation"] == 310.696
    assert (recs[0]["lat"], recs[0]["lon"]) == ORIGIN


def test_the_frame_zero_is_the_record_not_the_mesh_at_the_origin():
    auth = authored_zeros(_records())

    def mesh(la, lo):
        return 300.26                        # the lower level drawn at the lot
    assert frame_zero(mesh, ORIGIN, 8.499, auth) == 310.696
    # another lift at the origin, or another origin: the mesh, as before
    assert frame_zero(mesh, ORIGIN, 0.0, auth) == 300.26
    assert frame_zero(mesh, (39.2985, -94.7188), 8.499, auth) == 300.26 + 8.499
    assert frame_zero(mesh, ORIGIN, 8.499) == 300.26 + 8.499


def test_the_unit_touching_it_takes_the_record():
    piece = types.SimpleNamespace(id="fu:16:6938/p2", pids={10})
    frame_of = {10: (ORIGIN, 8.499)}
    auth = authored_zeros(_records())
    assert FU._adapted_zero(piece, [piece], {10}, frame_of, lambda la, lo: 300.26,
                            {}, auth) == 310.696


def _part(pid, feet=True):
    return types.SimpleNamespace(pid=pid, feet=((0.0, 0.0, 0.0),) if feet else ())


def test_a_member_at_the_same_origin_hangs_in_that_frame():
    """KMCI ``CEILING-DECO`` (+8.40 at the terminal's origin, no carrier)
    stood on the pad under its footprint, 2.6 m over the hall it hangs in."""
    deco = types.SimpleNamespace(id="deco", parts=(_part(1, feet=False),))
    far = types.SimpleNamespace(id="far", parts=(_part(2),))
    plan = types.SimpleNamespace(
        units=(types.SimpleNamespace(anchor=ORIGIN, agl_m=8.399, members=(deco,)),
               types.SimpleNamespace(anchor=(39.2985, -94.7188), agl_m=8.399,
                                     members=(far,))),
        adapted_frame_pids=(), authored_seats=tuple(_records()))
    got = member_zeros(plan, lambda la, lo: 304.89)
    assert set(got) == {"deco"}
    assert abs(got["deco"] - 310.596) < 1e-9


def test_a_loose_piece_moved_onto_the_frame_keeps_no_lift():
    from auto_patch_v2.airport import anchor_rule as AR
    from auto_patch_v2.airport import authored_landing as AL
    from auto_patch_v2.airport import open_frame_seat as OFS
    from auto_patch_v2.airport.placement_file import OWN_GROUND
    from auto_patch_v2.airport.placement_record import Body, Split
    a = AR.Anchor(AR.OTHER, ORIGIN[0], ORIGIN[1], 0.0, f"{OWN_GROUND}: no carrier",
                  304.89, offset=(0.0, 0.0, 0.0))
    b = Body(0, AR.OTHER, (0,), a, "Airport/T/deco__b0.obj", lift_m=8.399)
    m = types.SimpleNamespace(id="deco", resource="Airport/T/deco.obj", zero_y=0.0)
    rec = Split(0, m.id, m.resource, "/x/" + m.resource, ORIGIN[0], ORIGIN[1], 0.0, (b,))
    out = OFS.group_zero(rec, m, {}, {}, {}, "unit:19", adapted_zero=310.596)
    got = out.bodies[0]
    assert abs(got.anchor.surface_z - got.anchor.y_zero - 310.596) < 1e-9
    row = types.SimpleNamespace(kind="OBJECT_AGL", elevation=8.399, def_path=m.resource)
    assert AL.body_lift(row, got.anchor) == 0.0
    assert AL.body_lift(row, a) == 8.399


def test_the_row_is_written_at_the_record():
    row = types.SimpleNamespace(def_path="Airport/T/dsf:obj1.obj", lat=ORIGIN[0],
                                lon=ORIGIN[1], heading_deg=192.7)
    dump = types.SimpleNamespace(placements=[None, row])
    seats = TS.row_seats(dump, _records(), frozenset())
    assert [(m.index, m.elevation, m.why) for m in seats] == [(1, 310.696, TS.ADAPTED_WHY)]
    assert TS.row_seats(dump, _records(), frozenset({1})) == ()


def test_the_rest_of_the_anchor_family_is_written_at_the_record():
    from auto_patch_v2.airport.adapted_riders import family_seats

    def row(lift, la=ORIGIN[0], kind="OBJECT_AGL"):
        return types.SimpleNamespace(def_path="Airport/T/x.obj", lat=la, lon=ORIGIN[1],
                                     heading_deg=192.7, kind=kind, elevation=lift)
    dump = types.SimpleNamespace(placements=[
        row(8.498878462), row(8.498878462), row(8.399), row(8.498878462, la=39.2985),
        row(0.0, kind="OBJECT")])
    auth = authored_zeros(_records())
    got = family_seats(dump, auth, {1}, lambda la, lo: 300.26)
    assert [(m.index, m.elevation) for m in got] == [(0, 310.696)]
    # where the drape already stands there, the row stays AGL (14g (2))
    assert family_seats(dump, auth, set(), lambda la, lo: 302.197) == ()
