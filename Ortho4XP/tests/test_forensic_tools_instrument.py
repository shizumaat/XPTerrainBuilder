"""KNOWN-ANSWER CALIBRATION for the four forensic-tool instruments.

RULINGS 2026-08-06, "Instrument truth is law", binding point 1: *every
instrument carries a calibration twin feeding it a case whose answer is
known and asserting the report.*  Before the cycle-7.5 sweep these four
tools had **zero** tests between them:

  * ``tools/interval_reach_replay.py`` — and its ``--arm free-seams``
    selector had been dead since ``092af7f`` replaced the
    ``seed_rwy_seam`` blanket constant with the real classifier.  It
    matched nothing, freed nothing, and reported "no difference" — a
    silently degrading instrument, which is the defect binding point 2
    names.
  * ``tools/flex_audit.py`` — reading the sidecar key ``axes`` when the
    law spelling had become ``axes_exact``, so every cluster printed "no
    taxi axis nearby": a silent wrong answer that reads as an
    EXCULPATORY finding.
  * ``tools/trace_reach_route.py`` — its BUDGET DRIFT line asserted
    "different frames" from a bare numeric difference.
  * ``tools/patch_provenance.py`` — the library underneath is well
    twinned; the TOOL, including the exit-code contract its own docstring
    advertises for CI gating, was not.

Every answer below is hand-derived and stated before it is asserted.
No build, no network, ``tmp_path`` only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def irr():
    return _load("twin_interval_reach_replay", TOOLS / "interval_reach_replay.py")


@pytest.fixture(scope="module")
def fa():
    return _load("twin_flex_audit", TOOLS / "flex_audit.py")


@pytest.fixture(scope="module")
def pp():
    return _load("twin_patch_provenance", TOOLS / "patch_provenance.py")


@pytest.fixture(scope="module")
def trr():
    return _load("twin_trace_reach_route", TOOLS / "trace_reach_route.py")


# ══════════════════════════════════════════════════════════════════════
# interval_reach_replay — the arm that went dead in 092af7f
# ══════════════════════════════════════════════════════════════════════

def _state(hard_cat: dict | None, **extra) -> dict:
    """A minimal solve-state dump.  ``entries``/``hard`` are what
    ``_apply_arm`` slices; only their sizes matter here."""
    st = {"entries": [{"edges": [(0, 1, 1.0, 2.0)]}],
          "hard": {0, 1, 2, 3},
          "node_bounds": {}, "group_bounds": {}}
    if hard_cat is not None:
        st["hard_cat"] = hard_cat
    st.update(extra)
    return st


def test_the_seam_arm_selects_the_current_classes_not_the_dead_literal(irr):
    """KNOWN ANSWER.  hard_cat = {0: seam_pin, 1: rwy_profile,
    2: seam_spine_anchor, 3: rwy_join} and hard = {0,1,2,3}.  The seam
    classes are exactly {seam_pin, seam_spine_anchor} = nodes 0 and 2, so
    free-seams must free 2 anchors and leave {1, 3} hard.

    Under the pre-sweep code this selected on the literal
    ``"seed_rwy_seam"``, matched NOTHING, and returned all four still
    hard — byte-identical to --arm production.
    """
    st = _state({0: "seam_pin", 1: "rwy_profile",
                 2: "seam_spine_anchor", 3: "rwy_join"})
    _e, hard, _nb, _gb = irr._apply_arm(
        "free-seams", st["entries"], st["hard"],
        st["node_bounds"], st["group_bounds"], st)
    assert hard == {1, 3}, "free-seams must free exactly the seam classes"
    assert set(irr.SEAM_CLASSES) == {"seam_pin", "seam_spine_anchor"}
    assert "seed_rwy_seam" not in irr.HARD_CLASSES_CURRENT


def test_a_zero_match_seam_arm_REFUSES_and_names_what_the_dump_carries(irr):
    """KNOWN ANSWER: a dump whose hard anchors are all runway-surface
    values carries NO seam class, so the arm cannot run.  It must RAISE,
    not return the production set — and the message must carry the class
    census so the reader can see what was actually there."""
    st = _state({0: "rwy_profile", 1: "rwy_profile",
                 2: "rwy_join", 3: "rwy_flexed"})
    with pytest.raises(SystemExit) as excinfo:
        irr._apply_arm("free-seams", st["entries"], st["hard"],
                       st["node_bounds"], st["group_bounds"], st)
    msg = str(excinfo.value)
    assert "REFUSING --arm free-seams" in msg
    assert "ZERO" in msg
    # The whole point: it says the run WOULD have looked like production.
    assert "no difference" in msg
    assert "rwy_profile" in msg and "rwy_join" in msg


def test_a_LEGACY_blanket_dump_is_refused_not_silently_equated(irr):
    """A pre-092af7f dump DOES carry ``seed_rwy_seam`` — on every base-hard
    node, whatever made it hard.  Freeing that class is ``--arm free-hard``
    wearing this arm's name.  Reading it as the seam intervention is the
    two-instruments trap, so it must refuse and say so."""
    st = _state({i: irr.HARD_CLASS_LEGACY_BLANKET for i in range(4)})
    with pytest.raises(SystemExit) as excinfo:
        irr._apply_arm("free-seams", st["entries"], st["hard"],
                       st["node_bounds"], st["group_bounds"], st)
    msg = str(excinfo.value)
    assert "LEGACY" in msg and "BLANKET CONSTANT" in msg
    assert "free-hard" in msg


def test_a_dump_with_no_class_axis_is_refused(irr):
    """No ``hard_cat`` at all is a third state: the classes cannot be
    selected, so no seam claim is computable."""
    with pytest.raises(SystemExit) as excinfo:
        st = _state(None)
        irr._apply_arm("free-seams", st["entries"], st["hard"],
                       st["node_bounds"], st["group_bounds"], st)
    assert "NO hard_cat" in str(excinfo.value)


def test_production_is_the_identity_arm(irr):
    """The control arm must be exactly the inputs — otherwise every A/B
    against it measures the arm machinery instead of the intervention."""
    st = _state({0: "seam_pin"})
    out = irr._apply_arm("production", st["entries"], st["hard"],
                         st["node_bounds"], st["group_bounds"], st)
    assert out == (st["entries"], st["hard"],
                   st["node_bounds"], st["group_bounds"])


# ══════════════════════════════════════════════════════════════════════
# flex_audit — the sidecar spelling that made every answer exculpatory
# ══════════════════════════════════════════════════════════════════════

def test_the_law_spelling_is_read_first_and_is_reported(fa):
    """KNOWN ANSWER: a sidecar carrying BOTH spellings must resolve to the
    LAW one (``axes_exact``), because the two do not carry the same caps —
    so a number quoted without its spelling is a number without its law."""
    axes, spelling = fa.load_axes({"axes_exact": [{"cap": 0.02}],
                                   "axes": [{"cap": 0.05}, {"cap": 0.05}]})
    assert spelling == "axes_exact"
    assert len(axes) == 1 and axes[0]["cap"] == 0.02
    assert fa.AXES_KEYS[0] == "axes_exact", "law spelling must be first"


def test_a_legacy_only_sidecar_still_loads_and_says_which_spelling(fa):
    """The fallback must work AND be visible — a legacy read that looks
    identical to a law read is the frame gap this tool had."""
    axes, spelling = fa.load_axes({"axes": [{"cap": 0.05}]})
    assert spelling == "axes" and len(axes) == 1


def test_a_modern_sidecar_is_no_longer_read_as_zero_axes(fa):
    """THE REGRESSION LOCK.  Before the sweep, ``sidecar.get("axes")`` on a
    sidecar carrying only ``axes_exact`` returned nothing, so every cluster
    printed 'no taxi axis nearby' — an exculpatory finding produced by a
    key rename.  A law-spelled sidecar must now yield its axes."""
    axes, spelling = fa.load_axes({"axes_exact": [{"cap": 0.02}, {"cap": 0.02}]})
    assert (len(axes), spelling) == (2, "axes_exact")


def test_an_empty_sidecar_yields_no_axes_and_no_spelling(fa):
    """Zero axes must be DISTINGUISHABLE from 'axes loaded, none nearby' —
    the caller refuses on this, rather than reporting a clean audit."""
    assert fa.load_axes({}) == ([], None)
    assert fa.load_axes({"axes_exact": []}) == ([], None)


def test_the_patch_frame_reader_names_its_failure(fa, tmp_path):
    """``patch_frame`` must never crash the audit and must never return a
    bare None that reads as 'clean tree' — an unstamped patch gets a
    stated reason."""
    p = tmp_path / "unstamped.patch.osm"
    p.write_text("<?xml version='1.0'?>\n<osm version='0.6'></osm>\n")
    sha, note = fa.patch_frame(str(p))
    assert sha is None and isinstance(note, str) and note


# ══════════════════════════════════════════════════════════════════════
# trace_reach_route — node space as a MEASURED fact, and the drift contract
# ══════════════════════════════════════════════════════════════════════

class _G:
    """A 4-node chain 0—1—2—3, every hop budget 1.0 m."""

    def __init__(self):
        self.pos = {0: (0.0, 0.0), 1: (1.0, 0.0),
                    2: (2.0, 0.0), 3: (3.0, 0.0)}
        self.spine_adj = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 1.0)],
                          2: [(1, 1.0), (3, 1.0)], 3: [(2, 1.0)]}


def test_the_node_space_token_is_a_fact_two_reports_can_be_compared_on(trr):
    """Solver node ids are valid only inside the one ``_build_node_list``
    call that assigned them.  The token must therefore DIFFER between two
    graphs and be STABLE for one — that is what turns 'different frames'
    from an asserted cause into a measured fact."""
    g1, g2 = _G(), _G()
    assert trr._nodespace(g1) == trr._nodespace(g1)
    assert trr._nodespace(g1) != trr._nodespace(g2)
    assert "n=4" in trr._nodespace(g1)
    assert trr._nodespace(None) == "none"


def test_the_edge_budget_is_read_never_re_derived(trr):
    """KNOWN ANSWER: hop 0→1 is priced 1.0; a pair with no edge is None,
    not 0.0 — a missing edge and a free edge are different findings."""
    g = _G()
    assert trr._edge_budget(g, 0, 1) == 1.0
    assert trr._edge_budget(g, 0, 3) is None


def test_the_walk_replays_the_recorded_route_and_reports_completeness(trr):
    """KNOWN ANSWER.  Anchor 0; recorded budgets 0/1/2/3 m at nodes
    0/1/2/3.  Walking from node 3 must reproduce the chain [0,1,2,3]
    (anchor-first) and report path_complete=True, because every hop
    reconciles: rec[v] + edge == rec[u] exactly."""
    g = _G()
    prov = {0: (0, 0.0), 1: (0, 1.0), 2: (0, 2.0), 3: (0, 3.0)}
    path, complete = trr._walk_to_anchor(g, prov, 3, 0)
    assert path == [0, 1, 2, 3]
    assert complete is True


def test_a_route_that_does_not_reconcile_is_INCOMPLETE_not_invented(trr):
    """KNOWN ANSWER: node 2's recorded budget is 9.0 m, which no hop from
    node 3 reconciles.  The walk must STOP and say so rather than let a
    second metric quietly invent a path."""
    g = _G()
    prov = {0: (0, 0.0), 1: (0, 1.0), 2: (0, 9.0), 3: (0, 3.0)}
    path, complete = trr._walk_to_anchor(g, prov, 3, 0)
    assert complete is False
    assert path[0] == 3, "an incomplete walk returns what it reached"


def test_the_budget_agreement_contract_is_a_named_constant(trr):
    """Binding point 4 needs a MATERIALITY, not a bare literal buried in a
    format string.  The drift comparison is the agreement assertion for the
    route-budget quantity, so its contract has to be nameable and quotable."""
    assert isinstance(trr.ROUTE_BUDGET_AGREEMENT_M, float)
    assert trr.ROUTE_BUDGET_AGREEMENT_M > 0
    src = (TOOLS / "trace_reach_route.py").read_text()
    assert "do not equate" not in src, (
        "the BUDGET DRIFT line must report the number and the measured "
        "frame comparison, not instruct the reader")


# ══════════════════════════════════════════════════════════════════════
# patch_provenance — the discriminated absence, and the EXIT-CODE contract
# ══════════════════════════════════════════════════════════════════════

_STAMPED = (
    "<?xml version='1.0' encoding='UTF-8'?>\n"
    "<osm version='0.6' generator='auto_patch' "
    "o4_provenance_sha='{sha}' o4_provenance_dirty='{dirty}' "
    "o4_provenance_icao='HEAZ' o4_provenance_built='2026-08-06T13:03:00' "
    "o4_provenance_gates='' o4_provenance_dem='{dem}'>\n</osm>\n"
)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_the_absence_reason_is_discriminated_not_a_catch_all(pp, tmp_path):
    """KNOWN ANSWERS, four distinct states that the old single sentence
    '(unstamped or unreadable)' fused into one bucket."""
    missing = tmp_path / "nope.patch.osm"
    assert pp.stamp_absence_reason(str(missing)) == "no such file"

    d = tmp_path / "adir.patch.osm"
    d.mkdir()
    assert "directory" in pp.stamp_absence_reason(str(d))

    empty = _write(tmp_path, "empty.patch.osm", "")
    assert pp.stamp_absence_reason(str(empty)) == "file is empty"

    notxml = _write(tmp_path, "junk.patch.osm", "this is not osm at all\n")
    assert "no <osm> root" in pp.stamp_absence_reason(str(notxml))

    bare = _write(tmp_path, "bare.patch.osm",
                  "<?xml version='1.0'?>\n<osm version='0.6'></osm>\n")
    assert "no o4_provenance_* attributes" in pp.stamp_absence_reason(str(bare))


def test_an_unstamped_patch_prints_its_actual_condition(pp, tmp_path, capsys):
    bare = _write(tmp_path, "bare.patch.osm",
                  "<?xml version='1.0'?>\n<osm version='0.6'></osm>\n")
    pp._print_human(str(bare), None)
    out = capsys.readouterr().out
    assert "NO PROVENANCE STAMP" in out
    assert "no o4_provenance_* attributes" in out
    assert "unstamped or unreadable" not in out


def test_the_raw_dem_line_states_the_fact_and_defers_severity(pp, capsys):
    """KNOWN ANSWER: ``dem_raw`` is a verified boolean from the stamp.
    'WARNING' was the report deciding severity while ``main`` decided it
    again, differently — only ``--strict-raw`` reaches the exit code."""
    pp._print_human("x.patch.osm", {
        "sha": "abc123", "dirty": "false", "icao": "HEAZ",
        "built": "2026-08-06T13:03:00", "gates_on": [], "gates_total": 12,
        "gates_nondefault": [], "dem": "base RAW (no inset baked)",
        "dem_raw": True})
    out = capsys.readouterr().out
    assert "raw base DEM, no inset baked" in out
    assert "--strict-raw" in out
    assert "WARNING" not in out


def test_a_clean_stamped_patch_exits_zero(pp, tmp_path, capsys):
    """EXIT-CODE CONTRACT, case 0: everything stamped, tree clean, DEM
    inset baked ⇒ 0."""
    p = _write(tmp_path, "clean.patch.osm",
               _STAMPED.format(sha="abc123", dirty="false",
                               dem="base+inset(HEAZ)"))
    assert pp.main([str(p)]) == 0
    assert "NO PROVENANCE STAMP" not in capsys.readouterr().out


def test_a_dirty_or_unstamped_patch_exits_one(pp, tmp_path):
    """EXIT-CODE CONTRACT, case 1: a dirty tree, and separately a missing
    stamp, each fail the gate."""
    dirty = _write(tmp_path, "dirty.patch.osm",
                   _STAMPED.format(sha="abc123", dirty="true",
                                   dem="base+inset(HEAZ)"))
    assert pp.main([str(dirty)]) == 1

    bare = _write(tmp_path, "bare2.patch.osm",
                  "<?xml version='1.0'?>\n<osm version='0.6'></osm>\n")
    assert pp.main([str(bare)]) == 1


def test_a_missing_file_or_empty_selection_exits_two(pp, tmp_path):
    """EXIT-CODE CONTRACT, case 2: the tool could not read what it was
    asked about.  Distinct from 1 — 'the gate failed' and 'the gate never
    ran' must not share an exit code."""
    assert pp.main([str(tmp_path / "absent.patch.osm")]) == 2
    empty_dir = tmp_path / "nothing"
    empty_dir.mkdir()
    assert pp.main([str(empty_dir)]) == 2


def test_strict_raw_is_the_only_thing_that_makes_a_raw_dem_fail(pp, tmp_path):
    """KNOWN ANSWER: the same clean-but-raw patch is 0 without the flag and
    1 with it — severity lives in one place, the exit code."""
    raw = _write(tmp_path, "raw.patch.osm",
                 _STAMPED.format(sha="abc123", dirty="false",
                                 dem="base RAW (no inset baked)"))
    assert pp.main([str(raw)]) == 0
    assert pp.main([str(raw), "--strict-raw"]) == 1


def test_the_json_mode_emits_one_array_of_decoded_records(pp, tmp_path, capsys):
    p = _write(tmp_path, "j.patch.osm",
               _STAMPED.format(sha="deadbeef", dirty="false",
                               dem="base+inset(HEAZ)"))
    pp.main([str(p), "--json"])
    records = json.loads(capsys.readouterr().out)
    assert isinstance(records, list) and len(records) == 1
    assert records[0]["provenance"]["sha"] == "deadbeef"
    assert records[0]["provenance"]["icao"] == "HEAZ"


def test_a_directory_expands_to_its_patch_files(pp, tmp_path):
    """KNOWN ANSWER: two patches in a tile directory, one non-patch file
    that must NOT be collected."""
    d = tmp_path / "tile"
    d.mkdir()
    for name in ("a.patch.osm", "b.patch.osm"):
        (d / name).write_text(_STAMPED.format(
            sha="abc", dirty="false", dem="base+inset(X)"))
    (d / "notes.txt").write_text("ignore me")
    assert len(pp._collect_patch_files([str(d)])) == 2


# ══════════════════════════════════════════════════════════════════════
# interval_reach_replay — THE BOX KNIVES (c9air, 2026-08-06)
#
# ``--arm no-boxes`` frees the hard anchors AND drops every bound in one
# move, so a residual it clears is attributed no further than "boxes or
# hardness".  These three arms each drop ONE bound class with the hard
# set untouched, which is what makes the 2x2 readable.
# ══════════════════════════════════════════════════════════════════════

def _box_state():
    """A dump with both bound classes and a named groundside-pin subset:
    node bounds on 5 and 6, of which 6 is the groundside pin."""
    return {"entries": [{"edges": [(0, 1, 1.0)]}],
            "hard": {0, 1},
            "node_bounds": {5: (-1.0, 1.0), 6: (-1e18, -0.5)},
            "group_bounds": [(0.0, 1.0), None],
            "hard_cat": {0: "rwy_profile", 1: "rwy_join"},
            "fp8_kwargs": {"gs_pin_nodes": [6]}}


def test_the_box_knives_each_drop_one_class_and_keep_the_hard_set(irr):
    """KNOWN ANSWER, one dump, three arms:

    * ``no-node-boxes``  -> node bounds gone, group bounds kept, hard kept
    * ``no-group-boxes`` -> group bounds gone, node bounds kept, hard kept
    * ``no-gs-pin-boxes``-> ONLY node 6 (the named pin) gone; 5 kept
    """
    st = _box_state()
    _e, hard, nb, gb = irr._apply_arm(
        "no-node-boxes", st["entries"], st["hard"],
        st["node_bounds"], st["group_bounds"], st)
    assert nb is None and gb == st["group_bounds"] and hard == {0, 1}

    _e, hard, nb, gb = irr._apply_arm(
        "no-group-boxes", st["entries"], st["hard"],
        st["node_bounds"], st["group_bounds"], st)
    assert gb is None and nb == st["node_bounds"] and hard == {0, 1}

    _e, hard, nb, gb = irr._apply_arm(
        "no-gs-pin-boxes", st["entries"], st["hard"],
        st["node_bounds"], st["group_bounds"], st)
    assert set(nb) == {5}, "only the groundside-pin bound may be dropped"
    assert gb == st["group_bounds"] and hard == {0, 1}


@pytest.mark.parametrize("arm,empty", [
    ("no-node-boxes", {"node_bounds": {}}),
    ("no-group-boxes", {"group_bounds": [None, None]}),
    ("no-gs-pin-boxes", {"fp8_kwargs": {"gs_pin_nodes": []}}),
])
def test_a_box_knife_with_nothing_to_cut_REFUSES(irr, arm, empty):
    """A bound class the dump does not carry would replay identically to
    production and read as "this class owns nothing" — the free-seams
    failure mode.  Every knife refuses instead, naming the census."""
    st = {**_box_state(), **empty}
    with pytest.raises(SystemExit) as excinfo:
        irr._apply_arm(arm, st["entries"], st["hard"],
                       st["node_bounds"], st["group_bounds"], st)
    msg = str(excinfo.value)
    assert f"REFUSING --arm {arm}" in msg and "ZERO" in msg


def test_every_named_arm_is_reachable_from_the_cli_choices(irr):
    """The knives are useless if ``--arm`` will not accept them."""
    for arm in ("no-node-boxes", "no-group-boxes", "no-gs-pin-boxes"):
        assert arm in irr.ARMS


def test_the_pad_rigidity_knife_validates_here_and_applies_in_do_replay(irr):
    """``no-pad-groups`` intervenes on ``flat_groups``, which is not one
    of the four values ``_apply_arm`` slices — so it is VALIDATED here
    (one refusal law for every arm) and APPLIED in ``do_replay``.  The
    registry that carries it across must name it, or the arm would print
    its banner and change nothing."""
    st = {**_box_state(), "pad_groups": [{1, 2}, {3, 4}]}
    out = irr._apply_arm("no-pad-groups", st["entries"], st["hard"],
                         st["node_bounds"], st["group_bounds"], st)
    # a pass-through for the four sliced values: the pads are dissolved
    # by do_replay, and nothing else may change.
    assert out == (st["entries"], st["hard"],
                   st["node_bounds"], st["group_bounds"])
    assert "no-pad-groups" in irr.PAD_GROUP_ARMS
    assert "no-pad-groups" in irr.ARMS


def test_the_pad_rigidity_knife_REFUSES_when_there_are_no_pads(irr):
    st = {**_box_state(), "pad_groups": []}
    with pytest.raises(SystemExit) as excinfo:
        irr._apply_arm("no-pad-groups", st["entries"], st["hard"],
                       st["node_bounds"], st["group_bounds"], st)
    assert "REFUSING --arm no-pad-groups" in str(excinfo.value)
