"""#2090 spec A4 / A5: the AGP group's datum is read ONCE between the
stages (``constraints/agp_level.datum_rewrite``): stage 1's triangle under
the governor's ground point; every row naming the group moves by the delta
and no other row; an unread governor leaves the delta 0."""
from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "src"))

from auto_patch_v2.constraints import agp_level as AL  # noqa: E402
from auto_patch_v2.model.agp_group import AgpGroup, AgpJoin, AgpMember  # noqa: E402
from auto_patch_v2.model.constraints import Band, ConstraintSet, Pin, Source  # noqa: E402

GID = "agp:dsf:obj1"


def _group(dem_gov=1638.71):
    gov = AgpMember("dsf:obj2", 2, "Objects/A.agp", (0.0, 0.0), (39.85, -104.67), 0.0, 0.0)
    fol = AgpMember("dsf:obj1", 1, "Objects/J.agp", (0.0, -600.0), (39.84, -104.67), 466.0,
                    -9.02)
    return AgpGroup(GID, (fol, gov), (AgpJoin("dsf:obj1", "dsf:obj2", 9.02, 2, 1, (0, 0)),),
                    "dsf:obj2", dem_gov, "", frozenset({"dsf:obj2"}))


class _FI:
    """A face index whose one triangle under the governor is vertices 0-2."""

    def __init__(self, *_a):
        pass

    def terms_at(self, p):
        return ((0, 0.5), (1, 0.25), (2, 0.25)) if abs(p[1]) < 1.0 else None


def _planar(stacks=()):
    return types.SimpleNamespace(agp_groups=(_group(),), bridge_stacks=stacks)


def _cs():
    src = Source("agp_level", "x", (GID,))
    other = Source("road_ramp", "y", ("vertex:7",))
    stack = Source("deck_stack", "z", ("stack:kept:dsf:obj9", "dsf:obj9"))
    return ConstraintSet(pins=(Pin(5, 1629.0, src),),
                         bands=(Band(3, 1629.0, 1629.5, src), Band(4, 10.0, 11.0, other),
                                Band(6, None, 1632.0, stack)))


def test_every_tagged_band_moves_by_delta_and_no_other(monkeypatch):
    monkeypatch.setattr("auto_patch_v2.constraints.face_index.FaceIndex", _FI)
    st = types.SimpleNamespace(id="stack:kept:dsf:obj9", datum_group=GID)
    levels = {0: 1638.5, 1: 1638.5, 2: 1638.5}
    cs, rep = AL.datum_rewrite(_planar((st,)), None, _cs(), levels)
    r = rep["groups"][GID]
    assert r["z_gov"] == pytest.approx(1638.5) and r["delta"] == pytest.approx(-0.21)
    b = {x.v: x for x in cs.bands}
    assert (b[3].lo, b[3].hi) == pytest.approx((1628.79, 1629.29))
    assert (b[4].lo, b[4].hi) == (10.0, 11.0)                 # untagged: untouched
    assert b[6].hi == pytest.approx(1631.79) and b[6].lo is None   # the joined stack's
    assert cs.pins[0].z == pytest.approx(1628.79)
    assert r["moved"] == 3
    fz = AL.final_zero(_planar().agp_groups[0], rep)
    assert fz["datum"]["dsf:obj1"] == pytest.approx(1638.71 - 9.02 - 0.21)
    assert AL.stack_zero(types.SimpleNamespace(zero_z=1631.0, datum_group=GID),
                         _planar().agp_groups, rep) == pytest.approx(1630.79)


def test_an_unread_governor_leaves_delta_zero(monkeypatch):
    monkeypatch.setattr("auto_patch_v2.constraints.face_index.FaceIndex", _FI)
    cs0 = _cs()
    # vertex 2 is not stage 1's: the triangle is not all stage 1's
    cs, rep = AL.datum_rewrite(_planar(), None, cs0, {0: 1638.5, 1: 1638.5})
    r = rep["groups"][GID]
    assert r["unread"] and r["delta"] == 0.0 and r["why"].startswith("agp_datum_unread")
    assert cs is cs0


def test_published_records_carry_the_datum_and_a7_flags(monkeypatch):
    monkeypatch.setattr("auto_patch_v2.constraints.face_index.FaceIndex", _FI)
    _cs1, rep = AL.datum_rewrite(_planar(), None, _cs(), {0: 1638.5, 1: 1638.5, 2: 1638.5})
    (g,) = AL.published_groups(_planar().agp_groups, rep)
    assert g["governor"] == "dsf:obj2" and g["z_gov"] == pytest.approx(1638.5)
    m = {x["row"]: x for x in g["members"]}
    assert m["dsf:obj2"]["airside"] and not m["dsf:obj1"]["airside"]
    assert m["dsf:obj1"]["datum"] == pytest.approx(1629.48)
    assert g["joins"][0]["votes"] == 2
    assert all(not (isinstance(v, float) and math.isinf(v)) for v in m["dsf:obj1"].values())


def test_no_governed_group_returns_the_set_unchanged():
    cs0 = _cs()
    pm = types.SimpleNamespace(agp_groups=(), bridge_stacks=())
    assert AL.datum_rewrite(pm, None, cs0, {})[0] is cs0


def test_the_sidecar_registers_the_published_groups():
    from auto_patch_v2.emit import osm_adapter as OA
    assert "agp_groups" in OA.SIDECAR_KEYS


def test_b8_a_group_seeded_ramp_target_and_ceiling_move_by_delta_never_under_floor(
        monkeypatch):
    """#2090 amendment B′ B8 (census row 13): a governed vertex on a ramp a
    datum-group stack's deck end seeds (``PlanarMap.road_ramp_group``) has
    its §37 (6) target moved to ``max(floor, t + delta)`` and its ceiling to
    that plus ``visual_m``; another vertex's rows are untouched."""
    from auto_patch_v2.constraints.road_ramp import GEN, RULING, RULING_CEILING
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import Linear
    monkeypatch.setattr("auto_patch_v2.constraints.face_index.FaceIndex", _FI)
    law = Law.load()
    vis = float(law.tables.emit.cockpit.visual_m)

    def rows(v, t):
        return (Linear(((v, 1.0),), t, t, Source(GEN, RULING, (f"vertex:{v}", "r"))),
                Band(v, None, t + vis, Source(GEN, RULING_CEILING, (f"vertex:{v}", "r"))))
    (l7, c7), (l8, c8), (l9, c9) = rows(7, 1630.0), rows(8, 1631.6), rows(9, 1633.0)
    cs0 = ConstraintSet(linears=(l7, l8, l9), bands=(c7, c8, c9))
    pm = types.SimpleNamespace(agp_groups=(_group(),), bridge_stacks=(),
                               road_ramp_group={7: (GID, 1629.0), 8: (GID, 1631.5)})
    cs, rep = AL.datum_rewrite(pm, law, cs0, {0: 1638.5, 1: 1638.5, 2: 1638.5})
    lin = {r.terms[0][0]: r for r in cs.linears}
    cap = {r.v: r for r in cs.bands}
    assert lin[7].lo == lin[7].hi == pytest.approx(1629.79)
    assert cap[7].hi == pytest.approx(1629.79 + vis)
    assert lin[8].lo == pytest.approx(1631.5) and cap[8].hi == pytest.approx(1631.5 + vis)
    assert lin[9] is l9 and cap[9] is c9                       # not group-seeded
    assert rep["groups"][GID]["ramp_moved"] == 2
    assert "agp_ramp_foot_m" not in rep["groups"][GID]          # delta < 0
