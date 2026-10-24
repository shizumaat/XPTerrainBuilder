"""#1214 round 7 (owner, LFPG 1.0.424: "Check why it didn't get a second pad
like KMCI"): a held pad whose share of a connected group stands a storey
under the group's stand-side floor is the group's LOWER LEVEL, held at the
group's zero read on the airside -- never at its own pad's datum."""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.planar import group_low as GL
from shapely.geometry import box
from test_two_pads1214 import _airport, _wall


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


AIR = box(0.0, 100.0, 400.0, 130.0)       # the apron, north; the stand at (100, 101)
HALL = box(0.0, 0.0, 200.0, 100.0)        # the hall's pad: its walls on the apron
TRENCH = box(200.0, 0.0, 400.0, 100.0)    # the trench block: the storey under


def _group():
    hall = [_wall(60.0 + 10.0 * i, 99.5, 70.0 + 10.0 * i, 100.0, -0.04, 30) for i in range(8)]
    trench = [_wall(210.0, 10.0, 390.0, 90.0, -7.47, 120)]
    return hall + trench


def _floor_of(A, law):
    cache: dict = {}
    stands = [(100.0, 101.0)]
    return lambda ui: GL.group_floor(ui, A, lambda poly: AIR, stands, law,
                                     A.frame.entry(), cache)


def test_a_pad_a_storey_under_the_groups_floor_is_its_lower_level(law, tmp_path):
    """LFPG T2: ``building34`` holds only the trench storey's walls (y
    -7.47); the halls' stand-side walls read the group's floor at -0.04 on
    other pads -- ``plan_low`` reads one level, the group reads two."""
    A = _airport(_group(), tmp_path)
    got = GL.plan_group_low(TRENCH, AIR, A, law, 0.5, None, _floor_of(A, law))
    assert got is not None
    H, L, S, rec = got
    assert rec["witness"] == GL.GROUP_WITNESS
    assert rec["top_y"] == pytest.approx(-0.04)
    assert rec["y_feet"] == pytest.approx(-7.47)
    assert rec["y_lo"] == pytest.approx(-7.43)
    assert 0 < len(rec["air_xy"]) <= GL.WITNESS_MAX
    assert all(y == pytest.approx(-0.04) for y in rec["air_y"])
    assert L.distance(AIR) >= 3.0 - 1e-6 and H.area > 0.0 and S.area > 0.0


def test_the_pad_carrying_the_floor_is_never_lowered(law, tmp_path):
    A = _airport(_group(), tmp_path)
    assert GL.plan_group_low(HALL, AIR, A, law, 0.5, None, _floor_of(A, law)) is None


def test_no_stands_no_group_level(law, tmp_path):
    A = _airport(_group(), tmp_path)
    def none(ui):
        return GL.group_floor(ui, A, lambda poly: AIR, [], law, A.frame.entry(), {})
    assert GL.plan_group_low(TRENCH, AIR, A, law, 0.5, None, none) is None


class _Index:
    """A face index over a line of airside vertices ``100 + i`` at x = i:
    a point reads its nearest vertex, on the apron where ``x < 40``."""

    def role_at(self, p):
        return "apron" if 0.0 <= p[0] < 40.0 else "service_road"

    def terms_at(self, p):
        return ((100 + int(round(p[0])), 1.0),)


def test_the_level_is_held_at_the_airside_witnesses_not_the_pad_datum():
    """The tie: ``z_d - mean(airside z at the witnesses) = y_feet - mean(y)``
    (a witness off the airside reads its probe a metre inside); the other
    vertices of the level rigid to ``d``."""
    from auto_patch_v2.constraints.group_level import group_level_rows
    from auto_patch_v2.model.constraints import Source
    rec = {"air_xy": ((0.0, 0.0), (40.4, 0.0)), "air_y": (-0.04, -0.04), "y_feet": -7.47}
    rows = group_level_rows("b/p1", [1, 2], rec, Source("g", "r", ("low_level:b/p1",)),
                            (_Index(), frozenset({"apron"}), frozenset(range(100, 140))))
    w = dict(rows[0].terms[1:])
    assert rows[0].terms[0] == (1, 1.0) and w == {100: -0.5, 139: -0.5}
    assert rows[0].hi == pytest.approx(-7.43) and rows[1].hi == pytest.approx(7.43)
    assert len(rows) == 4 and {t[0] for t in rows[2].terms} == {1, 2}


def test_the_witnesses_are_the_feet_in_their_floors_band(law, tmp_path):
    """The object stage seats the group at the HIGHEST dense plane of
    ``airside z - y``; the mean over every stand-side foot read it a metre
    low at LFPG T2.  Only the feet in that plane's band (read on the DEM
    here, the airside being unsolved) tie the level."""
    import numpy as np
    A = _airport(_group(), tmp_path, ground=lambda x, y: 105.0 if x < 120.0 else 103.0)
    X = np.asarray([[100.0, 99.6], [110.0, 99.6], [130.0, 99.6], [140.0, 99.6]] * 10)
    Y = np.zeros(len(X))
    keep = GL._floor_band(A, X, Y, list(range(len(X))))
    assert keep and all(X[i, 0] < 120.0 for i in keep)


def test_between_the_stages_the_tie_becomes_a_pin_on_stage_1s_levels(monkeypatch):
    """A tie naming a vertex the door pads' blend released from stage 1 pulled
    a hall pad's apron 0.99 m; the pin at the mean read on stage 1's levels
    names none.  A vertex stage 1 did not level is not read."""
    import types

    from auto_patch_v2.constraints import group_level as G
    from auto_patch_v2.model.constraints import ConstraintSet, Source
    rec = {"kind": "low_level", "air_xy": tuple((float(i), 0.0) for i in range(4)),
           "air_y": (0.0,) * 4, "y_feet": -7.5}
    pm = types.SimpleNamespace(registries=types.SimpleNamespace(landings={"b/p1": rec}))
    index = (_Index(), frozenset({"apron"}), frozenset(range(100, 140)))
    monkeypatch.setattr(G, "witness_index", lambda planar, law: index)
    rows = G.group_level_rows("b/p1", [1, 2], rec, Source("g", "r", ("low_level:b/p1",)), index)
    levels = {100: 105.0, 101: 105.4, 102: 105.2}          # 103: released (stage 2's)
    cs, rep = G.group_level_rewrite(pm, None, ConstraintSet.from_rows(rows), levels)
    z0, n = rep["levels"]["b/p1"]
    assert n == 3 and z0 == pytest.approx(105.2)
    pins = [r for r in cs.linears if len(r.terms) == 1]
    assert len(pins) == 2 and pins[0].hi == pytest.approx(97.7)
    assert all(len(r.terms) <= 2 for r in cs.linears) and len(cs.linears) == 4
