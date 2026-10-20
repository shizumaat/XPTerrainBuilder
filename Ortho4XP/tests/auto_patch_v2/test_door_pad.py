"""Owner 2026-10-20 (#798): a sloping building's pad welded into the apron
is ONE level, its door line keeps the apron cap, and the apron's hard cap
rows elsewhere round it blend at up to the tunnel-ramp cap
(``constraints/door_pad``)."""
from __future__ import annotations

from auto_patch_v2.constraints import door_pad as DP
from auto_patch_v2.constraints.apron import GEN as APRON_GEN
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Flat, Source


def _pad(**kw):
    base = dict(ref="building1", group=(1, 2, 3), blend=frozenset({3, 7}),
                door=(0.0, 0.0), door_v=1, taxi_v=9, door_m=20.0, door_cap=0.0202)
    base.update(kw)
    return DP.DoorPad(**base)


def test_the_pad_is_one_level_and_its_door_line_keeps_the_cap(monkeypatch):
    monkeypatch.setattr(DP, "door_pads", lambda *a: [_pad()])
    rows = DP.door_pad_level(None, Law.for_airport("KASE"), None)
    flats = [r for r in rows if isinstance(r, Flat)]
    doors = [r for r in rows if isinstance(r, Diff)]
    assert [f.group for f in flats] == [(1, 2, 3)]
    assert [(d.a, d.b, d.cap, d.d) for d in doors] == [(1, 9, 0.0202, 20.0)]


def test_only_the_aprons_hard_rows_in_the_blend_are_relaxed(monkeypatch):
    law = Law.for_airport("KASE")
    top = float(law.tables.structures.tunnel.ramp_max_grade)
    monkeypatch.setattr(DP, "door_pads", lambda *a: [_pad()])
    apron = Source(APRON_GEN, "apron ring edge", ())
    taxi = Source("taxi_box", "taxi", ())
    rows = [Diff(3, 4, 0.0202, 10.0, apron),                 # blend foot: relaxed
            Diff(5, 6, 0.0202, 10.0, apron),                 # outside: kept
            Diff(3, 6, 0.01, 10.0, apron, soft="apron:1:0"),  # preference: kept
            Diff(7, 8, 0.0202, 10.0, taxi)]                  # taxi row: kept
    counts: dict = {}
    got = DP.relax_apron_caps(rows, None, law, None, counts)
    assert [r.cap for r in got] == [top, 0.0202, 0.01, 0.0202]
    assert counts[f"{DP.GEN}.apron_rows_relaxed"] == 1


def test_the_law_carries_the_door_corridor_and_the_ramp_cap():
    st = Law.for_airport("KASE").tables.structures
    assert st.placement.door_corridor_share == 0.5
    assert st.tunnel.ramp_max_grade == 0.1


def test_no_door_pad_on_stage_ones_map(monkeypatch):
    """Pads follow the solved airside (master 2026-10-20): while stage 1's
    map is derived no door-line pad exists, so it adds no row there."""
    monkeypatch.setattr(DP, "_derive", lambda *a: [_pad()])
    DP._MEMO.clear()
    with DP.stage_one():
        assert DP.door_pads(object(), None, None) == []
    DP._MEMO.clear()
    assert DP.door_pads(object(), None, None) == [_pad()]
    DP._MEMO.clear()


def test_stage_one_carries_mains_pads():
    """``stage_one_map.base_pad_map``: the classification's pad cells are
    replaced by main's (``Classification.base_pads``); nothing else moves."""
    import dataclasses as dc
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.pipeline.stage_one_map import base_pad_map

    def cell(i, role, ref, kind):
        return Cell(i, role, ref, ((0, 0), (1, 0), (1, 1)), (), None, None,
                    "airside", kind, {})
    apron, pad = cell(0, "apron", "pav1", "apron"), cell(1, "building", "building1", "building")
    main = cell(9, "building", "building1", "building")
    cl = Classification((apron, pad), (), {}, ())
    assert base_pad_map(cl) is None
    got = base_pad_map(dc.replace(cl, base_pads=(main,)))
    assert got.cells == (apron, main) and got.base_pads is None


def test_the_law_carries_the_blend_reach():
    assert Law.for_airport("KASE").tables.structures.placement.door_blend_reach_m == 60.0
