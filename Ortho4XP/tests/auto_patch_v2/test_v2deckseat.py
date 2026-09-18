"""§49 A PARAPET RIDES THE DECK — lane ``v2deckseat`` twins (budget mode,
owner 2026-09-17 late): the deck-face reader, the deck's own surface, and
the LOW-END fallback seat (§49 (6)); the shear (5) is NOT implemented, so
the "sheared within 1 cm" twin is not here."""
from __future__ import annotations

import dataclasses as _dc
import inspect

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_deck as PD
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport import placement_read as PR
from auto_patch_v2.airport import placement_record as REC
from auto_patch_v2.airport import placement_write as PW

LAT, LON = 40.0, -3.6
ML, MO = AR._m_per_deg(LAT)


def _ll(x_m: float, y_m: float) -> tuple[float, float]:
    """metres east / north of (LAT, LON) -> (lat, lon)"""
    return (LAT + y_m / ML, LON + x_m / MO)


def _deck(length_m: float = 60.0, grade: float = 0.04, z0: float = 600.0,
          half_w: float = 4.0, ref: str = "bridge_deck:-1") -> AR.DeckFace:
    """a planar deck rising ``grade`` along +x (east)"""
    corners = [(0.0, -half_w), (length_m, -half_w), (length_m, half_w),
               (0.0, half_w)]
    return AR.DeckFace(ref, tuple(_ll(x, y) for x, y in corners),
                       tuple(z0 + grade * x for x, _y in corners))


class _U:
    anchor = (LAT, LON)


class _M:
    heading_deg = 0.0
    resource = "objects/wall.obj"


def _body(feet=(), plan_box=None, cls=AR.LINE_SEGMENT, merged_into="",
          **anchor_kw) -> REC.Body:
    a = AR.Anchor(cls, LAT, LON, 0.0, "line segment 1/1: mid-foot", 605.0,
                  **anchor_kw)
    return REC.Body(0, cls, (0,), a, "objects/wall__b0.obj", feet=tuple(feet),
                    plan_box=plan_box, merged_into=merged_into)


# ── (1) the region reader ────────────────────────────────────────────────

def test_decks_from_graded_doc_reads_only_bridge_deck_refs():
    doc = {"vertices": [[1, 40.0, -3.6, 600.0], [2, 40.0, -3.5, 601.0],
                        [3, 40.1, -3.5, 602.0], [4, 40.1, -3.6, 603.0]],
           "faces": [{"ref": "bridge_deck:-6288", "role": "service_road",
                      "ring": [1, 2, 3, 4]},
                     {"ref": "building7", "role": "building",
                      "ring": [1, 2, 3]},
                     {"ref": "bridge_deck:short", "role": "service_road",
                      "ring": [1, 2]}],
           "breaklines": []}
    decks = PR.decks_from_graded_doc(doc)
    assert [d.ref for d in decks] == ["bridge_deck:-6288"]
    assert decks[0].ring == ((40.0, -3.6), (40.0, -3.5), (40.1, -3.5), (40.1, -3.6))
    assert decks[0].z == (600.0, 601.0, 602.0, 603.0)
    assert PR.DECK_REF_PREFIX == "bridge_deck:"
    assert PP.decks_from_graded_doc is PR.decks_from_graded_doc
    # the region is NOT a pad and NOT a rim
    pads, rims = PR.pads_rims_from_graded_doc(doc)
    assert [p.ref for p in pads] == ["building7"] and rims == ()


# ── (3) the deck's own surface ───────────────────────────────────────────

def test_deck_z_at_is_the_decks_own_plane():
    d = _deck()
    for x in (0.0, 12.5, 30.0, 59.0):
        la, lo = _ll(x, 1.0)
        assert AR.deck_of([d], la, lo) is d
        assert abs(AR.deck_z_at(d, la, lo) - (600.0 + 0.04 * x)) < 1e-6
    la, lo = _ll(70.0, 0.0)
    assert AR.deck_of([d], la, lo) is None


def test_deck_datum_of_needs_the_on_fraction():
    d = _deck()
    on = [_ll(x, 0.0) for x in (5.0, 25.0, 45.0)]
    off = [_ll(x, 0.0) for x in (80.0, 90.0, 100.0, 110.0)]
    assert AR.deck_datum_of(on + off, [d], 0.5) is None          # 3/7
    r = AR.deck_datum_of(on + off[:2], [d], 0.5)                 # 3/5
    assert r is not None and r[0] is d
    assert [i for i, _z in r[1]] == [0, 1, 2]
    assert abs(r[1][2][1] - 601.8) < 1e-6


# ── (6) the fallback seat: the LOW END, never a float ────────────────────

def test_a_footed_wall_on_a_four_percent_deck_seats_at_the_low_end():
    d = _deck()                                       # 600.0 -> 602.4
    feet = [(*_ll(x, 0.0), 0.0) for x in (5, 15, 25, 35, 45, 55)]
    counts: dict = {}
    b = PD.deck_seat(_body(feet=feet), _U(), _M(), [d], on_fraction=0.5,
                     counts=counts)
    a = b.anchor
    assert (a.lat, a.lon) == feet[0][:2]              # the low-end foot
    assert abs(a.surface_z - 600.2) < 1e-6            # the DECK's z there
    assert a.y_zero == 0.0 and a.datum is True
    assert a.reason.startswith("on deck bridge_deck:-1: low end")
    assert "deck rise 2.00 m" in a.reason
    # the seat is baked into the offset (the writer subtracts it) and the
    # file name keys on it (14at)
    assert a.offset != (0.0, 0.0, 0.0)
    assert b.new_resource != "objects/wall__b0.obj"
    assert counts == {"deck_on_bodies": 1, "deck_fallback": 1}
    # never a float: every on-deck foot's deck z is >= the seat
    assert all(AR.deck_z_at(d, f[0], f[1]) >= a.surface_z - 1e-9 for f in feet)


def test_a_footless_body_over_the_deck_takes_the_low_sample():
    d = _deck()
    la0, lo0 = _ll(10.0, -3.0)
    la1, lo1 = _ll(50.0, 3.0)
    b = PD.deck_seat(_body(plan_box=(la0, lo0, la1, lo1)), _U(), _M(), [d],
                     on_fraction=0.5, counts={})
    assert b.anchor.datum and b.anchor.reason.startswith("on deck ")
    # the lowest of the 81 samples: the western column, x = 10 + 40/18
    assert abs(b.anchor.surface_z - (600.0 + 0.04 * (10.0 + 40.0 / 18.0))) < 1e-6
    assert "81 on-deck samples" in b.anchor.reason


def test_a_wall_one_of_eighty_one_on_the_deck_is_untouched():
    d = _deck()
    # a 32 x 60 m box hanging off the deck's east end: ONE sample inside
    la0, lo0 = _ll(58.0, -30.0)
    la1, lo1 = _ll(90.0, 30.0)
    body = _body(plan_box=(la0, lo0, la1, lo1))
    counts: dict = {}
    r = AR.deck_datum_of([(p[0], p[1]) for p in PD._samples(body.plan_box)],
                         [d], 0.0)
    assert r is not None and len(r[1]) == 1                        # 1/81
    assert PD.deck_seat(body, _U(), _M(), [d], on_fraction=0.5,
                        counts=counts) is body
    assert counts == {}


def test_exclusions_by_construction():
    d = _deck()
    feet = [(*_ll(x, 0.0), 0.0) for x in (5, 15, 25, 35, 45, 55)]
    for body in (_body(feet=feet, cls=AR.BASIN),                # a basin body
                 _body(feet=feet, cls=AR.DECK),                 # a deck-class body
                 _body(feet=feet, merged_into="objects/x__b0.obj"),   # carried
                 _body(feet=feet, datum=True),                  # §16e datum
                 _body(feet=feet, family="fam:1"),              # family / unit
                 _body(feet=feet, connector_of="u1|u2"),        # connector
                 _body(feet=feet, unit_seat=True)):
        assert PD.deck_seat(body, _U(), _M(), [d], on_fraction=0.5,
                            counts={}) is body
    assert PD.deck_seat(_body(feet=feet), _U(), _M(), (), on_fraction=0.5,
                        counts={}) is not None


# ── (10) the keys, and the plumbing ─────────────────────────────────────

def test_deck_keys_are_law(tables=None):
    from auto_patch_v2.law import tables as T
    law = T.load_default()
    deck = law.tables.structures.deck
    assert deck.on_fraction == 0.5 and deck.shear is True
    assert deck.shear_max_grade == 0.10
    assert deck.edge_m == 6.0 and deck.under_m == 2.0


def test_a_pier_under_the_deck_is_not_a_parapet():
    """feet inside the edge band whose design surface reads 7 m UNDER the
    deck (the trench) stand under it: untouched, counted"""
    d = _deck()
    feet = [(*_ll(x, 5.0), 0.0) for x in (10, 20, 30, 40)]
    trench = lambda la, lo: 593.0                          # noqa: E731
    counts: dict = {}
    body = _body(feet=feet)
    assert PD.deck_seat(body, _U(), _M(), [d], on_fraction=0.5, counts=counts,
                        edge_m=6.0, surface=trench, under_m=2.0) is body
    assert counts == {"deck_refused_under": 1}
    on_deck = lambda la, lo: AR.deck_z_at(d, la, lo) - 0.5   # noqa: E731
    b = PD.deck_seat(body, _U(), _M(), [d], on_fraction=0.5, counts={},
                     edge_m=6.0, surface=on_deck, under_m=2.0)
    assert b.anchor.datum and abs(b.anchor.surface_z - 600.4) < 1e-6


def test_the_edge_band_reads_a_parapet_on_the_decks_kerb():
    """a wall standing 3 m OUTSIDE the road face is on the deck within
    ``[deck] edge_m``; a pier 20 m off is not"""
    d = _deck()                                       # half width 4 m
    kerb = [(*_ll(x, 7.0), 0.0) for x in (5, 15, 25, 35, 45, 55)]
    assert PD.deck_seat(_body(feet=kerb), _U(), _M(), [d], on_fraction=0.5,
                        counts={}, edge_m=0.0).anchor.datum is False
    b = PD.deck_seat(_body(feet=kerb), _U(), _M(), [d], on_fraction=0.5,
                     counts={}, edge_m=6.0)
    assert b.anchor.datum and abs(b.anchor.surface_z - 600.2) < 1e-6
    pier = [(*_ll(x, 24.0), 0.0) for x in (5, 15)]
    assert PD.deck_seat(_body(feet=pier), _U(), _M(), [d], on_fraction=0.5,
                        counts={}, edge_m=6.0).anchor.datum is False


def test_the_deck_region_reaches_build_splits_and_build_plan():
    for fn in (PP.build_splits, PW.build_plan):
        p = inspect.signature(fn).parameters
        assert "decks" in p and "deck_on_fraction" in p, fn.__name__
        assert "deck_edge_m" in p and "deck_under_m" in p
        assert p["decks"].default == ()
