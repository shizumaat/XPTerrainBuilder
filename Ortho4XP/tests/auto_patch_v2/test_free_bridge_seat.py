"""Owner RULINGS 2026-10-22m / 22p, class B (OTHH +25+051 Bridge_04 canal
bridge 25.25153, 51.62030 and the flyover ramps by 25.25185, 51.61724): a
frame that IS a free-standing bridge — its deck plus piers and rails on one
anchor, no building — seats its deck flush at the end nearer its ground,
every body with it (``airport/free_bridge_seat``); the end reading takes the
deck top AT each end and reads 22p's road-under only with the anchor under
the deck (``airport/bridge_approach``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import bridge_approach as BA
from auto_patch_v2.airport import free_bridge_seat as FB
from auto_patch_v2.airport.placement_record import Body, Split

# a 78 m canal bridge along latitude: banks at 40.0 and 40.0007, water between
RING = ((40.0, -3.0), (40.0, -2.9998), (40.0007, -2.9998), (40.0007, -3.0))
ENDS = (((40.0, -3.0), (40.0, -2.9998)), ((40.0007, -3.0), (40.0007, -2.9998)))
DECK = "objects/bridge_deck.obj"


def _member(**kw):
    base = dict(resource=DECK, id="dsf:obj1", deck_kind="flag", deck_top_y=4.65,
                deck_datum_z=None, deck_ring=RING, deck_ends=ENDS,
                deck_end_stations=(), plate_kind="", plate_y=None, plate_stations=(),
                parts=(), authored_path="", heading_deg=0.0)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _canal(la, lo):
    return 0.0 if 40.00001 < la < 40.00069 else 3.9


_canal.water = lambda la, lo: 40.00001 < la < 40.00069


def _staged(*members, keys=None):
    return [types.SimpleNamespace(m=m, bridge=list(keys or [DECK]), boxes=[None])
            for m in members]


def test_a_canal_bridge_frame_with_piers_is_seated_flush_at_its_banks():
    pier = _member(resource="objects/bridge_piers.obj", id="dsf:obj2", deck_kind="",
                   deck_top_y=None, deck_ring=None)
    zs = FB.free_bridge_zeros(_staged(_member(), pier), _canal,
                              origin=(40.00035, -2.9999), agl_m=-0.65, step_m=5.0,
                              walk_max_m=60.0, level_tol_m=0.3)
    zero, why, _box = zs[DECK]
    # deck top 4.65 flush with the 3.9 banks; the piers sink into the canal
    assert abs(zero + 4.65 - 3.9) < 1e-6 and "22m" in why


def test_a_frame_with_a_building_is_no_free_bridge():
    class Roles:
        def roles_many(self, la, lo):
            return ["building"] * len(la)
    surf = lambda la, lo: _canal(la, lo)                       # noqa: E731
    surf.water, surf.roles = _canal.water, Roles()
    hall = _member(resource="objects/hall.obj", deck_kind="", deck_top_y=None)
    st = _staged(_member()) + [types.SimpleNamespace(m=hall, bridge=[""],
                                                     boxes=[(40.0, -3.0, 40.0001, -2.9999)])]
    assert FB.free_bridge_zeros(st, surf, origin=(40.00035, -2.9999), agl_m=0.0,
                                step_m=5.0) == {}


def test_a_plated_deck_keeps_its_plates_reader():
    st = _staged(_member(plate_kind="overpass", plate_y=0.0))
    assert FB.free_bridge_zeros(st, _canal, origin=(40.00035, -2.9999), agl_m=0.0,
                                step_m=5.0) == {}


def test_a_ramp_is_flush_at_the_end_whose_ground_less_its_top_is_highest():
    def land(la, lo):
        return 296.0 if la < 40.00035 else 294.0
    d = AR.Datum(8.3, (), "deck top", ends=ENDS, step_m=5.0)
    s = BA.approach_seat(d, land, tops=(1.0, -0.5))
    # 296 - 1.0 = 295.0 beats 294 + 0.5 = 294.5: end 1 flush, end 2 floats 0.5
    assert abs(s.zero - 295.0) < 1e-6
    # without the ends' tops the crown would bury both ends 7 m
    assert abs(BA.approach_seat(d, land).zero - (296.0 - 8.3)) < 1e-6


def test_22p_reads_the_road_under_only_with_the_anchor_under_the_deck():
    flat = lambda la, lo: 3.96                                 # noqa: E731
    under = AR.Datum(8.3, (), "deck top", ends=ENDS, step_m=5.0, ring=RING)
    kept = BA.approach_seat(under, flat, origin=(40.00035, -2.9999), authored_agl_m=4.0)
    assert "22p" in kept.reason and abs(kept.zero - 7.96) < 1e-6
    off = BA.approach_seat(under, flat, origin=(40.002, -2.9999), authored_agl_m=4.0,
                           tops=(-0.1, 0.4))
    assert "22p" not in off.reason and abs(off.zero - 4.06) < 1e-6


def test_every_body_of_a_one_deck_frame_takes_the_decks_zero():
    def body(i, zero, key="", box=None):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 3.9 - zero, "own", 3.9,
                      offset=(0.0, 3.9 - zero, 0.0))
        return Body(i, AR.OTHER, (i,), a, f"objects/b__b{i}.obj", bridge_of=key,
                    geom_box=box)
    far = (41.0, -3.0, 41.001, -2.999)
    rec = Split(0, "dsf:obj1", "objects/rails.obj", "/x/objects/rails.obj", 40.0, -3.0,
                0.0, (body(0, 1.78, DECK), body(1, 1.78, box=RING[0] + RING[2]),
                      body(2, -0.75, DECK + "#1"), body(3, 1.78, box=far)))
    m = types.SimpleNamespace(resource="objects/rails.obj", zero_y=0.0)
    box = RING[0] + RING[2]
    out = FB.free_bridge_seat(rec, m, {DECK: (-0.75, "why", box)})
    assert {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies} == {-0.75}
    # several decks: a body no footprint names goes with the deck its box
    # overlaps; one overlapping none keeps its seat
    two = FB.free_bridge_seat(rec, m, {DECK: (-0.75, "a", box),
                                       "objects/other.obj": (9.0, "b", (50.0, 0.0, 50.1, 0.1))})
    assert [round(b.anchor.surface_z - b.anchor.y_zero, 2)
            for b in two.bodies] == [-0.75, -0.75, -0.75, 1.78]
