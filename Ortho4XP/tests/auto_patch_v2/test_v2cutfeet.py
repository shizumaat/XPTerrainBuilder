"""§11b (7) — A FOOT ON A STRUCTURE CUT STATES NO GROUND ROW (owner
RULINGS 2026-09-13bs, lane ``v2cutfeet``).

OTHH's tunnel object ``tunnel south west 2#b0`` was re-seated to the
ground (3.962) and its eight §11b foot rows then demanded that the ramp
ITS OWN WALLS CUT stand at that ground every few metres: +3.31 m off the
ramp's design line at the owner's point, 12 of 21 monotone rows
violated, and the whole design solve fell from OPTIMAL to ``feasible``
with two hard rows violated.  A foot on a structure-cut face now takes a
``cut`` verdict — counted, reported, NO ``Linear`` — and the object rides
the cut (§16a / §16c (3)).

Three readings, on the same lawful adjacent ground round 6's twins use
(``test_v2canopy6``), so nothing but the foot rows is in play:

1. a body whose feet stand on a STRUCTURE face fires no row and is
   reported ``cut`` with its role;
2. the role set is the ONE register ``precedence.toml`` states it in
   (``structure = true``) — never a literal tuple in this module, so a
   role added to the register is covered the day it lands;
3. a body on ordinary ground beside it still fires every foot: the
   verdict is per body, not a site-wide disarm.
"""
from __future__ import annotations

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import foot_rows as FR
from auto_patch_v2.law.tables import is_structure_role
from tests.auto_patch_v2.test_crown import _rect  # noqa: F401
from tests.auto_patch_v2.test_v2grounddem import _LawfulDem, _X0, _Y0, _Y1, _lawful_z
from tests.auto_patch_v2.test_v2canopy6 import (_PITCH, _FEET_X, _FEET_Y0, _feet,
                                                _group, _with_groups)
from tests.auto_patch_v2.test_v2smooth import _airport, law  # noqa: F401

#: the ramp cell: a small structure face out on the ground, under the
#: feet of reading (1)
_RAMP_X0, _RAMP_X1 = _FEET_X - 20.0, _FEET_X + 20.0
_RAMP_Y1 = _FEET_Y0 + 5.0
_RAMP_Y0 = _FEET_Y0 - 9 * _PITCH - 5.0


def _cells(r, *, ramp_role: str):
    return (Cell(0, "runway", "09/27", _rect(r, _X0, _Y0, _X0 + 2000.0, _Y1), (), 3,
                 "D", "airside", "runway", {}),
            Cell(9, ramp_role, "rampA",
                 _rect(r, _RAMP_X0, _RAMP_Y0, _RAMP_X1, _RAMP_Y1), (), None,
                 "D", "groundside", ramp_role, {}))


def _arm(law, groups, *, ramp_role: str):                          # noqa: F811
    """``test_v2canopy6._arm`` with a STRUCTURE face instead of an apron."""
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.solve import solve_design
    airport, r = _airport(law, _LawfulDem(), ())
    airport = _with_groups(airport, groups(airport, r))
    pm, _st = build(airport, Classification(_cells(r, ramp_role=ramp_role), (), {}, ()),
                    law)
    pm = with_runway_chord(pm, law, airport)
    cs, counts, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return airport, pm, cs, sol, rep, counts


def _colonnade(gid, airport, r, x):
    pts = [(x, _FEET_Y0 - i * _PITCH) for i in range(9)]
    zs = [_lawful_z(px, py) for px, py in pts]
    return _group(gid, _feet(airport, r, pts, [z - min(zs) for z in zs]))


def test_a_body_on_a_structure_cut_takes_no_rows(law):             # noqa: F811
    """(1) The feet stand on a ``tunnel_ramp`` face — the surface §33
    states, not ground.  No ``Linear``, verdict ``cut``, the role
    reported."""
    def groups(a, r):
        return [_colonnade("onramp", a, r, _FEET_X)]
    _a, _pm, _cs, _sol, rep, counts = _arm(law, groups, ramp_role="tunnel_ramp")
    st = FR.STATS["foot_rows"]
    assert st["cut"] == 1 and st["bare"] == 0, st
    assert st["cut_feet"] == 9 and st["rows"] == 0, st
    assert counts["foot_rows"] == 0 and rep.foot_rows == 0
    assert counts["foot_rows.cut"] == 1 and counts["foot_rows.cut_feet"] == 9
    v = [v for v in FR.VERDICTS if v.verdict == "cut"]
    assert v and v[0].gid == "onramp" and "tunnel_ramp" in v[0].roles


def test_the_cut_roles_are_the_precedence_register_not_a_literal(law):  # noqa: F811
    """(2) ONE list (RULINGS 2026-09-13bs): ``_FaceIndex`` reads the
    ``structure = true`` register, so every structure role the law names
    — the tunnel ramp, the trench a basin floor lives in, the two wall
    corridors, the door and garage ramps, the retaining wall, the bridge
    cuts — classifies ``cut`` without this module listing any of them."""
    def groups(a, r):
        return [_colonnade("onramp", a, r, _FEET_X)]
    _a, pm, _cs, _sol, _rep, _counts = _arm(law, groups, ramp_role="tunnel_ramp")
    idx = FR._FaceIndex(pm, law)
    named = {r for r in law.tables.precedence.roles if is_structure_role(law, r)}
    assert "tunnel_ramp" in named and "tunnel_trench" in named
    assert "retaining_wall" in named and "wall_corridor_ramp" in named
    for role in named:
        assert idx.kind(role) == "cut", role
    # and nothing else is swept in: the apron is still pavement, a
    # building pad still rigid, bare ground still ground
    assert idx.kind("apron") == "pavement"
    assert idx.kind("building") == "rigid"
    assert idx.kind("graded_strip") == "ground"
    assert idx.kind(None) == "none"


def test_a_neighbour_on_bare_ground_still_fires_every_foot(law):   # noqa: F811
    """(3) The verdict is PER BODY: the colonnade beside the ramp, on
    ordinary ground, still takes its nine rows (all or nothing, 11x (1)),
    so this is a cut reading and not a site-wide disarm."""
    def groups(a, r):
        return [_colonnade("onramp", a, r, _FEET_X),
                _colonnade("onground", a, r, _RAMP_X1 + 30.0)]
    _a, _pm, _cs, _sol, rep, counts = _arm(law, groups, ramp_role="tunnel_ramp")
    st = FR.STATS["foot_rows"]
    assert st["cut"] == 1 and st["bare"] == 1, st
    assert st["rows"] == 9 and st["partial"] == 0, st
    assert counts["foot_rows"] == 18 and rep.foot_rows == 18
    fired = {v.gid: v.rows for v in FR.VERDICTS}
    assert fired["onramp"] == 0 and fired["onground"] == 9
