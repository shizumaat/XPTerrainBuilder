"""Twins for the PAD-SEAT CONSISTENCY INTERVAL.

Spec: ``docs/specs/pad-seat-consistency-spec.md`` (twins (a)-(e) of its
"Twins" section, plus its implementation ruling of 2026-08-25).

Synthetic and headless by construction: the narrowing is pure interval
arithmetic over the frontage provenance the seat pass captured, so every
twin below constructs the provenance directly instead of building an
airport.  ``elev`` is a plain list — the solve's own array at the
post-phase-A slot.
"""

import pytest

from auto_patch.config import APRON_MAX_GRADE
from auto_patch.elevation_per_surface.node_space import store_of
from auto_patch.elevation_per_surface.route_profile import (
    pad_seat_consistency as psc)


class _Layout:
    """The two attributes the narrowing touches: the node-space store (for
    ``seat_boxes``) and the provenance the seat pass published."""

    def __init__(self, units):
        self._pad_seat_consistency_units = units


def _rec(anchor, route_m, *, off_mask_m=0.0, floor=0.0, ceiling=0.0,
         seat_m=0.0):
    """One frontage band record in the shape ``_frontage_band_records``
    emits (``anchor_nodes`` / ``route_m`` / ``off_mask_m`` come straight
    from ``band.attachment_at``)."""
    return {"pad": "buildingX", "ll": [0.0, 0.0],
            "floor": float(floor), "ceiling": float(ceiling),
            "anchor_nodes": list(anchor), "route_m": float(route_m),
            "off_mask_m": float(off_mask_m),
            "floor_at_anchor": float(floor), "ceiling_at_anchor": float(ceiling),
            "seat_m": float(seat_m), "seat_final_m": float(seat_m)}


def _unit(records, *, level, lo, hi, nodes=(10, 11), keys=("k10", "k11"),
          ref="building70"):
    return {"ref": ref, "refs": [ref], "level": float(level),
            "lo": float(lo), "hi": float(hi),
            "records": list(records), "nodes": list(nodes),
            "keys": list(keys)}


def _seed_boxes(layout, keys, lo, hi):
    boxes = store_of(layout).open_map("seat_boxes", "interval", reset=True)
    for k in keys:
        boxes[k] = (float(lo), float(hi))
    return boxes


# ── the budget's units (the measured correction to the spec's wording) ──

def test_budget_is_the_bands_own_cap_weighted_leg():
    """``route_m`` IS ``cap x route_distance`` already — the band's grid
    edges are weighted ``cap x step`` (``raster_reach_band._grid_edges``),
    so the half-width is the leg itself plus the band's own off-mask
    slack at ``APRON_MAX_GRADE``."""
    assert psc.record_budget_m(_rec([1], 3.0)) == pytest.approx(3.0)
    assert psc.record_budget_m(
        _rec([1], 3.0, off_mask_m=4.0)) == pytest.approx(
            3.0 + APRON_MAX_GRADE * 4.0)
    assert psc.record_budget_m({"pad": "x"}) is None


# ── twin (a): the seat interval IS the intersection ─────────────────────

def test_twin_a_interval_is_the_intersection():
    elev = [0.0] * 5
    elev[3] = 100.0
    lo, hi, used, binding = psc.consistency_interval(
        [_rec([3], 2.0)], elev, len(elev))
    assert (lo, hi, used) == (98.0, 102.0, 1)
    assert binding["ceil_anchor"] == 3
    assert binding["ceil_value"] == pytest.approx(100.0)


def test_twin_a_intersection_over_several_records():
    """⋂ over the pad's records — the TIGHTEST corridor constraint binds."""
    elev = [0.0] * 8
    elev[3], elev[5] = 100.0, 99.0
    lo, hi, used, _b = psc.consistency_interval(
        [_rec([3], 2.0), _rec([5], 0.5)], elev, len(elev))
    assert (lo, hi, used) == (98.5, 99.5, 2)


def test_twin_a_dem_seat_inside_the_intersection_is_kept():
    """The band-chosen, DEM-biased seat stays the authority when it is
    already consistent (the v4 lesson: never replace the seat source)."""
    lvl, lo, hi, empty, resid = psc.narrow_seat(99.2, 90.0, 110.0, 98.0, 102.0)
    assert (lvl, lo, hi, empty, resid) == (99.2, 98.0, 102.0, False, 0.0)


def test_twin_a_dem_seat_outside_clamps_to_the_intersection_edge():
    """...and NEVER to the raw band edge (the measured gap: the band is
    7-34 m wide, the consistency budget 0.13-1.06 m)."""
    lvl, lo, hi, empty, _r = psc.narrow_seat(107.0, 90.0, 110.0, 98.0, 102.0)
    assert lvl == pytest.approx(102.0)      # the intersection edge
    assert lvl != pytest.approx(110.0)      # not the band ceiling
    assert (lo, hi, empty) == (98.0, 102.0, False)
    lvl, _lo, _hi, _e, _r = psc.narrow_seat(80.0, 90.0, 110.0, 98.0, 102.0)
    assert lvl == pytest.approx(98.0)


def test_twin_a_end_to_end_moves_the_unit_to_one_flat_level():
    elev = [0.0] * 20
    elev[3] = 100.0                                    # the SOLVED corridor
    layout = _Layout([_unit([_rec([3], 1.0, seat_m=107.0)],
                            level=107.0, lo=90.0, hi=110.0,
                            nodes=(10, 11, 12),
                            keys=("k10", "k11", "k12"))])
    _seed_boxes(layout, ("k10", "k11", "k12"), 90.0, 110.0)
    seats = {10: 107.0, 11: 107.0, 12: 107.0}
    rep = psc.apply_pad_seat_consistency(
        layout, elev, seats, len(elev), stamped={10, 11, 12})
    assert rep["narrowed"] == 1 and rep["moved"] == 1
    assert rep["worst_move_m"] == pytest.approx(6.0)
    # ONE flat level at every seat node of the unit — never per node.
    assert sorted(seats.values()) == [pytest.approx(101.0)] * 3
    assert [elev[i] for i in (10, 11, 12)] == [pytest.approx(101.0)] * 3
    # ...and the box narrowed with it, so no downstream clamp puts it back.
    boxes = store_of(layout).raw("seat_boxes")
    assert boxes["k10"] == (pytest.approx(99.0), pytest.approx(101.0))


def test_unstamped_seat_nodes_keep_their_elevation():
    """A seat node whose ``elev`` does not hold the seat today (it is not
    on the spine adjacency) is not written by the narrowing either — only
    its ``building_seats`` entry moves."""
    elev = [0.0] * 20
    elev[3], elev[10], elev[11] = 100.0, 107.0, 55.5
    layout = _Layout([_unit([_rec([3], 1.0)], level=107.0, lo=90.0, hi=110.0,
                            nodes=(10, 11), keys=("k10", "k11"))])
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    seats = {10: 107.0, 11: 107.0}
    psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                   stamped={10})
    assert elev[10] == pytest.approx(101.0)
    assert elev[11] == pytest.approx(55.5)
    assert seats[11] == pytest.approx(101.0)


# ── twin (b): empty intersection is a SEAT DEFECT, never a silent pick ──

def test_twin_b_empty_intersection_grades_down_from_the_corridor_side():
    elev = [0.0] * 20
    elev[3] = 100.0
    # seat box entirely ABOVE the consistency interval
    layout = _Layout([_unit([_rec([3], 0.5)], level=106.0, lo=105.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 105.0, 110.0)
    seats = {10: 106.0, 11: 106.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    assert rep["empty"] == 1
    row = rep["empties"][0]
    # descend at cap from the SENIOR (corridor) side, residual reported
    assert row["seat_now_m"] == pytest.approx(100.5)
    assert row["residual_m"] == pytest.approx(4.5)
    assert rep["worst_residual_m"] == pytest.approx(4.5)
    line = psc.format_report("TEST", rep)
    assert "EMPTY" in line and "SEAT DEFECT" in line
    assert "residual" in line


def test_twin_b_empty_from_below_takes_the_consistency_floor():
    elev = [0.0] * 20
    elev[3] = 100.0
    layout = _Layout([_unit([_rec([3], 0.5)], level=90.0, lo=80.0, hi=95.0)])
    _seed_boxes(layout, ("k10", "k11"), 80.0, 95.0)
    seats = {10: 90.0, 11: 90.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    row = rep["empties"][0]
    assert row["seat_now_m"] == pytest.approx(99.5)
    assert row["residual_m"] == pytest.approx(4.5)


# ── the consistency intersection can itself be EMPTY ────────────────────

def test_corridor_inconsistent_pad_keeps_its_seat_and_is_named():
    """Two of the pad's own frontage anchors solved further apart than the
    sum of their route budgets: NO flat level is consistent with the pad's
    own frontage.  There is no corridor side to descend from, so the seat
    is KEPT and the contradiction named (split-level-seat trigger) — never
    resolved onto one of the two contradictory anchors."""
    elev = [0.0] * 20
    elev[3], elev[4] = 100.0, 90.0          # 10 m apart...
    recs = [_rec([3], 1.0), _rec([4], 1.0)]  # ...on 1 m budgets each
    lo, hi, used, _b = psc.consistency_interval(recs, elev, len(elev))
    assert used == 2 and lo > hi            # inverted by construction
    layout = _Layout([_unit(recs, level=95.0, lo=80.0, hi=110.0)])
    boxes = _seed_boxes(layout, ("k10", "k11"), 80.0, 110.0)
    seats = {10: 95.0, 11: 95.0}
    before_boxes = dict(boxes)
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    assert rep["inconsistent"] == 1
    assert rep["narrowed"] == 0 and rep["moved"] == 0 and rep["empty"] == 0
    assert rep["worst_inversion_m"] == pytest.approx(8.0)
    assert seats == {10: 95.0, 11: 95.0}        # seat KEPT
    assert elev[10] == 0.0                       # nothing written
    assert dict(boxes) == before_boxes           # box untouched
    line = psc.format_report("TEST", rep)
    assert "CORRIDOR-INCONSISTENT" in line
    assert layout._pad_seat_consistency_inconsistent == rep["inconsistents"]


def test_corridor_inconsistent_records_keep_seat_final_equal_to_seat():
    """An un-narrowed pad's sidecar records are not stamped with an
    inverted interval — ``seat_final_m`` stays what the capture set."""
    elev = [0.0] * 20
    elev[3], elev[4] = 100.0, 90.0
    recs = [_rec([3], 1.0, seat_m=95.0), _rec([4], 1.0, seat_m=95.0)]
    layout = _Layout([_unit(recs, level=95.0, lo=80.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 80.0, 110.0)
    psc.apply_pad_seat_consistency(layout, elev, {10: 95.0, 11: 95.0},
                                   len(elev), stamped={10, 11})
    for r in recs:
        assert "consist_floor" not in r
        assert r["seat_final_m"] == r["seat_m"]


# ── twin (c): a pad with no frontage band behaves exactly as today ──────

def test_twin_c_off_network_unit_is_untouched():
    elev = [0.0] * 20
    elev[3] = 100.0
    layout = _Layout([_unit([], level=107.0, lo=90.0, hi=110.0)])
    boxes = _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    seats = {10: 107.0, 11: 107.0}
    before_elev = list(elev)
    before_boxes = dict(boxes)
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    assert rep["no_provenance"] == 1 and rep["narrowed"] == 0
    assert elev == before_elev
    assert seats == {10: 107.0, 11: 107.0}
    assert dict(boxes) == before_boxes


def test_anchor_outside_the_node_space_is_skipped_never_mapped():
    """An anchor index the solve's node space does not contain is COUNTED
    and skipped — inventing a mapping is what the canonical-identity law
    forbids."""
    elev = [0.0] * 5
    lo, hi, used, binding = psc.consistency_interval(
        [_rec([99], 2.0)], elev, len(elev))
    assert (lo, hi, used) == (None, None, 0)
    assert binding["skipped_anchors"] == 1
    layout = _Layout([_unit([_rec([99], 2.0)], level=107.0, lo=90.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    seats = {10: 107.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10})
    assert rep["no_anchor"] == 1 and rep["narrowed"] == 0
    assert seats == {10: 107.0}


# ── twin (d): the flag ──────────────────────────────────────────────────

def test_twin_d_flag_default_off_and_one_enables(monkeypatch):
    """DEFAULT OFF (lead ruling 2026-08-25, after the HECA acceptance miss:
    2,249 censused against a ≤1,487 bar).  Flag unset ⇒ byte-identical to
    today's build; an explicit ``"1"`` still enables the whole mechanism."""
    monkeypatch.delenv(psc.ENV_FLAG, raising=False)
    assert psc.pad_seat_consistency_enabled() is False
    monkeypatch.setenv(psc.ENV_FLAG, "1")
    assert psc.pad_seat_consistency_enabled() is True
    monkeypatch.setenv(psc.ENV_FLAG, "0")
    assert psc.pad_seat_consistency_enabled() is False


def test_twin_d_no_provenance_published_is_a_no_op():
    """Flag OFF publishes an EMPTY provenance list, so the narrowing pass
    has nothing to key on and writes nothing (byte-identical)."""
    elev = [1.0, 2.0, 3.0]
    layout = _Layout([])
    seats = {0: 1.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev))
    assert rep["units"] == 0 and rep["narrowed"] == 0
    assert elev == [1.0, 2.0, 3.0] and seats == {0: 1.0}


# ── twin (e): the sidecar export carries the narrowed interval ──────────

def test_twin_e_frontage_band_records_gain_the_narrowed_interval():
    elev = [0.0] * 20
    elev[3] = 100.0
    rec = _rec([3], 1.0, floor=95.0, ceiling=105.0, seat_m=107.0)
    layout = _Layout([_unit([rec], level=107.0, lo=90.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    psc.apply_pad_seat_consistency(layout, elev, {10: 107.0, 11: 107.0},
                                   len(elev), stamped={10, 11})
    # the RAW band interval is still there, beside the narrowed one
    assert rec["floor"] == 95.0 and rec["ceiling"] == 105.0
    assert rec["consist_floor"] == pytest.approx(99.0)
    assert rec["consist_ceiling"] == pytest.approx(101.0)
    assert rec["seat_final_m"] == pytest.approx(101.0)
    assert rec["seat_unit_m"] == pytest.approx(107.0)


def test_twin_e_unnarrowed_record_keeps_seat_final_equal_to_seat():
    """A record captured but never narrowed ships ``seat_final_m ==
    seat_m`` — the capture stamps it, so the census never sees a hole."""
    rec = _rec([3], 1.0, seat_m=107.0)
    assert rec["seat_final_m"] == rec["seat_m"]


# ── the yield-hard seats are narrowed too, and counted apart ────────────

def test_yield_hard_units_are_narrowed_and_counted_separately():
    elev = [0.0] * 20
    elev[3] = 100.0
    layout = _Layout([_unit([_rec([3], 1.0)], level=107.0, lo=90.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    seats = {10: 107.0, 11: 107.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11}, yield_idx={11})
    assert rep["yield_units"] == 1 and rep["narrowed"] == 1
    assert seats[10] == pytest.approx(101.0)
    assert rep["moves"][0]["yield_hard"] is True


def test_report_names_every_moved_pad():
    elev = [0.0] * 20
    elev[3] = 100.0
    layout = _Layout([
        _unit([_rec([3], 1.0)], level=107.0, lo=90.0, hi=110.0,
              nodes=(10,), keys=("k10",), ref="building70"),
        _unit([_rec([3], 2.0)], level=90.0, lo=80.0, hi=110.0,
              nodes=(11,), keys=("k11",), ref="building76"),
    ])
    _seed_boxes(layout, ("k10", "k11"), 80.0, 110.0)
    seats = {10: 107.0, 11: 90.0}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    line = psc.format_report("TEST", rep)
    assert "building70" in line and "building76" in line
    assert layout._pad_seat_consistency_moves == rep["moves"]
    # sorted worst-first
    assert abs(rep["moves"][0]["move_m"]) >= abs(rep["moves"][1]["move_m"])


def test_materiality_floor_is_not_iterated_on():
    """A sub-centimetre clamp is applied but never reported as a move."""
    elev = [0.0] * 20
    elev[3] = 100.0
    layout = _Layout([_unit([_rec([3], 1.0)], level=101.005,
                            lo=90.0, hi=110.0)])
    _seed_boxes(layout, ("k10", "k11"), 90.0, 110.0)
    seats = {10: 101.005, 11: 101.005}
    rep = psc.apply_pad_seat_consistency(layout, elev, seats, len(elev),
                                         stamped={10, 11})
    assert rep["narrowed"] == 1 and rep["moved"] == 0
    assert seats[10] == pytest.approx(101.0)


# ═════════════════════════════════════════════════════════════════════
# SEAT NO-STEP CLAMP (airside-zero round, RULINGS 2026-09-01m item 3)
# ═════════════════════════════════════════════════════════════════════
#
# The junior-side-only enforcement of the tier 1/2 <-> 3 no-step pairs:
# pass 1 discards the imposed edges (no-step spec Amendment 2) and pass
# 2 frees only tier 4, so the SEAT's own narrowing slot is the one
# lawful mover.  Twinned dispositions: clamp-in-interval, kept-on-
# contradiction, kept-outside-box (never the ruling-§5 descent),
# unsettled-partner skip, flag default.

def _clamp_unit(level, lo, hi):
    return _unit([], level=level, lo=lo, hi=hi)


def test_no_step_clamp_moves_the_seat_and_only_the_seat():
    """The seat clamps into ``box ∩ [senior ± budget]`` with the minimal
    move; every unit node takes the one flat level; the SENIOR value is
    read, never written (spec §1.3 — one-sided against a constant)."""
    elev = [0.0] * 20
    elev[3] = 68.5
    elev[10] = elev[11] = 70.0
    layout = _Layout([_clamp_unit(70.0, 63.0, 71.0)])
    boxes = _seed_boxes(layout, ("k10", "k11"), 63.0, 71.0)
    seats = {10: 70.0, 11: 70.0}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.5)]}, settled={3})
    assert rep["moved"] == 1 and rep["units_constrained"] == 1
    assert seats[10] == pytest.approx(69.0)
    assert seats[11] == pytest.approx(69.0)
    assert elev[10] == pytest.approx(69.0)
    assert elev[11] == pytest.approx(69.0)
    assert elev[3] == pytest.approx(68.5), "the senior moved — ladder inverted"
    # the recorded yield box narrows to the lawful interval
    blo, bhi = boxes["k10"]
    assert blo == pytest.approx(68.0) and bhi == pytest.approx(69.0)


def test_no_step_clamp_contradictory_seniors_keep_the_seat():
    """Two seniors whose values differ by more than the summed budgets
    admit NO flat level: the seat is KEPT and the contradiction named —
    the split-level-seat trigger's disposition (RULINGS 2026-08-04),
    never a silent pick between two authorities."""
    elev = [0.0] * 20
    elev[3], elev[4] = 100.0, 98.0
    elev[10] = elev[11] = 99.5
    layout = _Layout([_clamp_unit(99.5, 90.0, 110.0)])
    seats = {10: 99.5, 11: 99.5}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.2)], 11: [(4, 0.2)]}, settled={3, 4})
    assert rep["kept_contradiction"] == 1 and rep["moved"] == 0
    assert seats[10] == pytest.approx(99.5)
    assert elev[10] == pytest.approx(99.5)
    row = rep["contradictions"][0]
    assert row["inversion_m"] == pytest.approx(1.6)


def test_no_step_clamp_outside_the_box_keeps_the_seat():
    """A compliant level exists but lies outside the pad's own band box:
    the junior may move only WITHIN ITS OWN CAPS (owner 2026-09-01m item
    3), so the seat is KEPT with the residual named — deliberately NOT
    ``narrow_seat``'s ruling-§5 descent onto the interval edge."""
    elev = [0.0] * 20
    elev[3] = 81.98
    elev[10] = elev[11] = 80.30
    layout = _Layout([_clamp_unit(80.30, 80.06, 81.41)])
    seats = {10: 80.30, 11: 80.30}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.33)]}, settled={3})
    assert rep["kept_outside_box"] == 1 and rep["moved"] == 0
    assert seats[10] == pytest.approx(80.30)
    row = rep["outside_box"][0]
    assert row["residual_m"] == pytest.approx(0.24, abs=1e-6)


def test_no_step_clamp_skips_partners_unsettled_at_the_slot():
    """A junction ring vertex is a FREE variable at the slot — pricing a
    seat against its seed is the residual-against-DEM trap.  Partners
    outside ``settled`` are skipped and counted; with none left the unit
    is unconstrained and untouched."""
    elev = [0.0] * 20
    elev[3] = 68.5
    layout = _Layout([_clamp_unit(70.0, 63.0, 71.0)])
    seats = {10: 70.0, 11: 70.0}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.5)]}, settled=set())
    assert rep["unsolved_partners"] == 1
    assert rep["units_constrained"] == 0 and rep["moved"] == 0
    assert seats[10] == pytest.approx(70.0)


def test_no_step_clamp_materiality_floor():
    """A sub-centimetre clamp is not applied as a move."""
    elev = [0.0] * 20
    elev[3] = 70.0
    layout = _Layout([_clamp_unit(70.005, 63.0, 71.0)])
    seats = {10: 70.005, 11: 70.005}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.0)]}, settled={3})
    assert rep["moved"] == 0
    assert seats[10] == pytest.approx(70.005)


def test_no_step_clamp_flag_default_on_and_zero_disables(monkeypatch):
    """Default ON (the airside-zero adjudication knob); ``"0"`` disables
    and the provenance reader follows it."""
    monkeypatch.delenv(psc.ENV_FLAG_NO_STEP_CLAMP, raising=False)
    monkeypatch.delenv(psc.ENV_FLAG, raising=False)
    monkeypatch.delenv(psc.ENV_FLAG_DEM_LAST, raising=False)
    assert psc.seat_no_step_clamp_enabled() is True
    assert psc.seat_provenance_wanted() is True
    monkeypatch.setenv(psc.ENV_FLAG_NO_STEP_CLAMP, "0")
    assert psc.seat_no_step_clamp_enabled() is False
    assert psc.seat_provenance_wanted() is False


def test_no_step_clamp_report_line_names_the_moved_pad():
    elev = [0.0] * 20
    elev[3] = 68.5
    layout = _Layout([_clamp_unit(70.0, 63.0, 71.0)])
    seats = {10: 70.0, 11: 70.0}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.5)]}, settled={3})
    line = psc.format_no_step_report("TEST", rep)
    assert "building70" in line and "seat-no-step-clamp" in line
    assert layout._seat_no_step_clamp_report is rep


def test_no_step_clamp_never_touches_a_declared_basin_floor():
    """A basin pad floor is DECLARED terrain (RULINGS 2026-08-25f) — a
    unit carrying one is skipped whole, never clamped toward a
    station."""
    elev = [0.0] * 20
    elev[3] = 68.5
    layout = _Layout([_clamp_unit(70.0, 63.0, 71.0)])
    seats = {10: 70.0, 11: 70.0}
    rep = psc.apply_seat_no_step_clamp(
        layout, elev, seats, len(elev), stamped={10, 11},
        senior_cons={10: [(3, 0.5)]}, settled={3}, excluded={11})
    assert rep.get("excluded_units") == 1 and rep["moved"] == 0
    assert seats[10] == pytest.approx(70.0)
