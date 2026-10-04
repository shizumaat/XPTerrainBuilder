"""TWINS FOR ``tools/ratchets.py`` (owner RULINGS 2026-10-04a (1), (3),
amended 04b and 04c).

SIZE IS A GUIDE AND A WARNING, NEVER A GATE (04c (1)): nothing here
asserts on a file's length — growth past 1,000 with no note PASSES and is
reported.  THE DUPLICATE RATCHET IS THE GATE (04c (2)): the identical-body
count may fall, never rise.  The live assertions run on the checked-out
tree (no build, no corpus, no network); the rules are pinned on synthetic
inputs.
"""
import io
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
def test_size_is_reported_and_never_fails_on_this_tree():
    base = ratchets.load_baseline()
    out = io.StringIO()
    rep = ratchets.print_size(ratchets.sizes(), base["size"], out=out,
                              justified=base.get("justified"))
    assert "never a gate" in out.getvalue()
    if rep["grew"] or rep["new"]:        # ONE warning; the test still passes
        warnings.warn("size report: %d grew, %d newly past %d — %s"
                      % (len(rep["grew"]), len(rep["new"]), ratchets.HARD,
                         ", ".join(x[0] for x in rep["grew"] + rep["new"])),
                      stacklevel=1)


def test_baseline_snapshot_lists_only_files_past_1000():
    base = ratchets.load_baseline()["size"]
    assert all(n > ratchets.HARD for n in base.values())
    assert all(r.startswith(tuple(x + "/" for x in ratchets.SIZE_ROOTS))
               and r.endswith(ratchets.EXTS) for r in base)


def test_duplicate_ratchet_holds_on_this_tree():
    groups = ratchets.duplicate_groups()
    bad = ratchets.check_duplicates(groups, ratchets.load_baseline()["duplicates"])
    assert not bad, bad[0] + "\n" + "\n".join(
        "%s:%d %s" % m for g in groups for m in g)


# ------------------------------------------------------------- the rule
def test_size_report_names_growth_and_new_files_without_refusing():
    recorded = {"tools/old.py": 1200, "tools/gone.py": 5000,
                "tools/shrunk.py": 1300}
    rep = ratchets.check_size(
        {"tools/a.py": 600, "tools/b.py": 601, "tools/c.py": 1000,
         "tools/old.py": 1450, "tools/shrunk.py": 1250,
         "tools/new.py": 1001}, recorded)
    assert rep["soft"] == [("tools/b.py", 601), ("tools/c.py", 1000)]
    assert rep["grew"] == [("tools/old.py", 1200, 1450)]
    assert rep["new"] == [("tools/new.py", 1001)]
    assert [r for r, _ in rep["past"]] == [
        "tools/new.py", "tools/old.py", "tools/shrunk.py"]


def test_default_run_exits_zero_on_size_and_one_on_duplicates(
        tmp_path, monkeypatch, capsys):
    """04c: growth past 1,000 with NO justification passes and is
    reported; a risen duplicate count still fails."""
    path = str(tmp_path / "baseline.json")
    g2 = [[("a.py", "f", 1), ("b.py", "f", 1)]]
    grown = {"tools/big.py": 1600, "tools/new.py": 1100}
    assert ratchets.regenerate(path, init=True, groups=g2, current={
        "tools/big.py": 1500}) == []
    monkeypatch.setattr(ratchets, "sizes", lambda roots=None: (
        grown if roots is None else {}))
    monkeypatch.setattr(ratchets, "long_functions", lambda: [])
    monkeypatch.setattr(ratchets, "duplicate_groups", lambda: g2)
    assert ratchets.main(["--baseline", path]) == 0
    out = capsys.readouterr().out
    assert "WARN tools/big.py: 1500 -> 1600 (+100)" in out
    assert "WARN tools/new.py: 1100" in out
    assert "DUPLICATE RATCHET PASS" in out
    monkeypatch.setattr(ratchets, "duplicate_groups", lambda: g2 + [
        [("c.py", "h", 1), ("d.py", "h", 1)]])
    assert ratchets.main(["--baseline", path]) == 1
    assert "DUPLICATE RATCHET FAIL" in capsys.readouterr().out


def test_long_functions_are_listed_longest_first(tmp_path):
    pad = "".join("    x%d = %d\n" % (i, i) for i in range(210))
    files = [
        _write(tmp_path, "a.py", "def short():\n    return 1\n\n"
               "def long_one():\n" + pad + "    return 0\n"),
        _write(tmp_path, "b.py", "class K:\n    def m(self):\n"
               + pad.replace("    x", "        x") + pad.replace("    x", "        y")
               + "        def inner():\n" + pad.replace("    x", "            x")
               + "        return inner\n"),
        _write(tmp_path, "broken.py", "def (:\n"),
    ]
    got = ratchets.long_functions(files, repo=str(tmp_path))
    assert [(n, name) for n, _, name, _ in got] == [
        (633, "K.m"), (212, "long_one"), (211, "K.m.inner")]
    assert ratchets.long_functions(files, repo=str(tmp_path), min_lines=700) == []
    out = io.StringIO()
    ratchets.print_funcs(
        [(250, "Ortho4XP/src/auto_patch_v2/x.py", "f", 3),
         (220, "tools/y.py", "g", 9)], out=out)
    assert "2 functions (Ortho4XP/src 1, tools 1; auto_patch_v2 1)" in out.getvalue()


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
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


def test_regenerate_snapshots_sizes_and_refuses_only_risen_duplicates(tmp_path):
    path = str(tmp_path / "baseline.json")
    g2 = [[("a.py", "f", 1), ("b.py", "f", 1)]]
    assert ratchets.regenerate(path, init=True, groups=g2, current={
        "tools/big.py": 1500, "tools/small.py": 10}) == []
    assert json.load(open(path, encoding="utf-8"))["size"] == {"tools/big.py": 1500}
    assert ratchets.regenerate(path, init=True, groups=g2, current={})  # exists
    before = open(path, encoding="utf-8").read()
    # a risen duplicate count refuses and writes nothing
    assert ratchets.regenerate(path, current={"tools/big.py": 1500}, groups=g2 + [
        [("c.py", "h", 1), ("d.py", "h", 1)]])
    assert open(path, encoding="utf-8").read() == before
    # growth and a new file past 1,000 are RECORDED (04c: a snapshot)
    assert ratchets.regenerate(path, groups=g2, current={
        "tools/big.py": 1501, "tools/new.py": 1001}) == []
    assert json.load(open(path, encoding="utf-8"))["size"] == {
        "tools/big.py": 1501, "tools/new.py": 1001}
    # shrink, delete, and a file that fell to 1,000 leaves the list
    assert ratchets.regenerate(path, groups=[], current={"tools/big.py": 900}) == []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["size"] == {} and doc["duplicates"] == 0


def test_justify_is_an_optional_note_shown_in_the_report(tmp_path):
    path = str(tmp_path / "baseline.json")
    cur = {"tools/big.py": 1500, "tools/new.py": 900}
    assert ratchets.regenerate(path, init=True, groups=[], current=cur) == []
    assert json.load(open(path, encoding="utf-8"))["justified"] == {}     # none invented
    grown = {"tools/big.py": 1600, "tools/new.py": 1100}
    before = open(path, encoding="utf-8").read()
    for reason in ("", "   ", "\n"):
        assert ratchets.justify("tools/big.py", reason, path, current=grown)
    assert ratchets.justify("tools/absent.py", "why", path, current=grown)
    assert ratchets.justify("tools/new.py", "why", path, current=cur)  # <= 1,000
    assert open(path, encoding="utf-8").read() == before
    assert ratchets.justify("tools/big.py", " one solver,\n one file ", path,
                            current=grown) == []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["size"]["tools/big.py"] == 1600
    assert doc["justified"] == {"tools/big.py": "one solver, one file"}
    # regenerate keeps the note while the file is past 1,000
    assert ratchets.regenerate(path, groups=[], current={
        "tools/big.py": 1700, "tools/new.py": 800}) == []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["size"] == {"tools/big.py": 1700}
    assert doc["justified"] == {"tools/big.py": "one solver, one file"}
    out = io.StringIO()
    ratchets.print_size({"tools/big.py": 1800}, doc["size"], out=out,
                        justified=doc["justified"])
    assert ("WARN tools/big.py: 1700 -> 1800 (+100)  [note: one solver, one "
            "file]") in out.getvalue()


def test_live_justifications_are_real():
    base = ratchets.load_baseline()
    for rel, why in base.get("justified", {}).items():
        assert rel in base["size"] and why.strip(), rel


def test_near_duplicates_ignore_local_names_and_constants(tmp_path):
    a = ("def clamp(vals, lo):\n    out = []\n    for v in vals:\n"
         "        out.append(max(v, lo) * 2.0)\n    return sorted(out)[:10]\n")
    b = ("class K:\n    def squash(self_, floor):\n        'doc.'\n"
         "        res = []\n        for x in self_:\n"
         "            res.append(max(x, floor) * 3.5)\n"
         "        return sorted(res)[:99]\n")
    c = a.replace("max(", "min(")            # another callee: other logic
    files = [_write(tmp_path, "a.py", a), _write(tmp_path, "b.py", b),
             _write(tmp_path, "c.py", c),
             _write(tmp_path, "tiny1.py", "def f(a):\n    return a + 1\n"),
             _write(tmp_path, "tiny2.py", "def g(b):\n    return b + 2\n")]
    groups = ratchets.near_duplicate_groups(files, repo=str(tmp_path))
    assert groups == [[("a.py", "clamp", 1), ("b.py", "K.squash", 2)]]
    # the identical-body ratchet does NOT see this pair
    assert ratchets.duplicate_groups(files, repo=str(tmp_path)) == []
    out = io.StringIO()
    assert ratchets.print_dupes(groups, None, out=out, near=True) == []
    assert "NOT GATED" in out.getvalue()


def test_blast_audit_carries_the_duplicate_section():
    """`blast.py --audit` is the ruled home of the duplicate count."""
    src = open(os.path.join(TOOLS, "blast.py"), encoding="utf-8").read()
    assert "ratchets.print_dupes(" in src and "ratchets.duplicate_groups()" in src


def test_ratchets_is_indexed():
    index = open(os.path.join(TOOLS, "INDEX.md"), encoding="utf-8").read()
    assert "| `tools/ratchets.py` |" in index
    assert "| `tools/ratchet_baseline.json` |" in index
