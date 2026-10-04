#!/usr/bin/env python3
"""THE MERGE RATCHETS (owner RULINGS 2026-10-04a (1) and (3)).

Two numbers that may FALL and never RISE, both recorded in
``tools/ratchet_baseline.json`` and asserted by
``Ortho4XP/tests/test_ratchets.py``:

SIZE.  Scope: tracked ``.py`` / ``.swift`` under ``Ortho4XP/src``,
``Ortho4XP/tools``, ``tools`` and ``Sources`` (lines as
``len(text.splitlines())`` — comments and blanks included; never fold
comments to make a number).  A file ABSENT from the baseline refuses past
1,000 lines and is listed past 600 (the PR says why it is not split).  A
file IN the baseline — it was already past 1,000 when the baseline was
taken — refuses when it exceeds its recorded size: it may shrink, never
grow.  A baseline entry whose file is gone is not an error.  Tests are
reported, never gated.

DUPLICATES.  Top-level functions under ``Ortho4XP/src`` whose normalised
AST (arguments + body, docstring dropped, name and decorators ignored) is
identical in two or more FILES.  The count is the number of such
functions.  One-statement stubs (``pass``, ``...``, a bare ``raise``, a
``return`` of a constant or a name) are not counted: they are interface
placeholders, not copied logic.

    tools/ratchets.py                 # both checks; exit 1 on a refusal
    tools/ratchets.py size            # the size report alone
    tools/ratchets.py dupes [--top N] # the duplicate groups alone
    tools/ratchets.py --regenerate    # rewrite the baseline DOWNWARD

``--regenerate`` refuses to RAISE anything: a size entry above its
recorded value, a new file past 1,000, or a duplicate count above the
recorded one stops it with nothing written.  ``--init`` writes the first
baseline and refuses when one already exists.  ``tools/blast.py --audit``
prints the duplicate section and fails on a rise.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

__all__ = ["SOFT", "HARD", "SIZE_ROOTS", "DUP_ROOT", "BASELINE",
           "tracked_sources", "line_count", "sizes", "check_size",
           "duplicate_groups", "duplicate_count", "check_duplicates",
           "load_baseline", "regenerate", "main"]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "tools", "ratchet_baseline.json")
SOFT, HARD = 600, 1000
SIZE_ROOTS = ("Ortho4XP/src", "Ortho4XP/tools", "tools", "Sources")
REPORT_ROOTS = ("Ortho4XP/tests",)          # reported, not gated
DUP_ROOT = "Ortho4XP/src"
EXTS = (".py", ".swift")


def tracked_sources(roots=SIZE_ROOTS, repo=REPO, exts=EXTS):
    """Tracked source files under ``roots`` (repo-relative, sorted)."""
    out = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--", *roots],
                         capture_output=True, text=True, encoding="utf-8",
                         check=True).stdout
    return sorted(p for p in out.split("\0")
                  if p.endswith(exts) and os.path.isfile(os.path.join(repo, p)))


def line_count(rel, repo=REPO):
    with open(os.path.join(repo, rel), encoding="utf-8", errors="replace") as f:
        return len(f.read().splitlines())


def sizes(roots=SIZE_ROOTS, repo=REPO):
    return {rel: line_count(rel, repo) for rel in tracked_sources(roots, repo)}


def load_baseline(path=BASELINE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_size(current, recorded):
    """``(refusals, soft)`` for ``current`` {rel: lines} against the
    baseline's ``recorded`` {rel: lines}.  Entries of ``recorded`` with no
    file in ``current`` are ignored (a deleted file is not an error)."""
    refusals, soft = [], []
    for rel, n in sorted(current.items()):
        cap = recorded.get(rel)
        if cap is not None:
            if n > cap:
                refusals.append("%s: %d lines, baseline %d — a ratcheted file "
                                "may shrink, never grow (RULINGS 2026-10-04a); "
                                "move the addition into its own module"
                                % (rel, n, cap))
        elif n > HARD:
            refusals.append("%s: %d lines — past the %d hard limit for a file "
                            "not in the baseline (RULINGS 2026-10-04a); split "
                            "by responsibility" % (rel, n, HARD))
        elif n > SOFT:
            soft.append((rel, n))
    return refusals, soft


# ------------------------------------------------------------- duplicates
def _is_stub(body):
    if len(body) != 1:
        return False
    s = body[0]
    if isinstance(s, ast.Pass) or (isinstance(s, ast.Raise)):
        return True
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
        return True
    return isinstance(s, ast.Return) and (
        s.value is None or isinstance(s.value, (ast.Constant, ast.Name)))


def _normalised(fn):
    """The function's identity for the duplicate census, or None for a
    stub.  ``ast.dump`` without attributes drops positions, so formatting
    and comments never matter; the docstring is dropped explicitly."""
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    if not body or _is_stub(body):
        return None
    return (type(fn).__name__ + ast.dump(fn.args)
            + "".join(ast.dump(s) for s in body))


def duplicate_groups(files=None, repo=REPO):
    """Groups of top-level functions with one normalised body in >= 2
    files: a list of ``[(rel, name, lineno), ...]``, largest group first."""
    if files is None:
        files = tracked_sources((DUP_ROOT,), repo, exts=(".py",))
    seen = {}
    for rel in files:
        try:
            with open(os.path.join(repo, rel), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = _normalised(node)
                if key is not None:
                    seen.setdefault(key, []).append((rel, node.name, node.lineno))
    groups = [sorted(g) for g in seen.values() if len({r for r, _, _ in g}) > 1]
    return sorted(groups, key=lambda g: (-len(g), g))


def duplicate_count(groups):
    return sum(len(g) for g in groups)


def check_duplicates(groups, recorded):
    n = duplicate_count(groups)
    if n > recorded:
        return ["duplicate functions: %d, baseline %d — the count may fall, "
                "never rise (RULINGS 2026-10-04a); import the existing one "
                "(`tools/ratchets.py dupes` prints the groups)" % (n, recorded)]
    return []


# ------------------------------------------------------------------ report
def _tree_of(rel):
    return next(r for r in sorted(SIZE_ROOTS + REPORT_ROOTS, key=len,
                                  reverse=True) if rel.startswith(r + "/"))


def print_size(current, recorded, out=sys.stdout):
    refusals, soft = check_size(current, recorded)
    live = {r: n for r, n in current.items() if r in recorded}
    gone = sorted(set(recorded) - set(current))
    print("== size ratchet (soft %d / hard %d for new files / baseline "
          "never grows) ==" % (SOFT, HARD), file=out)
    for root in SIZE_ROOTS:
        mine = {r: n for r, n in live.items() if _tree_of(r) == root}
        allf = [n for r, n in current.items() if _tree_of(r) == root]
        print("  %-16s %4d files %8d lines | ratcheted %3d files %7d lines "
              "(recorded %7d)" % (root, len(allf), sum(allf), len(mine),
                                  sum(mine.values()),
                                  sum(recorded[r] for r in mine)), file=out)
    print("  ratcheted entries: %d live, %d gone (not an error); soft-limit "
          "files (%d..%d, not in baseline): %d"
          % (len(live), len(gone), SOFT + 1, HARD, len(soft)), file=out)
    tests = sizes(REPORT_ROOTS)
    big = [n for n in tests.values() if n > HARD]
    print("  reported, not gated: %s %d files, %d past %d (%d lines)"
          % (REPORT_ROOTS[0], len(tests), len(big), HARD, sum(big)), file=out)
    for r in refusals:
        print("  REFUSED " + r, file=out)
    return refusals


def print_dupes(groups, recorded, top=10, out=sys.stdout):
    n = duplicate_count(groups)
    print("== duplicate ratchet (top-level functions under %s with one "
          "normalised body in >= 2 files) ==" % DUP_ROOT, file=out)
    print("  %d functions in %d groups (baseline %s)  %s"
          % (n, len(groups), recorded,
             "OK" if recorded is None or n <= recorded else "FAIL"), file=out)
    for g in groups[:top] if top else groups:
        names = sorted({name for _, name, _ in g})
        print("  x%-2d %s" % (len(g), ", ".join(names)), file=out)
        for rel, name, line in g:
            print("        %s:%d %s" % (rel[len(DUP_ROOT) + 1:], line, name),
                  file=out)
    return check_duplicates(groups, recorded) if recorded is not None else []


def regenerate(path=BASELINE, init=False, current=None, groups=None):
    """Rewrite the baseline DOWNWARD.  Returns the list of refusals; the
    file is written only when it is empty."""
    current = sizes() if current is None else current
    groups = duplicate_groups() if groups is None else groups
    past = {r: n for r, n in current.items() if n > HARD}
    if init:
        if os.path.exists(path):
            return ["%s exists — --init never overwrites a baseline" % path]
        bad = []
    else:
        old = load_baseline(path)
        bad = [r for r in check_size(current, old["size"])[0]]
        bad += check_duplicates(groups, old["duplicates"])
    if bad:
        return bad
    doc = {"ruling": "RULINGS 2026-10-04a",
           "note": "generated by tools/ratchets.py --regenerate; entries "
                   "fall, never rise; never edit by hand",
           "soft": SOFT, "hard": HARD,
           "duplicates": duplicate_count(groups),
           "size": dict(sorted(past.items()))}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    return []


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("what", nargs="?", choices=("size", "dupes"))
    p.add_argument("--top", type=int, default=10,
                   help="dupes: groups to print (0 = all)")
    p.add_argument("--regenerate", action="store_true",
                   help="rewrite the baseline; refuses to raise any entry")
    p.add_argument("--init", action="store_true",
                   help="write the FIRST baseline; refuses if one exists")
    p.add_argument("--baseline", default=BASELINE)
    a = p.parse_args(argv)
    if a.regenerate or a.init:
        bad = regenerate(a.baseline, init=a.init)
        for r in bad:
            print("REFUSED " + r)
        if not bad:
            b = load_baseline(a.baseline)
            print("baseline written: %d files, %d lines, %d duplicates"
                  % (len(b["size"]), sum(b["size"].values()), b["duplicates"]))
        return 1 if bad else 0
    base = load_baseline(a.baseline)
    bad = []
    if a.what in (None, "size"):
        bad += print_size(sizes(), base["size"])
    if a.what in (None, "dupes"):
        bad += print_dupes(duplicate_groups(), base["duplicates"], a.top)
    print("RATCHETS " + ("PASS" if not bad else "FAIL"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
