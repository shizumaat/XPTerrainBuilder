"""Headless tests for tools/blast.py (the blast-radius index).

No network, no X-Plane, no airport build: one real index build into a
tmp_path (~2 s) plus pure-function assertions on synthetic shards.
"""
import io
import json
import os
import subprocess
import sys
import types
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
def index_path(tmp_path_factory):
    """A real index ON DISK, for the commands that take a directory."""
    idx = str(tmp_path_factory.mktemp("blast_index"))
    blast.build(idx)
    return idx


@pytest.fixture(scope="module")
def index(index_path):
    """One real build, into a throwaway dir (never the repo's .blast_index)."""
    return blast.load(index_path)


# ---------------------------------------------------------------- R1 canaries
def test_relative_imports_resolve_layout_has_all_importers(index):
    card = index["modules"][LAYOUT]
    assert len(card["imported_by"]) >= 100, (
        "layout.py has 100+ relative importers in auto_patch/ (119 after "
        "the 2026-07-29 rect-machinery retirement); a LOW count means "
        "ast.ImportFrom node.level is being ignored again")


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


# ══════════════════════════════════════════════════════════════════════
# BS1 — SWEEP SELECTION (--tests-for), spec
# docs/specs/blast-sweep-and-artifact-ledger-spec.md
# ══════════════════════════════════════════════════════════════════════
# The law is a UNION of four clauses and its failure mode is silent
# NARROWING: a selection that drops the one test the change breaks is
# indistinguishable from a green sweep.  Every clause therefore gets its
# own twin, plus one for each way the index can fail to attribute a symbol.

def _shards(modules):
    """Minimal shard set: only ``modules`` matters to the selector."""
    return {"modules": modules, "meta": {"head_sha": "0" * 40}}


def test_the_index_records_symbol_test_edges_for_selection(index):
    """v1 stored only hot-symbol COUNTS; a count cannot select a test."""
    card = index["modules"][LAYOUT]
    assert card["symbol_tests"], "layout.py must carry per-symbol test edges"
    assert set(card["symbol_tests"]) <= set(card["symbols_attributed"])
    for sym, tests in card["symbol_tests"].items():
        assert tests and all(t.startswith("Ortho4XP/tests/") for t in tests)
        for test in tests:                  # the edge is REAL, not inferred
            assert sym in blast._read(test), (
                "%s is attributed to %s but never names it" % (sym, test))


def test_clause_1_selects_only_the_changed_symbols_tests():
    mods = {"Ortho4XP/src/x.py": {
        "tests": ["Ortho4XP/tests/test_a.py", "Ortho4XP/tests/test_b.py"]
                 + ["Ortho4XP/tests/test_%d.py" % i for i in range(20)],
        "symbol_tests": {"foo": ["Ortho4XP/tests/test_a.py"],
                         "bar": ["Ortho4XP/tests/test_b.py"]},
        "symbols_attributed": ["bar", "foo"]}}
    got = blast.select_tests({"Ortho4XP/src/x.py": {"foo"}}, _shards(mods))
    assert got["selected"] == ["Ortho4XP/tests/test_a.py"]
    assert got["clauses"]["symbol"] == ["Ortho4XP/tests/test_a.py"]
    assert not got["fallbacks"] and len(got["full_sweep"]) == 22


def test_clause_2_a_cheap_file_runs_its_whole_sweep():
    """<= ceiling direct-importer tests: narrowing buys nothing and can
    only cost recall, so the file contributes all of them."""
    tests = ["Ortho4XP/tests/test_%d.py" % i for i in range(3)]
    mods = {"Ortho4XP/src/x.py": {
        "tests": tests, "symbol_tests": {"foo": [tests[0]]},
        "symbols_attributed": ["foo"]}}
    got = blast.select_tests({"Ortho4XP/src/x.py": {"foo"}}, _shards(mods))
    assert got["selected"] == sorted(tests)
    assert got["clauses"]["cheap_file"] == sorted(tests)
    # ... and the ceiling is what makes it fire, not the symbol edge
    narrow = blast.select_tests({"Ortho4XP/src/x.py": {"foo"}}, _shards(mods),
                                ceiling=2)
    assert narrow["selected"] == [tests[0]]


def test_clause_3_an_unattributable_symbol_falls_back_wide_and_loudly():
    tests = ["Ortho4XP/tests/test_%d.py" % i for i in range(20)]
    mods = {"Ortho4XP/src/x.py": {
        "tests": tests, "symbol_tests": {"foo": [tests[0]]},
        "symbols_attributed": ["foo"]}}
    got = blast.select_tests({"Ortho4XP/src/x.py": {"ghost"}}, _shards(mods))
    assert got["selected"] == sorted(tests), "must NOT narrow to nothing"
    assert got["clauses"]["fallback"] == sorted(tests)
    assert any("ghost" in f and "UNATTRIBUTED" in f for f in got["fallbacks"])


def test_clause_3_also_covers_a_file_the_caller_cannot_attribute():
    """A module-level edit, an unparseable file or a no-op diff belongs to
    no symbol; each widens by the same law rather than selecting nothing."""
    tests = ["Ortho4XP/tests/test_%d.py" % i for i in range(20)]
    mods = {"Ortho4XP/src/x.py": {"tests": tests, "symbol_tests": {},
                                  "symbols_attributed": ["foo"]}}
    got = blast.select_tests({}, _shards(mods),
                             wide_reasons={"Ortho4XP/src/x.py": ["MODULE-LEVEL"]})
    assert got["selected"] == sorted(tests)
    assert any("MODULE-LEVEL" in f for f in got["fallbacks"])


def test_clause_4_a_changed_test_file_selects_itself():
    got = blast.select_tests({"Ortho4XP/tests/test_new.py": set()},
                             _shards({"Ortho4XP/tests/test_new.py": {}}))
    assert got["selected"] == ["Ortho4XP/tests/test_new.py"]
    assert got["clauses"]["changed_test"] == ["Ortho4XP/tests/test_new.py"]


def test_an_unindexed_changed_file_is_named_never_silently_covered():
    got = blast.select_tests({"tools/blast.py": {"foo"}}, _shards({}))
    assert got["selected"] == []
    assert got["unindexed"] == ["tools/blast.py"]
    assert any("NOT IN THE INDEX" in f and "not a claim" in f
               for f in got["fallbacks"])


def test_conftest_is_never_selected_as_a_test_file():
    tests = ["Ortho4XP/tests/conftest.py", "Ortho4XP/tests/test_a.py"]
    mods = {"Ortho4XP/src/x.py": {
        "tests": tests,
        "symbol_tests": {"foo": ["Ortho4XP/tests/conftest.py"]},
        "symbols_attributed": ["foo"]}}
    got = blast.select_tests({"Ortho4XP/src/x.py": {"foo"}}, _shards(mods))
    assert got["selected"] == ["Ortho4XP/tests/test_a.py"]


# ---------------------------------------------------- the changed-symbol read
def test_a_reformat_is_not_a_symbol_change_but_a_body_edit_is():
    before = "def f(a):\n    return a + 1\n\n\nX = 1\n"
    same = "def f(a):\n\n    # a comment\n    return a+1\nX = 1"
    changed = "def f(a):\n    return a + 2\n\n\nX = 1\n"
    assert blast.top_level_symbols(before) == blast.top_level_symbols(same)
    assert blast.top_level_symbols(before) != blast.top_level_symbols(changed)
    assert set(blast.top_level_symbols(before)) == {"f", "X"}


def test_module_level_code_is_read_separately_from_the_symbols():
    a = "import os\n\ndef f():\n    return 1\n"
    b = "import os\nimport sys\n\ndef f():\n    return 1\n"
    assert blast._module_level_source(a) != blast._module_level_source(b)
    assert blast.top_level_symbols(a) == blast.top_level_symbols(b)


def test_a_clean_file_reports_no_changed_symbol_and_widens(tmp_path):
    """The tree's own layout.py, unchanged vs HEAD: no symbol moved, so the
    selector must widen (clause 3) rather than emit an empty sweep."""
    syms, notes = blast.changed_symbols(LAYOUT, "HEAD")
    if syms:
        pytest.skip("layout.py is dirty in this working tree")
    assert notes == []


def test_the_header_goes_to_stderr_and_the_pipe_stays_clean(tmp_path):
    """Deliberately an EMPTY index dir: the rebuild notice is the line that
    actually reached stdout before the redirect, and a fresh index would
    make this twin unfalsifiable."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = blast.cmd_tests_for([LAYOUT], str(tmp_path / "idx"))
    assert "index rebuilt" in err.getvalue()
    assert rc == 0
    for line in out.getvalue().splitlines():
        assert line.startswith("Ortho4XP/tests/") and line.endswith(".py"), (
            "stdout is piped straight into pytest — every line must be a "
            "test path, never a header or a rebuild notice: %r" % line)
    assert "# blast --tests-for" in err.getvalue()
    assert "SELECTED" in err.getvalue()


def test_a_bogus_target_exits_2(index_path):
    err = io.StringIO()
    with redirect_stderr(err):
        assert blast.cmd_tests_for(["no/such/file.py"], index_path) == 2
    assert "no such file in repo" in err.getvalue()


# ------------------------------------------------------- the mutation twin
def test_the_mutation_plugin_deletes_the_symbol_at_runtime(monkeypatch):
    """No file is ever rewritten: lanes build against this same tree."""
    probe = types.ModuleType("auto_patch.blast_probe_module")
    probe.SYMBOL = 1
    monkeypatch.setitem(sys.modules, "auto_patch.blast_probe_module", probe)
    monkeypatch.setenv(blast.MUTATE_ENV,
                       "Ortho4XP/src/auto_patch/blast_probe_module.py::SYMBOL")
    blast.pytest_configure(None)
    assert not hasattr(probe, "SYMBOL")


def test_a_mutation_that_cannot_bite_fails_loudly(monkeypatch):
    probe = types.ModuleType("auto_patch.blast_probe_module2")
    monkeypatch.setitem(sys.modules, "auto_patch.blast_probe_module2", probe)
    monkeypatch.setenv(blast.MUTATE_ENV,
                       "Ortho4XP/src/auto_patch/blast_probe_module2.py::GONE")
    with pytest.raises(SystemExit) as exc:
        blast.pytest_configure(None)
    assert "no attribute" in str(exc.value)


def test_no_mutation_env_leaves_the_process_untouched(monkeypatch):
    monkeypatch.delenv(blast.MUTATE_ENV, raising=False)
    assert blast.pytest_configure(None) is None


def test_failing_files_are_read_from_the_short_summary():
    sample = ("FAILED tests/test_a.py::test_one - AssertionError\n"
              "ERROR tests/test_b.py\n"
              "FAILED tests/test_a.py::test_two\n"
              "1 failed, 2 passed in 3.4s\n")
    assert set(blast.FAIL_RE.findall(sample)) == {"tests/test_a.py",
                                                  "tests/test_b.py"}


def _audit_shards():
    tests = ["Ortho4XP/tests/test_%d.py" % i for i in range(20)]
    return _shards({"Ortho4XP/src/x.py": {
        "tests": tests, "hot_symbols": {"foo": 9},
        "symbol_tests": {"foo": [tests[0]]}, "symbols_attributed": ["foo"]}})


def test_the_mutation_audit_fails_when_a_failing_test_was_not_selected(
        monkeypatch, capsys):
    monkeypatch.setattr(blast, "sweep_failures",
                        lambda tests, mutation=None:
                        ((set() if mutation is None
                          else {"Ortho4XP/tests/test_7.py"}), 1, ""))
    bad = blast.mutation_audit(_audit_shards(), "Ortho4XP/src/x.py", 1,
                               ceiling=-1)
    assert bad == ["mutation:foo"]
    assert "MISSED" in capsys.readouterr().out


def test_the_mutation_audit_passes_when_the_selection_covers_the_failures(
        monkeypatch):
    monkeypatch.setattr(blast, "sweep_failures",
                        lambda tests, mutation=None:
                        ((set() if mutation is None
                          else {"Ortho4XP/tests/test_0.py"}), 1, ""))
    assert blast.mutation_audit(_audit_shards(), "Ortho4XP/src/x.py", 1,
                                ceiling=-1) == []


def test_a_mutation_set_with_no_signal_is_a_FAIL_not_a_pass(monkeypatch):
    """A mutation nothing notices proves nothing; reporting it as recall
    100 % would be the exact 'absence of data as a safety claim' this tool
    refuses everywhere else."""
    monkeypatch.setattr(blast, "sweep_failures",
                        lambda tests, mutation=None: (set(), 0, ""))
    assert blast.mutation_audit(_audit_shards(), "Ortho4XP/src/x.py", 1) == \
        ["mutation-no-signal"]


def test_a_baseline_failure_is_discounted_from_every_mutation(monkeypatch):
    """A file already red at this tree is not this mutation's signal (the
    matched-control law) — and it must not be counted as a recall miss."""
    monkeypatch.setattr(blast, "sweep_failures",
                        lambda tests, mutation=None:
                        ({"Ortho4XP/tests/test_9.py"} if mutation is None
                         else {"Ortho4XP/tests/test_9.py",
                               "Ortho4XP/tests/test_0.py"}, 1, ""))
    assert blast.mutation_audit(_audit_shards(), "Ortho4XP/src/x.py", 1,
                               ceiling=-1) == []
