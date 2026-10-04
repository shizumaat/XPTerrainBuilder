"""THE ORACLE RUNNER'S OWN TWINS — ``tools/harness/oracle.py``.

OWNER LAW (RULINGS 2026-08-06, "Instrument truth is law"): *"KNOWN-ANSWER
TWIN, or it is not an instrument.  Every instrument carries a calibration
twin feeding it a case whose answer is known and asserting the report."*

``tools/harness/oracle.py`` had ZERO tests.  ``_analytic_band``, the
verdict dicts, the PASS/SEE-REPORT roll-up and the exit code were all
untwinned — and the module is the entry a lane drives an investigation
with, so every number a report quotes from it came out of code nothing
checked.  ``src/auto_patch/constant_dem.py`` (the machinery) was well
twinned the whole time; the RUNNER, which is where the verdicts and the
verdict SENTENCES live, was not.  That is the exact asymmetry the ruling
names: report-only code exempt from the twin discipline.

EVERY ANSWER HERE IS HAND-COMPUTED and stated in the docstring before it
is asserted.  No build, no network, no X-Plane, ``tmp_path`` only: the
builds and the census are injected, so what is under test is the
oracle's own arithmetic and its own wording.

THE SYNTHETIC PAIR used throughout (the model is
``test_constant_dem_oracle.py``'s ``_layout_with``): one apron ring whose
5 vertices are (0,0) (1,0) (2,0) (2,10) (0,10).  A "plateau layout" seats
them all at 10.0 m and a "canyon layout" at 13.0 m, so the band-width
field is 3.0 m at every node and the analytic band (10.0, 13.0) agrees
with it exactly — the calibrated PASS.  Every other case is that one with
one number moved.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ══════════════════════════════════════════════════════════════════════
# HARNESS
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def oracle():
    """The runner, loaded from THIS tree by path — the same way
    ``test_harness.py`` loads every harness module."""
    spec = importlib.util.spec_from_file_location(
        "oracle_twin", ROOT / "tools" / "harness" / "oracle.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg(oracle):
    return oracle.HC.load_check_grade()


#: the 5 node coordinates ``_layout`` produces, in ring order
_XY = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (2.0, 10.0), (0.0, 10.0)]


def _status(oracle, code):
    """A ``_analytic_band`` status built from the register itself, so an
    injected status can never diverge from a real one."""
    defect, why = oracle.BAND_STATUS[code]
    return {"code": code, "defect": defect, "why": why, "detail": None}


def _census(cg, *, adjudicated=0, deferred=0):
    """A census report of the shape ``harness/census.py`` returns, with
    exactly ``adjudicated`` adjudicated rows and ``deferred`` deferred
    ones — built through ``check_grade.adjudication`` itself, so this
    fixture cannot drift from the register the oracle reads."""
    import types
    pairs = ([("within_shape", types.SimpleNamespace())] * adjudicated
             + [("drainage_minimum", types.SimpleNamespace())] * deferred)
    adj = cg.adjudication(pairs)
    total = adjudicated + deferred
    return {"adjudication": adj,
            "lawtrue": {"total": total, "airside": adjudicated,
                        "groundside": 0, "mixed": 0},
            "families": [{"family": "within_shape", "n": adjudicated}]}


# ══════════════════════════════════════════════════════════════════════
# §1 ``_analytic_band`` — WHICH exit was taken (Task 3a/3b)
# ══════════════════════════════════════════════════════════════════════
# The reader has four exits and used to collapse all of them into a bare
# ``None``, which the caller then labelled with a parenthetical naming
# three causes ("no anchors, no pavement, or the grid refused") — a
# catch-all bucket labelled with a cause, and one that did not even list
# the fourth member (a raised exception).  These four tests are the
# discriminator.


def test_the_retired_oracle_refuses_by_name(oracle) -> None:
    """THE LIVE BEHAVIOUR of ``oracle.py``: it refuses, and says why.

    Ruling (f) of the stage-B brief (lane v1retire, 2026-09-17) is "refuse
    BY NAME where an option becomes meaningless, never leave an option
    inert".  A retired instrument that raised ``AttributeError`` deep
    inside a build would satisfy the letter and none of the point, so this
    asserts the three things the refusal owes a reader: that it IS a
    refusal, WHY (v1 is retired, and which ruling says so), and WHAT
    answers the same questions on v2.
    """
    with pytest.raises(SystemExit) as excinfo:
        oracle.main(["HEAZ"])
    message = str(excinfo.value)
    assert message.startswith("REFUSED:"), message
    assert "v1 is " in message and "retired" in message, message
    assert "2026-09-13au" in message, message
    for pointer in ("v2_solve_replay", "census.py"):
        assert pointer in message, f"the refusal names no {pointer}: {message}"


def test_every_band_status_code_declares_whether_it_is_a_defect(oracle):
    """The register is the discriminator; a code missing from it would be
    an unlabelled bucket again."""
    assert set(oracle.BAND_STATUS) == {
        "ok", "no_nodes", "no_band", "band_reader_raised", "zero_coverage"}
    for code, (defect, why) in oracle.BAND_STATUS.items():
        assert isinstance(defect, bool) and why
    assert oracle.BAND_STATUS["band_reader_raised"][0] is True
    assert not any(d for c, (d, _w) in oracle.BAND_STATUS.items()
                   if c != "band_reader_raised"), (
        "exactly one status is a defect: the reader raising.  The others "
        "are legitimate answers about the layout")


# ══════════════════════════════════════════════════════════════════════
# §2 THE ANALYTIC BAND'S OWN DEM-INVARIANCE (the unchecked premise)
# ══════════════════════════════════════════════════════════════════════

def test_the_two_worlds_analytic_bands_are_compared_node_by_node(oracle):
    """KNOWN ANSWER, hand-computed.  Three nodes have a band in both
    worlds: widths (2.0 vs 2.0) agree, (2.0 vs 2.5) disagree by +0.5, and
    (2.0 vs 2.005) differ by 0.005 — below the 0.01 m materiality, so
    agreement-with-residual.  One node has a band in the plateau world
    only: a COVERAGE MISMATCH, counted on its own and never folded into
    the width disagreements.  Expect compared=3, width_disagreements=1,
    coverage_mismatches=1.
    """
    field = {("apron/", 0.0, 0.0): 0.0, ("apron/", 1.0, 0.0): 0.0,
             ("apron/", 2.0, 0.0): 0.0, ("apron/", 2.0, 10.0): 0.0}
    lo = {(0.0, 0.0): (0.0, 2.0), (1.0, 0.0): (0.0, 2.0),
          (2.0, 0.0): (0.0, 2.0), (2.0, 10.0): (0.0, 2.0)}
    hi = {(0.0, 0.0): (5.0, 7.0), (1.0, 0.0): (5.0, 7.5),
          (2.0, 0.0): (5.0, 7.005)}
    rep = oracle._analytic_band_world_diff(field, lo.get, hi.get, 0.01)
    assert rep["nodes"] == 4
    assert rep["compared"] == 3
    assert rep["coverage_mismatches"] == 1
    assert rep["width_disagreements"] == 1
    assert rep["max_abs_delta_m"] == pytest.approx(0.5)
    assert rep["worst"][0]["plateau_width_m"] == pytest.approx(2.0)
    assert rep["worst"][0]["canyon_width_m"] == pytest.approx(2.5)
    assert rep["worst_coverage_mismatches"][0]["x"] == 2.0


def test_an_identical_band_in_both_worlds_reports_zero_disagreement(oracle):
    """The premise HOLDING is the expected reading: the analytic band is
    derived from anchors, caps and geometry, none of which the DEM
    touches."""
    field = {("apron/", float(i), 0.0): 0.0 for i in range(4)}
    band = lambda xy: (100.0, 103.0)                     # noqa: E731
    rep = oracle._analytic_band_world_diff(field, band, band, 0.01)
    assert rep["compared"] == 4
    assert rep["width_disagreements"] == 0
    assert rep["coverage_mismatches"] == 0
    assert rep["max_abs_delta_m"] == 0.0


# ══════════════════════════════════════════════════════════════════════
# §3 THE FRAME STAMP (Task 4)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §4 THE VERDICTS, END TO END (Tasks 3, 5, and the roll-up)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §5 THE BAND-INVARIANCE ATTRIBUTION (cycle-8 pre-requirement)
#
# Assertion 4's self-test FALSIFIED ``_analytic_band``'s premise ("the
# band is identical in both worlds") at all four battery airports.  The
# instrument that reports the falsification now has to say WHICH INPUT
# differs, or the next round extends a band nobody has attributed.  These
# twins feed it hand-built bands whose carrier is known by construction.
# ══════════════════════════════════════════════════════════════════════

def _band_with_provenance(bands, prov):
    """A band closure carrying the ``attachment_at`` provenance the real
    ``raster_reach_band`` publishes."""
    def band(xy):
        return bands.get(xy)
    band.attachment_at = lambda x, y: prov.get((x, y))
    return band


def test_a_moved_attachment_is_named_as_the_carrier(oracle):
    """KNOWN ANSWER.  One node, band (0,2) vs (0,5) — a 3.0 m width
    disagreement — and the two worlds' lookups say the serving attachment
    sits in DIFFERENT cells ((3,4) vs (9,9)).  The carrier is the
    geometry the band was read over, so the row files under
    ``attachment_moved`` and nothing else is counted."""
    field = {("apron/", 0.0, 0.0): 0.0}
    lo = _band_with_provenance(
        {(0.0, 0.0): (0.0, 2.0)},
        {(0.0, 0.0): {"attachment_cell": (3, 4), "leg_m": 1.0,
                      "ceiling_at_attachment": 2.0,
                      "floor_at_attachment": 0.0}})
    hi = _band_with_provenance(
        {(0.0, 0.0): (0.0, 5.0)},
        {(0.0, 0.0): {"attachment_cell": (9, 9), "leg_m": 1.0,
                      "ceiling_at_attachment": 5.0,
                      "floor_at_attachment": 0.0}})
    rep = oracle._analytic_band_world_diff(field, lo, hi, 0.01)
    assert rep["width_disagreements"] == 1
    assert rep["carrier"]["attachment_moved"] == 1
    assert rep["carrier"]["route_interval_at_same_attachment"] == 0
    assert rep["carrier"]["off_route_leg_at_same_attachment"] == 0
    assert rep["carrier"]["unattributed"] == 0
    assert rep["carrier"]["max_abs_delta_m"]["attachment_moved"] == \
        pytest.approx(3.0)
    assert rep["worst"][0]["carrier"] == "attachment_moved"


def test_a_held_attachment_with_a_moved_interval_is_named_as_the_route(
        oracle):
    """KNOWN ANSWER.  Same attachment cell in both worlds, same leg, but
    the ROUTE INTERVAL at that attachment is 2.0 m in one world and 4.0 m
    in the other: the value field moved under a lookup that held still,
    which is a different finding from a layout that moved."""
    field = {("junction/", 5.0, 5.0): 0.0}
    lo = _band_with_provenance(
        {(5.0, 5.0): (0.0, 2.0)},
        {(5.0, 5.0): {"attachment_cell": (1, 1), "leg_m": 0.5,
                      "ceiling_at_attachment": 2.0,
                      "floor_at_attachment": 0.0}})
    hi = _band_with_provenance(
        {(5.0, 5.0): (0.0, 4.0)},
        {(5.0, 5.0): {"attachment_cell": (1, 1), "leg_m": 0.5,
                      "ceiling_at_attachment": 4.0,
                      "floor_at_attachment": 0.0}})
    rep = oracle._analytic_band_world_diff(field, lo, hi, 0.01)
    assert rep["carrier"]["route_interval_at_same_attachment"] == 1
    assert rep["carrier"]["attachment_moved"] == 0
    assert rep["worst"][0]["carrier"] == "route_interval_at_same_attachment"


def test_a_held_attachment_and_interval_with_a_moved_leg_is_the_leg(
        oracle):
    """KNOWN ANSWER.  Attachment and route interval identical; only the
    OFF-ROUTE LEG differs (0.5 m vs 1.5 m), which is the lookup's local
    geometry rather than the route's."""
    field = {("building/b1", 7.0, 0.0): 0.0}
    lo = _band_with_provenance(
        {(7.0, 0.0): (0.0, 2.0)},
        {(7.0, 0.0): {"attachment_cell": (2, 2), "leg_m": 0.5,
                      "ceiling_at_attachment": 1.0,
                      "floor_at_attachment": 0.0}})
    hi = _band_with_provenance(
        {(7.0, 0.0): (0.0, 3.0)},
        {(7.0, 0.0): {"attachment_cell": (2, 2), "leg_m": 1.5,
                      "ceiling_at_attachment": 1.0,
                      "floor_at_attachment": 0.0}})
    rep = oracle._analytic_band_world_diff(field, lo, hi, 0.01)
    assert rep["carrier"]["off_route_leg_at_same_attachment"] == 1
    assert rep["carrier"]["attachment_moved"] == 0


def test_a_band_without_provenance_is_named_unavailable_not_guessed(
        oracle):
    """A supplier that publishes no ``attachment_at`` cannot be split, and
    the instrument says so rather than filing the row under a cause it did
    not read (the catch-all-bucket-with-a-cause pattern)."""
    field = {("apron/", 0.0, 0.0): 0.0}
    rep = oracle._analytic_band_world_diff(
        field, {(0.0, 0.0): (0.0, 2.0)}.get,
        {(0.0, 0.0): (0.0, 5.0)}.get, 0.01)
    assert rep["carrier"]["provenance_unavailable"] == 1
    assert rep["carrier"]["attachment_moved"] == 0


def test_the_seed_map_diff_separates_keys_from_values(oracle):
    """KNOWN ANSWER.  Two seed maps: one key only in the plateau world,
    one only in the canyon world, two shared keys of which one differs by
    0.25 m (> materiality) and one by 0.001 m (below it).  Expect
    plateau_only=1, canyon_only=1, shared=2, value_disagreements=1."""
    lo = {(0.0, 0.0): 10.0, (1.0, 0.0): 20.0, (2.0, 0.0): 30.0}
    hi = {(0.0, 0.0): 10.25, (1.0, 0.0): 20.001, (3.0, 0.0): 40.0}
    rep = oracle._seed_map_diff(lo, hi, 0.01)
    assert rep["plateau_only"] == 1
    assert rep["canyon_only"] == 1
    assert rep["shared"] == 2
    assert rep["value_disagreements"] == 1
    assert rep["max_abs_delta_m"] == pytest.approx(0.25)
