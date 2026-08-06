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


# ── (f) THE LAW / RIDE SPLIT (fix-3 lane A) ──────────────────────────────
#
# A runway-join anchor value is sampled off the EMITTED runway surface, and
# that surface's interior is a DEM-FOLLOW SEED (``runway_segments``:
# ``clamp(DEM, base ± min(RUNWAY_DEM_FOLLOW_LAW_BAND_M, ½·K·d²))``).  So an
# anchor value is LAW plus a ride of up to ±10 m, and two constant-DEM
# worlds read the same station up to 20 m apart (HECA measured: exactly
# +20.000 m on 71 of 75 stations of 05C/23C, plateau vs canyon).
#
# The error therefore has to answer the ONE question its reader has: does
# this shortfall survive with the ride removed?  If yes it is a real
# metric / cap / topology defect and needs an owner ruling; if no, nothing
# is wrong with the law and the anchor is simply carrying a seed
# (docs/RULINGS.md: the DEM is a SEED, never an authority).  HECA canyon
# reads 12.84 m of shortfall of which 6.00 m is ride — one number until
# this line existed.

def _profiled_case(budget_a, budget_b, ride_a=0.0, ride_b=0.0):
    """The two-anchor case with both anchors sitting on RUNWAY PROFILES,
    each anchored only at its two ends, so ``_anchor_law_values`` has a
    law baseline to interpolate.  ``ride_*`` is the DEM-follow ride the
    emitted surface carries above that baseline at the anchor's station."""
    layout, G = _two_anchor_case(budget_a, budget_b)
    G.runway_anchor = {0: 100.0 + ride_a, 1: 110.0 + ride_b}
    # The ride sits on a FREE (un-anchored) interior station — that is what
    # a DEM-follow seed IS.  Nothing here is flex-minted: a flexed station
    # is law (see ``test_law_baseline_includes_the_flex_applied_station``).
    layout._runway_redistributed_profiles = {
        "A": {"axis_a": (0.0, 0.0), "axis_d": (0.0, 10.0),
              "axis_len2": 100.0, "half_width_m": 20.0,
              "fractions": [0.0, 0.5, 1.0],
              "elevs": [100.0, 100.0 + ride_a, 100.0],
              "anchored": [True, False, True],
              "flex_minted": [False, False, False]},
        "B": {"axis_a": (100.0, 0.0), "axis_d": (0.0, 10.0),
              "axis_len2": 100.0, "half_width_m": 20.0,
              "fractions": [0.0, 0.5, 1.0],
              "elevs": [110.0, 110.0 + ride_b, 110.0],
              "anchored": [True, False, True],
              "flex_minted": [False, False, False]},
    }
    return layout, G


def _flexed_station_case(flexed_value, minted=True):
    """One runway profile whose MIDDLE station was moved by the flex —
    inserted ``anchored=True`` and tagged ``flex_minted``, exactly as
    ``apply_runway_flex`` does — with an anchor node sitting AT that
    station (pos (0, 5) ⇒ t = 0.5 on the axis below)."""
    layout = _FakeLayout()
    G = _FakeG({0: flexed_value}, {}, {0: (0.0, 5.0)})
    layout._runway_redistributed_profiles = {
        "A": {"axis_a": (0.0, 0.0), "axis_d": (0.0, 10.0),
              "axis_len2": 100.0, "half_width_m": 20.0,
              "fractions": [0.0, 0.5, 1.0],
              "elevs": [100.0, flexed_value, 100.0],
              "anchored": [True, True, True],
              "flex_minted": [False, bool(minted), False]},
    }
    return layout, G


def test_law_baseline_includes_the_flex_applied_station():
    """A flex-applied target is a LAWFUL HARD MOVE — owner ruling
    2026-08-05 ("Runway flex: the LAW is the only bound": anything within
    the law is legal by definition) and ``cycle4-anchor-law-spec.md``
    requirement 1, which names flex-applied targets as part of the law
    line.  The baseline must therefore READ the flexed station instead of
    the chord the flex started from.

    Excluding it (the ``e5c8443`` cut) books lawful flex displacement as
    "DEM-follow ride": measured at HECA canyon, −1.461 m and −2.735 m of
    "ride" in a world whose DEM is 10 000 m and can only push a value UP,
    which mis-classified two anchor pairs as LAW-ALONE-IS-FEASIBLE."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        _anchor_law_values)
    layout, G = _flexed_station_case(94.0)
    laws = _anchor_law_values(layout, G, {0: 94.0})
    assert laws[0] == pytest.approx(94.0), (
        "the flexed station IS the law line at its own station; 100.0 "
        "would be the pre-flex chord, i.e. 6 m of lawful flex reported "
        "back as DEM-follow ride")


def test_the_flex_provenance_no_longer_changes_the_law_line():
    """Same station, same value, with and without the ``flex_minted``
    tag: the law line is anchored ∪ flex-applied, so the provenance array
    cannot move it.  (It still governs ``flex_slack_at``'s bounding set —
    that is a different question, and the self-anchor lock it exists for
    is untouched.)"""
    from auto_patch.elevation_per_surface.building_feasibility import (
        _anchor_law_values)
    minted, G_m = _flexed_station_case(94.0, minted=True)
    plain, G_p = _flexed_station_case(94.0, minted=False)
    assert (_anchor_law_values(minted, G_m, {0: 94.0})
            == _anchor_law_values(plain, G_p, {0: 94.0}))


def test_a_shortfall_the_ride_created_is_named_as_ride():
    """LAW alone is feasible (10 m spread, 8 m + margin of budget); the
    ride is what inverts the band.  The message must say so."""
    layout, G = _profiled_case(6.0, 6.0, ride_a=-6.0)   # 12 m of budget
    spine_value_fields(layout, G)
    message = str(pytest.raises(
        BandInversionError,
        assert_no_final_band_inversion, layout, "TEST").value)
    assert "LAW half" in message
    assert "LAW ALONE IS FEASIBLE" in message
    assert "SEED, never an" in message
    assert "METRIC / CAP / TOPOLOGY" not in message


def test_a_shortfall_that_survives_the_ride_is_named_as_law():
    """Zero ride, and the anchors still contradict through the route: this
    is the class that needs a ruling, and the message must not let it be
    read as a DEM artefact."""
    layout, G = _profiled_case(4.0, 4.0)
    spine_value_fields(layout, G)
    message = str(pytest.raises(
        BandInversionError,
        assert_no_final_band_inversion, layout, "TEST").value)
    assert "LAW half" in message
    assert "METRIC / CAP / TOPOLOGY" in message
    assert "law shortfall +2.0000 m" in message


def test_the_split_is_report_only():
    """The law values are a REPORT: adding them must not move either
    field, or the diagnostic has become an authority itself."""
    plain, G_p = _two_anchor_case(4.0, 4.0)
    ceil_p, floor_p = spine_value_fields(plain, G_p)
    profiled, G_q = _profiled_case(4.0, 4.0)
    ceil_q, floor_q = spine_value_fields(profiled, G_q)
    assert ceil_p == ceil_q and floor_p == floor_q


def test_no_profiles_means_no_law_line_and_no_crash():
    """The pre-solve band runs before any profile exists; it must keep the
    behaviour it has always had."""
    layout, G = _two_anchor_case(4.0, 4.0)
    spine_value_fields(layout, G)
    message = str(pytest.raises(
        BandInversionError,
        assert_no_final_band_inversion, layout, "TEST").value)
    assert "LAW half" not in message
