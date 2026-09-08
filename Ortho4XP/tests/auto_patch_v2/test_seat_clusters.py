"""THE CONTACT-CLUSTER SEAT twins (RULINGS 2026-09-06g, lane v2seatclusters):
v1's pools / structures / clusters law as v2 code — a pack of welded
objects on a stepped slope cuts into clusters at
``cluster_seat_tolerance_m``, every cluster seats on the median ground
under its ground parts, one file carries several PER-VERTEX deltas, a
deck plate seats its own cluster and never founds the ground around it,
the facility rule and the plate seat hold at cluster level, elevated
parts inherit, wide clusters bake and pad.  Hermetic, v2-pure."""
from __future__ import annotations

import dataclasses as _dc
import json

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.emit import clusters as C
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects

from test_m6a_rebake import _airport  # noqa: E402
from test_m6b_deck import _boxes_obj  # noqa: E402

ORIGIN = (60.5, -135.5)          # the fixture frame's origin (test_m6a_rebake._airport)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    root = tmp_path_factory.mktemp("clusterpack")
    (root / "Earth nav data").mkdir()
    (root / "Earth nav data" / "apt.dat").write_text("I\n1200\n\n1 700 0 0 ZZZZ Synthetic\n")
    d = root / "objects"
    # four objects in a row along +x, faces touching (welded contact), y 0..5
    _boxes_obj(d / "a.obj", [(10.0, 0.0, 10.0, 8.0, 0.0, 5.0)])
    # b: TWO components — the second 1 m clear of the first (no weld), touching c
    _boxes_obj(d / "b.obj", [(30.0, 0.0, 10.0, 8.0, 0.0, 5.0), (50.5, 0.0, 9.5, 8.0, 0.0, 5.0)])
    _boxes_obj(d / "c.obj", [(70.0, 0.0, 10.0, 8.0, 0.0, 5.0)])
    _boxes_obj(d / "d.obj", [(90.0, 0.0, 10.0, 8.0, 0.0, 5.0)])
    # a flagged deck plate at y 4..4.5 whose west face touches d's east face
    _boxes_obj(d / "e.obj", [(10.0, 0.0, 10.0, 8.0, 4.0, 4.5)], attr="ATTR_hard_deck")
    # a ground box with an ELEVATED box 0.1 m over it (contact, no weld) and a
    # sign floating over nothing
    _boxes_obj(d / "tower.obj", [(20.0, 0.0, 5.0, 5.0, 0.0, 3.0), (20.0, 0.0, 4.0, 4.0, 3.1, 6.0)])
    _boxes_obj(d / "sign.obj", [(20.0, 0.0, 1.0, 0.2, 3.5, 4.5)])
    # a 160 m chain of eight boxes 0.1 m apart (contact, no weld)
    _boxes_obj(d / "chain.obj", [(10.0 + 20.1 * i, 0.0, 10.0, 6.0, 0.0, 4.0) for i in range(8)])
    return root


def _planned(pack, law, placements, deck_datum=None):
    a = _airport(pack, law, placements)
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    return a, _plan(a, objs, cache, law, deck_datum)


def _x_sampler(steps):
    """Ground by EAST metres from the frame origin: ``steps`` is a sorted
    list of ``(x_from, z)``."""
    _m_lat, m_lon = C.metres_per_degree(ORIGIN[0])

    def f(lat, lon):
        x = (lon - ORIGIN[1]) * m_lon
        z = steps[0][1]
        for x0, zz in steps:
            if x >= x0:
                z = zz
        return (z, False)
    return f


# ── 1. the pack of four on a stepped slope ───────────────────────────────

@pytest.fixture(scope="module")
def row(pack, law):
    a, pl = _planned(pack, law, [
        ("a", (0.0, 0.0), 0.0, 0.0), ("b", (0.0, 0.0), 0.0, 0.0),
        ("c", (0.0, 0.0), 0.0, 0.0), ("d", (0.0, 0.0), 0.0, 0.0),   # one anchor family
        ("e", (100.0, 0.0), 0.0, 0.0),                                # the deck, its own anchor
    ], deck_datum=lambda ring: 720.0)
    return a, pl


def test_plan_carries_parts_and_contacts(row):
    _a, pl = row
    by = {m.resource: m for u in pl.units for m in u.members}
    assert len(by["objects/b.obj"].parts) == 2 and len(by["objects/a.obj"].parts) == 1
    assert pl.counts["parts"] == 6 and pl.counts["members"] == 5
    # a–b1, b2–c, c–d, d–e: four contacts, TWO structures (b's components
    # are 1 m apart: b spans both), no unproved pair
    assert pl.counts["contacts"] == 4 and pl.counts["structures"] == 2
    assert pl.counts["pairs_unproved"] == 0 and pl.counts["pools"] == 1
    assert all(p.base_y == pytest.approx(0.0) for m in by.values() if m.resource != "objects/e.obj"
               for p in m.parts)
    back = R.RebakePlan.from_json(pl.to_json())
    assert back == pl and json.loads(pl.to_json())["version"] == R.PLAN_VERSION == 5


def test_four_welded_objects_on_a_slope_cut_into_three_clusters(row, law):
    _a, pl = row
    rb = law.tables.structures.rebake
    # anchor (x = 0) at 690; a and b1 (x 10, 30) at 700; b2 and c (50.5, 70)
    # at 706; d (90) and the deck's anchor (100) at 712
    res = R.seat(pl, _x_sampler([(-1e9, 690.0), (5.0, 700.0), (40.5, 706.0), (80.0, 712.0)]), law)
    ground = [k for k in res.clusters if k.n_measured]
    assert len(ground) == 3 and res.cut_edges == 1          # c–d cut (706 vs 712 > 0.5)
    assert res.counts()["clusters_baked"] == 3 and res.counts()["structures"] == 2
    # d (22 m under) is NOT a facility: its structure's coalition (16 m
    # under) is no at-grade reference — a row on a slope lifts (v1)
    assert res.counts()["clusters_facility"] == 0
    fam = next(u for u in res.units if len(u.members) == 4)
    assert fam.datum == R.DATUM_CLUSTER and fam.bakes and fam.delta_m is None
    by = {m.resource.rsplit("/", 1)[-1]: m for m in fam.members}
    # each resource's delta = the cluster's median ground − ITS anchor ground (690)
    assert by["a.obj"].delta_m == pytest.approx(10.0)
    assert by["c.obj"].delta_m == pytest.approx(16.0)
    assert by["d.obj"].delta_m == pytest.approx(22.0)
    # b carries TWO deltas, per vertex
    b = by["b.obj"]
    assert b.delta_m is None and sorted(d for _c, _k, d in b.part_deltas) == [10.0, 16.0]
    assert res.counts()["members_multi_delta"] == 1
    assert any("several per-vertex deltas" in f for f in fam.findings)
    assert all(abs(d) >= rb.min_delta_m for m in by.values()
               for _c, _k, d in m.part_deltas)


def test_deck_plate_seats_its_own_cluster_and_never_founds_the_ground(row, law):
    _a, pl = row
    res = R.seat(pl, _x_sampler([(-1e9, 690.0), (5.0, 700.0), (40.5, 706.0), (80.0, 712.0)]), law)
    deck = next(u for u in res.units if u.members[0].resource == "objects/e.obj")
    # the solved surface put 720 at the deck: top (authored 4.5) lands there
    # from a base of 712 → +3.5; the deck is exempt from the threshold
    assert deck.datum == R.DATUM_DECK_TOP and deck.bakes
    assert deck.delta_m == pytest.approx(3.5) and deck.members[0].founding
    assert deck.members[0].part_deltas == ((0, deck.members[0].part_deltas[0][1], 3.5),)
    fixed = next(k for k in res.clusters if k.id == deck.members[0].part_deltas[0][1])
    assert fixed.n_measured == 0 and fixed.resources == ("objects/e.obj",)
    # d touches the deck and is NOT founded by it: its own cluster, +22
    fam = next(u for u in res.units if len(u.members) == 4)
    d = next(m for m in fam.members if m.resource == "objects/d.obj")
    assert d.delta_m == pytest.approx(22.0) and d.part_deltas[0][1] != fixed.id


def test_decision_writes_per_vertex_deltas(row, law):
    from auto_patch.engine_v2 import _decision_from_seats
    _a, pl = row
    res = R.seat(pl, _x_sampler([(-1e9, 690.0), (5.0, 700.0), (40.5, 706.0), (80.0, 712.0)]), law)
    dec = _decision_from_seats(pl, res, measure_only=False)
    b = dec.delta_by_resource_and_vertex["objects/b.obj"]
    assert sorted(set(b.values())) == [10.0, 16.0] and len(b) == 16
    assert sum(1 for v in b.values() if v == 10.0) == 8
    assert set(dec.delta_by_resource_and_vertex["objects/a.obj"].values()) == {10.0}
    assert set(dec.delta_by_resource_and_vertex["objects/e.obj"].values()) == {3.5}
    assert dec.decision_kind_by_resource["objects/b.obj"] == "v2_cluster"
    assert dec.decision_kind_by_resource["objects/e.obj"] == "v2_deck_top"
    assert "per-vertex deltas" in dec.seat_note_by_resource["objects/b.obj"]
    # the datum of a multi-delta file is the base (the provenance records the range)
    assert dec.seat_datum_by_resource["objects/b.obj"] == pytest.approx(690.0)
    assert dec.seat_datum_by_resource["objects/a.obj"] == pytest.approx(700.0)


def test_below_threshold_and_unmeasured_clusters_stay(row, law):
    _a, pl = row
    rb = law.tables.structures.rebake
    # flat: nothing is cut (two ground clusters: b's components are apart),
    # every cluster moves 0 < min_delta_m → stays; nothing written
    res = R.seat(pl, lambda la, lo: (700.0, False), law)
    fam = next(u for u in res.units if len(u.members) == 4)
    assert not fam.bakes and fam.skip_reason.startswith("below_threshold")
    assert res.counts()["clusters_below_threshold"] == 2 and res.cut_edges == 0
    assert all(d is None for m in fam.members for _c, _k, d in m.part_deltas)
    # water everywhere and no site datum: the anchor founds nothing (08d a)
    # — HELD, the current bytes kept, every cluster held
    res = R.seat(pl, lambda la, lo: (700.0, True), law)
    fam = next(u for u in res.units if len(u.members) == 4)
    assert fam.held and "anchor on water" in fam.skip_reason
    assert res.counts()["clusters_held"] == res.counts()["clusters"]
    assert rb.water_founds_seat is False and rb.anchor_water_founds_seat is False


# ── 2. hand-built plans: the facility rule, the plate, inheritance, pads ──

def _member(name: str, parts, deck=None):
    ps = tuple(R.Part(pid, i, lat, lon, base_y, 100.0, (lat - 1e-5, lon - 1e-5, lat + 1e-5, lon + 1e-5))
               for i, (pid, lat, lon, base_y) in enumerate(parts))
    return R.Member(name, f"objects/{name}.obj", name, name, 0.0, ps, **(deck or {}))


def _plan_of(units, contacts):
    return R.RebakePlan("ZZZZ", "p", "/p", tuple(units), (), {}, tuple(contacts))


def _by_lat(table):
    """``table``: ``{lat: z}`` — the anchor at lat 0.0."""
    return lambda lat, lon: (table.get(round(lat, 6), table[0.0]), False)


def test_facility_cluster_keeps_its_authored_y(law):
    """OTHH unit:21 at cluster level: three terminal parts at grade and a
    sunken road standing 2.5 m under the mesh — the road's edge is cut,
    its cluster is a FACILITY (outside the structure's coalition and
    deeper than contact_band_m): never seated, authored y kept; the
    terminal's cluster stays (delta 0)."""
    band = law.tables.structures.basin.contact_band_m
    t = [_member(f"Terminal_{i}", [(i, 0.001 * (i + 1), 0.0, 0.0)]) for i in range(3)]
    road = _member("TerminalRoads_03_004", [(3, 0.004, 0.0, 0.0)])
    pl = _plan_of([R.Unit("unit:21", (0.0, 0.0), 0.0, (*t, road))], [(0, 1), (1, 2), (2, 3)])
    res = R.seat(pl, _by_lat({0.0: 710.0, 0.001: 710.0, 0.002: 710.0, 0.003: 710.0,
                              0.004: 710.0 + band + 1.5}), law)
    us = res.units[0]
    by = {m.resource: m for m in us.members}
    r = by["objects/TerminalRoads_03_004.obj"]
    assert r.facility and not r.bakes and "facility" in r.note
    assert all(not by[k].facility for k in by if "Terminal_" in k)
    assert res.cut_edges == 1 and res.counts()["clusters_facility"] == 1
    assert res.counts()["facility_members"] == 1 and not us.bakes
    from auto_patch.engine_v2 import _decision_from_seats
    dec = _decision_from_seats(pl, res, measure_only=False)
    assert "facility member (05p)" in dict(dec.skipped)["objects/TerminalRoads_03_004.obj"]
    assert "objects/TerminalRoads_03_004.obj" in dec.anchor_by_resource


def test_a_structure_sunk_uniformly_lifts_as_one(law):
    """05q: a structure standing uniformly 2.15 m under the mesh is the
    seat's own case, never a facility — one cluster, one lift."""
    band = law.tables.structures.basin.contact_band_m
    a = _member("road", [(0, 0.001, 0.0, 0.0)])
    b = _member("parking", [(1, 0.002, 0.0, 0.0)])
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (a, b))], [(0, 1)])
    res = R.seat(pl, _by_lat({0.0: 710.0, 0.001: 712.0, 0.002: 712.3}), law)
    us = res.units[0]
    assert us.bakes and not any(m.facility for m in us.members)
    assert res.counts()["clusters"] == 1 and us.members[0].delta_m == pytest.approx(2.15)
    assert res.clusters[0].lift_m == pytest.approx(2.15) and 2.15 > band


def test_the_facility_reference_must_be_at_grade(law):
    """05q's "at-grade coalition": three parts 16 m under the mesh and one
    22 m under (a row on a slope) — no facility, every cluster lifts by
    its own ground; the strict relative reading is the key flipped."""
    import dataclasses as dc
    band = law.tables.structures.basin.contact_band_m
    ms = [_member(f"m{i}", [(i, 0.001 * (i + 1), 0.0, 0.0)]) for i in range(4)]
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, tuple(ms))], [(0, 1), (1, 2), (2, 3)])
    table = {0.0: 690.0, 0.001: 706.0, 0.002: 706.0, 0.003: 706.0, 0.004: 712.0}
    res = R.seat(pl, _by_lat(table), law)
    assert res.counts()["clusters_facility"] == 0 and res.counts()["clusters_baked"] == 2
    assert res.units[0].members[3].delta_m == pytest.approx(22.0)
    rb = law.tables.structures.rebake
    strict = dc.replace(law, tables=dc.replace(law.tables, structures=dc.replace(
        law.tables.structures, rebake=dc.replace(rb, facility_requires_at_grade_coalition=False))))
    res2 = R.seat(pl, _by_lat(table), strict)
    assert res2.counts()["clusters_facility"] == 1 and res2.units[0].members[3].facility
    assert 22.0 - 16.0 > band


def test_plate_seat_holds_at_cluster_level(law):
    """A tunnel wall object's plate seats its family on the ground at the
    band (05n-4); a neighbouring ground object in contact with it keeps
    its own cluster and is never founded by the plate."""
    wall = _member("tunnel1", [(0, 0.001, 0.0, -3.0)],
                   deck={"plate_y": 2.0, "plate_stations": ((0.001, 0.0), (0.0015, 0.0))})
    kerb = _member("kerb", [(1, 0.001, 0.0, -3.0)])          # its family: rigid with the plate
    shed = _member("shed", [(2, 0.002, 0.0, 0.0)])            # a neighbour in contact
    pl = _plan_of([R.Unit("u:wall", (0.0, 0.0), 0.0, (wall, kerb)),
                   R.Unit("u:shed", (0.0, 0.0), 0.0, (shed,))], [(0, 1), (0, 2)])
    # the ground at the band reads 710.5: plate (base 710 + 2) must land there → −1.5
    res = R.seat(pl, _by_lat({0.0: 710.0, 0.001: 710.5, 0.0015: 710.5, 0.002: 710.0}), law)
    w, s = res.units
    assert w.datum == R.DATUM_PLATE and w.bakes and w.delta_m == pytest.approx(-1.5)
    assert all(m.delta_m == pytest.approx(-1.5) for m in w.members)
    assert s.datum == R.DATUM_CLUSTER and not s.bakes
    assert s.skip_reason.startswith("below_threshold")
    assert s.members[0].part_deltas[0][1] != w.members[0].part_deltas[0][1]


def test_elevated_parts_inherit_the_supporter(pack, law):
    """v1 I-8: an elevated box 0.1 m over a ground box takes the ground
    box's cluster; a sign floating over nothing re-homes to the
    containing (else nearest) cluster's plan box (spec §4.2b)."""
    _a, pl = _planned(pack, law, [("tower", (0.0, 0.0), 0.0, 0.0), ("sign", (0.0, 0.0), 0.0, 0.0)])
    by = {m.resource: m for u in pl.units for m in u.members}
    tower = by["objects/tower.obj"]
    assert len(tower.parts) == 2 and pl.counts["contacts"] == 1
    assert sorted(p.base_y for p in tower.parts) == pytest.approx([0.0, 3.1])
    # the anchor (x = 0) reads 700, the tower (x = 20) 705: +5
    res = R.seat(pl, _x_sampler([(-1e9, 700.0), (5.0, 705.0)]), law)
    us = res.units[0]
    by = {m.resource: m for m in us.members}
    t, s = by["objects/tower.obj"], by["objects/sign.obj"]
    assert t.delta_m == pytest.approx(5.0) and len({k for _c, k, _d in t.part_deltas}) == 1
    assert s.delta_m == pytest.approx(5.0) and s.part_deltas[0][1] == t.part_deltas[0][1]
    assert res.counts()["clusters"] == 1 and res.counts()["parts"] == 3
    assert res.counts()["ground_parts"] == 1


def test_a_wide_cluster_bakes_and_pads(pack, law):
    """A chain of eight parts climbing 0.45 m each (every edge under the
    tolerance) spans 3.15 m > cluster_span_pad_m: it bakes at its median
    and raises pad requests for the ground parts left more than
    cluster_residual_pad_m off the mesh (v1 spec §4.3 / §5.3)."""
    rb = law.tables.structures.rebake
    _a, pl = _planned(pack, law, [("chain", (0.0, 0.0), 0.0, 0.0)])
    assert pl.counts["parts"] == 8 and pl.counts["contacts"] == 7
    steps = [(-1e9, 690.0)] + [(20.1 * i, 700.0 + 0.45 * i) for i in range(8)]
    res = R.seat(pl, _x_sampler(steps), law)
    k = res.clusters[0]
    assert res.cut_edges == 0 and k.bakes and k.needs_pad
    assert k.span_m == pytest.approx(3.15, abs=1e-6) and 3.15 > rb.cluster_span_pad_m
    assert k.ground_m == pytest.approx(700.0 + 0.45 * 3.5)
    # the ends sit 1.575 m off the median: two connected residual groups
    assert k.residual_parts == 4 and len(res.pad_requests) == 2
    worst = max(res.pad_requests, key=lambda p: abs(p.residual_m))
    assert abs(worst.residual_m) == pytest.approx(1.575) and worst.seated
    assert worst.part_count == 2 and not worst.over_relief_cap
    assert res.units[0].members[0].outliers == 4


def test_clusters_and_pads_round_trip_the_result(row, law):
    _a, pl = row
    res = R.seat(pl, _x_sampler([(-1e9, 690.0), (5.0, 700.0), (40.5, 706.0), (80.0, 712.0)]), law)
    d = res.to_dict()
    assert d["counts"]["clusters"] == 4 and len(d["clusters"]) == 4
    assert d["cut_edges"] == 1 and d["structures"] == 2
    assert all("part_deltas" in m for u in d["units"] for m in u["members"])
    assert _dc.is_dataclass(res.clusters[0])
