"""Twins for the DEM-LAST SEAT BIAS (owner ruling ``docs/RULINGS.md``
2026-08-25 second ruling; spec
``docs/specs/apron-chord-anchor-target-spec.md`` §2).

"Where the law leaves a choice of level, ANCHOR-CONSISTENCY is preferred
over DEM proximity; DEM is the LAST tiebreaker."  The seat inside a pad's
lawful band interval biases toward the level minimising chord residuals
against its OWN §1 anchor neighbourhood — the pads and centerlines its ring
vertices chord to under ``grade_graph.nearest_spine_pairs``.

The spec's twins (§2 "Twins"):

  (a) a seat inside its interval moves toward the RESIDUAL-MINIMISING
      level, not toward DEM;
  (b) an UNANCHORED pad is byte-identical — no §1 chord reaches it, so its
      DEM soft-seed stands;
  (c) ``O4_DEM_LAST_SEAT_BIAS=0`` ⇒ byte-identical to §1-only (nothing is
      captured, nothing moves);
  (d) the §2 seat NEVER leaves the pad's lawful band interval — the band
      stays the feasibility authority (the v4 lesson: a scaffold-derived
      seat source put 22 of 22 CYXY pads down a mean 9.07 m).

GATE STATE: ``O4_DEM_LAST_SEAT_BIAS`` is DEFAULT OFF (2026-08-25 lead
ruling, after the two-attempt acceptance miss — HECA 1,972 against the §1
baseline of 1,735, SPJC 440 against 175).  The mechanism, its report and
these twins are intact behind it and ``=1`` still enables it; the twins
therefore drive the functions DIRECTLY rather than through the gate, so
they keep testing the law whatever the default is.  The open question —
whether a pad-kind anchor, being another pad's provisional seat chosen in
the same pass, belongs in the neighbourhood at all — is RECORDED for the
next design round and is deliberately not implemented here.

Synthetic and headless: the bias is interval arithmetic over the anchor
chords the ONE enumeration published, so the twins construct those chords
directly rather than building an airport.  ``elev`` is a plain list — the
solve's own array at the post-phase-A slot.
"""

import pytest

from auto_patch.elevation_per_surface.node_space import store_of
from auto_patch.elevation_per_surface.route_profile import (
    pad_seat_consistency as psc)


class _Layout:
    def __init__(self, units):
        self._pad_seat_consistency_units = units


def _unit(*, level, lo, hi, nodes=(10, 11), keys=("k10", "k11"),
          ref="building70", records=()):
    return {"ref": ref, "refs": [ref], "level": float(level),
            "lo": float(lo), "hi": float(hi),
            "records": list(records), "nodes": list(nodes),
            "keys": list(keys)}


def _seed_boxes(layout, keys, lo, hi):
    boxes = store_of(layout).open_map("seat_boxes", "interval", reset=True)
    for k in keys:
        boxes[k] = (float(lo), float(hi))
    return boxes


def _apply(layout, elev, seats, chords, **kw):
    return psc.apply_pad_seat_consistency(
        layout, elev, seats, len(elev), anchor_chords=chords, **kw)


# ── the neighbourhood comes from the ONE enumeration ─────────────────

def test_the_neighbourhood_is_the_units_own_anchor_chords():
    """§2.1: "the pads/centerlines its ring vertices now chord to".  A
    chord with one end on the unit contributes its OTHER end as an anchor;
    a chord with BOTH ends inside the unit carries no information about
    where the unit's one flat level should be and is dropped."""
    chords = [(10, 40, 1.2, "spine"),      # unit -> centerline
              (11, 41, 0.8, "pad"),        # unit -> another pad
              (10, 11, 0.5, "pad"),        # inside the unit
              (60, 61, 9.9, "spine")]      # nothing to do with the unit
    recs = psc.anchor_neighborhood_records((10, 11), chords)
    assert [r["anchor_nodes"] for r in recs] == [[40], [41]]
    assert [r["budget_m"] for r in recs] == [1.2, 0.8]
    assert [r["kind"] for r in recs] == ["spine", "pad"]


def test_the_chords_own_budget_is_the_half_width():
    """The budget is the chord's own ``cap x dist``, minted where the chord
    was — never re-derived here and never a literal."""
    rec = psc.anchor_neighborhood_records((10,), [(10, 40, 1.75, "pad")])[0]
    assert psc.record_budget_m(rec) == pytest.approx(1.75)
    # …and the frontage record shape still reads exactly as before.
    assert psc.record_budget_m({"route_m": 0.5, "off_mask_m": 0.0}) == (
        pytest.approx(0.5))


# ── twin (a): anchor-consistency first, DEM last ─────────────────────

def test_the_seat_moves_to_the_residual_minimising_level_not_to_dem():
    """Twin (a).  The band box is [90, 110] and the DEM-biased seat sits at
    91.0.  Two anchors at 100.0 and 101.0 with 0.5 m budgets admit
    [100.5, 100.5] ∩ [99.5, 101.5] — the seat must climb to the
    residual-minimising level, ~100.5, and NOT stay at its DEM choice."""
    units = [_unit(level=91.0, lo=90.0, hi=110.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 50
    elev[40], elev[41] = 100.0, 101.0
    seats = {10: 91.0, 11: 91.0}
    rep = _apply(layout, elev, seats,
                 [(10, 40, 0.5, "spine"), (11, 41, 0.5, "pad")])
    assert rep["dem_last"] is True
    assert rep["narrowed"] == 1 and rep["moved"] == 1
    assert seats[10] == pytest.approx(100.5)
    assert seats[11] == pytest.approx(100.5)
    # the residual it removed is reported, and none is left
    assert rep["worst_residual_left_m"] == pytest.approx(0.0)
    assert rep["residual_cut_m"] > 0.0


def test_dem_is_the_last_tiebreaker_inside_the_zero_residual_set():
    """The other half of the ruling: among levels of EQUAL residual the
    DEM-biased band seat wins.  One anchor at 100.0 with a 5 m budget makes
    every level in [95, 105] lawful; the seat is already at 97.0 and must
    not move at all."""
    units = [_unit(level=97.0, lo=90.0, hi=110.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 50
    elev[40] = 100.0
    seats = {10: 97.0, 11: 97.0}
    rep = _apply(layout, elev, seats, [(10, 40, 5.0, "spine")])
    assert rep["moved"] == 0
    assert seats[10] == pytest.approx(97.0)


def test_the_residual_function_is_the_priced_excess():
    """The quantity minimised is the excess the census would price on each
    chord: zero while lawful, then metre for metre."""
    elev = [0.0] * 50
    elev[40] = 100.0
    recs = psc.anchor_neighborhood_records((10,), [(10, 40, 1.0, "spine")])
    assert psc.chord_residual_m(100.0, recs, elev, 50) == pytest.approx(0.0)
    assert psc.chord_residual_m(101.0, recs, elev, 50) == pytest.approx(0.0)
    assert psc.chord_residual_m(103.5, recs, elev, 50) == pytest.approx(2.5)


def test_contradictory_anchors_seat_at_the_residual_minimum():
    """Where the frontage-subset version had to KEEP the seat (no level
    satisfies every anchor, and picking one would be a silent pick), a
    residual MINIMUM is well defined and is not a pick.  Anchors at 100 and
    110 with 1 m budgets: the minimum is the whole segment between them,
    and the DEM tiebreak keeps the seat's own side of it."""
    units = [_unit(level=99.0, lo=90.0, hi=120.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 120.0)
    elev = [0.0] * 50
    elev[40], elev[41] = 100.0, 110.0
    seats = {10: 99.0, 11: 99.0}
    rep = _apply(layout, elev, seats,
                 [(10, 40, 1.0, "spine"), (11, 41, 1.0, "spine")])
    assert rep["inconsistent"] == 1
    assert rep["narrowed"] == 1
    assert seats[10] == pytest.approx(101.0)      # the near edge of the min
    assert rep["worst_residual_left_m"] == pytest.approx(8.0)
    row = rep["inconsistents"][0]
    assert row["dem_last"] is True
    assert row["seat_now_m"] == pytest.approx(101.0)


# ── twin (b): an unanchored pad is untouched ─────────────────────────

def test_an_unanchored_pad_keeps_its_dem_soft_seed():
    """Twin (b) / §2.1's own clause: "unanchored regions keep their DEM
    soft-seed".  No published chord touches this unit, so nothing narrows
    and the seat stays byte-identically where the band put it."""
    units = [_unit(level=91.0, lo=90.0, hi=110.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 50
    elev[40] = 100.0
    seats = {10: 91.0, 11: 91.0}
    rep = _apply(layout, elev, seats, [(60, 61, 1.0, "spine")])
    assert rep["no_provenance"] == 1
    assert rep["narrowed"] == 0 and rep["moved"] == 0
    assert seats == {10: 91.0, 11: 91.0}


def test_an_anchor_outside_the_node_list_is_never_invented():
    """An anchor index outside ``[0, n)`` is skipped and counted, never
    mapped into this node space (canonical-identity law)."""
    units = [_unit(level=91.0, lo=90.0, hi=110.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 12
    seats = {10: 91.0, 11: 91.0}
    rep = _apply(layout, elev, seats, [(10, 999, 1.0, "spine")])
    assert rep["no_anchor"] == 1 and rep["skipped_anchors"] == 1
    assert seats == {10: 91.0, 11: 91.0}


# ── twin (c): the kill switch ────────────────────────────────────────

def test_flag_off_is_byte_identical_to_section_one_only(monkeypatch):
    """Twin (c).  With ``O4_DEM_LAST_SEAT_BIAS=0`` and the frontage-subset
    flag off (its default), NOTHING is captured and nothing runs — the
    build is §1-only."""
    monkeypatch.setenv(psc.ENV_FLAG_DEM_LAST, "0")
    monkeypatch.delenv(psc.ENV_FLAG, raising=False)
    assert psc.dem_last_seat_bias_enabled() is False
    assert psc.pad_seat_consistency_enabled() is False
    assert psc.seat_provenance_wanted() is False
    monkeypatch.setenv(psc.ENV_FLAG_DEM_LAST, "1")
    assert psc.dem_last_seat_bias_enabled() is True
    assert psc.seat_provenance_wanted() is True


def test_both_defaults_are_off_and_the_two_flags_stay_separate(monkeypatch):
    """§2.2: the gates mean different things, and NEITHER is on by
    default.

    §2's default was flipped to OFF by the 2026-08-25 lead ruling after
    the two-attempt acceptance miss (HECA 1,972 against the §1 baseline
    1,735; SPJC 440 against 175) — the same disposition the frontage-
    subset version got, and for the same reason.  An unset environment
    must therefore leave BOTH mechanisms off and capture nothing, which is
    §1-only; and turning one on must never turn the other on."""
    monkeypatch.delenv(psc.ENV_FLAG_DEM_LAST, raising=False)
    monkeypatch.delenv(psc.ENV_FLAG, raising=False)
    assert psc.dem_last_seat_bias_enabled() is False
    assert psc.pad_seat_consistency_enabled() is False
    assert psc.seat_provenance_wanted() is False
    # …and each flag still enables ONLY its own mechanism.
    monkeypatch.setenv(psc.ENV_FLAG_DEM_LAST, "1")
    assert psc.dem_last_seat_bias_enabled() is True
    assert psc.pad_seat_consistency_enabled() is False
    monkeypatch.delenv(psc.ENV_FLAG_DEM_LAST, raising=False)
    monkeypatch.setenv(psc.ENV_FLAG, "1")
    assert psc.pad_seat_consistency_enabled() is True
    assert psc.dem_last_seat_bias_enabled() is False


def test_no_anchor_chords_argument_runs_the_frontage_version_unchanged():
    """``anchor_chords=None`` is the pre-§2 call, and it still narrows
    against the FRONTAGE records exactly as authored."""
    rec = {"anchor_nodes": [40], "route_m": 0.5, "off_mask_m": 0.0}
    units = [_unit(level=91.0, lo=90.0, hi=110.0, records=[rec])]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 50
    elev[40] = 100.0
    seats = {10: 91.0, 11: 91.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev))
    assert rep["dem_last"] is False
    assert seats[10] == pytest.approx(99.5)       # clamped into [99.5, 100.5]


# ── twin (d): the band is still the feasibility authority ────────────

def test_the_seat_never_leaves_its_band_box():
    """Twin (d), the v4 lesson made structural.  The anchors sit far ABOVE
    the pad's band; the residual-minimising level is therefore the box's
    own ceiling, and the seat stops there rather than following them."""
    units = [_unit(level=91.0, lo=90.0, hi=95.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 95.0)
    elev = [0.0] * 50
    elev[40] = 300.0
    seats = {10: 91.0, 11: 91.0}
    rep = _apply(layout, elev, seats, [(10, 40, 1.0, "spine")])
    assert seats[10] == pytest.approx(95.0)
    assert 90.0 <= seats[10] <= 95.0
    assert rep["worst_residual_left_m"] == pytest.approx(204.0)


def test_the_search_is_confined_to_the_box_from_below_too():
    """The same bound on the other side: anchors far BELOW the band cannot
    pull the seat under its floor."""
    lvl, resid, _n = psc.dem_last_seat_level(
        91.0, 90.0, 95.0,
        psc.anchor_neighborhood_records((10,), [(10, 40, 1.0, "spine")]),
        [0.0] * 41, 41)
    assert lvl == pytest.approx(90.0)
    assert resid == pytest.approx(89.0)


def test_the_box_is_widened_to_hold_a_resting_seat():
    """``build_building_seats``' own construction: an uncoupled seat may
    rest below its ``lo``, and the box must never move a resting seat.  The
    §2 search uses the WIDENED box, so such a seat is still reachable."""
    units = [_unit(level=88.0, lo=90.0, hi=95.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 88.0, 95.0)
    elev = [0.0] * 50
    elev[40] = 88.0
    seats = {10: 88.0, 11: 88.0}
    rep = _apply(layout, elev, seats, [(10, 40, 0.0, "spine")])
    assert seats[10] == pytest.approx(88.0)
    assert rep["moved"] == 0


# ── the report ───────────────────────────────────────────────────────

def test_the_report_names_the_mechanism_that_ran():
    """The two mechanisms share a chassis, so a reader must be able to tell
    from the report WHICH one moved a seat."""
    units = [_unit(level=91.0, lo=90.0, hi=110.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    elev = [0.0] * 50
    elev[40] = 100.0
    rep = _apply(layout, elev, {10: 91.0, 11: 91.0},
                 [(10, 40, 0.5, "spine")])
    text = psc.format_report("HECA", rep)
    assert "[dem-last-seat]" in text
    assert "anchor neighbourhood" in text
    assert "[pad-seat-consistency]" not in text


# ── the solved-anchor filter (arm-2 correction) ──────────────────────

def test_an_unsolved_anchor_is_dropped_not_measured_against():
    """At this slot ``elev`` holds a solved value only at phase A's own set
    and at the seats it stamped; everywhere else it is still the DEM SEED.
    A residual against a seed is a residual against DEM — the quantity this
    ruling demotes to LAST — so such a chord is dropped and COUNTED, never
    silently folded into the minimisation."""
    chords = [(10, 40, 1.0, "spine"), (11, 41, 1.0, "pad")]
    recs = psc.anchor_neighborhood_records((10, 11), chords, {40})
    assert [r.get("anchor_nodes") for r in recs] == [[40], []]
    assert recs[1]["unsolved"] is True
    # …and with no filter supplied, nothing is dropped (the frontage path
    # and the twins above are unaffected).
    assert all("unsolved" not in r
               for r in psc.anchor_neighborhood_records((10, 11), chords))


def test_the_filter_changes_which_level_wins():
    """The correction is load-bearing, not cosmetic: an un-solved anchor
    metres away moves the minimiser, and dropping it puts the seat back
    where the SOLVED corridor wants it."""
    units = [_unit(level=100.0, lo=90.0, hi=130.0)]
    layout = _Layout(units)
    _seed_boxes(layout, ("k10", "k11"), 90.0, 130.0)
    elev = [0.0] * 50
    elev[40] = 100.0            # solved corridor
    elev[41] = 128.0            # still the DEM seed
    seats = {10: 100.0, 11: 100.0}
    rep = _apply(layout, elev, seats,
                 [(10, 40, 0.5, "spine"), (11, 41, 0.5, "pad")],
                 solved_nodes={40})
    assert rep["unsolved_anchors"] == 1
    assert rep["moved"] == 0
    assert seats[10] == pytest.approx(100.0)
