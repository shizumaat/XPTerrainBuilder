"""M6b twins (RULINGS 2026-09-04k): the DECK SIGNATURE by geometry for
objects without ``ATTR_hard_deck``, the abutment seat (R12), the founding
witness floor, the basin-family exclusion and the one-anchor family —
v2-pure, hermetic, no v1 import."""
from __future__ import annotations

import dataclasses as _dc
import math
from pathlib import Path

import pytest
from shapely.geometry import LineString

from auto_patch_v2.airport import deck_signature as DS
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects

from test_m6a_rebake import _airport, _box_obj  # noqa: E402  (rootdir-relative, as the suite imports)

# ── synthetic OBJ8: a set of boxes in one file ───────────────────────────


def _boxes_obj(path: Path, boxes, attr: str = "") -> Path:
    """``boxes``: ``(cx, cz, hx, hz, y_bottom, y_top)`` each; one solid
    ``TRIS`` range (``attr`` before it, e.g. ``ATTR_hard_deck``)."""
    vt: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []
    for cx, cz, hx, hz, y0, y1 in boxes:
        base = len(vt)
        corners = [(cx - hx, cz - hz), (cx + hx, cz - hz), (cx + hx, cz + hz), (cx - hx, cz + hz)]
        for x, z in corners:
            vt.append((x, y1, z))
            vt.append((x, y0, z))
        for i in range(4):
            a, b = base + 2 * i, base + 2 * ((i + 1) % 4)
            tris += [(a, a + 1, b), (a + 1, b + 1, b)]
        tris += [(base + 0, base + 2, base + 4), (base + 0, base + 4, base + 6),
                 (base + 1, base + 5, base + 3), (base + 1, base + 7, base + 5)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ") + " ".join(map(str, chunk)))
    if attr:
        lines.append(attr)
    lines.append(f"TRIS 0 {len(idx)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def _bridge_boxes(length: float = 60.0, half_w: float = 6.0, deck_y: float = 4.0):
    """A deck slab ``deck_y`` up on four piers reaching y = 0."""
    hx = length / 2.0
    boxes = [(0.0, 0.0, hx, half_w, deck_y - 0.4, deck_y)]
    for px in (-hx + 3.0, hx - 3.0):
        for pz in (-half_w + 1.0, half_w - 1.0):
            boxes.append((px, pz, 0.6, 0.6, 0.0, deck_y - 0.4))
    return boxes


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    root = tmp_path_factory.mktemp("deckpack")
    (root / "Earth nav data").mkdir()
    (root / "Earth nav data" / "apt.dat").write_text("I\n1200\n\n1 700 0 0 ZZZZ Synthetic\n")
    d = root / "objects"
    _box_obj(d / "flag.obj", 12.0, 8.0, 0.5, top=4.0, attr="ATTR_hard_deck")
    _boxes_obj(d / "plate.obj", _bridge_boxes())               # an un-flagged deck
    _boxes_obj(d / "rail.obj", [(0.0, 6.5, 30.0, 0.1, 4.3, 5.3)])   # a railing above the deck plane
    _boxes_obj(d / "wall.obj", [(0.0, 0.0, 30.0, 0.15, 0.0, 4.0)])  # a wall: no plate
    _boxes_obj(d / "canopy.obj", _bridge_boxes(length=40.0, deck_y=5.0))   # a canopy on columns
    _boxes_obj(d / "pit.obj", [(0.0, 0.0, 10.0, 8.0, -6.0, 0.0)])   # a basin
    _boxes_obj(d / "rim.obj", [(0.0, 9.0, 10.0, 0.5, 0.0, 0.3)])    # its rim piece
    # a SKIRT 5 m under grade with many feet and no floor plate (walls only)
    _boxes_obj(d / "skirt.obj", [(0.0, -9.0, 8.0, 0.2, -5.0, 0.0), (0.0, 9.0, 8.0, 0.2, -5.0, 0.0),
                                 (-9.0, 0.0, 0.2, 8.0, -5.0, 0.0), (9.0, 0.0, 0.2, 8.0, -5.0, 0.0)])
    _boxes_obj(d / "shed.obj", [(0.0, 0.0, 6.0, 6.0, 0.0, 3.0)])     # a shed on the ground
    return root


def _ways(*specs):
    out = []
    for i, (pts, tags) in enumerate(specs):
        out.append(OsmWay(-(i + 1), "highway", tuple(pts), False, dict(tags)))
    return out


def _read(pack, law, placements, ways=()):
    a = _airport(pack, law, placements)
    a = _dc.replace(a, osm_ways=tuple(ways))
    objs, rep = read_objects(a, law)
    return a, objs, rep


# ── 1. the signature ─────────────────────────────────────────────────────

def test_flagged_deck_keeps_the_primary_signature(pack, law):
    _a, objs, _rep = _read(pack, law, [("flag", (0.0, 0.0), 0.0, 0.0)],
                           _ways(([(-30.0, 0.0), (30.0, 0.0)], {"highway": "trunk", "bridge": "yes"})))
    o = objs[0]
    assert o.deck_kind == "flag" and o.hard_deck is not None
    assert o.deck_evidence == ("ATTR_hard_deck: the primary deck signature",)


def test_unflagged_plate_with_a_bridge_way_is_a_deck(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    _a, objs, rep = _read(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0),
                                      ("rail", (0.0, 0.0), 0.0, 0.0)], way)
    plate = next(o for o in objs if o.path.endswith("plate.obj"))
    rail = next(o for o in objs if o.path.endswith("rail.obj"))
    assert plate.deck_kind == "signature" and plate.hard_deck is not None
    assert plate.deck_top_z == pytest.approx(700.0 + 4.0)
    pl = plate.deck_plate
    assert pl.ends is not None and pl.length_m == pytest.approx(60.0, abs=0.5)
    assert pl.width_m == pytest.approx(12.0, abs=0.5)
    assert pl.elevation_above_feet_m == pytest.approx(4.0, abs=0.01)
    assert pl.stations and max(y for _p, y in pl.stations) == pytest.approx(4.0)
    assert any("road_bridge" in e for e in plate.deck_evidence)
    # the end lines are the plate's short edges, 60 m apart
    (a, b), (c, d) = pl.ends
    assert math.hypot((a[0] + b[0]) / 2 - (c[0] + d[0]) / 2,
                      (a[1] + b[1]) / 2 - (c[1] + d[1]) / 2) == pytest.approx(60.0, abs=0.5)
    # the railing shares the anchor: a member of the deck family, no plate of its own
    assert rail.deck_kind == "family" and rail.hard_deck is None
    assert rep.deck_signature_families == 1


def test_plate_without_spanning_evidence_is_a_candidate(pack, law):
    _a, objs, rep = _read(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)])
    o = objs[0]
    assert o.deck_kind == "candidate" and o.hard_deck is None and o.deck_plate is not None
    assert rep.deck_candidate_families == 1 and rep.deck_signature_families == 0


def test_a_way_crossing_the_plate_transversally_is_no_evidence(pack, law):
    way = _ways(([(0.0, -40.0), (0.0, 40.0)], {"highway": "trunk", "bridge": "yes"}))
    _a, objs, _rep = _read(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)], way)
    o = objs[0]
    assert o.deck_kind == "candidate"
    assert DS.way_cover(o.deck_plate, LineString([(0.0, -40.0), (0.0, 40.0)])) < 0.5
    assert DS.way_cover(o.deck_plate, LineString([(-40.0, 0.0), (40.0, 0.0)])) > 0.9


def test_a_wall_is_not_a_deck(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    _a, objs, rep = _read(pack, law, [("wall", (0.0, 0.0), 0.0, 0.0)], way)
    assert objs[0].deck_kind == "" and objs[0].deck_plate is None
    assert rep.deck_signature_families == 0 and rep.deck_candidate_families == 0


def test_candidate_over_a_below_grade_region_is_promoted(pack, law):
    _a, objs, _rep = _read(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)])
    from shapely.geometry import Polygon
    promoted, n = DS.promote(objs, [Polygon([(-5, -20), (5, -20), (5, 20), (-5, 20)])])
    assert n == 1 and promoted[0].deck_kind == "signature"
    untouched, n0 = DS.promote(objs, [Polygon([(200, 200), (210, 200), (210, 210), (200, 210)])])
    assert n0 == 0 and untouched[0].deck_kind == "candidate"


# ── 2. the plan: families, exclusions ───────────────────────────────────

def _planned(pack, law, placements, ways=(), exclude=(), below_grade=()):
    a, objs, _rep = _read(pack, law, placements, ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    return _plan(a, objs, cache, law, None, exclude=exclude, below_grade=below_grade)


def test_basin_family_excluded_whole(pack, law):
    pl = _planned(pack, law, [("pit", (0.0, 0.0), 0.0, 0.0), ("rim", (0.0, 0.0), 0.0, 0.0),
                              ("plate", (500.0, 0.0), 0.0, 0.0)],
                  exclude={"dsf:obj0"})
    resources = [m.resource for u in pl.units for m in u.members]
    assert "objects/pit.obj" not in resources and "objects/rim.obj" not in resources
    assert "objects/plate.obj" in resources
    assert pl.counts["terrain_adapted"] == 2


def test_deck_family_seats_its_below_grade_pier_rigidly(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    # a pit sharing the deck's anchor but no basin: in a deck family it seats with the deck
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0), ("pit", (0.0, 0.0), 0.0, 0.0)], way)
    unit = pl.units[0]
    assert {m.resource for m in unit.members} == {"objects/plate.obj", "objects/pit.obj"}
    m = next(m for m in unit.members if m.resource == "objects/plate.obj")
    assert m.deck_kind == "signature" and m.deck_ends is not None and m.deck_stations
    assert m.deck_top_y == pytest.approx(4.0)


def test_plan_json_round_trips_the_signature(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)], way)
    back = R.RebakePlan.from_json(pl.to_json())
    assert back == pl and back.units[0].members[0].deck_ends is not None


# ── 3. the seat ──────────────────────────────────────────────────────────

def _span_sampler(land_z: float, water_half_width: float, anchor_ll, m_per_deg):
    """Land at ``land_z`` everywhere except a WATER band ``water_half_width``
    metres either side of the anchor's east-west axis... measured along
    the deck (x): the canal under the mid-span."""
    la0, lo0 = anchor_ll
    m_lat, m_lon = m_per_deg

    def f(lat, lon):
        x = (lon - lo0) * m_lon
        if abs(x) <= water_half_width:
            return (0.0, True)
        return (land_z, False)
    return f


def test_deck_seats_its_top_at_the_abutment_ground(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0), ("rail", (0.0, 0.0), 0.0, 0.0)], way)
    u = pl.units[0]
    mpd = R._metres_per_degree(u.anchor[0])
    # anchor over the canal at 0.0; the banks 20 m either side at 705
    res = R.seat(pl, _span_sampler(705.0, 20.0, u.anchor, mpd), law)
    us = res.units[0]
    assert us.datum == "deck_top" and us.bakes
    # deck top (authored 4.0) at the bank: delta = 705 − (0 + 0 + 4) = 701
    assert us.delta_m == pytest.approx(701.0, abs=0.01)
    deck = next(s for s in us.members if s.resource == "objects/plate.obj")
    assert deck.founding and deck.delta_m == pytest.approx(701.0, abs=0.01)
    assert any("stations over water" in r for r in deck.records)
    rail = next(s for s in us.members if s.resource == "objects/rail.obj")
    assert not rail.founding
    assert any("foot member(s) follow rigidly" in f for f in us.findings)


def test_abutment_walks_landward_off_the_water(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)], way)
    u = pl.units[0]
    mpd = R._metres_per_degree(u.anchor[0])
    # water reaches 12 m past the deck ends (30 + 12): the line must walk
    res = R.seat(pl, _span_sampler(705.0, 42.0, u.anchor, mpd), law)
    us = res.units[0]
    assert us.bakes and us.delta_m == pytest.approx(701.0, abs=0.01)
    deck = us.members[0]
    assert any("walked 15 m" in r for r in deck.records)
    # water beyond the walk cap: no abutment, the deck cannot found; feet on water: HELD
    res = R.seat(pl, _span_sampler(705.0, 30.0 + 70.0, u.anchor, mpd), law)
    assert res.units[0].held


def test_canopy_on_the_ground_is_refused_by_the_crest_clearance(pack, law):
    way = _ways(([(-30.0, 0.0), (30.0, 0.0)], {"highway": "service", "bridge": "yes"}))
    pl = _planned(pack, law, [("canopy", (0.0, 0.0), 0.0, 0.0)], way)
    assert pl.units[0].members[0].deck_kind == "signature"
    # flat land everywhere: the deck seat would drop the canopy 5 m
    res = R.seat(pl, lambda la, lo: (704.0, False), law)
    us = res.units[0]
    assert us.datum == "feet"
    assert any("crest clearance" in f or "stands over anything" in f for f in us.findings)
    # the feet law: the columns' feet (y = 0) already stand on the flat
    # 704 ground (the deck seat would have dropped the canopy 5 m)
    assert us.delta_m == pytest.approx(0.0, abs=0.01)
    assert any(r.startswith("deck reading") for r in us.members[0].records)


def test_disagreeing_deck_members_stand_down(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)], way)
    m = pl.units[0].members[0]
    # two deck members whose abutments read 3 m apart: no coalition
    m2 = _dc.replace(m, id="x", resource="objects/plate2.obj", deck_top_y=m.deck_top_y + 3.0)
    pl2 = R.RebakePlan(pl.icao, pl.pack_name, pl.pack_root,
                       (R.Unit("u", pl.units[0].anchor, 0.0, (m, m2)),), (), {})
    mpd = R._metres_per_degree(pl.units[0].anchor[0])
    res = R.seat(pl2, _span_sampler(705.0, 20.0, pl.units[0].anchor, mpd), law)
    us = res.units[0]
    assert us.datum == "feet"
    assert any("deck members disagree" in f for f in us.findings)


def test_founding_witness_floor(law):
    rb = law.tables.structures.rebake
    lat, lon = 60.5, -135.5
    feet_big = tuple(R.Foot(lat + i * 1e-5, lon, 0.0) for i in range(100))
    feet_tiny = tuple(R.Foot(lat - i * 1e-5, lon, -6.0) for i in range(4))
    big = R.Member("a", "objects/big.obj", "big", "big", 0.0, feet_big)
    tiny = R.Member("b", "objects/tiny.obj", "tiny", "tiny", 0.0, feet_tiny)
    pl = R.RebakePlan("ZZZZ", "p", "/p", (R.Unit("u", (lat, lon), 0.0, (big, tiny)),), (), {})
    res = R.seat(pl, lambda la, lo: (702.0, False), law)
    us = res.units[0]
    # flat ground under the anchor: the 100-witness member's feet sit on it
    # (0); the 4-witness piece 6 m under would have lifted the unit +6
    assert us.delta_m == pytest.approx(0.0)
    assert next(s for s in us.members if s.resource == "objects/big.obj").founding
    assert not next(s for s in us.members if s.resource == "objects/tiny.obj").founding
    assert any("under the founding witness floor" in f for f in us.findings)
    assert 4 < rb.founding_min_witnesses


def test_family_takes_one_anchor_one_delta(pack, law):
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0), ("rail", (0.0, 0.0), 0.0, 0.0),
                              ("wall", (0.0, 0.0), 90.0, 0.0)], way)
    assert len(pl.units) == 1 and len(pl.units[0].members) == 3
    u = pl.units[0]
    mpd = R._metres_per_degree(u.anchor[0])
    us = R.seat(pl, _span_sampler(705.0, 20.0, u.anchor, mpd), law).units[0]
    assert us.bakes and us.datum == "deck_top"
    assert len(us.resources) == 3 and us.delta_m == pytest.approx(701.0, abs=0.01)


def test_below_grade_skirt_never_founds_its_family(pack, law):
    """A member whose genuine solids reach the admission depth under the
    local ground is below-grade structure the terrain adapts to — floor
    plate or not (OTHH TerminalRoads_03_005: 84 witnesses 4.7 m under,
    lifted a 403-member family +5.96 once the witness floor had stopped
    the 4-witness piece)."""
    pl = _planned(pack, law, [("shed", (0.0, 0.0), 0.0, 0.0), ("skirt", (0.0, 0.0), 0.0, 0.0)])
    unit = pl.units[0]
    assert [m.resource for m in unit.members] == ["objects/shed.obj"]
    assert pl.counts["below_grade"] == 1
    us = R.seat(pl, lambda la, lo: (702.0, False), law).units[0]
    assert us.delta_m == pytest.approx(0.0) and not us.held


def test_a_way_along_a_small_plate_does_not_carry_a_large_family(pack, law):
    """OTHH Terminal_Parking: one 90 m kerb road (bridge=yes) beside
    50,000 m² of parking slabs — the way must carry most of the family's
    deck plane."""
    # the deck (60 m) plus a much larger slab in the same plane at the same anchor
    _boxes_obj(pack / "objects" / "slab.obj", [(0.0, 60.0, 30.0, 40.0, 3.6, 4.0)])
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    _a, objs, rep = _read(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0),
                                      ("slab", (0.0, 0.0), 0.0, 0.0)], way)
    assert all(o.deck_kind == "candidate" for o in objs)
    assert any("refused" in e and "%" in e for o in objs for e in o.deck_evidence)
    assert rep.deck_signature_families == 0


def test_deck_seat_is_exempt_from_the_threshold(pack, law):
    """OTHH's interchange sits at +0.9576 (v1, owner-accepted): a deck
    seat under 1.0 m still bakes; a feet seat under it stays."""
    way = _ways(([(-40.0, 0.0), (40.0, 0.0)], {"highway": "trunk", "bridge": "yes"}))
    pl = _planned(pack, law, [("plate", (0.0, 0.0), 0.0, 0.0)], way)
    u = pl.units[0]
    mpd = R._metres_per_degree(u.anchor[0])
    # anchor over the canal at 0.0; the banks at 4.5: delta = 4.5 − 4.0 = 0.5
    us = R.seat(pl, _span_sampler(4.5, 20.0, u.anchor, mpd), law).units[0]
    assert us.datum == "deck_top" and us.delta_m == pytest.approx(0.5, abs=0.01) and us.bakes


def test_basin_exclusion_matches_paths_too(pack, law):
    pl = _planned(pack, law, [("pit", (0.0, 0.0), 0.0, 0.0), ("rim", (0.0, 0.0), 0.0, 0.0)],
                  exclude={"objects/pit.obj"})
    assert pl.units == () and pl.counts["terrain_adapted"] == 2
