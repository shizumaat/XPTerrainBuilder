"""Twins for AUTHORED TO THE CUT (object-placement spec §18; owner RULINGS
2026-10-07b (1), (3) and 2026-10-07c (3)-(5)): the arithmetic
(``airport/authored_seat``), the seat decision (``pipeline/authored_seats``),
the plate site that enters only re-seated members, the plan that publishes
the records, and the basin intake that reads a pit lifted by its own depth
as ground-seated.

Synthetic packs only — the wall object and the bore of
``test_tunnel_objects``, the box pit of ``test_m4b``."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_m4b as M4B                                         # noqa: E402
import test_tunnel_objects as TO                               # noqa: E402
from auto_patch_v2.airport import authored_seat as AS         # noqa: E402
from auto_patch_v2.airport import obj8                         # noqa: E402
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan  # noqa: E402
from auto_patch_v2.classify.roles import Classification       # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.model.rebake import PLAN_VERSION, RebakePlan  # noqa: E402
from auto_patch_v2.pipeline.authored_seats import kept_ids, seat_records  # noqa: E402
from auto_patch_v2.pipeline.build import _plate_seats, _rebake_inputs  # noqa: E402
from auto_patch_v2.planar.basins import read_objects           # noqa: E402
from auto_patch_v2.planar.build import build                   # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def walls(tmp_path_factory):
    return TO.objs.__wrapped__(tmp_path_factory)


@pytest.fixture(scope="module")
def pits(tmp_path_factory):
    return M4B.objs.__wrapped__(tmp_path_factory)


# ── the arithmetic ────────────────────────────────────────────────────────

def test_the_two_bands_and_the_median():
    assert AS.crest_over(1.0, 0.0, 5.0, 4.0) == pytest.approx(2.0)
    assert AS.crest_in_band(0.0, 3.0) and AS.crest_in_band(3.0, 3.0)
    assert not AS.crest_in_band(-0.01, 3.0) and not AS.crest_in_band(3.01, 3.0)
    assert not AS.crest_in_band(None, 3.0)
    assert AS.rim_over(-4.5, 4.3, 0.0) == pytest.approx(-0.2)
    assert AS.rim_in_band(-1.0, 1.0) and not AS.rim_in_band(1.01, 1.0)
    # one wall states the height over the cut, else over uncut ground
    assert AS.stated_height(2.1, 5.0, 3.0) == 2.1
    assert AS.stated_height(-1.2, 2.0, 3.0) == 2.0
    assert AS.stated_height(-1.2, 7.5, 3.0) is None
    # 07c (4): the pack's MEDIAN, flush (None) when nothing is stated
    assert AS.pack_proud_height([1.58, 1.59, 1.98, 1.98, 2.0, 2.0, 2.15, 2.4, 2.59]) == 2.0
    assert AS.pack_proud_height([None, None]) is None


def test_a_lift_is_ground_seated_only_when_it_is_the_shells_own_depth():
    f = AS.lifted_by_own_depth
    assert f(4.2985, -3.816, 1.0, 2.5)            # lifted by its depth + 0.48
    assert f(13.498, -13.142, 1.0, 2.5)
    assert not f(0.0, -3.816, 1.0, 2.5)           # a plain placement
    assert not f(8.0, -3.816, 1.0, 2.5)           # a pit on a podium
    assert not f(0.04, -0.003, 1.0, 2.5)          # a figure 4 cm off the ground
    assert not f(4.2985, -3.816, 0.0, 2.5)        # the law switched off
    assert not f(4.0, 1.0, 1.0, 0.0)              # nothing under the zero plane


# ── the wall: kept over the cut, re-seated to the pack's median otherwise ──

def _wall_map(walls, law, agl):
    airport = TO._airport(walls, law, [("wall_long", (0.0, 0.0), 180.0, agl, "OBJECT_AGL")],
                          TO._bore(y_in=-70.0, y_open=80.0))
    cl = Classification(tuple(TO._cells(-200, -300, 200, -60)), (), {}, ())
    out: list = []
    pm, _st = build(airport, cl, law, objects_out=out)
    (tn,) = [t for t in pm.structures if t.source == "object"]
    return airport, pm, tn, out


def test_a_wall_authored_to_uncut_ground_is_re_seated_to_the_packs_proud_height(walls, law):
    """The 5 m crest plate seated 3 m under flat ground: +2.0 over UNCUT
    ground, under the cut it would stand below grade (h_cut < 0) — not
    authored to the cut, so it is plate-seated as before, and its crest
    goes to the height the pack itself states (07c (4)), not flush."""
    _airport, pm, tn, _out = _wall_map(walls, law, -3.0)
    ((h_cut, h_uncut),) = tn.authored_crest_m
    assert h_uncut == pytest.approx(2.0) and h_cut < 0.0
    assert tn.reseat_expect_m == (pytest.approx(-h_cut),)
    recs = seat_records(pm, law)
    rec = recs[tn.objects[0]]
    assert rec["seat"] == AS.SEAT_RESEATED and rec["datum"] == "crest"
    assert rec["proud_m"] == pytest.approx(2.0) and not kept_ids(recs)
    seats = _plate_seats(pm, law)
    assert set(seats) == set(tn.objects)
    assert seats[tn.objects[0]][0] == pytest.approx(5.0)
    assert seats[tn.objects[0]][2] == pytest.approx(2.0)      # the clearance IS the proud height


def test_a_wall_seated_two_metres_over_the_cut_keeps_its_seat(walls, law):
    """The SAME wall lifted by what the cut takes from under its anchor:
    the crest stands +2.0 over grade on the cut terrain — AUTHORED TO THE
    CUT.  No plate entry, excluded from every seat, published on the plan."""
    _a, _pm, tn0, _o = _wall_map(walls, law, -3.0)
    agl = -3.0 + (2.0 - tn0.authored_crest_m[0][0])
    airport, pm, tn, out = _wall_map(walls, law, agl)
    ((h_cut, h_uncut),) = tn.authored_crest_m
    assert h_cut == pytest.approx(2.0, abs=0.01)
    assert h_uncut > law.tables.structures.tunnel.object.authored_crest_max_m
    recs = seat_records(pm, law)
    oid = tn.objects[0]
    assert recs[oid]["seat"] == AS.SEAT_AUTHORED and recs[oid]["proud_m"] is None
    assert kept_ids(recs) == {oid}
    assert _plate_seats(pm, law) == {}
    args = _rebake_inputs(pm, law, None, airport)
    assert oid in args["exclude"] and args["tunnel_objects"] == {}
    objects, cache = out
    pl = rebake_plan(airport, objects, cache, law, **args)
    assert pl.counts["plate_members"] == 0 and pl.counts["terrain_adapted"] == 1
    assert not [m for u in pl.units for m in u.members if m.id == oid]
    (pub,) = pl.authored_seats
    assert pub["id"] == oid and pub["seat"] == AS.SEAT_AUTHORED
    assert pub["h_cut_m"] == pytest.approx(2.0, abs=0.01)
    d = pl.to_dict()
    assert d["version"] == PLAN_VERSION == 13
    assert RebakePlan.from_json(pl.to_json()).authored_seats == pl.authored_seats
    # a version-12 plan reads with no record: the pre-§18 law
    d12 = {k: v for k, v in d.items() if k != "authored_seats"} | {"version": 12}
    assert RebakePlan.from_dict(d12).authored_seats == ()


def test_a_pack_that_states_no_height_is_re_seated_flush(law):
    """05n-4 is the fallback: neither reading in band (a crest 4 m under
    the cut, 7 m over uncut ground) states nothing — flush, and named."""
    tn = types.SimpleNamespace(source="object", objects=("o1",), resource="w.obj",
                               authored_crest_m=((-4.0, 7.0),))
    pm = types.SimpleNamespace(structures=(tn,), basins=())
    (rec,) = seat_records(pm, law).values()
    assert rec["seat"] == AS.SEAT_RESEATED and rec["proud_m"] == 0.0 and not rec["stated"]
    # ... while a sibling that states 2.0 m standardises the pack on it
    tn2 = types.SimpleNamespace(source="object", objects=("o2",), resource="w.obj",
                                authored_crest_m=((2.0, 5.0),))
    recs = seat_records(types.SimpleNamespace(structures=(tn, tn2), basins=()), law)
    assert recs["o2"]["seat"] == AS.SEAT_AUTHORED
    assert recs["o1"]["proud_m"] == pytest.approx(2.0)
    # a structure carrying no witness seats as before (no record at all)
    old = types.SimpleNamespace(source="object", objects=("o3",), resource="w.obj")
    assert seat_records(types.SimpleNamespace(structures=(old,), basins=()), law) == {}


# ── the pit: a lift of the shell's own depth is read ground-seated ────────

def _pit_map(pits, law, agl):
    airport = M4B._airport(pits, law, [("pit", (0.0, 0.0), 30.0, agl)])
    out: list = []
    pm, stats = build(airport, Classification(tuple(M4B._cells()), (), {}, ()), law,
                      objects_out=out)
    return airport, pm, stats, out


def test_the_lifted_twin_of_a_plain_pit_is_the_same_basin_and_keeps_its_seat(pits, law):
    """A 6 m pit lifted 6.3 m (its depth, its floor clearance, a little
    less): the basin intake reads the shell ground-seated, so the region
    and the floor are its plain twin's exactly — and the rim, at the
    authored seat on the cut floor, stands inside the band: the seat is
    the author's, where the plain twin (rim 6.5 m under grade once its
    anchor sinks into its own trench) is re-seated onto its floor plate."""
    bl = law.tables.structures.basin
    _a0, pm0, _s0, _o0 = _pit_map(pits, law, 0.0)
    airport, pm1, _s1, out = _pit_map(pits, law, 6.3)
    (b0,), (b1,) = pm0.basins, pm1.basins
    assert Polygon(b1.region).equals(Polygon(b0.region))
    assert b1.floor_z == pytest.approx(b0.floor_z) and b1.plate_y_m == pytest.approx(b0.plate_y_m)
    assert b1.agl_m == pytest.approx(6.3) and b0.agl_m == 0.0
    # the plain twin states no seat (no lift): no record, the floor-plate
    # seat as before; the lifted one's rim reads on the cut floor
    assert b0.rim_cut_m is None
    assert b1.rim_cut_m == pytest.approx(b0.plate_y_m - bl.floor_clearance_m + 6.3, abs=0.05)
    assert abs(b1.rim_cut_m) <= bl.authored_rim_tol_m
    r0, r1 = seat_records(pm0, law), seat_records(pm1, law)
    assert r0 == {}
    assert r1[b1.witness_id]["seat"] == AS.SEAT_AUTHORED
    assert set(r1[b1.witness_id]["members"]) == set(b1.member_ids)
    assert r1[b1.witness_id]["agl_authored_m"] == pytest.approx(6.3)
    assert set(_plate_seats(pm0, law)) == {b0.witness_id} and _plate_seats(pm1, law) == {}
    assert set(b1.member_ids) <= _rebake_inputs(pm1, law, None, airport)["exclude"]
    objects, _cache = out
    (o,) = [o for o in objects if o.id == b1.witness_id]
    assert o.ground_seated and o.agl_m == pytest.approx(6.3)
    assert o.base_z == pytest.approx(o.anchor_z)


def test_a_pit_lifted_twice_its_depth_stays_refused(pits, law):
    _a, pm, _stats, out = _pit_map(pits, law, 12.0)
    assert not pm.basins
    objects, _cache = out
    assert not any(o.ground_seated or o.witnesses for o in objects)


def test_a_lift_that_founds_no_pit_is_read_as_it_was(pits, law):
    """§18 (5): a lifted shell with no floor witness (the SKIRT of
    ``test_m4b``: four walls 6 m deep, no floor plate) is NOT read
    ground-seated — its record is the plain reading's, zero plane and all."""
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    airport = M4B._airport(pits, law, [("skirt", (0.0, 0.0), 0.0, 6.2)])
    objects, _rep = read_objects(airport, law, cache)
    (o,) = objects
    assert not o.witnesses and not o.ground_seated
    assert o.base_z == pytest.approx(o.anchor_z + 6.2)


def test_the_seat_column_is_one_line_per_wall_and_pit():
    """Spec §18 (6), last row: the replay's ``--emit`` / ``--verify`` report
    and ``obj8_split_report`` print ONE formatter's table — the seat and
    the numbers it was decided on, per placement; nothing where the map
    admits no below-grade object."""
    from auto_patch_v2.airport.authored_seat import SEAT_AUTHORED, SEAT_RESEATED
    from auto_patch_v2.pipeline.authored_seats import seat_lines
    assert seat_lines(()) == []
    recs = [
        {"id": "dsf:obj2", "resource": "wall_b.obj", "datum": "crest", "seat": SEAT_RESEATED,
         "h_cut_m": 4.4, "h_uncut_m": 0.1, "proud_m": 2.0},
        {"id": "dsf:obj1", "resource": "wall_a.obj", "datum": "crest", "seat": SEAT_AUTHORED,
         "h_cut_m": 2.0, "h_uncut_m": 4.5, "proud_m": None},
        {"id": "dsf:obj9", "resource": "basin:1", "datum": "rim", "seat": SEAT_AUTHORED,
         "h_cut_m": -0.02, "agl_authored_m": 4.3, "members": ["dsf:obj9"]},
    ]
    out = seat_lines(recs)
    assert len(out) == 2 + len(recs)
    assert "3 wall / pit placement(s)" in out[0] and f"2 {SEAT_AUTHORED}" in out[0]
    assert f"1 {SEAT_RESEATED}" in out[0] and "seat" in out[1] and "h_cut" in out[1]
    body = out[2:]
    # sorted by datum, resource: the walls first, each row its own placement
    assert [ln.split()[-2] for ln in body] == ["dsf:obj1", "dsf:obj2", "dsf:obj9"]
    assert SEAT_AUTHORED in body[0] and "+2.00" in body[0] and "+4.50" in body[0]
    assert SEAT_RESEATED in body[1] and "+2.00" in body[1]          # the proud target
    assert "rim" in body[2] and "-0.02" in body[2]


# ── §18 (5) / (9) (1): the lift is ONE decision per ANCHOR FAMILY ─────────

def _family_map(pits, law, agl, body_xy=(0.0, 0.0), body_agl=None):
    """The 6 m sump ``pit`` and a 3 m trench BODY around it (a skirt: four
    walls, no floor) — two placements, one heading, the lift ``agl``."""
    objs2 = dict(pits)
    objs2["body"] = M4B._box_obj(pits["dir"] / "body.obj", 34.0, 24.0, 3.0, floor=False)
    airport = M4B._airport(objs2, law, [
        ("pit", (0.0, 0.0), 30.0, agl),
        ("body", body_xy, 30.0, agl if body_agl is None else body_agl)])
    out: list = []
    pm, _stats = build(airport, Classification(tuple(M4B._cells()), (), {}, ()), law,
                       objects_out=out)
    return pm, {o.path.split("/")[-1]: o for o in out[0]}


def test_the_anchor_family_key_is_the_anchor_the_heading_and_the_lift():
    k = AS.anchor_family_key
    assert k((10.0, 20.0), 30.0, 4.2985, 0.01) == k((10.004, 19.996), 30.0, 4.2985, 0.01)
    assert k((10.0, 20.0), 30.0, 4.2985, 0.01) != k((10.0, 21.0), 30.0, 4.2985, 0.01)
    assert k((10.0, 20.0), 30.0, 4.2985, 0.01) != k((10.0, 20.0), 30.5, 4.2985, 0.01)
    assert k((10.0, 20.0), 30.0, 4.2985, 0.01) != k((10.0, 20.0), 30.0, 4.31, 0.01)


def test_a_two_shell_pit_at_one_anchor_is_one_basin_and_the_keep_follows_the_family(pits, law):
    """The sump is lifted by its own depth; the trench body, 3 m deep, is
    3.3 m off that lift alone — but it stands at the SAME anchor with the
    SAME heading and lift, so the author lifted them as one body: both
    read ground-seated, ONE basin with both members on its plain twin's
    region, and the kept seat takes BOTH out of every unit."""
    pm0, o0 = _family_map(pits, law, 0.0)
    pm1, o1 = _family_map(pits, law, 6.3)
    (b0,), (b1,) = pm0.basins, pm1.basins
    assert Polygon(b1.region).equals(Polygon(b0.region))
    assert b1.floor_z == pytest.approx(b0.floor_z)
    ids = {o1["pit.obj"].id, o1["body.obj"].id}
    assert o1["pit.obj"].ground_seated and o1["body.obj"].ground_seated
    assert set(o1["pit.obj"].family) == set(o1["body.obj"].family) == ids
    assert set(b1.member_ids) == ids
    recs = seat_records(pm1, law)
    assert recs[b1.witness_id]["seat"] == AS.SEAT_AUTHORED
    assert kept_ids(recs) == ids              # the shallow sibling is in no unit
    assert not o0["pit.obj"].ground_seated and o0["pit.obj"].family == ()


def test_the_same_two_shells_at_two_anchors_are_not_a_family(pits, law):
    _pm, o = _family_map(pits, law, 6.3, body_xy=(1.0, 0.0))
    assert o["pit.obj"].ground_seated and o["pit.obj"].family == ()
    assert not o["body.obj"].ground_seated and o["body.obj"].family == ()
    # ...nor with two lifts at one anchor
    _pm, o = _family_map(pits, law, 6.3, body_agl=6.0)
    assert not o["body.obj"].ground_seated and o["body.obj"].family == ()


def test_a_family_whose_lift_is_not_its_depth_stays_lifted(pits, law):
    """A deep member and a lift that is NOT the family's depth (twice it):
    nobody is read ground-seated, no basin, the readings as they were."""
    pm, o = _family_map(pits, law, 12.0)
    assert not pm.basins
    assert not any(x.ground_seated or x.family for x in o.values())
