"""#1214 round 6 (owner RULINGS 2026-10-23b, "simply make two pads one at
each of those levels"): a two-level group's pad is cut at the SEAT'S OWN two
foot levels; a share touching no airside stands on its low side; a footless
lifted frame stands on its author's ground."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.planar import low_level as LL
from shapely.geometry import box


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


def _wall(x0, y0, x1, y1, y, n=8):
    """A walled part standing on ``y`` with ``n`` feet along its south side
    (frame = degrees: the identity entry below)."""
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))
    feet = tuple((y0 + 0.1, x0 + (x1 - x0) * (i + 0.5) / n, y) for i in range(n))
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=y,
                                 rings=(ring,), feet=feet, line=False, height_m=6.0)


def _airport(parts, tmp_path, ground=lambda x, y: 300.0):
    nav = tmp_path / "apt.dat"
    nav.write_text("I\n1100 Version\n\n1 1000 0 0 ZZZZ Test\n"
                   "1300 101.0 100.0 90.0 gate jets A1\n\n99\n", encoding="utf-8",
                   newline="")
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    return types.SimpleNamespace(
        icao="ZZZZ", pack=types.SimpleNamespace(apt_dat_path=str(nav)),
        partition=types.SimpleNamespace(units=[unit]),
        frame=types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat))),
        dem=types.SimpleNamespace(z=ground))


P = box(0.0, 0.0, 200.0, 100.0)          # the held block; the apron north of it
AIR = box(0.0, 100.0, 200.0, 130.0)


def _terminal(low_y=-8.2):
    # the airside walls on the apron at y -5.8 (their feet within 1 m of it,
    # by the stand at (100, 101)); the concourse at -1; the lower storey
    front = [_wall(60.0 + 10.0 * i, 99.5, 70.0 + 10.0 * i, 100.0, -5.8, 30) for i in range(8)]
    conc = [_wall(10.0, 85.0, 190.0, 95.0, -1.0, 400)]
    low = [_wall(0.0, 0.0, 200.0, 70.0, low_y, 300)]
    return front + conc + low


def test_the_levels_are_the_seats_feet_not_the_frontage_mode(law, tmp_path):
    """KMCI ``building26/b1``: the frontage parts' modal base (the
    concourse, 0 / -1) read as the frontage cut the apron walls into a
    level 12.7 m down; the stand-side floor is -5.8 and the lower storey's
    walls stand 2.4 m under it -- under round 3's 3 m bar, the owner's
    second pad all the same."""
    A = _airport(_terminal(), tmp_path)
    got = LL.plan_low(P, AIR, A, law, 0.5)
    assert got is not None
    H, L, S, rec = got
    assert rec["witness"] == "feet"
    assert rec["top_y"] == pytest.approx(-5.8)
    assert rec["y_lo"] == pytest.approx(-8.2 + 5.8)
    assert L.distance(AIR) >= 3.0 - 1e-6
    assert L.area > 10_000 and H.area > 0.0 and S.area > 0.0
    # no ground veto: the owner's two pads are the object's (DEM level)


def test_one_foot_level_is_one_pad(law, tmp_path):
    parts = [p for p in _terminal() if p.base_y > -8.0]
    assert LL.plan_low(P, AIR, _airport(parts, tmp_path), law, 0.5) is None


def test_no_stands_keeps_the_round_3_reading(law, tmp_path):
    A = _airport(_terminal(), tmp_path)
    A.pack = types.SimpleNamespace(apt_dat_path="")
    assert LL.feet_levels(LL._unit_parts(P, A, lambda lo, la: (lo, la)), AIR, [], law,
                          lambda lo, la: (lo, la)) is None


def test_a_block_keeps_its_lower_and_its_upper_level(law, tmp_path, monkeypatch):
    """A two-level block touching a storey lot: the lower level ``/p1``
    AND the upper level ``/p2`` (round 5's KMCI terminal kept only the
    upper, ``building26/b1/p1``)."""
    from auto_patch_v2.airport.obj8_grade import STEPPED
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar import pad_blocks
    monkeypatch.setattr(pad_blocks, "unit_base", lambda P, a: (STEPPED, "u"))
    A = _airport(_terminal(), tmp_path)
    reg = Registries()
    reg.held["blk"] = {"unit": "blk"}
    from auto_patch_v2.planar.overlay import Region
    region = Region(role="building", ref="blk", polygon=P, code_number=None,
                    code_letter=None, side="airside", source="cell")
    lot = box(200.0, 75.0, 260.0, 95.0)               # a forecourt a storey up, east
    LL.low_level_split([region], [AIR], A, law, 0.5, {}, reg=reg, storey_lots=[(lot, 4.8)])
    kinds = {k: v["kind"] for k, v in reg.landings.items()}
    assert kinds == {"blk/p1": LL.LOW_KIND, "blk/p2": LL.UP_KIND}


def test_a_share_on_no_airside_stands_on_its_low_side():
    """KMCI's tower frame on ground falling 1.5 m: the median of its feet
    floated the tower 1.2 m; the lowest substantial plane does not."""
    from auto_patch_v2.airport.airside_group_seat import ground_plane
    zs = [301.07] * 30 + [301.3] * 40 + [302.3] * 200 + [302.6] * 100
    assert ground_plane(zs) < 301.4
    assert ground_plane([]) is None
    assert ground_plane([5.0]) == 5.0


def test_a_footless_frame_with_a_negative_lift_stands_on_the_authors_ground():
    """KMCI 39.294747, -94.724552: walls authored at y +5.09 under
    ``OBJECT_AGL -5.502`` and no ground-contact feet; y = 0 on the ground
    floated the building 5 m."""
    from auto_patch_v2.airport import footprint_unit as FU
    wall = types.SimpleNamespace(base_y=5.09, height_m=10.0, line=False, feet=())
    parts = {1: wall, 2: wall}
    un = types.SimpleNamespace(id="fu:14:1", pids=frozenset(parts))
    lifted = {q: ((39.29, -94.72), -5.502) for q in parts}
    assert FU._wall_base(un, [un], parts, 2.5, {}, lifted) == pytest.approx(5.502)
    flat = {q: ((39.29, -94.72), 0.0) for q in parts}
    assert FU._wall_base(un, [un], parts, 2.5, {}, flat) == 0.0


def test_no_row_but_the_landing_spans_a_lower_levels_riser():
    """KMCI ``building26/b1``: the pad ceiling and plane read across the
    riser strip, and road ribbons crossing it, held the lower level's edge
    up to 2 m over it (832 pad rows relaxed)."""
    from auto_patch_v2.constraints import riser
    from auto_patch_v2.model.constraints import Diff, Linear, Source
    def face(i, ref, role, ring):
        return types.SimpleNamespace(id=i, ref=ref, role=role, ring=ring, holes=())
    faces = {0: face(0, "b", "building", (1, 2)), 1: face(1, "b/p1#strip", "building", (2, 3)),
             2: face(2, "b/p1", "building", (3, 4)), 3: face(3, "r", "service_road", (2, 3, 5))}
    pm = types.SimpleNamespace(
        faces=faces, registries=types.SimpleNamespace(
            landings={"b/p1": {"block": "b", "kind": "low_level", "y_lo": -2.4}}),
        ring_vertices=lambda ring: ring)
    src = Source("g", "r")
    land = Source("landing_rows", "r", ("low_level:b/p1", "b/p1", "platform:b"))
    rows = [Diff(2, 3, 0.01, 1.0, src),            # across the riser: withdrawn
            Diff(3, 4, 0.01, 1.0, src),            # inside the lower level: kept
            Diff(1, 2, 0.01, 1.0, src),            # inside the block: kept
            Linear(((3, 1.0), (1, -1.0)), None, -2.4, land)]   # the landing row
    counts: dict = {}
    got = riser.riser_exempt(rows, pm, counts)
    assert got == rows[1:]
    assert counts["riser_rows_withdrawn"] == 1 and counts["riser_road_sites"] == 1
    assert riser.STATS["riser_road_sites"] == ["r"]


def _sq(x0, y0, s=10.0):
    d = 1e-5                                        # ~1.1 m per unit in lat
    return ((y0 * d, x0 * d), (y0 * d, (x0 + s) * d), ((y0 + s) * d, (x0 + s) * d),
            ((y0 + s) * d, x0 * d))


def test_23e_units_an_unchained_part_joins_move_with_the_airside_share():
    """22o / 23e: an unchained part within 1 m of two units joins them; the
    group moves with its AIRSIDE-seated unit; two airside units are kept."""
    from auto_patch_v2.airport.open_frame_seat import group_key, unchained_links

    def part(pid, x0, s=10.0):
        return types.SimpleNamespace(pid=pid, rings=(_sq(x0, 0.0, s),))
    u = types.SimpleNamespace(id="f", anchor=(0.0, 0.0), members=[types.SimpleNamespace(
        parts=[part(1, 0.0), part(2, 10.5, 3.0), part(3, 14.0), part(4, 40.0)])])
    pw = {1: ("fu:1:1", 0.0), 3: ("fu:1:3", 0.0), 4: ("fu:1:4", 0.0)}   # 2 is unchained
    assert len(unchained_links(u, pw)) == 1
    got = unchained_links(u, pw, airside={group_key("fu:1:3", "f")})
    assert got == {"fu:1:1": "fu:1:3"}                      # airside wins
    counts: dict = {}
    both = {group_key("fu:1:1", "f"), group_key("fu:1:3", "f")}
    assert unchained_links(u, pw, airside=both, counts=counts) == {}
    assert counts["unchained_airside_conflicts"] == 1
