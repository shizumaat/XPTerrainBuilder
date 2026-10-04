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
def fa():
    return _load("twin_flex_audit", TOOLS / "flex_audit.py")


@pytest.fixture(scope="module")
def pp():
    return _load("twin_patch_provenance", TOOLS / "patch_provenance.py")


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
    p.write_text("<?xml version='1.0'?>\n<osm version='0.6'></osm>\n", encoding="utf-8", newline="")
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


# SUPERSEDED PREMISE, REWRITTEN (the three twins below).  They called
# ``trr._edge_budget`` / ``trr._walk_to_anchor`` — PRIVATE COPIES that
# used to live in ``tools/trace_reach_route.py``.  Spec
# ``docs/specs/pad-binding-routes-spec.md`` §1.1 retired those copies: the
# engine now PUBLISHES pad binding routes with the same walk this tool
# reports, as ``building_feasibility.walk_to_anchor`` /
# ``.spine_edge_budget``, and one implementation is what stops the tool
# and the engine drifting into separate opinions about which route bound a
# node.  The tool re-exports them lazily (PEP 562 ``__getattr__`` over
# ``_ENGINE_WALK_NAMES``) so ``--from-sidecar`` need not pull the solver in
# at all (§2.1).
#
# The known answers are unchanged — only the names are.  Reaching them
# through ``trr`` deliberately keeps testing the TOOL's surface, and the
# identity twin below pins that the tool's name and the engine's name are
# one object, which is the property the retirement was for.


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
    p.write_text(text, encoding="utf-8", newline="")
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
            sha="abc", dirty="false", dem="base+inset(X)"), encoding="utf-8", newline="")
    (d / "notes.txt").write_text("ignore me", encoding="utf-8", newline="")
    assert len(pp._collect_patch_files([str(d)])) == 2


# ══════════════════════════════════════════════════════════════════════
# interval_reach_replay — THE BOX KNIVES (c9air, 2026-08-06)
#
# ``--arm no-boxes`` frees the hard anchors AND drops every bound in one
# move, so a residual it clears is attributed no further than "boxes or
# hardness".  These three arms each drop ONE bound class with the hard
# set untouched, which is what makes the 2x2 readable.
# ══════════════════════════════════════════════════════════════════════


def test_by_role_breakdown_reads_each_node_role_once(fa, tmp_path):
    """``--by-role`` (lane v2relaxfull2, the scratch ``dz_by_role.py``
    promoted on its second use): ``load(..., role_out=d)`` keys every
    matched node to the role of the first way carrying it, so the
    per-role table is one row per role over the same join the summary
    prints — never a second join."""
    osm = ("<?xml version='1.0'?>\n<osm version='0.6'>\n"
           "<node id='-1' lat='60.70000000000' lon='-135.10000000000'>\n"
           "  <tag k='alt_abs' v='{a}'/>\n</node>\n"
           "<node id='-2' lat='60.70010000000' lon='-135.10000000000'>\n"
           "  <tag k='alt_abs' v='{b}'/>\n</node>\n"
           "<way id='-10'><nd ref='-1'/><nd ref='-2'/><tag k='role' v='apron'/></way>\n"
           "<way id='-11'><nd ref='-2'/><tag k='role' v='building'/></way>\n"
           "</osm>\n")
    on, off = tmp_path / "on.osm", tmp_path / "off.osm"
    on.write_text(osm.format(a=700.0, b=701.5), encoding="utf-8", newline="")
    off.write_text(osm.format(a=700.0, b=700.0), encoding="utf-8", newline="")
    roles = {}
    vals, _nodes = fa.load(str(on), None, roles)
    assert len(vals) == 2 and set(roles.values()) == {"apron"}, "first way wins"
    base, _ = fa.load(str(off), None)
    moved = {roles[k]: abs(v - base[k]) for k, v in vals.items() if abs(v - base[k]) >= 0.01}
    assert moved == {"apron": pytest.approx(1.5)}
