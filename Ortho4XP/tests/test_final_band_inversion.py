"""THE LOUD ERROR — the twin of ``kill-half-spec.md`` §3.

Owner law (docs/RULINGS.md, feasibility-is-guaranteed, ESCALATED
2026-08-01): a real airport with real thresholds HAS a lawful surface, so
a FINAL reach band the anchors contradict through is a law defect to
attribute — a wrong metric, a wrong anchor value, a wrong role/cap or a
false topology — never a region to quarantine.  §2 deleted the quarantine
that used to paint over it; this is what replaced it.

What is pinned here:

  (a) NON-VACUITY — ``spine_value_fields`` RECORDS its inversions on the
      layout every time it runs.  Without this the acceptance claim ("the
      error fires zero times on the battery") could be satisfied by a
      recorder that never ran;
  (b) the check RAISES on a material inversion (> 0.01 m) and the message
      names the node, its floor, its ceiling, the deficit AND both route
      distances — the four things an attribution needs;
  (c) it PASSES an inversion at or below the 0.01 m materiality floor and
      returns the residual count (the convergence guards' PASS-with-
      residual, never iterated on);
  (d) the error type is not swallowed by the pipeline's geometry guards;
  (e) the recorder is write-only: nothing about the returned fields
      changes when it runs.

MEASURED at the new defaults when this landed (2026-08-04, 5 builds, no
``O4_`` var set): fires ZERO times — SPLP/CYXY/SPJC/HECA carry no
inverted node at all and HEAZ carries 2 at ≤ 0.01 m, reported
PASS-with-residual.
"""
import pytest

from auto_patch.elevation_per_surface.building_feasibility import (
    BandInversionError, FINAL_BAND_INVERSION_TOL_M,
    assert_no_final_band_inversion, spine_value_fields)


class _FakeG:
    """The three attributes ``spine_value_fields`` reads."""

    def __init__(self, anchors, adj, pos):
        self.runway_anchor = anchors
        self.spine_adj = adj
        self.pos = pos
        self.service_spine_pairs = set()


class _FakeLayout:
    pass


def _two_anchor_case(budget_a, budget_b):
    """Node 2 sits between two runway anchors: node 0 at 100 m and node 1
    at 110 m.  Its ceiling is ``100 + budget_a`` (cheapest route from the
    low anchor) and its floor is ``110 − budget_b``; make the two budgets
    small and the floor lands ABOVE the ceiling by
    ``10 − budget_a − budget_b`` metres."""
    anchors = {0: 100.0, 1: 110.0}
    adj = {0: [(2, budget_a)], 1: [(2, budget_b)],
           2: [(0, budget_a), (1, budget_b)]}
    pos = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (50.0, 0.0)}
    return _FakeLayout(), _FakeG(anchors, adj, pos)


# ── (a) non-vacuity ──────────────────────────────────────────────────────

def test_the_recorder_runs_on_every_field_build():
    layout, G = _two_anchor_case(4.0, 4.0)
    spine_value_fields(layout, G)
    assert hasattr(layout, "_final_band_inversions"), (
        "the acceptance claim is vacuous unless the recorder actually ran")
    assert layout._final_band_node_count == 3


def test_a_feasible_band_records_no_rows():
    layout, G = _two_anchor_case(20.0, 20.0)     # 40 m of budget for 10 m
    spine_value_fields(layout, G)
    assert layout._final_band_inversions == []
    assert assert_no_final_band_inversion(layout, "TEST") == 0


# ── (b) the error, and what it must name ─────────────────────────────────

def test_a_material_inversion_is_a_build_error():
    layout, G = _two_anchor_case(4.0, 4.0)       # inverted by 2.0 m
    ceiling, floor = spine_value_fields(layout, G)
    assert floor[2] - ceiling[2] == pytest.approx(2.0)
    with pytest.raises(BandInversionError) as caught:
        assert_no_final_band_inversion(layout, "TEST")
    message = str(caught.value)
    assert "TEST" in message and "node 2" in message
    assert "104.000" in message and "106.000" in message   # ceiling, floor
    assert "2.0000 m" in message                           # the deficit
    assert "route:" in message and "4.00 m of budget" in message
    # and it points at the law, not at a knob to turn
    assert "quarantine" in message


def test_the_contradicting_ANCHORS_are_named_too():
    """★ The anchors are IN the output, so they are checked like any other
    node — and an anchor pair that contradicts through the route graph is
    exactly the "wrong anchor value" defect class this error exists to
    name (docs/RULINGS.md: attribute the metric, the anchor value, the
    role/cap or the topology).  Quarantining the middle node while leaving
    the two authorities unnamed is what the deleted machinery did."""
    layout, G = _two_anchor_case(4.0, 4.0)
    spine_value_fields(layout, G)
    rows = layout._final_band_inversions
    assert {r["node"] for r in rows} == {0, 1, 2}
    deficits = [r["deficit_m"] for r in rows]
    assert deficits == sorted(deficits, reverse=True), "worst deficit first"
    message = str(pytest.raises(
        BandInversionError,
        assert_no_final_band_inversion, layout, "TEST").value)
    for node in (0, 1, 2):
        assert f"node {node}" in message
    # each row carries its OWN route distances, not a shared number
    assert "0.00 m of budget" in message and "8.00 m" in message


# ── (c) the materiality floor ────────────────────────────────────────────

def test_a_sub_materiality_inversion_passes_with_residual():
    # HALF the floor, deliberately: an inversion built to land EXACTLY on
    # 0.01 m lands on either side of it by one float ulp depending on the
    # route, which would make this test's verdict a rounding accident
    # rather than a statement about the law.
    deficit = 0.5 * FINAL_BAND_INVERSION_TOL_M
    half = 5.0 - 0.5 * deficit
    layout, G = _two_anchor_case(half, half)
    spine_value_fields(layout, G)
    assert layout._final_band_inversions, "the row is still RECORDED"
    assert (layout._final_band_inversions[0]["deficit_m"]
            == pytest.approx(deficit))
    # below the floor is a pass, and the residual COUNT comes back so the
    # caller can log it (production logs "N sub-materiality inversion(s),
    # PASS-with-residual")
    assert assert_no_final_band_inversion(layout, "TEST") == 3


def test_just_over_the_floor_still_raises():
    half = 5.0 - 0.5 * (FINAL_BAND_INVERSION_TOL_M + 0.002)
    layout, G = _two_anchor_case(half, half)
    spine_value_fields(layout, G)
    with pytest.raises(BandInversionError):
        assert_no_final_band_inversion(layout, "TEST")


# ── (d) it cannot be swallowed by the pipeline's geometry guards ─────────

def test_the_error_is_not_a_geometry_exception():
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _snapshot_geom_exceptions)
    assert not issubclass(BandInversionError, _snapshot_geom_exceptions())
    assert issubclass(BandInversionError, RuntimeError)


# ── (e) the recorder is write-only ───────────────────────────────────────

def test_recording_does_not_move_the_fields():
    layout_a, G_a = _two_anchor_case(4.0, 4.0)
    ceiling_a, floor_a = spine_value_fields(layout_a, G_a)
    # a second, independent build of the same graph must agree exactly
    layout_b, G_b = _two_anchor_case(4.0, 4.0)
    ceiling_b, floor_b = spine_value_fields(layout_b, G_b)
    assert ceiling_a == ceiling_b and floor_a == floor_b
    assert (layout_a._final_band_inversions
            == layout_b._final_band_inversions)


def test_no_layout_attribute_is_required():
    """A caller that hands in a layout with no slot for the record (a
    probe, a synthetic object) must not crash the field build."""
    class _Slotted:
        __slots__ = ()

    _layout, G = _two_anchor_case(4.0, 4.0)
    ceiling, floor = spine_value_fields(_Slotted(), G)
    assert ceiling[2] == pytest.approx(104.0)
    assert floor[2] == pytest.approx(106.0)
