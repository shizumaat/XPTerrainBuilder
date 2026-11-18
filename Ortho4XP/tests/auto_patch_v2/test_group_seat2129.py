"""#2129 (owner RULINGS 2026-11-18h): building groups on slopes -- fix the
problem spots only.

(4) a seat tilt that floats a foot as WRITTEN is undone and its frame
seats level at its no-float zero (``tilt_float``); KASE's shelters, whose
tilt seats every foot, keep it.  (2) a deck stacked on walls rides those
walls whatever the gap (``stacked_deck``, in ``touch_seat``).  (3) a
connector touching two seats is the warp's (``connector_warp.bridges``).
Synthetic, in the shapes of EDDH's car park (53.625561, 10.006926) and
KASE's ``Shelters.OBJ``.
"""
from __future__ import annotations

import dataclasses as dc
import types

from test_objtilt162 import BAND_M, CAP_DEG, TOL_M, _M, _U, _body, _feet, _surface
from test_touch_seat2110 import _World, _zero

from auto_patch_v2.airport import placement_seat_tilt as PST
from auto_patch_v2.airport import tilt_float as TF
from auto_patch_v2.airport import touch_seat as TS
from auto_patch_v2.airport.placement_record import Split

LAW = TS._TouchLaw(touch_m=0.1, tol_m=0.05, min_share=0.10, walled_m=2.5, contact_tol_m=0.3)


# ── (4) a tilt that floats a foot as written is undone ────────────────────

def _tilted(lift: float = 0.0):
    """KASE's shelters tilted on their apron grade, then their zero moved
    up ``lift`` (a later pass re-zeroing the frame, as EDDH's 22o group did
    to ``park_03__b0``)."""
    b = PST.seat_tilt(_body(_feet()), _U(), _M(), surface=_surface(),
                      max_total_deg=CAP_DEG, foot_tol_m=TOL_M, band_m=BAND_M, counts={})
    assert b.seat.applied
    a = b.anchor
    b = dc.replace(b, anchor=dc.replace(a, y_zero=a.y_zero - lift,
                                        offset=(a.offset[0], a.offset[1] - lift, a.offset[2])))
    rec = Split(0, "dsf:shelters", _M.resource, "", a.lat, a.lon, 0.0, (b,))
    u = types.SimpleNamespace(id="unit:1", anchor=_U.anchor)
    return [rec], {"dsf:shelters": (u, _M())}


def _untilt(splits, members, sink_max_m=1.0):
    counts: dict = {}
    moved, rows = TF.untilt_floating(splits, members, _surface(), band_m=BAND_M,
                                     contact_tol_m=TOL_M, tol_m=0.05, sink_max_m=sink_max_m,
                                     counts=counts)
    return moved, rows, counts


def test_the_shelters_keep_their_tilt():
    """The tilt seats every foot on the apron grade: nothing floats, so
    rule (4) leaves it exactly as written."""
    splits, members = _tilted()
    before = splits[0].bodies[0]
    moved, rows, counts = _untilt(splits, members)
    assert not moved and not rows and not counts
    assert splits[0].bodies[0] is before and before.seat.applied


def test_a_tilt_re_zeroed_to_float_is_levelled_at_its_no_float_zero():
    """The shelters' level seat floats their high end 1.64 m + the lift:
    with a sink allowance past that, the frame is levelled ..."""
    splits, members = _tilted(lift=0.5)
    u, m = members["dsf:shelters"]
    tilted = splits[0].bodies[0]
    worst = max(f[4] for f in TF._floats_as_written(tilted, u, m, _surface(), BAND_M, TOL_M))
    assert worst > 0.4
    _moved, rows, counts = _untilt(splits, members, sink_max_m=3.0)
    b = splits[0].bodies[0]
    assert counts["seat_tilt_refused_floats"] == 1 and len(rows) == 1
    assert not b.seat.applied and "RULINGS 2026-11-18h (4)" in b.anchor.reason
    assert b.new_resource != tilted.new_resource       # the file bakes no tilt now
    fs = TF._floats_as_written(b, u, m, _surface(), BAND_M, TOL_M)
    assert -1e-6 < max(f[4] for f in fs) <= 1e-6     # the highest zero floating nothing


# ── (2) a deck stacked on walls rides them ────────────────────────────────

def _deck(w: _World, i: int) -> None:
    rec = w.records[i]
    w.records[i] = dc.replace(rec, bodies=(dc.replace(rec.bodies[0], body_class="deck"),))


def test_a_deck_on_walls_1_4_m_apart_rides_the_walls():
    """EDDH g1: the top deck seated 1.40 m over the walls it stands on (16v's
    judgement band) takes the walls' zero; the walls do not move."""
    w = _World()
    walls = w.body("walls", (0, 0, 40, 0.5), 11.86, h=8.48)
    deck = w.body("deck", (0, -10, 40, 10), 13.26, base=7.60, h=0.88)
    _deck(w, deck)
    out, table, counts = w.run(law=LAW)
    assert _zero(out[walls]) == 11.86
    assert _zero(out[deck]) == 11.86
    assert table["stacked"] == [("objects/deck__b0.obj", "objects/walls__b0.obj", 13.26, 11.86)]
    assert counts["touch_stacked_decks"] == 1
    assert "RULINGS 2026-11-18h (2)" in out[deck].bodies[0].anchor.reason


def test_a_deck_beside_a_building_is_not_stacked():
    """Touching side by side (no plan overlap) is no bearing: 16v as before."""
    w = _World()
    w.body("walls", (0, 0, 40, 20), 11.86, h=8.48)
    deck = w.body("deck", (40.05, 0, 80, 20), 13.26, base=7.60, h=0.88)
    _deck(w, deck)
    out, table, _c = w.run(law=LAW)
    assert table["stacked"] == [] and _zero(out[deck]) == 13.26


def test_a_slab_on_the_ground_over_a_wall_is_not_stacked():
    """A part on the ground (no elevated slab) is not a deck on walls."""
    w = _World()
    w.body("walls", (0, 0, 40, 0.5), 11.86, h=8.48)
    deck = w.body("deck", (0, -10, 40, 10), 13.26, base=0.0, h=0.88)
    _deck(w, deck)
    _out, table, _c = w.run(law=LAW)
    assert table["stacked"] == []


# ── (3) a connector touching two seats goes to the warp ───────────────────

def test_a_sky_bridge_between_two_seats_is_listed_for_the_warp():
    """A 2 m spread is 16v's separate pads: nobody moves, the bridge is
    handed to the warp."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (60, 0, 80, 20), 433.0)
    br = w.body("bridge", (19.95, 8, 60.05, 12), 431.0, base=6.0, h=3.0, feet=False)
    out, table, _c = w.run(law=LAW)
    assert table["connectors"] == [(br, str(out[br].bodies[0].body_id))]


def test_a_connector_between_one_seat_is_no_bridge():
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (60, 0, 80, 20), 431.0)
    w.body("bridge", (19.95, 8, 60.05, 12), 431.0, base=6.0, h=3.0, feet=False)
    _out, table, _c = w.run(law=LAW)
    assert table["connectors"] == []


def test_a_frame_whose_level_seat_floats_past_a_metre_is_listed_and_kept():
    """... and with 16v's metre it is no tilt problem: listed, untouched."""
    splits, members = _tilted(lift=0.5)
    before = splits[0].bodies[0]
    moved, rows, counts = _untilt(splits, members, sink_max_m=1.0)
    assert not moved and rows[0][3] is None and counts["seat_tilt_float_unreached"] == 1
    assert splits[0].bodies[0] is before
