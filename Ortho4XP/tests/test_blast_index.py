"""Headless tests for tools/blast.py (the blast-radius index).

No network, no X-Plane, no airport build: one real index build into a
tmp_path (~2 s) plus pure-function assertions on synthetic shards.
"""
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
# The repo root has no __pycache__ rule (only Ortho4XP/.gitignore does), so
# importing from tools/ must not litter an untracked bytecode dir there.
sys.dont_write_bytecode = True

import blast  # noqa: E402

LAYOUT = "Ortho4XP/src/auto_patch/layout.py"
STRIPS = "Ortho4XP/src/auto_patch/pavement/strips.py"


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """One real build, into a throwaway dir (never the repo's .blast_index)."""
    return blast.build(str(tmp_path_factory.mktemp("blast_index")))


# ---------------------------------------------------------------- R1 canaries
def test_relative_imports_resolve_layout_has_all_importers(index):
    card = index["modules"][LAYOUT]
    assert len(card["imported_by"]) >= 120, (
        "layout.py has 753 relative importers in auto_patch/; a low count "
        "means ast.ImportFrom node.level is being ignored again")


def test_submodule_package_gets_a_card(index):
    """`from .pavement import strips` must produce an edge to strips.py."""
    card = index["modules"].get(STRIPS)
    assert card is not None, "strips.py must be indexed, not silently dropped"
    assert len(card["imported_by"]) >= 1
    assert LAYOUT in card["imported_by"]


def test_role_aliases_resolved_through_strips(index):
    for value in ("apron", "primary_parallel", "runway"):
        assert value in index["roles"], (
            "%s is aliased from pavement/strips.py; a regex that only sees "
            "direct string assigns in layout.py loses it" % value)


def test_role_confidence_split_is_stored_not_printed(index):
    assert set(index["roles"]["apron"]) == {"high", "low"}
    assert LAYOUT in index["roles"]["apron"]["high"]
    lows = {f for v in index["roles"].values() for f in v["low"]}
    for rel in lows - {f for v in index["roles"].values() for f in v["high"]}:
        assert not any(line.startswith("ROLE LITERALS HERE")
                       for line in blast.render(rel, index))


# ------------------------------------------------------- R2 fail-loud output
def test_nonexistent_path_exits_2_and_prints_no_card(tmp_path, index):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = blast.cmd_query("Ortho4XP/src/auto_patch/no_such_file.py",
                             str(tmp_path / "idx"))
    assert rc == 2
    assert "no such file in repo" in err.getvalue()
    assert "===" not in out.getvalue()


def test_nonexistent_path_exit_code_via_cli(tmp_path):
    proc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "blast.py"), "nope/nope.py",
         "--index-dir", str(tmp_path / "idx")],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "ERROR: no such file in repo" in proc.stderr


def test_out_of_scope_file_is_not_a_safety_claim(index, capsys):
    assert blast.render("Ortho4XP/STATUS.md", index) == []
    blast.render(LAYOUT, index)                       # scoped file still works


def test_zero_relationship_file_says_indexed_not_missing(index):
    quiet = [r for r, c in index["modules"].items()
             if r.endswith(".py") and not c.get("imported_by")]
    assert quiet, "expected at least one leaf module"
    line = blast.render(quiet[0], index)[0]
    assert line.startswith("indexed (") and "no direct importers recorded" in line
    assert "leaf" not in line


# ---------------------------------------------------- path normalization (R2)
def test_three_path_forms_resolve_identically():
    forms = [os.path.join(REPO, LAYOUT), LAYOUT, "src/auto_patch/layout.py"]
    resolved = [blast.normalize(f) for f in forms]
    assert resolved == [(LAYOUT, True)] * 3


# ------------------------------------------------------------- R6 wire drift
def test_wire_drift_prints_loud_when_python_only_non_empty(index):
    synthetic = dict(index["wire"], python_only=["GhostEvent"], swift_only=[])
    lines = blast._wire_lines(synthetic)
    assert any("WIRE DRIFT -- FIX BEFORE SHIP" in x and "GhostEvent" in x
               for x in lines)
    assert not any("verified in sync" in x for x in lines)


def test_wire_in_sync_claim_requires_both_drift_lists_empty(index):
    clean = dict(index["wire"], python_only=[], swift_only=[])
    assert any("verified in sync (%d events)" % len(clean["events"]) in x
               for x in blast._wire_lines(clean))
    both = dict(index["wire"], python_only=[], swift_only=["Stale"])
    assert not any("verified in sync" in x for x in blast._wire_lines(both))


def test_incomplete_command_scan_says_so(index):
    lines = blast._wire_lines(dict(index["wire"], commands_swift=[],
                                   commands_scan="incomplete"))
    assert any("scan INCOMPLETE" in x and "NOT covered" in x for x in lines)


def test_events_card_carries_the_wire_section(index):
    lines = blast.render(blast.EVENTS_PY, index)
    assert any(x.startswith("WIRE PROTOCOL") for x in lines)


# --------------------------------------------------------------- R4 env flags
def test_flag_shard_uses_read_in_tests_and_records_default_sets(index):
    for name, rec in index["flags"].items():
        assert "read_in_tests" in rec and "tested" not in rec
        assert isinstance(rec["defaults"], list)
        assert rec["default_conflict"] == (len(rec["defaults"]) > 1)


def test_conflicting_flag_defaults_produce_a_warning_line(index):
    rel = LAYOUT
    synthetic = dict(index, flags={"O4_FAKE_FLAG": {
        "defaults": ["'0'", "'1'"], "default_conflict": True,
        "files": [rel], "read_in_tests": False}})
    lines = blast.render(rel, synthetic)
    assert any("ENV FLAGS READ HERE" in x and "read in no test file" in x
               for x in lines)
    assert any("WARNING: O4_FAKE_FLAG has conflicting defaults" in x
               and "'0'" in x and "'1'" in x for x in lines)
    assert not any("untested" in x for x in lines)


# ------------------------------------------------------------ R7 swift target
def test_swift_card_has_no_python_only_lines(index):
    lines = blast.render(blast.SWIFT_CLIENT, index)
    assert lines and lines[0].startswith("swift: co-change + wire coverage only")
    for line in lines:
        assert not line.startswith(("TESTS", "IMPORTED BY", "HOT SYMBOLS",
                                    "ROLE LITERALS", "ENV FLAGS", "indexed ("))
    assert any(x.startswith("WIRE PROTOCOL") for x in lines)


def test_cochange_is_labelled_a_weak_signal(index):
    cards = [(r, c) for r, c in index["modules"].items() if c.get("cochange")]
    assert cards, "expected some co-change coupling in 200+ commits"
    rel, _ = cards[0]
    assert any("CO-CHANGED (historical, weak signal):" in x
               for x in blast.render(rel, index))


# ----------------------------------------------------------------- meta/shape
def test_meta_records_staleness_fingerprint_and_shards_exist(tmp_path):
    idx = str(tmp_path / "idx")
    blast.build(idx)
    for name in blast.SHARDS:
        assert os.path.exists(os.path.join(idx, name + ".json"))
    with open(os.path.join(idx, "meta.json")) as fh:
        meta = json.load(fh)
    assert meta["head_sha"] and len(meta["dirty_hash"]) == 64
    assert meta["version"] == blast.VERSION
    assert meta["parse_failures"] == []
    out = io.StringIO()
    with redirect_stdout(out):
        blast.ensure_fresh(idx)                       # fresh: must not rebuild
    assert out.getvalue() == ""
    meta["head_sha"] = "0" * 40
    with open(os.path.join(idx, "meta.json"), "w") as fh:
        json.dump(meta, fh)
    with redirect_stdout(out):
        blast.ensure_fresh(idx)
    assert "index rebuilt (stale)" in out.getvalue()


def test_tests_line_drops_conftest_and_is_hedged(index):
    for rel, card in index["modules"].items():
        conftests = [t for t in card.get("tests", ())
                     if os.path.basename(t) == "conftest.py"]
        if not conftests:
            continue
        for line in blast.render(rel, index):
            if line.startswith("TESTS"):
                assert "may miss dynamic use" in line
                assert "conftest.py" not in line
        break
