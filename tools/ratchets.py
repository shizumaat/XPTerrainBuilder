#!/usr/bin/env python3
"""THE MERGE RATCHETS (owner RULINGS 2026-10-04a (1), (3) as amended by
2026-10-04b: no hard line limit; the priority is reuse).

Recorded in ``tools/ratchet_baseline.json``, asserted by
``Ortho4XP/tests/test_ratchets.py``:

SIZE.  Scope: tracked ``.py`` / ``.swift`` under ``Ortho4XP/src``,
``Ortho4XP/tools``, ``tools`` and ``Sources`` (lines as
``len(text.splitlines())`` — comments and blanks included; never fold
comments to make a number).  Modules past 1,000 lines should be rare:
a file that PASSES 1,000, or a file already past it that GROWS beyond its
recorded size, needs a RECORDED JUSTIFICATION — one line beside its entry
in the baseline, written by the explicit act ``--justify`` and visible in
the diff the master reviews.  Unjustified growth past 1,000 fails the
twin; justified growth (recorded size covers the file) passes.  Entries
taken at the first baseline need no justification until they grow.  A
baseline entry whose file is gone is not an error.  601..1,000 is a
reported soft band.  Tests are reported, never gated.

DUPLICATES (ratcheted).  Top-level functions under ``Ortho4XP/src`` whose
normalised AST (arguments + body, docstring dropped, name and decorators
ignored) is identical in two or more FILES.  The count is the number of
such functions and may fall, never rise.  One-statement stubs (``pass``,
``...``, a bare ``raise``, a ``return`` of a constant or a name) are not
counted: they are interface placeholders, not copied logic.

NEAR-DUPLICATES (reported, NOT gated — 04b (2)).  ``dupes --near``:
top-level functions and class methods under ``Ortho4XP/src`` whose bodies
are identical after renaming every parameter and locally-bound name to
its order of first appearance and replacing every constant by its type,
in two or more files.  Functions under ``NEAR_MIN_NODES`` AST nodes are
skipped (accessors and one-liners match by shape, not by copied logic).
Streaming: one file parsed at a time, one 16-byte digest kept per function.

    tools/ratchets.py                    # both checks; exit 1 on a refusal
    tools/ratchets.py size               # the size report alone
    tools/ratchets.py dupes [--top N]    # the identical-body groups
    tools/ratchets.py dupes --near       # the near-duplicate groups
    tools/ratchets.py --justify PATH "reason"   # record size + reason
    tools/ratchets.py --regenerate       # rewrite the baseline DOWNWARD

``--justify`` records the file's CURRENT size and the reason; it refuses
an empty reason and a file at or under 1,000.  ``--regenerate`` only
lowers: it keeps existing justifications, never invents one, and refuses
(writing nothing) on unjustified growth or a risen duplicate count.
``--init`` writes the first baseline and refuses when one already exists.
``tools/blast.py --audit`` prints the duplicate section and fails on a rise.
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
           "NEAR_MIN_NODES", "main"]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "tools", "ratchet_baseline.json")
SOFT, HARD = 600, 1000           # HARD: past it a justification is needed
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
    """``(refusals, soft)`` for ``current`` {rel: lines} against the
    baseline's ``recorded`` {rel: lines}.  A file past 1,000 passes when
    its recorded size covers it (first-baseline entries and justified
    ones alike — ``--justify`` is what raises a recorded size).  Entries
    of ``recorded`` with no file in ``current`` are ignored."""
    refusals, soft = [], []
    for rel, n in sorted(current.items()):
        cap = recorded.get(rel)
        if n > HARD and (cap is None or n > cap):
            refusals.append(
                "%s: %d lines, %s — growth past %d needs a recorded "
                "justification (RULINGS 2026-10-04b): split by "
                "responsibility, or `tools/ratchets.py --justify %s "
                "\"why it is one module\"`"
                % (rel, n, "not in the baseline" if cap is None
                   else "recorded %d" % cap, HARD, rel))
        elif cap is None and n > SOFT:
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


def print_size(current, recorded, out=sys.stdout, justified=None):
    refusals, soft = check_size(current, recorded)
    live = {r: n for r, n in current.items() if r in recorded}
    gone = sorted(set(recorded) - set(current))
    print("== size ratchet (soft band past %d / past %d growth needs a "
          "recorded justification) ==" % (SOFT, HARD), file=out)
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
    just = {r: why for r, why in sorted((justified or {}).items())
            if r in current}
    print("  justified past %d: %d" % (HARD, len(just)), file=out)
    for r, why in just.items():
        print("    %s (%d lines, recorded %d): %s"
              % (r, current[r], recorded.get(r, 0), why), file=out)
    for r in refusals:
        print("  REFUSED " + r, file=out)
    return refusals


def print_dupes(groups, recorded, top=10, out=sys.stdout, near=False):
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
    doc = {"ruling": "RULINGS 2026-10-04a, amended 2026-10-04b",
           "note": "generated by tools/ratchets.py (--regenerate lowers; "
                   "--justify PATH \"reason\" is the only way an entry "
                   "rises); never edit by hand",
           "soft": SOFT, "hard": HARD, "duplicates": duplicates,
           "size": dict(sorted(size.items())),
           "justified": dict(sorted(justified.items()))}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")


def regenerate(path=BASELINE, init=False, current=None, groups=None):
    """Rewrite the baseline DOWNWARD.  Returns the list of refusals; the
    file is written only when it is empty.  Justifications of files still
    past 1,000 are kept; none is ever invented."""
    current = sizes() if current is None else current
    groups = duplicate_groups() if groups is None else groups
    past = {r: n for r, n in current.items() if n > HARD}
    kept = {}
    if init:
        if os.path.exists(path):
            return ["%s exists — --init never overwrites a baseline" % path]
        bad = []
    else:
        old = load_baseline(path)
        bad = [r for r in check_size(current, old["size"])[0]]
        bad += check_duplicates(groups, old["duplicates"])
        kept = {r: w for r, w in old.get("justified", {}).items() if r in past}
    if bad:
        return bad
    _write_baseline(path, past, kept, duplicate_count(groups))
    return []


def justify(rel, reason, path=BASELINE, current=None):
    """THE EXPLICIT ACT (04b (1)): record ``rel``'s current size and the
    one-line ``reason``.  Returns refusals; writes only when it is empty."""
    reason = " ".join((reason or "").split())
    if not reason:
        return ["--justify needs a reason: one line saying why %s is one "
                "module" % rel]
    rel = os.path.relpath(os.path.abspath(rel), REPO) if os.path.isabs(rel) \
        else rel
    current = sizes() if current is None else current
    if rel not in current:
        return ["%s is not a tracked source file under %s"
                % (rel, ", ".join(SIZE_ROOTS))]
    if current[rel] <= HARD:
        return ["%s: %d lines — at or under %d needs no justification"
                % (rel, current[rel], HARD)]
    old = load_baseline(path)
    size, just = dict(old["size"]), dict(old.get("justified", {}))
    size[rel], just[rel] = current[rel], reason
    _write_baseline(path, size, just, old["duplicates"])
    return []


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("what", nargs="?", choices=("size", "dupes"))
    p.add_argument("--top", type=int, default=10,
                   help="dupes: groups to print (0 = all)")
    p.add_argument("--near", action="store_true",
                   help="dupes: the near-duplicate groups (reported, not "
                        "gated)")
    p.add_argument("--justify", nargs=2, metavar=("PATH", "REASON"),
                   help="record PATH's current size with a one-line reason")
    p.add_argument("--regenerate", action="store_true",
                   help="rewrite the baseline; refuses to raise any entry")
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
        bad += print_size(sizes(), base["size"],
                          justified=base.get("justified"))
    if a.what in (None, "dupes"):
        bad += print_dupes(duplicate_groups(), base["duplicates"], a.top)
    print("RATCHETS " + ("PASS" if not bad else "FAIL"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
