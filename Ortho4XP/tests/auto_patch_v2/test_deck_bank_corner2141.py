"""#2141 ONE EMBANKMENT ROUND A BANKED DECK'S CORNERS (owner sim read
2026-11-18T13:58Z, ESSA 1.0.558: "we're cutting a strange jagged edge around
the corner of the bridge ... graded smoothly to ground the entire width, with
the same embankment the whole way").  The bank blending out past the run-on
is the bank's face carried on at its slope in every direction
(``constraints/edge_deck._blend_drop``), from the run-on's edge and from the
corridor's floor beside it (``_rim``); the ground round the deck that no cell
owned is the deck's skirt (``planar/deck_skirt``).  Synthetic, no capture."""
from __future__ import annotations

import itertools
import types

import pytest
from shapely.geometry import LineString, Point, box

from auto_patch_v2.constraints.edge_deck import _blend_drop, _rim
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.deck_bank import deck_bank_slope
from auto_patch_v2.model.structures import DeckBridge
from auto_patch_v2.planar.deck_generated import GENERATED_WITNESS
from auto_patch_v2.planar.deck_skirt import SKIRT_PREFIX, deck_skirt_pieces, skirt_region
from auto_patch_v2.planar.overlay import Region

LAW = load_default()
SLOPE = 2.0 / 3.0
# a deck 20 m across a road along y, end lines (seats) along x = 0 and x = 20
ENDS = [types.SimpleNamespace(line=[(0.0, -10.0), (0.0, 10.0)], depth=6.0),
        types.SimpleNamespace(line=[(20.0, -10.0), (20.0, 10.0)], depth=6.0)]
RUN_ON = box(0.0, -10.0, 20.0, 10.0).buffer(1.0, join_style="mitre")


def test_the_bank_round_the_corner_is_never_steeper_than_the_bank():
    """Past the run-on, round its corner and beside its sides, the drop
    changes by at most the bank's slope per metre in any direction -- no
    crease steeper than the bank where the side's face meets the end's
    (1.0.558 read the nearest edge point alone: 1.41x the bank beside the
    side, a cone from the corner)."""
    rim = _rim(ENDS, RUN_ON, SLOPE)
    pts = [Point(x, y) for x, y in itertools.product(
        [-6.0 + 0.75 * i for i in range(14)], [8.0 + 0.75 * j for j in range(12)])
        if not RUN_ON.contains(Point(x, y))]
    drop = {(p.x, p.y): _blend_drop(ENDS, p, RUN_ON, SLOPE, rim=rim) for p in pts}
    worst = max(abs(drop[(a.x, a.y)] - drop[(b.x, b.y)]) / a.distance(b)
                for a, b in itertools.combinations(pts, 2) if a.distance(b) < 1.1)
    assert worst <= SLOPE + 0.02          # the edge is read every RIM_STEP_M
    # beside the side, over the floor, the bank rises from the run-on's edge
    assert _blend_drop(ENDS, Point(10.0, 11.0), RUN_ON, SLOPE) == pytest.approx(6.0)
    assert _blend_drop(ENDS, Point(10.0, 14.0), RUN_ON, SLOPE) == pytest.approx(4.0, abs=0.1)
    # round the corner, moving outward the drop only falls (no notch)
    out = [_blend_drop(ENDS, Point(10.0 + 0.6 * k, 11.0 + 0.6 * k), RUN_ON, SLOPE)
           for k in range(12)]
    assert all(a >= b for a, b in zip(out, out[1:])) and out[0] > out[-1]


def test_the_corridor_floor_beside_the_deck_carries_the_bank():
    """The road's trench running on past the deck's side: its floor's edge
    is the bank's foot too, so the trench's wall beside the deck is the same
    embankment (MEASURED ESSA o4gen_c8fe47a5: the rim 4.2 m past the ring
    3.9 m over the floor 2.5 m away)."""
    floor = box(6.0, 11.0, 14.0, 30.0).exterior          # the road beyond the side
    near = Point(15.0, 20.0)                              # 9 m past the run-on, 1 m off the floor
    bare = _blend_drop(ENDS, near, RUN_ON, SLOPE)
    with_floor = _blend_drop(ENDS, near, RUN_ON, SLOPE, rim=_rim(ENDS, RUN_ON, SLOPE, [floor]))
    assert bare == 0.0 and with_floor == pytest.approx(6.0 - SLOPE * 1.0, abs=0.1)


def test_the_kerb_still_rises_to_the_airside():
    kerb = LineString([(4.0, 13.0), (12.0, 13.0)])
    assert _blend_drop(ENDS, Point(4.0, 12.0), RUN_ON, SLOPE, kerb) == pytest.approx(SLOPE)


def _deck(ring=((0.0, -10.0), (20.0, -10.0), (20.0, 10.0), (0.0, 10.0))):
    return DeckBridge("o4gen_s", "objects/o4_generated/deck_s.obj", (), ring,
                      ((0.0, -10.0), (0.0, 10.0)), ((20.0, -10.0), (20.0, 10.0)), 0.0, 0.0,
                      -6.0, 0.0, floor_min_m=6.0, witness=GENERATED_WITNESS)


def _region(role, ref, poly, source="cell", side="groundside"):
    return Region(role, ref, poly, None, None, side, source)


def test_the_skirt_takes_the_free_ground_the_bank_reaches():
    """The ground round the deck no cell owns becomes the deck's skirt: it
    meets the zone bands and the deck's own corridor, never overlaps them,
    and stands off a building."""
    db = _deck()
    reach = 1.0 + 6.0 / deck_bank_slope(LAW) + 1.0
    zone = _region("graded_strip", "adjacent_ground:taxi:E:zone1#1",
                   box(-30.0, -10.0, 0.0, 10.0), "zone", "airside")
    ramp = _region("tunnel_ramp", "tunnel_ramp", box(5.0, -40.0, 15.0, 40.0))
    house = _region("building", "bldg:1", box(30.0, 12.0, 40.0, 20.0))
    out = deck_skirt_pieces([db], [zone, ramp, house], [], 0.6, 0.2, 5.0, LAW)
    assert out and all(ref.startswith(SKIRT_PREFIX + "o4gen_s#") for ref, _g in out)
    got = out[0][1].union(*[g for _r, g in out[1:]]) if len(out) > 1 else out[0][1]
    assert got.area > 100.0
    for r in (zone, ramp):
        assert got.intersection(r.polygon).area < 1e-6
    assert got.distance(house.polygon) >= 0.6 - 1e-6
    assert skirt_region(db, LAW).buffer(1e-6).contains(got)
    assert got.distance(Point(25.0, 15.0)) == 0.0          # the corner is ground now
    assert abs(skirt_region(db, LAW).bounds[2] - (20.0 + reach)) < 1e-6


def test_a_walled_deck_mints_no_skirt():
    walled = _deck()
    walls = ((0.0, 1.0), (1.0, 0.0), ((5.0, -10.0, 10.0), (15.0, -10.0, 10.0)))
    import dataclasses
    walled = dataclasses.replace(walled, walls=walls)
    assert deck_skirt_pieces([walled], [], [], 0.6, 0.2, 5.0, LAW) == []


def test_only_a_rim_the_ground_shares_takes_the_blend():
    """A corridor's wall rim the ground shares takes the bank's cap; a rim on
    the wall's face alone keeps its pin (MEASURED KIAH: released, a rim
    beside obj24551 fell to 0.00, 28.3 m under its DEM)."""
    from auto_patch_v2.constraints.edge_deck import _open_ground
    faces = {1: types.SimpleNamespace(role="retaining_wall", ref="tunnel_wall"),
             2: types.SimpleNamespace(role="graded_strip", ref="deck_skirt:o#0"),
             3: types.SimpleNamespace(role="retaining_wall", ref="pad_wall")}
    pm = types.SimpleNamespace(faces=faces)

    def vx(*fs):
        return types.SimpleNamespace(incident_faces=fs)
    assert _open_ground(pm, vx(1, 2), walls=True)
    assert not _open_ground(pm, vx(1, 2))
    assert not _open_ground(pm, vx(1), walls=True)
    assert not _open_ground(pm, vx(3, 2), walls=True)
    assert _open_ground(pm, vx(2))
