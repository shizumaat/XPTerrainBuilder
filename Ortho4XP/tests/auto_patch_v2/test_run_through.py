"""TWO CUTS ON ONE ROAD ARE ONE RUN-THROUGH (owner RULINGS 2026-11-03b Q340 a;
Q367 / Q369, #1717; ``planar/structure_overlap``).

MEASURED (capture lfpg6, main 0702f0e7b): the A1 bore under LFPG's H18 deck
(``tunnel:-21305+-13766+-21304+-160+-13765``) was refused both halves — its
corridor overlapped the H19 bore's to the north and the H17 bore's to the
south, OSM mapping the motorway as a separate tunnel under each deck — and
nothing was cut under runway 09R/27L.  KPHX's Terminal 4 road: R6 run 1's
east half refused against run 0's west half.
"""
from __future__ import annotations

import types

from auto_patch_v2.planar import structure_overlap as SO
from shapely.geometry import LineString, Polygon


def _cut(tid, mouth, end, climb_from=10.0, half=12.0):
    return types.SimpleNamespace(id=tid, axis=(mouth, end), half_width_m=half,
                                 climb_from_s=climb_from, source="osm")


def test_two_cuts_facing_along_one_road_pair_at_the_line_between_their_covers():
    a = _cut("a@0", (0.0, 0.0), (0.0, 300.0))
    b = _cut("b@1", (2.0, 200.0), (0.0, -100.0))
    pair = SO._run_pair(a, b)
    assert pair is not None
    ra, rb = pair
    assert ra.partner == "b@1" and rb.partner == "a@0"
    # covered ends at s = 10 on each: (0, 10) and ~(1.9, 190); the line halfway
    s_a = SO.run_stop_s(LineString(a.axis), ra, 0.3)
    s_b = SO.run_stop_s(LineString(b.axis), rb, 0.3)
    assert 99.0 < s_a < 100.0 and 99.0 < s_b < 100.0
    assert abs((s_a + s_b) - (200.0 - 0.6)) < 0.5        # a gap-wide strip between them


def test_cuts_on_two_roads_or_with_pavement_between_are_no_run():
    a = _cut("a@0", (0.0, 0.0), (0.0, 300.0))
    across = _cut("c@0", (0.0, 150.0), (300.0, 150.0))
    assert SO._run_pair(a, across) is None                  # crossing, not facing
    beside = _cut("d@1", (40.0, 200.0), (40.0, -100.0))
    assert SO._run_pair(a, beside) is None                  # another road 40 m over
    b = _cut("b@1", (0.0, 200.0), (0.0, -100.0))
    taxiway = Polygon([(-50, 90), (50, 90), (50, 110), (-50, 110)])
    assert SO._run_pair(a, b, taxiway) is None              # §34 (12) (3): pavement over it


def test_resolve_overlaps_keeps_both_and_records_the_run(monkeypatch):
    monkeypatch.setattr(SO, "overlap_yield", lambda *a, **k: ({}, {}))
    a = _cut("a@0", (0.0, 0.0), (0.0, 300.0))
    b = _cut("b@1", (0.0, 200.0), (0.0, -100.0))
    fa = LineString(a.axis).buffer(12.0)
    fb = LineString(b.axis).buffer(12.0)
    keep, refused, runs = [True, True], [], {}
    SO.resolve_overlaps([a, b], [fa, fb], keep, {}, {}, {}, {}, None, 0.6, 0.1, True,
                        refused, runs)
    assert keep == [True, True] and not refused and set(runs) == {"a@0", "b@1"}
    keep, refused = [True, True], []
    SO.resolve_overlaps([a, b], [fa, fb], keep, {}, {}, {}, {}, None, 0.6, 0.1, False,
                        refused, {})
    assert keep.count(True) == 1 and refused                # no re-plan left: the old refusal


def test_a_run_takes_one_floor_the_lowest_through_both_mouths_of_a_bore():
    """Owner 2026-11-03 (KPHX picture): a merged run has ONE floor, the
    lowest its members give; the other mouth of a bore whose half runs
    through is a member too (its floor meets the half's at the deck)."""
    def t(tid, z):
        return types.SimpleNamespace(id=tid, mouth_z=z, profile=())
    a0, a1, b0 = t("tunnel:-1@0", 104.5), t("tunnel:-1@1", 104.5), t("tunnel:-2@0", 102.0)
    r = SO._Run("tunnel:-2@0", (0.0, 1.0), 50.0, (0.0, 0.0))
    back = SO._Run("tunnel:-1@0", (0.0, 1.0), 50.0, (0.0, 99.0))
    runs = {"tunnel:-1@0": r, "tunnel:-2@0": back}
    out = SO.run_members([a0, a1, b0], [True, True, True], runs, {})
    assert set(out) == {"tunnel:-1@0", "tunnel:-1@1", "tunnel:-2@0"}
    assert all(abs(m.partner_floor - 102.0) < 1e-9 and m.lead == "tunnel:-2@0"
               for m in out.values())
    assert out["tunnel:-1@0"].level and not out["tunnel:-1@1"].level
    assert abs(SO.run_floor(104.5, out["tunnel:-1@1"]) - 102.0) < 1e-9
