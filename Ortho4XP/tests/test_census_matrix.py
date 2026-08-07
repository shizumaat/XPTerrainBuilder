"""THE CENSUS MATRIX's calibration twin (RULINGS 2026-08-06, "Instrument
truth is law": a known-answer twin, or it is not an instrument).

``tools/census_matrix.py`` is a REPORTER: it lays several census JSONs side
by side and applies a stated ceiling to one column.  Its one hard property
is that it DERIVES NOTHING — every number it prints is read verbatim out of
a ``tools/harness/census.py --json`` artifact.  A reporter that recomputes a
defect count is the census-wrapper defect (CLAUDE.md), so the twin feeds it a
census whose every field is a distinctive known value and asserts those exact
values come back out, plus the gate verdict at its boundary.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cm():
    return _load("twin_census_matrix", ROOT / "tools" / "census_matrix.py")


def _entry(patch, lawtrue, adj, air, gs, mix, bands=None):
    e = {
        "patch": patch,
        "lawtrue": {"total": lawtrue},
        "adjudication": {"adjudicated_total": adj,
                         "adjudicated_by_side": {"airside": air,
                                                 "groundside": gs,
                                                 "mixed": mix}},
    }
    if bands is not None:
        e["magnitude_bands"] = bands
    return e


def _write(tmp_path, name, entries):
    p = tmp_path / name
    p.write_text(json.dumps(entries))
    return p


# ── the known answer ─────────────────────────────────────────────────

def test_every_printed_number_is_the_census_value_verbatim(cm, tmp_path):
    """Distinctive primes: any arithmetic on the way through shows up."""
    p = _write(tmp_path, "a.json", [
        _entry("/x/HECA_lo.osm", 11171, 4781, 4129, 636, 16)])
    cells = cm.read_cells(p)
    assert cells["HECA_lo"] == {
        "lawtrue": 11171, "adj": 4781, "air": 4129, "gs": 636, "mix": 16,
        # the ONE composite, and it is the census's own applied ruling
        # (a mixed row counts against airside), not a new statistic
        "a4a": 4129 + 16, "bands": None}


def test_a_rebuilt_world_folds_onto_its_own_cell(cm):
    """``HECA_lo2`` is HECA's low world measured again — it must compare
    with the baseline cell, not appear as a ninth one."""
    assert cm.cell_tag("/t/HECA_lo2.osm") == "HECA_lo"
    assert cm.cell_tag("/t/KCLT_hi3.osm") == "KCLT_hi"
    assert cm.cell_tag("/t/SPJC_lo.osm") == "SPJC_lo"


def test_the_gate_is_may_not_rise_so_equality_passes(cm, tmp_path):
    """The Q4 gate's exact semantics: ``<=`` the ceiling, and the
    boundary is the case that decides whether a lane ships."""
    base = _write(tmp_path, "base.json", [
        _entry("/x/A_lo.osm", 100, 90, 50, 40, 0),
        _entry("/x/A_hi.osm", 100, 90, 50, 40, 0),
        _entry("/x/B_lo.osm", 100, 90, 50, 40, 0)])
    arm = _write(tmp_path, "arm.json", [
        _entry("/x/A_lo.osm", 80, 70, 50, 20, 0),     # equal   → PASS
        _entry("/x/A_hi.osm", 80, 70, 49, 21, 0),     # lower   → PASS
        _entry("/x/B_lo.osm", 80, 70, 51, 19, 0)])    # +1      → FAIL
    arms = [cm.read_cells(base), cm.read_cells(arm)]
    order = cm.order_of(arms)
    cap = cm.ceilings(arms, 0, None)
    rows = [r for r in cm.gate_rows(arms, ["base", "arm"], cap, order)
            if r[0] == "arm"]
    assert {(r[1], r[4]) for r in rows} == {
        ("A_lo", True), ("A_hi", True), ("B_lo", False)}


def test_a_cell_with_no_ceiling_is_reported_not_passed(cm, tmp_path):
    """A cell the ceiling source never measured must not be counted as a
    pass — a silent pass is how a gate stops gating."""
    base = _write(tmp_path, "base.json", [_entry("/x/A_lo.osm", 9, 9, 5, 4, 0)])
    arm = _write(tmp_path, "arm.json", [
        _entry("/x/A_lo.osm", 9, 9, 5, 4, 0),
        _entry("/x/NEW_hi.osm", 9, 9, 5, 4, 0)])
    arms = [cm.read_cells(base), cm.read_cells(arm)]
    cap = cm.ceilings(arms, 0, None)
    rows = {r[1]: r[4] for r in
            cm.gate_rows(arms, ["base", "arm"], cap, cm.order_of(arms))
            if r[0] == "arm"}
    assert rows == {"A_lo": True, "NEW_hi": None}


def test_a_recorded_frame_of_record_can_be_the_ceiling(cm, tmp_path):
    """The lane copy hard-coded one round's frame as a module constant —
    the thing that goes stale.  A recorded frame is an argument."""
    frame = tmp_path / "frame.json"
    frame.write_text(json.dumps({"A_lo": 390, "A_hi": 162}))
    arm = _write(tmp_path, "arm.json", [
        _entry("/x/A_lo.osm", 148, 115, 91, 24, 0),
        _entry("/x/A_hi.osm", 277, 265, 162, 103, 0)])
    arms = [cm.read_cells(arm)]
    cap = cm.ceilings(arms, None, str(frame))
    rows = {r[1]: (r[2], r[3], r[4])
            for r in cm.gate_rows(arms, ["arm"], cap, cm.order_of(arms))}
    assert rows == {"A_lo": (91, 390, True), "A_hi": (162, 162, True)}


def test_a_non_census_json_is_refused_by_name(cm, tmp_path):
    """Printing zeros for a schema it does not understand is how a
    reporter lies; it must name what is missing instead."""
    bad = _write(tmp_path, "bad.json", [{"patch": "/x/A_lo.osm",
                                         "lawtrue": {"total": 1}}])
    with pytest.raises(KeyError) as e:
        cm.read_cells(bad)
    assert "adjudication" in str(e.value)


def test_the_cell_order_is_the_batterys_reading_order(cm, tmp_path):
    """Low world before high, airports in first-seen order — so two arms
    of the same battery print as comparable columns."""
    p = _write(tmp_path, "a.json", [
        _entry("/x/HECA_hi.osm", 1, 1, 1, 0, 0),
        _entry("/x/HEAZ_lo.osm", 1, 1, 1, 0, 0),
        _entry("/x/HECA_lo.osm", 1, 1, 1, 0, 0),
        _entry("/x/HEAZ_hi.osm", 1, 1, 1, 0, 0)])
    assert cm.order_of([cm.read_cells(p)]) == [
        "HECA_lo", "HECA_hi", "HEAZ_lo", "HEAZ_hi"]


def test_it_runs_end_to_end_on_two_arms(cm, tmp_path, capsys):
    base = _write(tmp_path, "base.json", [_entry("/x/A_lo.osm", 9, 8, 5, 3, 0)])
    arm = _write(tmp_path, "arm.json", [_entry("/x/A_lo.osm", 7, 6, 4, 2, 0)])
    assert cm.main([str(base), str(arm)]) == 0
    out = capsys.readouterr().out
    assert "1/1 PASS" in out
    assert "air    -1" in out or "air -1" in out.replace("   ", " ")
