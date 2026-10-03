"""What a ``--collect-only`` run SAW, and whether the suite ran that set (#244).

``.github/workflows/ci.yml``'s collection floor exists to catch a glob or
path that stopped matching (#63).  It reported ~10 FEWER items than the
suite in the same job on the same tree -- 12,991 vs 13,001 on run
37016002700, 12,871 vs 12,880 before it -- so the gate was measuring a
smaller set than the suite runs, and a regression living only in those
items was invisible to it by construction.

THE MECHANISM (measured, not hypothesised).  It is not the ``-n``:
pytest-xdist skips itself entirely when only collecting
(``xdist/plugin.py``, "Skip this plugin entirely when only doing
collection"), so the floor's ``-n0 --collect-only`` collects exactly what
an ``-n auto --collect-only`` would and the two can never differ.  The
gap is what the two numbers MEAN.  The floor counts COLLECTED ITEMS; the
suite's summary counts REPORTED OUTCOMES, and a module that skips or
errors AT COLLECTION TIME -- ``pytest.importorskip`` at module level, an
optional dependency the runner lacks, an import error under
``--continue-on-collection-errors`` -- contributes ZERO node ids to a
collect-only run and ONE outcome to the suite's tally:

    <testcase classname="" name="tests.test_las_tile_index">
      <skipped message="collection skipped">...

The ~10 are those modules.  They differ per runner (a Windows leg lacks
different optional packages than Linux), which is why the gap moved
between runs and why no local checkout reproduced it.

So the two numbers are reconciled, not equated by force:

    expected outcomes  =  collected items
                       +  modules skipped at collection
                       +  modules errored at collection

``census`` computes the left side from the floor's own output; ``reconcile``
compares it to the junit XML the suite writes -- as SETS, so a divergence
is NAMED rather than merely counted, which is the whole point of the gate.

Usage (from ``Ortho4XP/``)::

    venv/bin/python tools/ci_collection_census.py census collect-non-qt.txt \\
        [--json census-non-qt.json] [--floor 9000]
    venv/bin/python tools/ci_collection_census.py reconcile \\
        --census census-non-qt.json --junit suite-non-qt.xml [--limit 20]

``census`` exits 2 below ``--floor``; ``reconcile`` exits 2 when the sets
differ.  Standard library only: it runs on every CI runner with no install.
Twin: ``tests/test_ci_collection_census.py``.
"""

from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Self-contained and ahead of every
# other import because a tool's own ``--help`` carries the house spelling
# (``Δ``, ``ε``, ``≥``, ``→``) and a Windows console RAISES on those
# rather than mangling them.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse                                                      # noqa: E402
import hashlib                                                       # noqa: E402
import io                                                            # noqa: E402
import json                                                          # noqa: E402
import re                                                            # noqa: E402
import xml.etree.ElementTree as ElementTree                          # noqa: E402

#: A collect-only node id: a path under ``tests/`` and at least one ``::``.
#: The ``.py::`` is what separates an ITEM from a traceback line in the
#: ERRORS section, which also starts with ``tests/`` (``tests/test_x.py:12:
#: in <module>`` -- one colon) and which ci.yml's own ``grep -E '^tests/'``
#: used to fold into the digest.  Everything after the ``::`` is taken
#: whole: 70 of this suite's ids carry SPACES inside their parametrisation
#: (``...[emit.toml-coordinate_dp           = 11-...]``), and a ``\S``
#: match silently dropped every one of them.
NODE_ID = re.compile(r"^(tests/\S+\.py::.+?)\s*$")

#: ``SKIPPED [3] tests/test_x.py:23: could not import 'laspy'`` -- pytest's
#: collection-skip report.  The bracketed number is the count, not an index.
COLLECTION_SKIP = re.compile(r"^SKIPPED \[(\d+)\] ([^:]+\.py):")

#: ``___ ERROR collecting tests/test_x.py ___`` -- one per errored module.
COLLECTION_ERROR = re.compile(r"ERROR collecting (\S+\.py)")

#: junit marks a module-level collection skip with this exact message, and
#: carries the module (not a test) in ``name`` with an empty ``classname``.
JUNIT_COLLECTION_SKIP = "collection skipped"

#: xdist turns the ``xdist_group`` marker into an ``@<group>`` NODE-ID
#: SUFFIX (``xdist/remote.py``; this suite's ``tests/conftest.py`` assigns
#: every airport-parametrised test the group ``<icao>`` so one worker builds
#: each airport once).  So the same item is named
#: ``...::test_x[CYXY]@CYXY`` by the suite and ``...::test_x[CYXY]`` by the
#: floor, which does not run xdist at all: 130 items here.  A renaming, not
#: a different item, so it is normalised away rather than reported.
XDIST_GROUP_SUFFIX = re.compile(r"@[^@\[\]]+$")


def canonical(node_id: str) -> str:
    """One spelling for a node id and for junit's classname/name pair.

    ``tests/a/test_b.py::TestC::test_d[p]`` and junit's
    ``classname="tests.a.test_b.TestC" name="test_d[p]"`` are the same
    item written two ways.  pytest's own ``mangle_test_address`` converts
    the FILE PATH to a dotted name and leaves everything after the first
    ``[`` alone, so this does exactly that and no more: a parametrised id
    carries backslashes of its own (``...[CYQQ-\n]``, 40 items here) and
    folding those into dots would invent a divergence out of a rendering.
    """
    # pytest's own ``mangle_test_address`` (_pytest/junitxml.py), which is
    # what wrote the junit names: partition at the FIRST ``[`` before
    # splitting on ``::``, because a parametrised id can contain both
    # (``test_the_loopback_predicate[::1-True]``, 3 items here).
    head, bracket, params = XDIST_GROUP_SUFFIX.sub("", node_id).partition("[")
    names = [part for part in head.split("::") if part]
    names[0] = names[0].replace("\\", "/").replace("/", ".")
    if names[0].endswith(".py"):
        names[0] = names[0][:-3]
    names[-1] += bracket + params
    return ".".join(names)


def census(collect_output: str) -> dict:
    """The set a ``--collect-only`` run saw, and what the suite will report."""
    items, skipped, errors = [], {}, []
    for line in collect_output.splitlines():
        node = NODE_ID.match(line)
        if node:
            items.append(node.group(1))
            continue
        skip = COLLECTION_SKIP.match(line)
        if skip:
            module = skip.group(2)
            skipped[module] = skipped.get(module, 0) + int(skip.group(1))
            continue
        error = COLLECTION_ERROR.search(line)
        if error and error.group(1) not in errors:
            errors.append(error.group(1))
    node_ids = sorted(items)
    digest = hashlib.sha256(
        "".join(line + "\n" for line in node_ids).encode("utf-8")
    ).hexdigest()[:16]
    skipped_modules = sorted(skipped)
    return {
        "collected": len(items),
        "digest": digest,
        "node_ids": node_ids,
        "collection_skipped": [
            {"module": module, "count": skipped[module]}
            for module in skipped_modules
        ],
        "collection_errors": errors,
        # One outcome per collected item, plus one per module that could
        # not be collected at all -- which is the number the suite reports.
        "expected_outcomes": (len(items)
                              + sum(skipped[m] for m in skipped_modules)
                              + len(errors)),
    }


def junit_outcomes(junit_xml: str) -> dict:
    """Every outcome the suite reported, canonicalised, from its junit XML."""
    root = ElementTree.fromstring(junit_xml)
    items, collection_skipped = [], []
    for case in root.iter("testcase"):
        class_name = case.get("classname") or ""
        name = case.get("name") or ""
        skipped = case.find("skipped")
        if (not class_name and skipped is not None
                and skipped.get("message") == JUNIT_COLLECTION_SKIP):
            collection_skipped.append(name)
            continue
        # junit already carries the dotted module name, so only the
        # ``@group`` suffix xdist added needs normalising away -- running
        # the path conversion over a name would eat its parametrisation.
        items.append(XDIST_GROUP_SUFFIX.sub(
            "", ".".join(part for part in (class_name, name) if part)))
    return {"items": items, "collection_skipped": collection_skipped}


def _print_census(name: str, record: dict) -> None:
    print("%s: collected %d items, sorted sha256 %s"
          % (name, record["collected"], record["digest"]))
    for entry in record["collection_skipped"]:
        print("%s: skipped at collection: %s (%d)"
              % (name, entry["module"], entry["count"]))
    for module in record["collection_errors"]:
        print("%s: ERRORED at collection: %s" % (name, module))
    print("%s: the suite should report %d outcomes "
          "(%d items + %d uncollectable modules)"
          % (name, record["expected_outcomes"], record["collected"],
             record["expected_outcomes"] - record["collected"]))


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _run_census(arguments) -> int:
    record = census(_read(arguments.collect_output))
    _print_census(arguments.name, record)
    if arguments.json:
        with io.open(arguments.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, indent=1, sort_keys=True)
    if arguments.nodeids:
        # The sorted list behind the digest, which CI has uploaded since
        # #221 so two runs that disagree can be diffed by node id.
        with io.open(arguments.nodeids, "w", encoding="utf-8",
                     newline="\n") as fh:
            for node_id in record["node_ids"]:
                fh.write(node_id + "\n")
    if arguments.floor is not None and record["collected"] < arguments.floor:
        print("::error::%s collected %d items, below the floor %d — a glob or"
              " path stopped matching.  CI is not running what it claims."
              % (arguments.name, record["collected"], arguments.floor))
        return 2
    return 0


def _run_reconcile(arguments) -> int:
    for path, what in ((arguments.census, "collection floor"),
                       (arguments.junit, "suite run")):
        if not _o4os.path.isfile(path):
            # A step killed at its wall clock (the Windows leg's every run
            # until 2026-10-02) writes no junit, and a floor that never ran
            # writes no census.  That job is ALREADY red for its own
            # reason; failing here too would only bury it.
            print("::notice::%s: no %s artifact (%s) — nothing to reconcile;"
                  " the step that should have written it is the report."
                  % (arguments.name, what, path))
            return 0
    with io.open(arguments.census, encoding="utf-8") as fh:
        record = json.load(fh)
    reported = junit_outcomes(_read(arguments.junit))
    collected = {canonical(node_id) for node_id in record["node_ids"]}
    ran = set(reported["items"])
    expected_uncollectable = {
        canonical(entry["module"]) for entry in record["collection_skipped"]
    } | {canonical(module) for module in record["collection_errors"]}
    uncollectable = set(reported["collection_skipped"])

    print("%s: the floor collected %d items; the suite reported %d outcomes"
          " (%d items + %d uncollectable modules)"
          % (arguments.name, len(collected),
             len(ran) + len(uncollectable), len(ran), len(uncollectable)))
    failures = []
    for label, missing in (
            ("the suite RAN items the floor never collected",
             sorted(ran - collected)),
            ("the floor collected items the suite never ran",
             sorted(collected - ran)),
            ("the suite could not collect modules the floor collected from",
             sorted(uncollectable - expected_uncollectable)),
            ("the floor could not collect modules the suite collected from",
             sorted(expected_uncollectable - uncollectable))):
        if not missing:
            continue
        failures.append("%s (%d)" % (label, len(missing)))
        print("::error::%s: %s (%d):" % (arguments.name, label, len(missing)))
        for name in missing[:arguments.limit]:
            print("    %s" % name)
        if len(missing) > arguments.limit:
            print("    ... and %d more" % (len(missing) - arguments.limit))
    if failures:
        print("::error::%s: the collection floor is not gating the set the"
              " suite runs (#244): %s" % (arguments.name, "; ".join(failures)))
        return 2
    print("%s: the floor gates exactly the set the suite ran." % arguments.name)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile CI's collection floor with the suite it gates"
                    " (#244).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def named(subparser):
        """Every subcommand takes the floor's own label for the target."""
        subparser.add_argument(
            "--name", default="non-Qt",
            help="label for the target, as the floor names it")
        return subparser

    census_parser = named(subparsers.add_parser(
        "census", help="what a --collect-only run saw"))
    census_parser.add_argument("collect_output",
                               help="the floor's --collect-only output file")
    census_parser.add_argument("--json", help="write the census here")
    census_parser.add_argument("--floor", type=int,
                               help="fail below this many collected items")
    census_parser.add_argument("--nodeids",
                               help="write the sorted node-id list here")
    census_parser.set_defaults(handler=_run_census)

    reconcile_parser = named(subparsers.add_parser(
        "reconcile", help="did the suite run exactly the floor's set?"))
    reconcile_parser.add_argument("--census", required=True,
                                  help="the census JSON written above")
    reconcile_parser.add_argument("--junit", required=True,
                                  help="the suite run's --junitxml file")
    reconcile_parser.add_argument("--limit", type=int, default=20,
                                  help="how many names to print per side")
    reconcile_parser.set_defaults(handler=_run_reconcile)

    arguments = parser.parse_args(argv)
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
