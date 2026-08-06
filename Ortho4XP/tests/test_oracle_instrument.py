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
import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch.layout import (                          # noqa: E402
    BuiltShape, PavementLayout, ROLE_APRON)


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


def _layout(values, role=ROLE_APRON, ref=""):
    """One apron ring: 5 vertices at (0,0) (1,0) (2,0) (2,10) (0,10)."""
    ring = [(float(i), 0.0) for i in range(len(values))]
    ring = ring + [(float(len(values)) - 1.0, 10.0), (0.0, 10.0)]
    vals = list(values) + [values[-1], values[0]]
    lay = PavementLayout(icao="ORACLE", anchor=(0.0, 0.0))
    lay.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=role, ref=ref,
        node_altitudes=vals + [vals[0]]))
    return lay


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


def _run(oracle, cg, monkeypatch, tmp_path, *, lo_vals, hi_vals, band,
         adjudicated=0, deferred=0, analytic_band=None):
    """Drive ``oracle.main`` over injected builds.  Returns
    ``(rc, verdicts, progress_text)``."""
    lo_layout, hi_layout = _layout(lo_vals), _layout(hi_vals)

    def _build_patch(icao, root, out_dir, tag, prog, const_dem=None, **kw):
        layout = lo_layout if const_dem == min(WORLDS) else hi_layout
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"_layout": layout, "patch": str(out_dir / f"{tag}.osm"),
                "icao": icao, "tag": tag, "shapes": len(layout.shapes)}

    monkeypatch.setattr(oracle.HB, "require_build_cwd", lambda p: ROOT)
    monkeypatch.setattr(oracle.HB, "build_patch", _build_patch)
    monkeypatch.setattr(oracle.HC, "census_one",
                        lambda osm, _cg, **kw: _census(
                            cg, adjudicated=adjudicated, deferred=deferred))
    monkeypatch.setattr(oracle, "_frame_stamp",
                        lambda root, args, worlds: {
                            "env": {"git_head": "0" * 40, "git_dirty": False,
                                    "code_tree_hash": "deadbeef",
                                    "o4_env": {}},
                            "data_corpus": {"shared": 6, "total": 6,
                                            "private": []},
                            "frame_warnings": []})
    if analytic_band is None:
        def analytic_band(layout):
            return ((band.get if isinstance(band, dict) else band),
                    _status(oracle, "ok"))
    monkeypatch.setattr(oracle, "_analytic_band", analytic_band)

    rc = oracle.main(["ORCL", "--out", str(tmp_path)])
    doc = json.loads((tmp_path / "ORCL_oracle.json").read_text())
    prog = (tmp_path / "ORCL_oracle.progress").read_text()
    return rc, doc["verdicts"], prog


from auto_patch.constant_dem import (                    # noqa: E402
    CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)

WORLDS = [PLATEAU_ELEVATION_M, CANYON_ELEVATION_M]


# ══════════════════════════════════════════════════════════════════════
# §1 ``_analytic_band`` — WHICH exit was taken (Task 3a/3b)
# ══════════════════════════════════════════════════════════════════════
# The reader has four exits and used to collapse all of them into a bare
# ``None``, which the caller then labelled with a parenthetical naming
# three causes ("no anchors, no pavement, or the grid refused") — a
# catch-all bucket labelled with a cause, and one that did not even list
# the fourth member (a raised exception).  These four tests are the
# discriminator.

def _patch_band_internals(monkeypatch, *, nodes=None, band=..., raises=None,
                          seen=None):
    from auto_patch import grade_graph as GG
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch.elevation_per_surface import solver_primitives as SP

    def _nodes(layout, *, readonly=False):
        if seen is not None:
            seen["readonly"] = readonly
        return (nodes if nodes is not None else [(0.0, 0.0)]), {}

    def _band(layout, G):
        if raises is not None:
            raise raises
        return band

    monkeypatch.setattr(SP, "_build_node_list", _nodes)
    monkeypatch.setattr(GG, "build_unified_graph", lambda lay, b2i: object())
    monkeypatch.setattr(BF, "reach_band_unified", _band)


def test_an_empty_node_list_is_named_no_nodes(oracle, monkeypatch):
    """KNOWN ANSWER: node list empty ⇒ code 'no_nodes', defect False."""
    _patch_band_internals(monkeypatch, nodes=[])
    band, status = oracle._analytic_band(_layout([1.0]))
    assert band is None
    assert status["code"] == "no_nodes"
    assert status["defect"] is False
    assert "no pavement-role nodes" in status["why"]


def test_a_missing_band_factory_is_named_no_band(oracle, monkeypatch):
    """KNOWN ANSWER: ``reach_band_unified`` returns None ⇒ 'no_band'."""
    _patch_band_internals(monkeypatch, band=None)
    band, status = oracle._analytic_band(_layout([1.0]))
    assert band is None
    assert status["code"] == "no_band"
    assert status["defect"] is False


def test_a_RAISED_band_reader_is_a_DEFECT_not_an_answer(oracle, monkeypatch):
    """KNOWN ANSWER: the reader raises ⇒ 'band_reader_raised',
    ``defect`` TRUE, and the exception itself in ``detail``.

    THIS IS THE ONE THAT MATTERED.  The bare ``except Exception`` printed
    a line and returned the same ``None`` a genuinely band-less layout
    returns, so a CODE failure inside the instrument was indistinguishable
    from a legitimate result about the airport — and assertion 2 then read
    "NOT EVALUATED" as though the layout were at fault.  It is the same
    shape as the key-shape bug ``constant_dem.saturation_report``'s
    docstring records as having made assertion 2 read as a clean pass for
    a whole campaign.
    """
    _patch_band_internals(monkeypatch, raises=RuntimeError("grid exploded"))
    band, status = oracle._analytic_band(_layout([1.0]))
    assert band is None
    assert status["code"] == "band_reader_raised"
    assert status["defect"] is True, (
        "a raise is a defect in the instrument, never an answer about the "
        "layout — the two must not share a report")
    assert "grid exploded" in status["detail"]["exception"]
    assert status["detail"]["traceback"]


def test_a_built_band_is_ok_and_adapts_the_call_shape(oracle, monkeypatch):
    """KNOWN ANSWER: the engine's ``band(x, y)`` is adapted to the
    reader's ``band_of((x, y))``, and the status is 'ok'."""
    _patch_band_internals(monkeypatch, band=lambda x, y: (x, y))
    band, status = oracle._analytic_band(_layout([1.0]))
    assert status["code"] == "ok" and status["defect"] is False
    assert band((3.0, 4.0)) == (3.0, 4.0), (
        "the adapter must unpack the point into two positional arguments "
        "— the engine's contract is literally band(x, y)")


def test_the_band_reader_takes_the_READONLY_node_list(oracle, monkeypatch):
    """``_build_node_list``'s own docstring: ``readonly`` "exists for
    MEASUREMENT INSTRUMENTS", because the default ``get_or_add`` interning
    MUTATES the canonical registry — it measured a probe-only node-list
    rebuild moving SPJC's emitted surface (+1 node, 86 altitudes, |dz| <=
    0.21 m).  This reader is a measurement instrument."""
    seen = {}
    _patch_band_internals(monkeypatch, band=lambda x, y: None, seen=seen)
    oracle._analytic_band(_layout([1.0]))
    assert seen["readonly"] is True, (
        "the oracle's band reader interned into the shared canonical "
        "registry — an instrument mutating the thing it measures")


def test_the_band_reader_restores_the_layout_indices_it_perturbs(
        oracle, monkeypatch):
    """``_build_node_list`` publishes two node-space indices ON the layout
    and its docstring instructs a probe caller to snapshot and restore
    them.  A layout that had neither must still have neither."""
    from auto_patch.elevation_per_surface import solver_primitives as SP

    def _nodes(layout, *, readonly=False):
        layout._terrain_host_yield_first_index = 7
        layout._adjacent_ground_first_zone_index = 9
        return [(0.0, 0.0)], {}

    _patch_band_internals(monkeypatch, band=lambda x, y: None)
    monkeypatch.setattr(SP, "_build_node_list", _nodes)
    lay = _layout([1.0])
    oracle._analytic_band(lay)
    assert not hasattr(lay, "_terrain_host_yield_first_index")
    assert not hasattr(lay, "_adjacent_ground_first_zone_index")


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

def test_the_frame_stamp_records_the_tree_the_corpus_and_the_worlds(
        oracle, monkeypatch, tmp_path):
    """KNOWN ANSWER: the frame carries the git HEAD, the code-tree hash,
    the O4_* env, the data mounts and the worlds actually built — and it
    names every guard it REPORTS rather than enforces.

    Before this, ``oracle.py`` called ``HB.build_patch`` directly and
    wrote no env/frame snapshot at all, so an oracle number could not be
    joined to a tree.  ``build_airport.main`` writes both; this path never
    goes through it.
    """
    monkeypatch.setattr(oracle.HB, "cfg_frame_diff",
                        lambda root: {"apt_smoothing_pix": (4, 8)})
    monkeypatch.setattr(oracle.HB, "env_snapshot",
                        lambda root, diff: {"git_head": "abc123",
                                            "git_dirty": True,
                                            "code_tree_hash": "feed",
                                            "o4_env": {"O4_X": "1"}})
    monkeypatch.setattr(oracle.HB, "frame_surface_keys", lambda root: {})
    monkeypatch.setattr(oracle.HB, "data_mounts", lambda root: {
        "Elevation_data": {"present": True, "shared": True},
        "OSM_data": {"present": True, "shared": False}})
    monkeypatch.setattr(oracle.HB, "resolve_tile_for", lambda icao, root: None)

    class _Args:
        icao = "ORCL"
        allow_degraded_dem = True

    frame = oracle._frame_stamp(ROOT, _Args(), WORLDS)
    assert frame["env"]["git_head"] == "abc123"
    assert frame["env"]["git_dirty"] is True
    assert frame["worlds_m"] == WORLDS
    assert frame["ruled_worlds_m"]["plateau"] == -500.0
    assert frame["ruled_worlds_m"]["canyon"] == 10000.0
    assert frame["data_corpus"] == {"shared": 1, "total": 2,
                                    "private": ["OSM_data"]}
    assert frame["allow_degraded_dem"] is True, (
        "the flag's help text promises it is 'accepted and recorded'; "
        "recorded means it appears in an artifact")
    assert "require_dem_frame" in frame["guards_reported_not_enforced"]
    # the divergence, the private corpus and the unresolved tile are all
    # WARNINGS carried out, not silences
    assert len(frame["frame_warnings"]) == 3
    assert any("apt_smoothing_pix" in w for w in frame["frame_warnings"])
    assert any("PRIVATE data corpus" in w for w in frame["frame_warnings"])
    assert any("anchor tile" in w for w in frame["frame_warnings"])


def test_the_run_writes_its_env_and_frame_beside_the_verdicts(
        oracle, cg, monkeypatch, tmp_path):
    """An oracle number must be joinable to a tree from the artifacts
    alone."""
    monkeypatch.setattr(oracle.HB, "cfg_frame_diff", lambda root: {})
    monkeypatch.setattr(oracle.HB, "env_snapshot",
                        lambda root, d: {"git_head": "h", "git_dirty": False,
                                         "code_tree_hash": "t", "o4_env": {}})
    monkeypatch.setattr(oracle.HB, "frame_surface_keys", lambda root: {})
    monkeypatch.setattr(oracle.HB, "data_mounts", lambda root: {})
    monkeypatch.setattr(oracle.HB, "resolve_tile_for", lambda i, r: None)

    def _build_patch(icao, root, out_dir, tag, prog, const_dem=None, **kw):
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"_layout": _layout([10.0, 10.0, 10.0]),
                "patch": str(out_dir / f"{tag}.osm"), "tag": tag}

    monkeypatch.setattr(oracle.HB, "require_build_cwd", lambda p: ROOT)
    monkeypatch.setattr(oracle.HB, "build_patch", _build_patch)
    monkeypatch.setattr(oracle.HC, "census_one",
                        lambda osm, _cg, **kw: _census(cg))
    monkeypatch.setattr(oracle, "_analytic_band",
                        lambda lay: (None, _status(oracle, "no_nodes")))
    oracle.main(["ORCL", "--out", str(tmp_path)])
    env = json.loads((tmp_path / "ORCL_oracle.env.json").read_text())
    frame = json.loads((tmp_path / "ORCL_oracle.frame.json").read_text())
    doc = json.loads((tmp_path / "ORCL_oracle.json").read_text())
    assert env["git_head"] == "h"
    assert frame["join"] and frame["guards_armed"]
    assert doc["frame"]["env"]["code_tree_hash"] == "t", (
        "the verdict document must carry its own frame, not only a "
        "sibling file that can be separated from it")


# ══════════════════════════════════════════════════════════════════════
# §4 THE VERDICTS, END TO END (Tasks 3, 5, and the roll-up)
# ══════════════════════════════════════════════════════════════════════

def test_the_calibrated_PASS(oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER, hand-computed, all four verdicts PASS and rc == 0.

    Plateau seats all 5 nodes at 10.0, canyon at 13.0, analytic band
    (10.0, 13.0) everywhere.
      * compliance: 0 adjudicated rows in both worlds ⇒ PASS.
      * band_width: every node 13.0 − 10.0 = 3.0; nodes 5, pinned 0,
        negative 0 ⇒ PASS.
      * saturation: plateau expects the FLOOR 10.0 and sits at 10.0;
        canyon expects the CEILING 13.0 and sits at 13.0 ⇒ 0 unsaturated
        of 5/5 covered ⇒ PASS.
      * band_agreement: measured 3.0 vs analytic 13.0 − 10.0 = 3.0 ⇒
        delta 0.0 at all 5 ⇒ 0 disagreements, 5 compared ⇒ PASS.
    """
    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                       band=lambda xy: (10.0, 13.0))
    assert v["compliance"]["pass"] is True
    assert v["band_width"]["pass"] is True
    assert v["band_width"]["summary"] == {
        "nodes": 5, "pinned": 0, "negative": 0, "min": 3.0, "p50": 3.0,
        "max": 3.0, "mean": 3.0}
    assert v["saturation"]["pass"] is True
    assert v["saturation"]["plateau"]["coverage"] == {
        "nodes": 5, "with_band": 5, "no_band": 0, "unsaturated": 0}
    assert v["saturation"]["canyon"]["unsaturated"] == 0
    assert v["band_agreement"]["pass"] is True
    assert v["band_agreement"]["compared"] == 5
    assert v["band_agreement"]["disagreements"] == 0
    assert v["band_agreement"]["max_abs_delta_m"] == 0.0
    assert rc == 0
    assert "compliance=PASS" in prog and "band_agreement=PASS" in prog


def test_one_node_off_its_ceiling_shows_in_saturation_AND_agreement(
        oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER, hand-computed.

    Canyon values [13, 13, 12] ⇒ ring vals [13, 13, 12, 12, 13]: the two
    nodes at (2,0) and (2,10) sit 1.0 m BELOW the 13.0 ceiling.
      * saturation canyon: 2 unsaturated, worst off_edge −1.0 ⇒
        SEE-REPORT (plateau still clean).
      * band_width: those two nodes measure 12.0 − 10.0 = 2.0, the other
        three 3.0 ⇒ min 2.0, negative 0 ⇒ still PASS.
      * band_agreement: 2 nodes measure 2.0 against an analytic 3.0 ⇒
        delta −1.0, over the 0.01 m materiality ⇒ 2 disagreements, and
        ``pass`` stays True because the comparison WAS made (it is a
        report, not a gate).
    rc == 1, because saturation did not pass.
    """
    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 12.0],
                       band=lambda xy: (10.0, 13.0))
    assert v["saturation"]["plateau"]["unsaturated"] == 0
    assert v["saturation"]["canyon"]["unsaturated"] == 2
    assert v["saturation"]["canyon"]["by_author"][0]["author"] == "apron/"
    assert (v["saturation"]["canyon"]["by_author"][0]["worst_off_edge_m"]
            == pytest.approx(-1.0))
    assert v["saturation"]["pass"] is False
    assert v["band_width"]["pass"] is True
    assert v["band_width"]["summary"]["min"] == pytest.approx(2.0)
    assert v["band_agreement"]["disagreements"] == 2
    assert v["band_agreement"]["max_abs_delta_m"] == pytest.approx(1.0)
    assert v["band_agreement"]["worst"][0]["measured_width_m"] == 2.0
    assert v["band_agreement"]["worst"][0]["analytic_width_m"] == 3.0
    assert v["band_agreement"]["pass"] is True, (
        "the agreement verdict is a REPORT: 'pass' says the comparison "
        "was made, not that the two suppliers agreed")
    assert rc == 1
    assert "saturation=SEE-REPORT" in prog


def test_a_negative_band_width_is_SEE_REPORT(oracle, cg, monkeypatch,
                                             tmp_path):
    """KNOWN ANSWER: canyon 9.0 below plateau 10.0 at every node ⇒ width
    −1.0, negative 5 ⇒ band_width fails, rc 1.  No monotone seating can
    put the high world below the low one."""
    rc, v, _p = _run(oracle, cg, monkeypatch, tmp_path,
                     lo_vals=[10.0, 10.0, 10.0], hi_vals=[9.0, 9.0, 9.0],
                     band=lambda xy: None)
    assert v["band_width"]["summary"]["negative"] == 5
    assert v["band_width"]["summary"]["min"] == pytest.approx(-1.0)
    assert v["band_width"]["pass"] is False
    assert rc == 1


def test_adjudicated_rows_fail_compliance_and_the_note_carries_the_worlds(
        oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER: 3 adjudicated + 2 version-deferred rows per world.

    ``compliance`` fails on the 3 adjudicated and REPORTS the 2 deferred
    under their own heading (never folded in, never dropped).  The verdict
    sentence — the one sentence in this file that makes a causal claim —
    is world-invariant only because the worlds carry no terrain signal, so
    the CONSTANTS travel with it (Task 3c).
    """
    rc, v, _p = _run(oracle, cg, monkeypatch, tmp_path,
                     lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                     band=lambda xy: (10.0, 13.0),
                     adjudicated=3, deferred=2)
    c = v["compliance"]
    assert c["pass"] is False
    assert c["adjudicated_by_world"] == {"-500": 3, "10000": 3}
    assert c["rows_by_world"] == {"-500": 5, "10000": 5}
    assert (c["version_deferred_by_world"]["-500"]["families"]
            ["drainage_minimum"] == 2)
    assert c["worlds_m"] == WORLDS
    assert c["worlds_are_the_ruled_pair"] is True
    assert "-500 m" in c["note"] and "10000 m" in c["note"], (
        "the claim 'with no terrain signal these are defects' is only "
        "true of the RULED worlds — the constants must travel with it")
    assert "The low extreme is -500 m" in c["worlds_ruling"]
    assert rc == 1


def test_a_RAISED_band_reader_reads_as_DEFECT_in_the_exit_summary(
        oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER: the reader raises ⇒ saturation NOT EVALUATED with
    ``defect`` True, the exit line says ``saturation=DEFECT`` (never
    SEE-REPORT, which would read as a finding about the airport), an
    explicit INSTRUMENT DEFECT line follows, and rc == 1."""
    def _raising(layout):
        return None, {"code": "band_reader_raised", "defect": True,
                      "why": oracle.BAND_STATUS["band_reader_raised"][1],
                      "detail": {"exception": "RuntimeError('boom')"}}

    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                       band=None, analytic_band=_raising)
    for world in ("plateau", "canyon"):
        assert v["saturation"][world]["evaluated"] is False
        assert v["saturation"][world]["defect"] is True
        assert v["saturation"][world]["reason_code"] == "band_reader_raised"
        assert "NOT EVALUATED" in v["saturation"][world]["verdict"]
    assert v["saturation"]["defect"] is True
    assert v["saturation"]["pass"] is False
    assert "saturation=DEFECT" in prog
    assert "saturation=SEE-REPORT" not in prog
    assert "INSTRUMENT DEFECT" in prog
    # the agreement assertion loses its second supplier with the band
    assert v["band_agreement"]["evaluated"] is False
    assert v["band_agreement"]["pass"] is False
    assert rc == 1


def test_an_empty_node_list_reads_as_NOT_EVALUATED_not_as_a_pass(
        oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER: 'no_nodes' is a legitimate answer about the layout,
    so it is NOT a defect — but it is still NOT EVALUATED, and the
    reported reason is the one that happened rather than a list of three
    candidates."""
    def _none(layout):
        return None, {"code": "no_nodes", "defect": False,
                      "why": oracle.BAND_STATUS["no_nodes"][1],
                      "detail": None}

    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                       band=None, analytic_band=_none)
    assert v["saturation"]["plateau"]["reason_code"] == "no_nodes"
    assert v["saturation"]["plateau"]["defect"] is False
    assert v["saturation"]["defect"] is False
    assert v["saturation"]["pass"] is False
    assert "saturation=SEE-REPORT" in prog and "DEFECT" not in prog
    assert rc == 1


def test_a_band_that_answers_None_everywhere_is_NOT_a_clean_pass(
        oracle, cg, monkeypatch, tmp_path):
    """THE LIVE RESURRECTION OF THE CAMPAIGN BUG, and the reason
    ``coverage_out`` exists.

    ``reach_band_unified`` NEVER returns ``None``: when no field can be
    built it returns ``lambda x, y: None`` (its own source says so — "with
    one engine there is nothing to fall back TO").  So ``band is None`` is
    NOT the path a band-less airport takes.  The band factory exists, it
    answers ``None`` at every node, ``saturation_report`` skips every node
    and returns ``[]`` — and ``[]`` is also what a PASS looks like.

    KNOWN ANSWER: 5 nodes, 0 with a band, 0 unsaturated ⇒ evaluated False,
    reason 'zero_coverage', ``pass`` False, rc 1.  Before the coverage
    denominator this scored ``unsaturated == 0`` and PASSED.
    """
    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                       band=lambda xy: None)
    sat = v["saturation"]["plateau"]
    assert sat["unsaturated"] == 0, "the row list is empty, as in a pass"
    assert sat["coverage"] == {"nodes": 5, "with_band": 0, "no_band": 5,
                               "unsaturated": 0}
    assert sat["evaluated"] is False
    assert sat["reason_code"] == "zero_coverage"
    assert sat["defect"] is False, (
        "a band-less layout is a legitimate answer; only the reader "
        "RAISING is a defect")
    assert v["saturation"]["pass"] is False
    assert "zero_coverage" in prog
    # …and the agreement assertion is equally NOT EVALUATED, not passed
    assert v["band_agreement"]["evaluated"] is False
    assert v["band_agreement"]["pass"] is False
    assert "never compared" in v["band_agreement"]["why"]
    assert rc == 1


def test_partial_band_coverage_still_evaluates_what_it_covered(
        oracle, cg, monkeypatch, tmp_path):
    """KNOWN ANSWER: a band at 2 of the 5 nodes ⇒ evaluated True with
    ``with_band`` 2 — coverage is REPORTED, not used to disqualify the
    rows that were checked.  Canyon node (2,0) sits at 12.0 against a
    13.0 ceiling ⇒ exactly 1 unsaturated row."""
    covered = {(0.0, 0.0): (10.0, 13.0), (2.0, 0.0): (10.0, 13.0)}
    rc, v, _p = _run(oracle, cg, monkeypatch, tmp_path,
                     lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 12.0],
                     band=covered)
    assert v["saturation"]["canyon"]["coverage"] == {
        "nodes": 5, "with_band": 2, "no_band": 3, "unsaturated": 1}
    assert v["saturation"]["canyon"]["evaluated"] is True
    assert v["band_agreement"]["compared"] == 2
    assert v["band_agreement"]["no_analytic_band"] == 3
    assert v["band_agreement"]["evaluated"] is True
    assert rc == 1


def test_the_exit_summary_states_every_verdict_and_the_rc_follows_it(
        oracle, cg, monkeypatch, tmp_path):
    """The roll-up contract: one token per verdict carrying a ``pass``
    key, and ``rc == 0`` iff every one of them passed."""
    rc, v, prog = _run(oracle, cg, monkeypatch, tmp_path,
                       lo_vals=[10.0, 10.0, 10.0], hi_vals=[13.0, 13.0, 13.0],
                       band=lambda xy: (10.0, 13.0))
    exit_line = [ln for ln in prog.splitlines() if "EXIT oracle" in ln][-1]
    for name in ("compliance", "band_width", "saturation", "band_agreement"):
        assert f"{name}=" in exit_line, f"{name} missing from the exit line"
    assert set(v) == {"compliance", "band_width", "saturation",
                      "band_agreement"}
    assert rc == 0
    assert all(x.get("pass") for x in v.values())


def test_the_allow_degraded_dem_flag_is_actually_recorded(
        oracle, cg, monkeypatch, tmp_path):
    """The flag's help text promised "accepted and recorded" while
    ``args.allow_degraded_dem`` was read NOWHERE in the file — a claim the
    code did not verify, inside an argument's own help.  It is recorded
    now, with what it does and does not authorise."""
    monkeypatch.setattr(oracle.HB, "cfg_frame_diff", lambda root: {})
    monkeypatch.setattr(oracle.HB, "env_snapshot", lambda r, d: {})
    monkeypatch.setattr(oracle.HB, "frame_surface_keys", lambda root: {})
    monkeypatch.setattr(oracle.HB, "data_mounts", lambda root: {})
    monkeypatch.setattr(oracle.HB, "resolve_tile_for", lambda i, r: None)

    class _Args:
        icao = "ORCL"
        allow_degraded_dem = True

    frame = oracle._frame_stamp(ROOT, _Args(), WORLDS)
    assert frame["allow_degraded_dem"] is True
    assert "-500" in frame["allow_degraded_dem_effect"]
    assert "does NOT authorise" in frame["allow_degraded_dem_effect"]
    _Args.allow_degraded_dem = False
    assert oracle._frame_stamp(ROOT, _Args(), WORLDS)[
        "allow_degraded_dem"] is False
