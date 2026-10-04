#!/usr/bin/env python3
"""THE MERGE REPORT AND THE DUPLICATE RATCHET (owner RULINGS 2026-10-04a
(1), (3), amended 04b and 04c: size is a guide and a warning, never a
gate; split by responsibility, never to make a number; the priority is
reuse).

Recorded in ``tools/ratchet_baseline.json``; twin
``Ortho4XP/tests/test_ratchets.py``.

SIZE — REPORTED, NEVER FAILS A TEST OR A MERGE (04c (1)).  Scope: tracked
``.py`` / ``.swift`` under ``Ortho4XP/src``, ``Ortho4XP/tools``, ``tools``
and ``Sources`` (lines as ``len(text.splitlines())``, comments and blanks
included).  The report the master reads at merge: files past 1,000, files
past 1,000 that GREW against the baseline snapshot (name, old -> new),
files NEWLY past 1,000, the 601..1,000 count, and the tests summary.  A
split is made because a file holds two responsibilities, never to reach a
number.  ``--justify PATH "reason"`` is an OPTIONAL NOTE shown beside the
file in the report; it is not a pass condition.

LONG FUNCTIONS — reported the same way (04c (1): "the better target").
``funcs``: every function and method (nested ones included) of
``LONG_FUNCTION``+ lines (``def`` line to last line, decorators
excluded) in the ``.py`` files of the size roots, longest first.

DUPLICATES — THE ONE GATE (04c (2)).  Top-level functions under
``Ortho4XP/src`` whose normalised AST (arguments + body, docstring
dropped, name and decorators ignored) is identical in two or more FILES.
The count is the number of such functions and may fall, never rise.
One-statement stubs (``pass``, ``...``, a bare ``raise``, a ``return`` of
a constant or a name) are not counted.

NEAR-DUPLICATES — reported, not gated (04b (2)).  ``dupes --near``:
top-level functions and class methods under ``Ortho4XP/src`` whose bodies
are identical after renaming every parameter and locally-bound name to
its order of first appearance and replacing every constant by its type,
in two or more files.  Functions under ``NEAR_MIN_NODES`` AST nodes are
skipped.  Streaming: one file parsed at a time, one digest per function.

    tools/ratchets.py                    # all sections; exit 1 ONLY on a
                                         # risen duplicate count
    tools/ratchets.py size               # the size report alone
    tools/ratchets.py funcs [--top N]    # the long functions
    tools/ratchets.py dupes [--top N]    # the identical-body groups
    tools/ratchets.py dupes --near       # the near-duplicate groups
    tools/ratchets.py --justify PATH "reason"   # an optional note
    tools/ratchets.py --regenerate       # re-snapshot the baseline

``--regenerate`` re-snapshots the sizes (growth included — the snapshot
is what "grew" is measured against), keeps existing notes, and refuses
(writing nothing) only on a risen duplicate count.  ``--init`` writes the
first baseline and refuses when one exists.  ``tools/blast.py --audit``
prints the duplicate section and fails on a rise.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys

__all__ = ["SOFT", "HARD", "SIZE_ROOTS", "DUP_ROOT", "BASELINE",
           "tracked_sources", "line_count", "sizes", "check_size",
           "duplicate_groups", "duplicate_count", "check_duplicates",
           "load_baseline", "regenerate", "justify", "near_duplicate_groups",
           "NEAR_MIN_NODES", "long_functions", "LONG_FUNCTION", "main"]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "tools", "ratchet_baseline.json")
SOFT, HARD = 600, 1000           # report bands only (04c): never a gate
LONG_FUNCTION = 200
NEAR_MIN_NODES = 25
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
    """THE SIZE REPORT — warnings only, never a refusal (04c (1)).
    ``current`` {rel: lines} against the baseline snapshot ``recorded``:
    ``past`` every file past 1,000, ``grew`` those above their recorded
    size ``(rel, old, new)``, ``new`` those past 1,000 with no record
    ``(rel, lines)``, ``soft`` the 601..1,000 band.  Entries of
    ``recorded`` with no file in ``current`` are ignored."""
    rep = {"past": [], "grew": [], "new": [], "soft": []}
    for rel, n in sorted(current.items()):
        cap = recorded.get(rel)
        if n > HARD:
            rep["past"].append((rel, n))
            if cap is None:
                rep["new"].append((rel, n))
            elif n > cap:
                rep["grew"].append((rel, cap, n))
        elif n > SOFT:
            rep["soft"].append((rel, n))
    return rep


def long_functions(files=None, repo=REPO, min_lines=LONG_FUNCTION):
    """Functions and methods of ``min_lines``+ lines, longest first, as
    ``(lines, rel, qualified name, lineno)``.  Streaming: one tree at a
    time, only the long ones kept."""
    if files is None:
        files = tracked_sources(SIZE_ROOTS, repo, exts=(".py",))
    out = []
    for rel in files:
        try:
            with open(os.path.join(repo, rel), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        stack = [("", tree)]
        while stack:
            prefix, node = stack.pop()
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                    name = prefix + ch.name
                    if not isinstance(ch, ast.ClassDef):
                        n = ch.end_lineno - ch.lineno + 1
                        if n >= min_lines:
                            out.append((n, rel, name, ch.lineno))
                    stack.append((name + ".", ch))
                else:
                    stack.append((prefix, ch))
        del tree
    return sorted(out, key=lambda x: (-x[0], x[1], x[3]))


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


# -------------------------------------------------------- near-duplicates
def _near_digest(fn):
    """16-byte digest of ``fn`` with parameters / locally-bound names
    renamed by first appearance and constants replaced by their type, or
    None when it is a stub or too small.  MUTATES ``fn`` (the caller
    discards the tree)."""
    body = fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = fn.body = body[1:]
    if not body or _is_stub(body):
        return None
    nodes = list(ast.walk(fn))
    if len(nodes) < NEAR_MIN_NODES:
        return None
    local = {n.arg for n in nodes if isinstance(n, ast.arg)} | {
        n.id for n in nodes if isinstance(n, ast.Name)
        and isinstance(n.ctx, (ast.Store, ast.Del))}
    order = {}
    for n in nodes:                       # ast.walk order is deterministic
        if isinstance(n, ast.arg):
            n.arg = order.setdefault(n.arg, "v%d" % len(order))
            n.annotation = None
        elif isinstance(n, ast.Name) and n.id in local:
            n.id = order.setdefault(n.id, "v%d" % len(order))
        elif isinstance(n, ast.Constant):
            n.value = type(n.value).__name__
            n.kind = None
    fn.returns = None
    text = ast.dump(fn.args) + "".join(ast.dump(s) for s in body)
    return hashlib.blake2b(text.encode(), digest_size=16).digest()


def near_duplicate_groups(files=None, repo=REPO):
    """Near-duplicate groups (see the module docstring), largest first,
    as ``[(rel, qualified name, lineno), ...]`` spanning >= 2 files."""
    if files is None:
        files = tracked_sources((DUP_ROOT,), repo, exts=(".py",))
    seen = {}
    for rel in files:
        try:
            with open(os.path.join(repo, rel), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        fns = [("", n) for n in tree.body]
        fns += [(c.name + ".", n) for c in tree.body
                if isinstance(c, ast.ClassDef) for n in c.body]
        for prefix, node in fns:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name, line = prefix + node.name, node.lineno
                key = _near_digest(node)
                if key is not None:
                    seen.setdefault(key, []).append((rel, name, line))
        del tree, fns
    groups = [sorted(g) for g in seen.values() if len({r for r, _, _ in g}) > 1]
    return sorted(groups, key=lambda g: (-len(g), g))


# ------------------------------------------------------------------ report
def _tree_of(rel):
    return next(r for r in sorted(SIZE_ROOTS + REPORT_ROOTS, key=len,
                                  reverse=True) if rel.startswith(r + "/"))


def print_size(current, recorded, out=None, justified=None):
    """Print the size report; returns it.  Nothing here fails anything."""
    out = out or sys.stdout
    rep = check_size(current, recorded)
    notes = justified or {}
    gone = sorted(set(recorded) - set(current))
    print("== size report — a guide and a warning, never a gate (soft band "
          "past %d, look at the architecture past %d) ==" % (SOFT, HARD),
          file=out)
    for root in SIZE_ROOTS:
        allf = [n for r, n in current.items() if _tree_of(r) == root]
        mine = [n for r, n in rep["past"] if _tree_of(r) == root]
        print("  %-16s %4d files %8d lines | past %d: %3d files %7d lines"
              % (root, len(allf), sum(allf), HARD, len(mine), sum(mine)),
              file=out)
    print("  past %d: %d files; %d..%d band: %d files; baseline entries "
          "whose file is gone: %d"
          % (HARD, len(rep["past"]), SOFT + 1, HARD, len(rep["soft"]),
             len(gone)), file=out)

    def note(rel):
        return "  [note: %s]" % notes[rel] if rel in notes else ""
    print("  GREW since the baseline: %d" % len(rep["grew"]), file=out)
    for rel, old, new in rep["grew"]:
        print("    WARN %s: %d -> %d (+%d)%s"
              % (rel, old, new, new - old, note(rel)), file=out)
    print("  NEWLY past %d: %d" % (HARD, len(rep["new"])), file=out)
    for rel, n in rep["new"]:
        print("    WARN %s: %d%s" % (rel, n, note(rel)), file=out)
    rest = [r for r in sorted(notes) if r in current
            and r not in {x[0] for x in rep["grew"] + rep["new"]}]
    for rel in rest:
        print("    note %s (%d lines): %s" % (rel, current[rel], notes[rel]),
              file=out)
    tests = sizes(REPORT_ROOTS)
    big = [n for n in tests.values() if n > HARD]
    print("  tests (reported only): %s %d files, %d past %d (%d lines)"
          % (REPORT_ROOTS[0], len(tests), len(big), HARD, sum(big)), file=out)
    return rep


def print_funcs(funcs, top=10, out=None):
    out = out or sys.stdout
    print("== long functions — reported, never a gate (functions and "
          "methods of %d+ lines under the size roots) ==" % LONG_FUNCTION,
          file=out)
    by = {}
    for n, rel, _, _ in funcs:
        by[_tree_of(rel)] = by.get(_tree_of(rel), 0) + 1
    v2 = sum(1 for _, rel, _, _ in funcs
             if rel.startswith(DUP_ROOT + "/auto_patch_v2/"))
    print("  %d functions (%s; auto_patch_v2 %d)"
          % (len(funcs), ", ".join("%s %d" % kv for kv in sorted(by.items())),
             v2), file=out)
    for n, rel, name, line in funcs[:top] if top else funcs:
        print("  %5d  %s:%d %s" % (n, rel, line, name), file=out)


def print_dupes(groups, recorded, top=10, out=None, near=False):
    out = out or sys.stdout
    n = duplicate_count(groups)
    if near:
        print("== near-duplicates, REPORTED NOT GATED (functions and "
              "methods under %s, >= %d AST nodes, identical after renaming "
              "locals and typing constants, in >= 2 files) =="
              % (DUP_ROOT, NEAR_MIN_NODES), file=out)
        print("  %d functions in %d groups" % (n, len(groups)), file=out)
    else:
        print("== duplicate ratchet (top-level functions under %s with one "
              "normalised body in >= 2 files) ==" % DUP_ROOT, file=out)
        print("  %d functions in %d groups (baseline %s)  %s"
              % (n, len(groups), recorded, "OK" if recorded is None
                 or n <= recorded else "FAIL"), file=out)
    for g in groups[:top] if top else groups:
        names = sorted({name for _, name, _ in g})
        print("  x%-2d %s" % (len(g), ", ".join(names)), file=out)
        for rel, name, line in g:
            print("        %s:%d %s" % (rel[len(DUP_ROOT) + 1:], line, name),
                  file=out)
    if near or recorded is None:
        return []
    return check_duplicates(groups, recorded)


def _write_baseline(path, size, justified, duplicates):
    doc = {"ruling": "RULINGS 2026-10-04a, amended 04b and 04c",
           "note": "generated by tools/ratchets.py; `size` is a snapshot "
                   "the report measures growth against (never a gate), "
                   "`duplicates` may fall and never rise; never edit by "
                   "hand",
           "soft": SOFT, "hard": HARD, "duplicates": duplicates,
           "size": dict(sorted(size.items())),
           "justified": dict(sorted(justified.items()))}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")


def regenerate(path=BASELINE, init=False, current=None, groups=None):
    """Re-snapshot the baseline: every file past 1,000 at its CURRENT size
    (growth included — size is a report, 04c), notes kept for files still
    past 1,000, none invented.  Refuses, writing nothing, only on a risen
    duplicate count.  Returns the list of refusals."""
    current = sizes() if current is None else current
    groups = duplicate_groups() if groups is None else groups
    past = {r: n for r, n in current.items() if n > HARD}
    kept = {}
    if init:
        if os.path.exists(path):
            return ["%s exists — --init never overwrites a baseline" % path]
    else:
        old = load_baseline(path)
        bad = check_duplicates(groups, old["duplicates"])
        if bad:
            return bad
        kept = {r: w for r, w in old.get("justified", {}).items() if r in past}
    _write_baseline(path, past, kept, duplicate_count(groups))
    return []


def justify(rel, reason, path=BASELINE, current=None):
    """AN OPTIONAL NOTE (04c (1)): record the one-line ``reason`` beside
    ``rel`` (and its current size); the report shows it.  Not a pass
    condition.  Returns refusals; writes only when it is empty."""
    reason = " ".join((reason or "").split())
    if not reason:
        return ["--justify needs a reason: one line saying why %s is one "
                "module (it is the note the master reads)" % rel]
    rel = os.path.relpath(os.path.abspath(rel), REPO) if os.path.isabs(rel) \
        else rel
    current = sizes() if current is None else current
    if rel not in current:
        return ["%s is not a tracked source file under %s"
                % (rel, ", ".join(SIZE_ROOTS))]
    if current[rel] <= HARD:
        return ["%s: %d lines — at or under %d, nothing to note"
                % (rel, current[rel], HARD)]
    old = load_baseline(path)
    size, just = dict(old["size"]), dict(old.get("justified", {}))
    size[rel], just[rel] = current[rel], reason
    _write_baseline(path, size, just, old["duplicates"])
    return []


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("what", nargs="?", choices=("size", "funcs", "dupes"))
    p.add_argument("--top", type=int, default=10,
                   help="dupes / funcs: rows to print (0 = all)")
    p.add_argument("--near", action="store_true",
                   help="dupes: the near-duplicate groups (reported, not "
                        "gated)")
    p.add_argument("--justify", nargs=2, metavar=("PATH", "REASON"),
                   help="an optional one-line note shown beside PATH in "
                        "the size report")
    p.add_argument("--regenerate", action="store_true",
                   help="re-snapshot the baseline; refuses only a risen "
                        "duplicate count")
    p.add_argument("--init", action="store_true",
                   help="write the FIRST baseline; refuses if one exists")
    p.add_argument("--baseline", default=BASELINE)
    a = p.parse_args(argv)
    if a.justify:
        bad = justify(a.justify[0], a.justify[1], a.baseline)
        for r in bad:
            print("REFUSED " + r)
        if not bad:
            print("justified: %s" % a.justify[0])
        return 1 if bad else 0
    if a.near:
        print_dupes(near_duplicate_groups(), None, a.top, near=True)
        return 0
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
        print_size(sizes(), base["size"], justified=base.get("justified"))
    if a.what in (None, "funcs"):
        print_funcs(long_functions(), a.top)
    if a.what in (None, "dupes"):
        bad += print_dupes(duplicate_groups(), base["duplicates"], a.top)
    if a.what in (None, "dupes"):
        print("DUPLICATE RATCHET " + ("PASS" if not bad else "FAIL")
              + " (size and long functions are reports, never a gate)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
