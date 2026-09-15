"""THE DEFECT MATERIALITY FLOOR twins (lane ``v2defectfloor``, owner
RULINGS 2026-09-14bx).

On app 1.0.339 the owner's +40-004 tile ABORTED on ONE LEMD
``runway_transverse`` row: ``grade_pct`` 1.6527 against ``cap_pct`` 1.5
over ``distance_m`` 29.977 — 0.15 pp, which is 4.6 cm of excess fall over
30 m.  The structural-DEFECT gate (``auto_patch/engine_v2.py``, over
``verify/census.py``'s ``DEFECT_KEYS``) aborted the whole tile on ANY row
of a structural family regardless of magnitude.

Ruled: a structural DEFECT aborts only when MATERIAL.  ``[verify]
defect_min_excess_m`` (``law/emit.toml``) is the floor; a row under it
stays a census VIOLATION — counted in ``by_family``, present in the rows,
read by the cockpit — and is NAMED in the engine log; it never aborts.

The twins here read the gate itself: the arithmetic, the two sides of the
floor, the fallback for a family stating no cap/distance pair, and that
the number comes from the tables and nowhere else.
"""
from __future__ import annotations

import dataclasses

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.verify.census import (DEFECT_KEYS, FAMILY_TRANSVERSE,
                                         FAMILY_VERTICAL_CURVE, defect_excess_m,
                                         defect_gate, under_floor_text)
from auto_patch_v2.verify.frame import row


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("LEMD")


def _transverse(grade_pct: float, cap_pct: float, distance_m: float):
    """A ``runway_transverse`` row in the reader's own shape
    (``verify/runway.py``: ``magnitude_m`` is the RAW ``|fall|``)."""
    fall = grade_pct / 100.0 * distance_m
    r = row(FAMILY_TRANSVERSE, ("runway", "runway"), "airside",
            fall, grade_pct, cap_pct, distance_m, (0.0, 0.0), (distance_m, 0.0),
            "face35", "face35")
    r.update({"reading": "transverse_max", "face": "face35", "direction": "fall"})
    return r


def _vertical_curve(change_pct: float, bound_pct: float, span_m: float):
    """A ``runway_vertical_curve`` row in the reader's own shape: its
    ``magnitude_m`` is ALREADY ``(|change| − bound) × span``."""
    mag = (abs(change_pct) - bound_pct) / 100.0 * span_m
    r = row(FAMILY_VERTICAL_CURVE, ("runway", "runway"), "airside",
            mag, change_pct, bound_pct, span_m, (0.0, 0.0), (span_m, 0.0),
            "spine", "spine")
    r.update({"reading": "vertical_curve", "face": "14L/32R"})
    return r


# ── the arithmetic ───────────────────────────────────────────────────────

def test_the_lemd_row_reads_4_6_cm_of_excess():
    """The owner's row, field for field off the 1.0.339 report."""
    r = _transverse(1.6527, 1.5, 29.977)
    assert r["magnitude_m"] == pytest.approx(0.4954, abs=5e-4)
    assert defect_excess_m(r) == pytest.approx(0.0458, abs=5e-4)


def test_transverse_excess_is_magnitude_minus_cap_times_distance():
    """For the transverse family the grade reading and the ruling's own
    ``magnitude_m − cap_pct/100 × distance_m`` are the SAME metres."""
    r = _transverse(1.6527, 1.5, 29.977)
    assert defect_excess_m(r) == pytest.approx(
        r["magnitude_m"] - r["cap_pct"] / 100.0 * r["distance_m"], abs=1e-3)


def test_vertical_curve_excess_is_its_own_magnitude_not_double_subtracted():
    """``runway_vertical_curve`` publishes the EXCESS as ``magnitude_m``.
    Subtracting the cap a second time would push every curve row under any
    floor; reading the row's grade fields gives the same metres it already
    states."""
    r = _vertical_curve(change_pct=0.9, bound_pct=0.4, span_m=100.0)
    assert r["magnitude_m"] == pytest.approx(0.5, abs=1e-6)
    assert defect_excess_m(r) == pytest.approx(0.5, abs=1e-6)
    naive = r["magnitude_m"] - r["cap_pct"] / 100.0 * r["distance_m"]
    assert naive == pytest.approx(0.1, abs=1e-6)  # what double-subtracting gives
    assert defect_excess_m(r) > naive


def test_a_family_without_a_cap_or_distance_falls_back_to_magnitude():
    r = row(FAMILY_TRANSVERSE, ("runway", "runway"), "airside",
            0.37, None, None, None, None, None, "w", "w")
    assert defect_excess_m(r) == pytest.approx(0.37)
    r2 = row(FAMILY_TRANSVERSE, ("runway", "runway"), "airside",
             0.37, 2.0, None, 30.0, None, None, "w", "w")
    assert defect_excess_m(r2) == pytest.approx(0.37)


def test_the_excess_is_floored_at_zero_and_capped_at_the_magnitude():
    """The v1 harness's two guards (``tools/check_grade.py``
    ``MATERIALITY_ACCUMULATION_RULE``): a row can never be more unlawful
    than its whole elevation difference, and never negatively unlawful."""
    lawful = _transverse(1.2, 1.5, 30.0)   # under its own cap
    assert defect_excess_m(lawful) == 0.0
    # a row whose stated magnitude is SMALLER than the grade arithmetic
    # implies (a reader that priced a vertical quantity) is capped there
    odd = row(FAMILY_TRANSVERSE, ("runway", "runway"), "airside",
              0.02, 5.0, 1.5, 30.0, (0.0, 0.0), (30.0, 0.0), "w", "w")
    assert defect_excess_m(odd) == pytest.approx(0.02)
    # a zero span has nothing to price over: the magnitude IS the excess
    zero = row(FAMILY_TRANSVERSE, ("runway", "runway"), "airside",
               0.44, 5.0, 1.5, 0.0, (0.0, 0.0), (0.0, 0.0), "w", "w")
    assert defect_excess_m(zero) == pytest.approx(0.44)


# ── the two sides of the floor ───────────────────────────────────────────

def test_the_4_6_cm_row_does_not_abort_and_is_named(law):
    rows = {FAMILY_TRANSVERSE: [_transverse(1.6527, 1.5, 29.977)]}
    defects, under = defect_gate(law, rows)
    assert defects == {}, defects
    assert set(under) == {FAMILY_TRANSVERSE}
    assert under[FAMILY_TRANSVERSE]["rows"] == 1
    assert under[FAMILY_TRANSVERSE]["worst_excess_m"] == pytest.approx(0.0458, abs=5e-4)
    text = under_floor_text(under)
    assert "under the materiality floor" in text
    assert "1 rows" in text and "0.04" in text
    # THE ROW IS STILL A VIOLATION: the gate never touches ``rows``
    assert len(rows[FAMILY_TRANSVERSE]) == 1


def test_a_40_cm_row_still_aborts(law):
    """0.4 m of excess over 30 m — a real structural defect."""
    rows = {FAMILY_TRANSVERSE: [_transverse(2.8333, 1.5, 30.0)]}
    r = rows[FAMILY_TRANSVERSE][0]
    assert defect_excess_m(r) == pytest.approx(0.40, abs=5e-3)
    defects, under = defect_gate(law, rows)
    assert defects == {FAMILY_TRANSVERSE: 1}, defects
    assert under == {}


def test_a_mixed_family_aborts_on_the_material_rows_only(law):
    rows = {FAMILY_TRANSVERSE: [_transverse(1.6527, 1.5, 29.977),
                                _transverse(1.55, 1.5, 30.0),
                                _transverse(2.8333, 1.5, 30.0)]}
    defects, under = defect_gate(law, rows)
    assert defects == {FAMILY_TRANSVERSE: 1}, defects
    assert under[FAMILY_TRANSVERSE]["rows"] == 2
    assert under[FAMILY_TRANSVERSE]["worst_excess_m"] == pytest.approx(0.0458, abs=5e-4)


def test_no_defect_rows_is_no_defects_and_no_floor_talk(law):
    assert defect_gate(law, {k: [] for k in DEFECT_KEYS}) == ({}, {})


def test_a_vertical_curve_row_is_gated_on_its_own_excess(law):
    """A hair over the bound does not abort; half a metre does."""
    small = _vertical_curve(change_pct=0.45, bound_pct=0.4, span_m=100.0)
    assert defect_excess_m(small) == pytest.approx(0.05, abs=1e-6)
    defects, under = defect_gate(law, {FAMILY_VERTICAL_CURVE: [small]})
    assert defects == {} and under[FAMILY_VERTICAL_CURVE]["rows"] == 1
    big = _vertical_curve(change_pct=0.9, bound_pct=0.4, span_m=100.0)
    defects, under = defect_gate(law, {FAMILY_VERTICAL_CURVE: [big]})
    assert defects == {FAMILY_VERTICAL_CURVE: 1} and under == {}


# ── the number lives in the tables ───────────────────────────────────────

def test_the_floor_is_a_law_key_read_from_the_tables(law):
    floor = law.tables.emit.verify.defect_min_excess_m
    assert floor == pytest.approx(0.10)
    # and the gate READS it: move the key, the verdict moves with it
    tight = dataclasses.replace(
        law.tables,
        emit=dataclasses.replace(
            law.tables.emit,
            verify=dataclasses.replace(law.tables.emit.verify,
                                       defect_min_excess_m=0.01)))
    tight_law = dataclasses.replace(law, tables=tight)
    rows = {FAMILY_TRANSVERSE: [_transverse(1.6527, 1.5, 29.977)]}
    assert defect_gate(tight_law, rows)[0] == {FAMILY_TRANSVERSE: 1}
    loose = dataclasses.replace(
        law.tables,
        emit=dataclasses.replace(
            law.tables.emit,
            verify=dataclasses.replace(law.tables.emit.verify,
                                       defect_min_excess_m=1.0)))
    loose_law = dataclasses.replace(law, tables=loose)
    assert defect_gate(loose_law, {FAMILY_TRANSVERSE: [_transverse(2.8333, 1.5, 30.0)]})[0] == {}


def test_no_numeric_literal_for_the_floor_in_python():
    """The floor is stated in ``law/emit.toml`` and nowhere else — every
    Python reader goes through ``emit.verify.defect_min_excess_m``."""
    import pathlib
    import auto_patch_v2
    src = pathlib.Path(auto_patch_v2.__file__).parent
    hits = [py for py in src.rglob("*.py")
            if "defect_min_excess_m" in py.read_text()
            and "0.10" in py.read_text().split("defect_min_excess_m")[1][:40]]
    assert not hits, hits
    toml = (src / "law" / "emit.toml").read_text()
    assert "[verify]" in toml and "defect_min_excess_m" in toml
