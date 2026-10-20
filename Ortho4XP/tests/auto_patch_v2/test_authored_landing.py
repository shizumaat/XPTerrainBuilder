"""Owner RULINGS 2026-10-14g (refs #662, #678): the authored placement is
kept where our ground asks nothing of it.

(1) an ``OBJECT_AGL`` row is KEPT AS AUTHORED — never converted to
    on-ground (only ``OBJECT_MSL`` is), and a split of one keeps the lift
    on its body rows;
(2) an AGL row is not re-expressed as ``OBJECT_MSL`` when that changes
    nothing within the tolerance;
(3) a placement is not split when every body would land within the
    tolerance of its authored seat — and a rigid placement over SLOPING
    ground is still split and re-seated.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import authored_landing as AL
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.model.placement import MslSeat

from test_v2objsplit import _fence, _fence_plan, _line_args  # noqa: E402

TOL = 0.05


def _row(kind="OBJECT", elevation=None, lat=40.0, lon=-3.0, path="objects/x.obj"):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=0.0,
                                 kind=kind, elevation=elevation)


def _flat(z=100.0):
    return lambda la, lo: z


# ── (1) an AGL row on a deck stays AGL ──────────────────────────────────

def test_an_agl_row_on_a_deck_is_not_converted():
    """The car 4.1 m up on a car-park deck (OTHH TerminalRoads class): its
    lift is the author's statement about our terrain.  Only the MSL row
    converts; the AGL row is listed by nothing and the writer leaves it."""
    dump = types.SimpleNamespace(placements=[
        _row("OBJECT_AGL", 4.16, path="lib/cars/car_static.obj"),
        _row("OBJECT_MSL", 310.0, path="objects/tower.obj"),
        _row("OBJECT", None, path="objects/hangar.obj")])
    conv, kept = W.conversions_for_dump(dump)
    assert [c.index for c in conv] == [1] and kept == []
    # a SINK (negative column) is not a lift: it converts as before
    sunk = types.SimpleNamespace(placements=[_row("OBJECT_AGL", -0.45)])
    assert AL.is_sink(sunk.placements[0])
    assert [c.index for c in W.conversions_for_dump(sunk)[0]] == [0]
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, riders, counts = PW.dump_rows(dump, plan, ss, (), _flat(), "",
                                             tol_m=0.02, keep_tol_m=TOL)
    assert {c.index for c in conv} == {1} and not msl and not riders


def test_body_lift_is_the_agl_column_except_where_the_law_states_the_zero():
    agl = _row("OBJECT_AGL", 3.5)
    plain = types.SimpleNamespace(datum=False, reason="footless_own_ground: …")
    assert AL.body_lift(agl, plain) == 3.5
    assert AL.body_lift(_row("OBJECT_MSL", 300.0), plain) == 0.0
    assert AL.body_lift(_row(), plain) == 0.0
    assert AL.body_lift(agl, plain, reseated=True) == 0.0           # §18
    assert AL.body_lift(_row("OBJECT_AGL", -0.45), plain) == 0.0     # a sink
    assert AL.body_lift(agl, types.SimpleNamespace(datum=True, reason="")) == 0.0
    assert AL.body_lift(agl, types.SimpleNamespace(
        datum=False, reason="basin rim (r1): the object's zero is the rim")) == 0.0


# ── (2) an AGL row whose MSL equivalent equals it stays AGL ─────────────

def test_an_agl_row_whose_msl_changes_nothing_stays_agl():
    """§16g (5) wrote 12,365 cluster-pad rows at OTHH whose elevation was
    the drape + lift to the centimetre: they stay AGL.  A seat that moves
    the row by more than the tolerance is the ground's requirement and
    stays written."""
    rows = [_row("OBJECT_AGL", 1.5, path="objects/pax.obj"),
            _row("OBJECT_AGL", 1.5, path="objects/pax.obj", lat=40.001),
            _row("OBJECT", None, path="objects/seat.obj")]
    assert AL.msl_changes_nothing(rows[0], 101.52, _flat(), TOL)
    assert not AL.msl_changes_nothing(rows[0], 101.8, _flat(), TOL)
    assert not AL.msl_changes_nothing(rows[2], 100.0, _flat(), TOL)   # plain row
    assert not AL.msl_changes_nothing(rows[0], 101.5, _flat(), 0.0)   # disarmed
    msl = (MslSeat(0, "objects/pax.obj", -3.0, 40.0, 0.0, 101.52, "cluster_pad"),
           MslSeat(1, "objects/pax.obj", -3.0, 40.001, 0.0, 101.80, "cluster_pad"),
           MslSeat(2, "objects/seat.obj", -3.0, 40.0, 0.0, 100.40, "cluster_pad"))
    keep, n = PW._agl_rows_kept(types.SimpleNamespace(placements=rows), msl,
                                _flat(), TOL)
    assert [m.index for m in keep] == [1, 2] and n == 1


# ── (3) a split that moves nothing is not made ──────────────────────────

def _rows_for(path, kind="OBJECT", elevation=None):
    res = "objects/" + path.name
    return [_row(path="objects/other.obj"), _row(kind, elevation, path=res)]


def test_a_split_whose_bodies_all_land_on_the_authored_seat_is_not_split(tmp_path):
    """A 400 m fence over FLAT ground cuts into four segments (11f (2)),
    every one landing exactly where the authored row draws it: with 14g
    (3) armed it stays ONE placement of the original object."""
    path, _n = _fence(tmp_path, 400.0)
    plan = _fence_plan(path, 400.0)
    ss0 = PP.build_splits(plan, _flat(), write=True, **_line_args())
    assert len(ss0.splits) == 1 and len(ss0.splits[0].bodies) == 4   # the control
    ss = PP.build_splits(plan, _flat(), write=True, **_line_args(),
                         rows=_rows_for(path), authored_keep_tol_m=TOL)
    assert not ss.splits
    assert [k.reason for k in ss.kept] == ["authored_seat_lands"]
    assert ss.counts["authored_seat_lands"] == 1


def test_an_agl_split_that_moves_nothing_is_not_split_and_keeps_its_lift(tmp_path):
    path, _n = _fence(tmp_path, 400.0)
    plan = _fence_plan(path, 400.0)
    ss = PP.build_splits(plan, _flat(), write=True, **_line_args(),
                         rows=_rows_for(path, "OBJECT_AGL", 3.0),
                         authored_keep_tol_m=TOL)
    assert not ss.splits and ss.kept[0].reason == "authored_seat_lands"


def test_a_rigid_placement_over_sloping_ground_is_still_split(tmp_path):
    """The other way: the ground falls 1 m per 100 m along the fence, so a
    rigid placement at its row floats or sinks by metres at its far end —
    our ground requires the split, and it stands.  An AGL fence's bodies
    keep the author's 3 m lift on their rows."""
    path, _n = _fence(tmp_path, 400.0)
    plan = _fence_plan(path, 400.0)
    slope = lambda la, lo: 100.0 + (lo + 3.0) * 85000.0 * 0.01    # noqa: E731
    ss = PP.build_splits(plan, slope, write=True, **_line_args(),
                         rows=_rows_for(path), authored_keep_tol_m=TOL)
    assert len(ss.splits) == 1 and len(ss.splits[0].bodies) == 4
    assert all(b.lift_m == 0.0 for b in ss.splits[0].bodies)
    ss = PP.build_splits(plan, slope, write=True, **_line_args(),
                         rows=_rows_for(path, "OBJECT_AGL", 3.0),
                         authored_keep_tol_m=TOL)
    assert len(ss.splits) == 1
    assert all(b.lift_m == 3.0 for b in ss.splits[0].bodies)
    splits, _k = PP.to_placement_records(ss)
    assert all(b.lift_m == 3.0 for b in splits[0].bodies)
    assert all(b.to_dict()["lift_m"] == 3.0 for b in splits[0].bodies)


def test_lands_needs_a_row_and_a_surface():
    b = types.SimpleNamespace(anchor=types.SimpleNamespace(lat=40.0, lon=-3.0,
                                                           offset=(0.0, 0.0, 0.0)),
                              seat=None, lift_m=0.0)
    assert AL.lands_on_authored_seat((b,), _row(), _flat(), TOL)
    assert not AL.lands_on_authored_seat((b,), None, _flat(), TOL)
    assert not AL.lands_on_authored_seat((b,), _row(), lambda la, lo: None, TOL)
    assert not AL.lands_on_authored_seat((b,), _row(), _flat(), 0.0)
    tilted = types.SimpleNamespace(**{**vars(b), "seat": types.SimpleNamespace(applied=True)})
    assert not AL.lands_on_authored_seat((tilted,), _row(), _flat(), TOL)


def test_the_kept_lift_survives_the_compact_edit_record():
    """#25: a sibling airport re-applies this airport's edits from
    ``edit_rows`` — the lift must ride it, or the sibling's write would put
    the bodies back on the ground."""
    from auto_patch_v2.model import placement as PM
    body = PM.Body("b0", "other", (0,), PM.Anchor(-3.0, 40.0, 0.0), "r",
                   "objects/x__b0.obj", lift_m=3.5)
    plan = PM.PlacementPlan(icao="T", pack_name="p", pack_root="/p", dsf_path="/p/a.dsf",
                            dsf_backup_path="/p/a.dsf.anchor_bak",
                            provenance=PM.Provenance("", "", ""),
                            splits=(PM.Split(PM.PlacementRef(1, "objects/x.obj", -3.0,
                                                             40.0, 0.0), (body,)),))
    back = PM.PlacementPlan.from_dict({**plan.edit_rows(), "pack_root": "/p"})
    assert back.splits[0].bodies[0].lift_m == 3.5
    assert PM.PlacementPlan.from_json(plan.to_json()).splits[0].bodies[0].lift_m == 3.5


def test_a_placement_carrying_a_draped_slab_is_never_kept_by_rule_3():
    """14d (1) before 14g (3): a draped base slab is a rewrite of the
    placement's geometry, so a placement carrying one is written even
    where every body would land on its authored seat."""
    from auto_patch_v2.airport import placement_file as PF
    from auto_patch_v2.airport.placement_record import Split
    m = types.SimpleNamespace(id="dsf:obj1", resource="objects/lot.obj", tilted=(),
                              live_path="/nonexistent/lot.obj",
                              authored_path="/nonexistent/lot.obj", zero_y=0.0)
    body = types.SimpleNamespace(body_id=0, new_resource="objects/lot__b0.obj", seat=None,
                                 merged_into="")
    rec = Split(1, "dsf:obj1", "objects/lot.obj", "", 40.0, -3.0, 0.0, (body,))

    def run(**kw):
        counts = {"kept": 0, "one_body": 0, "split": 0, "files": 0, "write_error": 0}
        splits, kept, whole = [], [], []
        PF._cut_and_file(rec, m, False, counts, splits, kept, whole,
                         always_write=False, tilted_whole=[], landed=True, **kw)
        return splits, kept
    splits, kept = run()
    assert not splits and [k.reason for k in kept] == ["authored_seat_lands"]
    splits, kept = run(drape_comps=frozenset({0}), drape_law=object())
    assert len(splits) == 1 and not kept
