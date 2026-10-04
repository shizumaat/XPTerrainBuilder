"""TWINS FOR THE MERGE RATCHETS (owner RULINGS 2026-10-04a (1), (3)).

``tools/ratchets.py`` is the one implementation; ``tools/blast.py --audit``
and these twins read it.  The live assertions run on the checked-out tree
(no build, no corpus, no network); the rule itself is pinned on synthetic
inputs so a baseline that happens to be green cannot hide a broken rule.
"""
import json
import os
import sys
import warnings

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
sys.dont_write_bytecode = True          # no __pycache__ at the repo root

import ratchets  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists(ratchets.BASELINE),
    reason="no repo-root tools/ratchet_baseline.json in this checkout")


# ------------------------------------------------------------------ live
def test_size_ratchet_holds_on_this_tree():
    base = ratchets.load_baseline()
    assert (base["soft"], base["hard"]) == (ratchets.SOFT, ratchets.HARD)
    refusals, soft = ratchets.check_size(ratchets.sizes(), base["size"])
    if soft:                             # ONE warning, not one per file
        worst = sorted(soft, key=lambda x: -x[1])[:5]
        warnings.warn("%d files past the %d-line soft limit (largest: %s) — "
                      "a PR that takes a file past it says why it is not split"
                      % (len(soft), ratchets.SOFT,
                         ", ".join("%s %d" % x for x in worst)), stacklevel=1)
    assert not refusals, "\n".join(refusals)


def test_baseline_lists_only_files_that_were_past_the_hard_limit():
    """An entry at or under 1,000 would be a licence to grow back to it."""
    base = ratchets.load_baseline()["size"]
    assert base and all(n > ratchets.HARD for n in base.values())
    assert all(r.startswith(tuple(x + "/" for x in ratchets.SIZE_ROOTS))
               and r.endswith(ratchets.EXTS) for r in base)


def test_duplicate_ratchet_holds_on_this_tree():
    groups = ratchets.duplicate_groups()
    bad = ratchets.check_duplicates(groups, ratchets.load_baseline()["duplicates"])
    assert not bad, bad[0] + "\n" + "\n".join(
        "%s:%d %s" % m for g in groups for m in g)


# ------------------------------------------------------------- the rule
def test_size_rule_new_file_soft_hard_and_ratchet():
    recorded = {"tools/old.py": 1200, "tools/gone.py": 5000}
    refusals, soft = ratchets.check_size(
        {"tools/a.py": 600, "tools/b.py": 601, "tools/c.py": 1000,
         "tools/old.py": 1200}, recorded)
    assert refusals == []                      # a gone entry is not an error
    assert soft == [("tools/b.py", 601), ("tools/c.py", 1000)]
    refusals, _ = ratchets.check_size({"tools/c.py": 1001}, recorded)
    assert len(refusals) == 1 and "hard limit" in refusals[0]
    refusals, _ = ratchets.check_size({"tools/old.py": 1201}, recorded)
    assert len(refusals) == 1 and "never grow" in refusals[0]
    # 13bz's 1,500 band is gone: a ratcheted file may sit past it, a new
    # file may not sit anywhere past 1,000
    assert ratchets.check_size({"tools/old.py": 1199}, recorded)[0] == []


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return name


def test_duplicate_rule_normalises_and_needs_two_files(tmp_path):
    body = "    t = [p for p in ring]\n    return t[:-1] if t[0] == t[-1] else t\n"
    files = [
        _write(tmp_path, "a.py", "def _open_ring(ring):\n" + body),
        # other name, a docstring, a comment, other spacing: still the same
        _write(tmp_path, "b.py", 'def opened(ring):\n    """doc."""\n    # c\n'
               + body.replace(" = ", "  =  ")),
        # the same body twice in ONE file is not a cross-file duplicate
        _write(tmp_path, "c.py", "def f(x):\n    return x + 1\n\n"
                                 "def g(x):\n    return x + 1\n"),
        # a different argument list is a different function
        _write(tmp_path, "d.py", "def _open_ring(ring, k=1):\n" + body),
        # one-statement stubs and methods are not counted
        _write(tmp_path, "e.py", "def s():\n    raise NotImplementedError\n\n"
               "class K:\n    def _open_ring(ring):\n" + body.replace("    ", "        ")),
        _write(tmp_path, "f.py", "def s():\n    raise NotImplementedError\n"),
        _write(tmp_path, "broken.py", "def (:\n"),
    ]
    groups = ratchets.duplicate_groups(files, repo=str(tmp_path))
    assert groups == [[("a.py", "_open_ring", 1), ("b.py", "opened", 1)]]
    assert ratchets.duplicate_count(groups) == 2
    assert ratchets.check_duplicates(groups, 2) == []
    assert ratchets.check_duplicates(groups, 1)


def test_regenerate_only_ever_lowers(tmp_path):
    path = str(tmp_path / "baseline.json")
    g2 = [[("a.py", "f", 1), ("b.py", "f", 1)]]
    assert ratchets.regenerate(path, init=True, groups=g2, current={
        "tools/big.py": 1500, "tools/small.py": 10}) == []
    assert json.load(open(path))["size"] == {"tools/big.py": 1500}
    assert ratchets.regenerate(path, init=True, groups=g2, current={})  # exists
    before = open(path).read()
    # a grown entry, a new file past the hard limit, a risen duplicate
    # count: each refuses and writes nothing
    for cur, grp in (({"tools/big.py": 1501}, g2),
                     ({"tools/big.py": 1500, "tools/new.py": 1001}, g2),
                     ({"tools/big.py": 1500}, g2 + [[("c.py", "h", 1),
                                                     ("d.py", "h", 1)]])):
        assert ratchets.regenerate(path, groups=grp, current=cur)
        assert open(path).read() == before
    # shrink, delete, and a file that fell under the limit leaves the list
    assert ratchets.regenerate(path, groups=[], current={"tools/big.py": 1100}) == []
    doc = json.load(open(path))
    assert doc["size"] == {"tools/big.py": 1100} and doc["duplicates"] == 0
    assert ratchets.regenerate(path, groups=[], current={"tools/big.py": 900}) == []
    assert json.load(open(path))["size"] == {}


def test_blast_audit_carries_the_duplicate_section():
    """`blast.py --audit` is the ruled home of the duplicate count."""
    src = open(os.path.join(TOOLS, "blast.py"), encoding="utf-8").read()
    assert "ratchets.print_dupes(" in src and "ratchets.duplicate_groups()" in src


def test_ratchets_is_indexed():
    index = open(os.path.join(TOOLS, "INDEX.md"), encoding="utf-8").read()
    assert "| `tools/ratchets.py` |" in index
    assert "| `tools/ratchet_baseline.json` |" in index
