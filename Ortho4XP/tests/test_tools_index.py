"""TWINS FOR ``tools/INDEX.md`` ITSELF (issue #187).

RULINGS ``7e90032`` makes the index the consultation surface: a tool
absent from it is treated as ABSENT, and every new tool lands with its
index entry in the same commit.  Nothing, until this file, read the index
as a TABLE — so the file could carry TWO rows for one tool path and every
per-tool twin stayed green, because each of those twins asserts only
``"<name>.py" in index.read_text()``, a substring the NEIGHBOURING row's
prose satisfies on its own (measured 2026-10-02: the first occurrence of
``role_overlap_read.py`` is in ``lattice_overlap_read``'s description,
and of ``role_edge_census.py`` in ``pad_frontage_step``'s — neither twin
was matching its own row at all).

Two rows for one tool is not a cosmetic defect: the two disagree about
the tool's flags and its twin, so a lane that consults the index reads
whichever it meets first and runs a tool that no longer exists as
described.  The way it gets in is a MERGE: both branches edited the same
row, and the resolution kept both (``15e5c2c4`` "Merge branch
'lane/ltbatch3'" did exactly that to ``role_overlap_read.py`` — each
parent carried one row, the merge carried two).

WHAT IS PINNED HERE

1. every row's first cell parses as a backticked path (the parser sees
   the WHOLE table, so the rules below cannot be satisfied by a row the
   parser quietly skipped);
2. no tool path has two rows, except the paths in
   :data:`KNOWN_DUPLICATE_PATHS` — the register of duplicates that were
   already in the file when this twin was written and that a lane
   working only issue #187 is not entitled to adjudicate (the rows
   disagree on flags: ``tunnel_portal_acceptance.py``'s line 74 names
   six flags its longest row does not, so "keep the longest" would DROP
   documented flags);
3. the register only ever SHRINKS — a path in it that is no longer
   duplicated fails here, so closing one of those duplicates forces its
   line out of the register rather than leaving a stale exemption;
4. ``role_overlap_read.py`` — issue #187's subject — has exactly ONE row;
5. every ``tests/...py`` file an index row names EXISTS.

A row whose description is a pointer (``See above``) is a
CROSS-REFERENCE, not a second entry: ``harness/build_airport.py`` is
listed under THE HARNESS in full and under Build drivers as
"**Default.** See above."  A pointer row must say so in those words.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]           # Ortho4XP/
INDEX = _ROOT.parent / "tools" / "INDEX.md"

#: a table row: the line starts with the first cell's backticked path
_ROW = re.compile(r"^\|\s*`([^`]+)`")
#: how a row is written at all (used to prove the parser sees every one)
_ROW_LINE = re.compile(r"^\|\s*`")
#: a pointer row -- a cross-reference to the full entry in another section
_CROSS_REF = re.compile(r"See above", re.IGNORECASE)
#: every twin file an index row names
_TWIN = re.compile(r"\btests?/[A-Za-z0-9_./-]+\.py\b")

#: THE REGISTER (issue #187, reported, not adjudicated).  Tool paths that
#: already carried more than one row when this twin landed.  Each entry
#: is a defect; none may be ADDED without an owner ruling, and an entry
#: whose rows have been merged must be DELETED (test 3 enforces that).
KNOWN_DUPLICATE_PATHS = frozenset({
    "Ortho4XP/tools/lattice_overlap_read.py",         # 3 rows (two identical)
    "Ortho4XP/tools/tunnel_portal_acceptance.py",     # 4 rows, flags disagree
    "Ortho4XP/tools/object_pad_evidence_report.py",   # 2 rows
    "Ortho4XP/tools/classify_report.py",              # 2 rows
})

#: issue #187's subject: the stale duplicate was dropped, the superset kept
SUBJECT = "Ortho4XP/tools/role_overlap_read.py"


def _rows() -> list[tuple[int, str, str]]:
    """``(line number, tool path, the rest of the row)`` for every row."""
    if not INDEX.exists():                            # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    out = []
    for n, line in enumerate(INDEX.read_text(encoding="utf-8").splitlines(), 1):
        m = _ROW.match(line)
        if m:
            out.append((n, m.group(1), line[m.end():]))
    return out


def _entries() -> dict[str, list[int]]:
    """Tool path -> the lines of its ENTRY rows (pointer rows excluded)."""
    by_path: dict[str, list[int]] = {}
    for n, path, rest in _rows():
        if _CROSS_REF.search(rest):
            continue
        by_path.setdefault(path, []).append(n)
    return by_path


def test_the_parser_sees_every_row():
    """No rule below can be met by a row the parser skipped."""
    if not INDEX.exists():
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    written = sum(1 for line in INDEX.read_text(encoding="utf-8").splitlines()
                  if _ROW_LINE.match(line))
    assert written == len(_rows()), (
        "a table row's first cell is not a single backticked path -- the "
        "uniqueness twin would not see it")


def test_no_tool_path_has_two_rows():
    """RULINGS ``7e90032``: ONE row per tool.  Two rows disagree, and the
    lane reads whichever it meets first (issue #187)."""
    dups = {p: ls for p, ls in _entries().items() if len(ls) > 1}
    new = {p: ls for p, ls in dups.items() if p not in KNOWN_DUPLICATE_PATHS}
    assert not new, (
        "tools/INDEX.md carries two rows for one tool path (issue #187; the "
        "way it gets in is a merge keeping both sides of an edited row): "
        + "; ".join(f"{p} at lines {ls}" for p, ls in sorted(new.items()))
        + ".  Keep ONE row -- the current text -- or, if the rows cannot be "
          "adjudicated in this lane, report them and add the path to "
          "KNOWN_DUPLICATE_PATHS with the reason.")


def test_the_duplicate_register_only_shrinks():
    """A path whose rows have been merged must leave the register, so a
    stale exemption can never hide a NEW duplicate of the same path."""
    dups = {p for p, ls in _entries().items() if len(ls) > 1}
    stale = sorted(KNOWN_DUPLICATE_PATHS - dups)
    assert not stale, (
        "these paths are no longer duplicated in tools/INDEX.md -- delete "
        f"them from KNOWN_DUPLICATE_PATHS: {stale}")


def test_role_overlap_read_has_exactly_one_row():
    """Issue #187: the stale earlier row (it stopped at ``--min-area`` and
    the HECA round-6b basis) is gone; the superset row -- anchor repair,
    ``--contains``, ``--slivers``, ``--hole-rings`` -- is the one left."""
    lines = _entries().get(SUBJECT, [])
    assert len(lines) == 1, f"{SUBJECT}: rows at lines {lines}, expected one"
    row = [r for n, p, r in _rows() if p == SUBJECT][0]
    for flag in ("--contains", "--slivers", "--hole-rings"):
        assert flag in row, f"{SUBJECT}: the row left behind is the STALE one"


def test_every_twin_a_row_names_exists():
    """The assertion that would have caught issue #187's class: a row
    naming a twin that does not exist is a row describing a tool that is
    not there any more."""
    missing: dict[str, list[int]] = {}
    for n, _path, rest in _rows():
        for twin in sorted(set(_TWIN.findall(rest))):
            if not ((_ROOT / twin).exists() or (_ROOT.parent / twin).exists()):
                missing.setdefault(twin, []).append(n)
    assert not missing, (
        "tools/INDEX.md names twin files that do not exist: "
        + "; ".join(f"{t} (lines {ls})" for t, ls in sorted(missing.items())))
