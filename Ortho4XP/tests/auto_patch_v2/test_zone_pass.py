"""#770 THE AIRSIDE VERTEX SET IS A FUNCTION OF THE AIRSIDE ALONE (*airside
is king*; RULINGS 2026-10-15h (2)): a change of the adjacent-ground zone
widths moves 0 airside vertices (``planar/zone_pass``: the zones join the
airside's own pass-A0 line work, and a zone sliver carrying a zone node
grows no aircraft pavement — ``overlay.dissolve_sliver_zones``).

Measured on a CYXY capture before the fix: a 5 m runway / taxi zone-width
change gave the airside vertex set 71 gone / 70 new; after it 0 / 0."""
from __future__ import annotations

import importlib

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.overlay import build_arrangement
from auto_patch_v2.planar.ribbons import airside_vertex_set
from tests.auto_patch_v2.test_rwyzone15c import _FlatDem

Z = importlib.import_module("auto_patch_v2.planar.zones")


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="icao")


def _airport(law):
    frame = Frame("ZZZZ", origin=(39.9, -105.1), identity_dp=11)
    ll = (39.9, -105.1)
    rw = Runway("09/27", 45.0, 1,
                (RunwayEnd("09", (-1200.0, 0.0), ll, 0.0, 0.0, 1700.0, "fixture"),
                 RunwayEnd("27", (1200.0, 0.0), ll, 0.0, 0.0, 1700.0, "fixture")),
                4, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 1700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _FlatDem(), law.ruleset_key)


def _cells():
    # a runway, a parallel 180 m north, and two connectors — one square,
    # one OBLIQUE — that leave the runway's band at points no pavement
    # vertex stands on (the class the zone rings used to re-node)
    return (
        Cell(0, "runway", "09/27",
             ((-1200.0, -22.5), (1200.0, -22.5), (1200.0, 22.5), (-1200.0, 22.5)),
             (), 4, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "pav1",
             ((-1100.0, 170.0), (1100.0, 170.0), (1100.0, 193.0), (-1100.0, 193.0)),
             (), None, "D", "airside", "taxi", {}),
        Cell(2, "junction", "pav2",
             ((-611.5, 22.5), (-588.5, 22.5), (-588.5, 170.0), (-611.5, 170.0)),
             (), None, "D", "airside", "taxi", {}),
        Cell(3, "junction", "pav3",
             ((300.0, 22.5), (333.0, 22.5), (473.0, 170.0), (440.0, 170.0)),
             (), None, "D", "airside", "taxi", {}),
    )


def _airside(law, delta: float, monkeypatch) -> set:
    z2, off = Z.zone2_half_width_m, Z.runway_zone_edge_offset_m
    if delta:
        monkeypatch.setattr(Z, "zone2_half_width_m", lambda *a, **k: (
            None if z2(*a, **k) is None else z2(*a, **k) + delta))
        monkeypatch.setattr(Z, "runway_zone_edge_offset_m", lambda *a, **k: (
            None if off(*a, **k) is None else max(1.0, off(*a, **k) + delta)))
    arr = build_arrangement(_airport(law), Classification(_cells(), (), {}, ()), law)
    monkeypatch.undo()
    assert any(r.source == "zone" for _p, r in arr.faces)
    return airside_vertex_set(arr.faces, law)


@pytest.mark.parametrize("delta", [-5.0, -2.3, 4.1])
def test_a_zone_width_change_moves_no_airside_vertex(law, delta, monkeypatch):
    base = _airside(law, 0.0, monkeypatch)
    arm = _airside(law, delta, monkeypatch)
    assert base - arm == set() and arm - base == set(), (
        f"zone width {delta:+} m: {len(base - arm)} airside vertices gone, "
        f"{len(arm - base)} new")


def test_the_zone_pass_mints_no_node_on_the_airside(law):
    arr = build_arrangement(_airport(law), Classification(_cells(), (), {}, ()), law)
    pa = arr.registries.pad_airside
    assert pa.get("zone_renode_minted") == 0 and pa.get("zone_renode_deleted") == 0
