"""ISSUE #10 [HECA-5] — A UNIT'S CONTENTS RIDE THE UNIT (lane
``interiors10``).

Measured on the HECA placement plan at main 0bc1a0ce: of the 2,491
written bodies whose part ids the plan-wide §16g map puts in a footprint
unit, 180 stood more than 0.5 m off that unit's datum, 140 of them CARRIED
— 118 by §16c (7)'s contact cluster, whose senior footed body was a kerb,
a sidewalk or a neighbour's wall, 20 by §15's "rests on it".  The windows,
doors and glass of a terminal rendered at the sidewalk's level.

``footprint_unit.contents_seat`` keeps a carrier only at the unit's zero,
else a cluster member at that zero, else the unit itself; and the unit
carry reads the surface AT ITS ANCHOR, which is where X-Plane drapes the
row.  The twins are synthetic and hermetic.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import placement_plan as PP

import test_v2jetways31 as J

U_ZERO = 110.0
TOL = 0.3


def _cand(name: str, zero: float, surface_z: float = 100.0):
    """A carrier candidate whose zero plane is ``zero``."""
    a = AR.Anchor("building", 40.0, -3.0, surface_z - zero, "test", surface_z)
    return types.SimpleNamespace(anchor=a, resource=name)


#: two units of the plan-wide map: pids 1-3 are ``fu:0:0``'s, 9 ``fu:0:9``'s
PW = {1: ("fu:0:0", U_ZERO, "building80", "pad"),
      2: ("fu:0:0", U_ZERO, "building80", "pad"),
      3: ("fu:0:0", U_ZERO, "building80", "pad"),
      9: ("fu:0:9", 95.0, "", "ground")}
BOX = (40.0, -3.0, 40.0001, -2.9999)
INDEX = {"fu:0:0": (BOX, (BOX,), U_ZERO, "building80", "pad"),
         "fu:0:9": (BOX, (BOX,), 95.0, "", "ground")}


def _seat(over, pids, *, alts=(), box=BOX, span=200.0):
    counts: dict = {}
    out, uc = FU.contents_seat(over, frozenset(pids), box, PW, INDEX,
                               alternatives=alts, tol_m=TOL,
                               span_max_m=span, counts=counts)
    return out, uc, counts


def test_contents_carried_by_a_sidewalk_ride_their_own_unit_instead():
    """The HECA class: the window's parts are unit fu:0:0's, its contact
    cluster's senior body is a sidewalk 7 m lower — it takes the UNIT."""
    side = _cand("side_walk__b4.obj", U_ZERO - 7.24)
    out, uc, counts = _seat([(side, "§16c (7) bound by contact")], {1, 2})
    assert out == []
    assert uc is not None and uc.unit == "fu:0:0"
    assert uc.zero_z == U_ZERO
    assert "issue #10" in uc.why and "-7.24" in uc.why
    assert counts[FU.CONTENTS_SEAT] == 1
    assert counts[FU.CONTENTS_SEAT + "_worst_m"] == 7.24


def test_a_carrier_at_the_units_zero_is_kept():
    shell = _cand("terminal__b0.obj", U_ZERO + 0.1)
    over = [(shell, "rests on it")]
    out, uc, counts = _seat(over, {1})
    assert uc is None and out == over and not counts


def test_a_cluster_member_at_the_units_zero_is_preferred_to_the_unit():
    side = _cand("side_walk__b1.obj", U_ZERO - 6.14)
    wall = _cand("T3_1__b0.obj", U_ZERO)
    out, uc, counts = _seat([(side, "§16c (7)")], {3}, alts=[side, wall])
    assert uc is None
    assert out[0][0] is wall and "issue #10" in out[0][1]
    assert counts[FU.CONTENTS_SEAT + "_alt_carrier"] == 1


def test_every_piece_of_a_divided_carry_must_stand_at_the_units_zero():
    """A piece the carrier cut divided between two carriers is ONE rigid
    content body: one carrier off the zero sends the whole piece to the
    unit."""
    shell = _cand("terminal__b0.obj", U_ZERO)
    kerb = _cand("kerb__b0.obj", U_ZERO - 2.0)
    out, uc, _c = _seat([(shell, "a"), (kerb, "b")], {1})
    assert out == [] and uc is not None and uc.unit == "fu:0:0"


def test_a_piece_in_no_unit_keeps_its_carrier():
    side = _cand("side_walk.obj", 90.0)
    over = [(side, "rests on it")]
    out, uc, _c = _seat(over, {42})
    assert uc is None and out == over


def test_the_unit_holding_most_of_the_parts_decides():
    other = _cand("hangar.obj", 95.0)          # fu:0:9's zero
    out, uc, _c = _seat([(other, "x")], {9, 1, 2})
    assert uc is not None and uc.unit == "fu:0:0"


def test_a_connector_length_piece_is_left_alone():
    """The owner's railway carve-out (09-18s): a piece spanning
    ``connector_span_m`` is never bound rigidly to one unit's datum."""
    side = _cand("rail.obj", 90.0)
    over = [(side, "x")]
    long_box = (40.0, -3.0, 40.003, -2.997)        # ~420 m diagonal
    out, uc, _c = _seat(over, {1}, box=long_box)
    assert uc is None and out == over


def _two_part_plan(tmp_path, dlat):
    """``test_v2jetways31``'s terminal and a footless jetway of TWO parts
    side by side (6 m squares at 4 m and 14 m east): the file's anchor is
    the HULL's centroid, between the two, while the ground under its
    footprint is read at each part's own centre."""
    import dataclasses as dc
    plan = J._plan(tmp_path, jetway_dlat_m=dlat)
    u = plan.units[0]
    m_j = u.members[1]
    p2 = J._part(3, 1, dlat, 14.0, 6.0, J.JETWAY_Y)
    m_j = dc.replace(m_j, parts=m_j.parts + (p2,))
    return dc.replace(plan, units=(dc.replace(u, members=(u.members[0], m_j)),))


def test_the_unit_carry_reads_the_surface_at_its_anchor(tmp_path):
    """The row is draped at the surface AT THE ANCHOR, so the written zero
    is ``surface(anchor) - y_zero`` and must be the unit's datum even
    where that point is not the median ground under the footprint (a
    kerb, a drain).  The median reading put the jetway 3 m over its
    terminal's floor here."""
    dlat = J.TERMINAL_SIDE_M + J.FRONTAGE_GAP_M
    # the hull of the two parts: (dlat .. dlat+6) x (4 .. 20) metres
    c_lat = J.LAT0 + (dlat + 3.0) / J._ML
    c_lon = J.LON0 + 12.0 / J._MO

    def bump(la: float, lo: float) -> float:
        d = ((la - c_lat) * J._ML) ** 2 + ((lo - c_lon) * J._MO) ** 2
        return J.GROUND_Z + (3.0 if d < 0.25 else 0.0)

    ss = PP.build_splits(_two_part_plan(tmp_path, dlat), bump,
                         (J._pad(),), write=False, **J._args())
    b = J._jetway_body(ss)
    assert abs(b.anchor.lat - c_lat) < 1e-9 and abs(b.anchor.lon - c_lon) < 1e-9
    assert b.anchor.surface_z == bump(b.anchor.lat, b.anchor.lon) == J.GROUND_Z + 3.0
    zero = float(b.anchor.surface_z) - float(b.anchor.y_zero)
    assert abs(zero - J.PAD_Z) < 1e-6, (zero, b.anchor.reason)
    # the reason still reports the ground under the footprint
    assert "own ground -10.00 m" in b.anchor.reason


def test_the_contents_census_reads_the_stages_own_unit_map(tmp_path):
    """``contents_census`` reads ``SplitSet.plan_wide`` — the map the stage
    seated by — and the records' own anchors: the jetway and the terminal
    of the #31 twin are one unit at the pad, nobody is apart; a body moved
    3 m off the datum is counted under the rule its reason names."""
    import dataclasses as dc
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "tools"))
    import contents_census as CC

    ss = PP.build_splits(J._plan(tmp_path), J._flat(J.GROUND_Z), (J._pad(),),
                         write=False, **J._args())
    assert ss.plan_wide
    c = CC.census_unit_levels(ss)
    assert c["bodies"] >= 2 and c["off"] == 0
    s0 = ss.splits[0]
    b0 = s0.bodies[0]
    moved = dc.replace(b0, anchor=dc.replace(
        b0.anchor, y_zero=b0.anchor.y_zero - 3.0,
        reason="carried by kerb.obj (rests on it)"))
    ss2 = dc.replace(ss, splits=(dc.replace(s0, bodies=(moved,) + s0.bodies[1:]),)
                     + ss.splits[1:])
    c2 = CC.census_unit_levels(ss2)
    assert c2["off"] == 1 and c2["off_gt_2m"] == 1
    assert c2["by_rule"] == {"carried": (1, 3.0)} or \
        abs(c2["by_rule"]["carried"][1] - 3.0) < 1e-9
    assert CC.census_unit_levels_lines(c2)[0].startswith("CONTENTS APART")
