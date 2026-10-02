"""THE COLLECTION FLOOR GATES THE SET THE SUITE RUNS (#244).

CI's floor step reported ~10 FEWER items than the suite in the same job
on the same tree (12,991 vs 13,001 on run 37016002700; 12,871 vs 12,880
before it), so a regression living only in those items was invisible to
the gate.  ``tools/ci_collection_census.py`` reconciles the two, and
these twins pin both halves:

1. the CENSUS -- what a ``--collect-only`` run saw: items (and only
   items: the ERRORS section's traceback lines start with ``tests/``
   too, and the bash the tool replaces folded them into its digest),
   the modules that could not be collected AT ALL, and the identity
   ``items + uncollectable modules = the outcomes the suite reports``,
   which is the whole mechanism of the gap;
2. the RECONCILIATION -- the two sets compared by NAME, so a divergence
   is attributable rather than a subtraction the reader does;
3. the WIRING in ``.github/workflows/ci.yml``, textually, like
   ``tests/test_ci_workflow_triggers.py``: a gate whose steps stop
   feeding each other is a gate that passes while measuring nothing.

Hermetic: synthetic collect output and junit XML, ``tmp_path`` only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ci_collection_census as CENSUS                      # noqa: E402

CI_YML = _ROOT.parent / ".github" / "workflows" / "ci.yml"

#: A collect-only run that collected three items from two modules, could
#: not collect a third at all, and errored on a fourth -- with the ERRORS
#: section's traceback lines that a ``^tests/`` match would have counted.
COLLECT_OUTPUT = """tests/test_a.py::test_one
tests/test_a.py::test_two[x-1]
tests/sub/test_b.py::TestC::test_three
SKIPPED [1] tests/test_optional.py:23: could not import 'laspy': No module named 'laspy'
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_broken.py _________________
tests/test_broken.py:12: in <module>
    import nothing_at_all
E   ModuleNotFoundError: No module named 'nothing_at_all'
3/4 tests collected (1 deselected), 1 error in 1.23s
"""


def _junit(items, collection_skipped=()):
    """The junit XML pytest writes, in the shape it really writes it."""
    cases = []
    for module in collection_skipped:
        cases.append(
            '<testcase classname="" name="%s" time="0.0">'
            '<skipped message="collection skipped">(\'x\', 1, "Skipped")'
            '</skipped></testcase>' % module)
    for class_name, name in items:
        cases.append('<testcase classname="%s" name="%s" time="0.0" />'
                     % (class_name, name))
    return ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
            '<testsuite name="pytest">%s</testsuite></testsuites>'
            % "".join(cases))


#: The same three items as ``COLLECT_OUTPUT``, written the way junit
#: writes them (dots, and the class split off into ``classname``).
RAN = [("tests.test_a", "test_one"),
       ("tests.test_a", "test_two[x-1]"),
       ("tests.sub.test_b.TestC", "test_three")]


# =====================================================================
# The census
# =====================================================================
def test_the_census_counts_items_and_not_the_error_tracebacks():
    record = CENSUS.census(COLLECT_OUTPUT)
    assert record["collected"] == 3
    assert record["node_ids"] == [
        "tests/sub/test_b.py::TestC::test_three",
        "tests/test_a.py::test_one",
        "tests/test_a.py::test_two[x-1]"]
    assert [entry["module"] for entry in record["collection_skipped"]] == [
        "tests/test_optional.py"]
    assert record["collection_errors"] == ["tests/test_broken.py"]


def test_the_expected_outcome_count_is_the_mechanism_of_the_gap():
    """#244's ~10: a module that cannot be collected contributes ZERO node
    ids to the floor and ONE outcome to the suite's tally."""
    record = CENSUS.census(COLLECT_OUTPUT)
    assert record["expected_outcomes"] == 3 + 1 + 1
    assert record["expected_outcomes"] - record["collected"] == 2


def test_the_digest_is_order_independent():
    shuffled = "\n".join(reversed(COLLECT_OUTPUT.splitlines())) + "\n"
    assert (CENSUS.census(shuffled)["digest"]
            == CENSUS.census(COLLECT_OUTPUT)["digest"])


@pytest.mark.parametrize("node_id,junit", [
    ("tests/test_a.py::test_one", "tests.test_a.test_one"),
    ("tests/test_a.py::test_two[x-1]", "tests.test_a.test_two[x-1]"),
    ("tests/sub/test_b.py::TestC::test_three",
     "tests.sub.test_b.TestC.test_three"),
    ("tests/test_optional.py", "tests.test_optional"),
])
def test_a_node_id_and_its_junit_spelling_canonicalise_together(
        node_id, junit):
    assert CENSUS.canonical(node_id) == junit


def test_the_floor_still_fails_below_its_threshold(tmp_path, capsys):
    collect = tmp_path / "collect.txt"
    collect.write_text(COLLECT_OUTPUT, encoding="utf-8", newline="")
    assert CENSUS.main(["census", str(collect), "--floor", "4"]) == 2
    assert "below the floor 4" in capsys.readouterr().out
    assert CENSUS.main(["census", str(collect), "--floor", "3"]) == 0


def test_the_census_writes_the_json_and_the_node_id_list(tmp_path):
    collect = tmp_path / "collect.txt"
    collect.write_text(COLLECT_OUTPUT, encoding="utf-8", newline="")
    record_path = tmp_path / "census.json"
    nodeids = tmp_path / "nodeids.txt"
    assert CENSUS.main(["census", str(collect), "--json", str(record_path),
                        "--nodeids", str(nodeids)]) == 0
    assert json.loads(record_path.read_text(encoding="utf-8"))["collected"] == 3
    assert nodeids.read_text(encoding="utf-8").splitlines() == [
        "tests/sub/test_b.py::TestC::test_three",
        "tests/test_a.py::test_one",
        "tests/test_a.py::test_two[x-1]"]


# =====================================================================
# The reconciliation
# =====================================================================
def _reconcile(tmp_path, junit_xml, collect_output=COLLECT_OUTPUT):
    collect = tmp_path / "collect.txt"
    collect.write_text(collect_output, encoding="utf-8", newline="")
    record = tmp_path / "census.json"
    assert CENSUS.main(["census", str(collect), "--json", str(record)]) == 0
    junit = tmp_path / "junit.xml"
    junit.write_text(junit_xml, encoding="utf-8", newline="")
    return CENSUS.main(["reconcile", "--census", str(record),
                        "--junit", str(junit)])


def test_the_matching_pair_reconciles(tmp_path, capsys):
    assert _reconcile(tmp_path, _junit(
        RAN, collection_skipped=["tests.test_optional",
                                 "tests.test_broken"])) == 0
    assert "gates exactly the set the suite ran" in capsys.readouterr().out


def test_an_item_the_suite_RAN_and_the_floor_MISSED_is_named(
        tmp_path, capsys):
    """#244's own signature, and the reason this compares sets: the gate
    must say WHICH items it was not gating."""
    assert _reconcile(tmp_path, _junit(
        RAN + [("tests.test_a", "test_invisible")],
        collection_skipped=["tests.test_optional", "tests.test_broken"])) == 2
    out = capsys.readouterr().out
    assert "tests.test_a.test_invisible" in out
    assert "RAN items the floor never collected" in out


def test_an_item_the_floor_collected_and_the_suite_never_ran_is_named(
        tmp_path, capsys):
    assert _reconcile(tmp_path, _junit(
        RAN[:-1], collection_skipped=["tests.test_optional",
                                      "tests.test_broken"])) == 2
    out = capsys.readouterr().out
    assert "tests.sub.test_b.TestC.test_three" in out
    assert "never ran" in out


def test_a_module_only_the_SUITE_could_not_collect_is_named(
        tmp_path, capsys):
    """The asymmetric case: the floor collected a module's tests and the
    suite then could not import it at all.  Both numbers can still look
    plausible; the set cannot."""
    assert _reconcile(tmp_path, _junit(
        RAN, collection_skipped=["tests.test_optional", "tests.test_broken",
                                 "tests.test_a"])) == 2
    out = capsys.readouterr().out
    assert "tests.test_a" in out
    assert "could not collect modules the floor collected from" in out


def test_a_killed_suite_step_is_a_notice_and_not_a_second_red(
        tmp_path, capsys):
    """A step killed at its wall clock writes no junit.  That job is
    already red for its own reason."""
    collect = tmp_path / "collect.txt"
    collect.write_text(COLLECT_OUTPUT, encoding="utf-8", newline="")
    record = tmp_path / "census.json"
    assert CENSUS.main(["census", str(collect), "--json", str(record)]) == 0
    assert CENSUS.main(["reconcile", "--census", str(record),
                        "--junit", str(tmp_path / "absent.xml")]) == 0
    assert "nothing to reconcile" in capsys.readouterr().out


# =====================================================================
# The wiring (textual, like tests/test_ci_workflow_triggers.py)
# =====================================================================
@pytest.fixture(scope="module")
def ci_yml():
    if not CI_YML.exists():                     # a lane worktree mirror
        pytest.skip("no .github/workflows/ci.yml in this checkout")
    return CI_YML.read_text(encoding="utf-8")


@pytest.mark.parametrize("slug", ["non-qt", "qt"])
def test_both_targets_are_censused_and_reconciled(ci_yml, slug):
    """Every link in the chain, per target: the floor writes a census, the
    suite writes a junit, the reconciliation reads both by those names."""
    assert "--json \"census-$slug.json\"" in ci_yml, (
        "the floor step must write the census the reconciliation reads")
    assert "--junitxml=junit-%s.xml" % slug in ci_yml, (
        "the %s suite step must write the junit the reconciliation reads"
        % slug)
    assert ("--census census-%s.json --junit junit-%s.xml" % (slug, slug)
            in ci_yml), (
        "the reconciliation step must read the %s pair" % slug)


def test_the_floor_still_passes_a_floor_for_both_targets(ci_yml):
    """The gate #63 asked for is not traded away for the one #244 asks
    for: a target whose count collapses still fails."""
    calls = re.findall(r"^\s*floor \"([^\"]+)\"\s+(\d+)\s", ci_yml,
                       re.MULTILINE)
    assert [name for name, _ in calls] == ["non-Qt", "Qt"]
    assert all(int(minimum) > 0 for _, minimum in calls)
    assert "--floor \"$min\"" in ci_yml


def test_the_collect_output_and_census_are_uploaded(ci_yml):
    """#244's own suggested next step: the collect output carries the
    collection-error text, and a census that is not uploaded cannot be
    read after the fact."""
    for path in ("Ortho4XP/collect-non-qt.txt", "Ortho4XP/collect-qt.txt",
                 "Ortho4XP/census-non-qt.json", "Ortho4XP/census-qt.json"):
        assert path in ci_yml


def test_the_tool_is_in_the_index():
    """RULINGS ``7e90032``: a tool absent from ``tools/INDEX.md`` is
    treated as absent, and every new tool lands with its index entry in
    the same commit."""
    index = _ROOT.parent / "tools" / "INDEX.md"
    if not index.exists():                      # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    rows = [ln for ln in index.read_text(encoding="utf-8").splitlines()
            if re.match(r"^\|\s*`[^`]*/ci_collection_census\.py`", ln)]
    assert len(rows) == 1, (
        "tools/INDEX.md has %d rows whose first cell is this tool" % len(rows))
