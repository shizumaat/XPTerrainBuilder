"""ONE CI RUN PER COMMIT: no workflow may fire on two events at once (#225).

Until 2026-10-02 ``.github/workflows/ci.yml`` carried both

    on:
      push:
        branches: ["**"]
      pull_request:

and keyed its concurrency group on ``github.ref``.  Both triggers matched
every push to every branch with an open PR, and the group could not collapse
them because ``github.ref`` is a different string for the two events
(``refs/heads/<branch>`` vs ``refs/pull/<n>/merge``).  Result: the full 4-job
matrix ran TWICE on every push, ~40-50 runner-minutes each time, silently —
``cancel-in-progress`` works *within* a trigger, which is why it looked fine.

Nothing in CI could notice: both runs were green, and a doubled run is not a
failing run.  Hence this twin, which asserts the shape rather than the cost.

Two independent invariants, both over EVERY workflow in the directory so the
next one added is checked rather than exempt:

1. A workflow carrying both ``push`` and ``pull_request`` must not take a
   WILDCARD push branch filter.  ``["**"]`` (or a missing ``branches:``, which
   means every branch) guarantees the overlap that #225 measured.
2. Such a workflow's concurrency group must be EVENT-INDEPENDENT — it cannot
   be keyed on bare ``github.ref``, or the two runs land in two groups and
   neither cancels the other.

Textual, not YAML: no ``yaml`` module is installed in the engine venv (same
reason ``test_version_scheme.py`` parses ``release.yml`` by hand), and
``on`` is a YAML 1.1 boolean anyway, which a naive loader turns into ``True``.

Pure hermetic: reads the repo's own files, nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]

# The engine is vendored inside the XPTerrainBuilder repo; used standalone,
# the app-side tree (and .github/) simply is not there.
REPO_ROOT = ENGINE_DIR.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

app_side = pytest.mark.skipif(
    not WORKFLOWS.is_dir(),
    reason="engine checked out standalone — no .github/workflows tree",
)

#: Expressions that are equal across a ``push`` and a ``pull_request`` event
#: on the same branch, so a group keyed on one collapses the two runs.
#: ``github.head_ref`` is the source branch name on a pull_request and EMPTY
#: on a push, hence the ``||`` fallback idiom; the PR number works the same
#: way.  Bare ``github.ref`` is exactly what #225 was.
EVENT_INDEPENDENT_KEYS = ("github.head_ref", "github.event.pull_request.number")


def _workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert files, f"no workflow files under {WORKFLOWS}"
    return files


def _top_level_blocks(text: str) -> dict[str, str]:
    """``{top-level key: its block}`` for one workflow file.

    A top-level key is a line starting in column 0 that looks like ``key:``.
    Its block is every following line until the next such line; comment lines
    in column 0 belong to no block (they sit BETWEEN keys, which is where
    this repo's workflows put their prose).
    """
    blocks: dict[str, str] = {}
    key = None
    for line in text.splitlines(keepends=True):
        if line.startswith("#"):
            continue
        head = re.match(r"([A-Za-z_][\w-]*):", line)
        if head:
            key = head.group(1)
            blocks[key] = line[head.end():]
            continue
        if key is not None:
            blocks[key] += line
    return blocks


def _triggers(on_block: str) -> set[str]:
    """The event names inside an ``on:`` block.

    Handles both spellings GitHub accepts: the nested mapping this repo uses
    (``push:`` indented two spaces) and the inline list ``on: [push, ...]``.
    """
    inline = re.match(r"\s*\[([^\]]*)\]", on_block)
    if inline:
        return {e.strip() for e in inline.group(1).split(",") if e.strip()}
    return set(re.findall(r"^  ([A-Za-z_][\w-]*):", on_block, re.MULTILINE))


def _push_branches(on_block: str) -> list[str] | None:
    """The ``push.branches`` filter, or ``None`` when there is none.

    ``None`` is not "no branches" — it is EVERY branch, which is the same
    hazard as ``["**"]`` and is asserted as such below.
    """
    push = re.search(
        r"^  push:\n((?:    .*\n|\s*\n|\s*#.*\n)*)", on_block, re.MULTILINE)
    if not push:
        return None
    inline = re.search(r"^    branches:\s*\[([^\]]*)\]", push.group(1), re.MULTILINE)
    if inline:
        return [b.strip().strip("'\"") for b in inline.group(1).split(",") if b.strip()]
    block = re.search(
        r"^    branches:\s*\n((?:      - .*\n)+)", push.group(1), re.MULTILINE)
    if block:
        return [re.sub(r"^      - ", "", ln).strip().strip("'\"")
                for ln in block.group(1).splitlines()]
    return None


@app_side
def test_the_parser_sees_ci_yml_as_it_is() -> None:
    """Pin the parser against the real file, so a silent mis-parse cannot
    make the two assertions below vacuously pass."""
    blocks = _top_level_blocks((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    assert {"name", "on", "concurrency", "jobs"} <= set(blocks), sorted(blocks)
    assert _triggers(blocks["on"]) == {"push", "pull_request"}, blocks["on"]
    assert _push_branches(blocks["on"]) == ["main"], blocks["on"]


@app_side
def test_no_workflow_fires_on_both_push_and_pull_request_for_one_commit() -> None:
    """The #225 defect itself: a wildcard push filter beside pull_request."""
    for path in _workflow_files():
        blocks = _top_level_blocks(path.read_text(encoding="utf-8"))
        on_block = blocks.get("on")
        assert on_block is not None, f"{path.name} has no `on:` block"
        triggers = _triggers(on_block)
        if not {"push", "pull_request"} <= triggers:
            continue
        branches = _push_branches(on_block)
        assert branches is not None, (
            f"{path.name} fires on both `push` and `pull_request` with NO "
            f"`push.branches:` filter, i.e. every branch — so every push to "
            f"a branch with an open PR runs the whole matrix twice (#225). "
            f"Narrow the push trigger, e.g. `branches: [main]`.")
        wild = [b for b in branches if "*" in b]
        assert not wild, (
            f"{path.name} fires on both `push` and `pull_request`, and its "
            f"push filter {branches} is a WILDCARD ({wild}) that matches PR "
            f"branches too — the double run #225 measured (8 check runs, 4 "
            f"names, two run ids, on every head of PR #220). List the "
            f"branches that need a non-PR run explicitly.")


@app_side
def test_a_two_trigger_workflow_keys_concurrency_event_independently() -> None:
    """Belt and braces to the trigger fix: even if both events fired, the
    group must collapse them.  Bare ``github.ref`` cannot — it is
    ``refs/heads/<branch>`` for a push and ``refs/pull/<n>/merge`` for a
    pull_request, which is why #225's group never deduped anything."""
    for path in _workflow_files():
        blocks = _top_level_blocks(path.read_text(encoding="utf-8"))
        triggers = _triggers(blocks.get("on", ""))
        if not {"push", "pull_request"} <= triggers:
            continue
        conc = blocks.get("concurrency")
        assert conc is not None, (
            f"{path.name} fires on both `push` and `pull_request` with no "
            f"`concurrency:` block at all")
        group = re.search(r"^  group:\s*(.+)$", conc, re.MULTILINE)
        assert group, f"{path.name} has a concurrency block with no `group:`"
        expr = group.group(1).strip()
        assert any(k in expr for k in EVENT_INDEPENDENT_KEYS), (
            f"{path.name} keys its concurrency group on {expr!r}, which "
            f"differs between the push and pull_request events for one "
            f"commit, so neither run cancels the other (#225). Key it on an "
            f"event-independent value: one of {list(EVENT_INDEPENDENT_KEYS)}, "
            f"e.g. `${{{{ github.head_ref || github.ref }}}}`.")
