"""Twins for the lane-startup surface (owner 2026-09-13): `tools/docq.py`,
`tools/brief_pack.py`, `tools/harness/frames.py`.

The point of these tools is that a lane reads ONE section, ONE ruling, ONE
index row — so the twins assert exactness: a spec query returns the whole
requested section and nothing filed between its sub-blocks; a ruling query
returns one entry with its bullets; every INDEX row parses; a missing key
is a named refusal, never an empty print.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "harness"))
import docq  # noqa: E402
import frames  # noqa: E402


def _cli(*args):
    return subprocess.run([sys.executable, os.path.join(TOOLS, "docq.py"), *args],
                          capture_output=True, text=True)


def test_spec_section_returns_the_section_and_all_its_sub_blocks():
    text = docq.spec_section(docq.SPEC_DESIGN, "§37")
    heads = [ln for ln in text.split("\n") if re.match(r"^#{2,3} §", ln)]
    assert heads[0].startswith("## §37 ")
    keys = [re.match(r"^#{2,3} (§\S+(?: \(\d+\))?)", h).group(1) for h in heads]
    assert all(k == "§37" or k.startswith("§37 ") or k.startswith("§37.") for k in keys), keys
    # sub-blocks filed later in the file are included …
    assert any(k.startswith("§37 (6)") for k in keys)
    # … and a foreign block filed between them is NOT
    assert "§32 (4)" not in text.split("\n")[0]
    assert not any(ln.startswith("### §32") for ln in text.split("\n"))


def test_spec_sub_block_is_exact():
    text = docq.spec_section(docq.SPEC_DESIGN, "§37 (6)")
    lines = text.split("\n")
    assert lines[0].startswith("### §37 (6) ")
    # every block returned is a §37 (6) block — the original and any later
    # "§37 (6) AMENDED …" heading — and nothing else
    heads = [ln for ln in lines if re.match(r"^#{2,3} §", ln)]
    assert heads and all(h.split(" ", 1)[1].startswith("§37 (6)") for h in heads), heads
    # a size guard, not a law: §37 (6) carries three lane rounds of MEASURED
    # blocks (2026-09-13); the exactness assertions above are the twin
    assert len(text) < 80_000


def test_object_spec_is_addressable():
    text = docq.spec_section(docq.SPEC_OBJECT, "§16f")
    assert text.startswith("## §16f ")


def test_missing_spec_key_is_a_named_refusal():
    r = _cli("spec", "§999")
    assert r.returncode != 0 and "no spec heading matches" in r.stderr
    assert r.stdout.strip() == ""


def test_ruling_by_short_id_returns_one_entry_with_its_bullets():
    text = docq.ruling_entry(["13ak"])
    assert text.startswith("## 2026-09-13ak ")
    assert text.count("\n## ") == 0            # exactly one entry
    assert "\n* " in text                        # its bullets ride along


def test_ruling_missing_is_a_named_refusal():
    r = _cli("ruling", "13zz")
    assert r.returncode != 0 and "no RULINGS entry" in r.stderr


def test_every_index_row_parses_and_the_short_index_is_short():
    raw = sum(1 for ln in open(docq.INDEX, encoding="utf-8") if ln.startswith("| `"))
    rows = docq.index_rows()
    assert len(rows) == raw, (len(rows), raw)
    short = docq.index_short()
    assert short.count("\n") + 1 == raw
    assert len(short) < 20_000                  # the point: ~3k tokens, not ~69k
    for path, _ in rows:
        assert path in short
    # the near-fit lookup returns the FULL row
    full = docq.index_full("seat_feet_census")
    assert full.startswith("| `") and "seat_feet_census" in full


def test_frames_registry_round_trip(tmp_path, monkeypatch):
    reg = tmp_path / "frames.jsonl"
    monkeypatch.setattr(frames, "REGISTRY", str(reg))
    p = tmp_path / "KCLT.pkl"; p.write_bytes(b"x")
    frames.register("kclt", "capture", str(p), "864e7577", "v2test", "unit")
    rows = frames.list_frames("KCLT", "capture")
    assert len(rows) == 1 and rows[0]["icao"] == "KCLT" and rows[0]["base"] == "864e7577"
    assert frames.latest("KCLT", "capture")["path"] == str(p)
    with pytest.raises(SystemExit):
        frames.register("KCLT", "capture", str(tmp_path / "nope.pkl"), "x", "y")
    with pytest.raises(SystemExit):
        frames.register("KCLT", "bogus", str(p), "x", "y")
    p.unlink()
    assert frames.latest("KCLT", "capture") is None   # a vanished path is never served
    assert json.loads(reg.read_text().splitlines()[0])["lane"] == "v2test"


def test_brief_pack_assembles_from_the_tools(tmp_path):
    notes = tmp_path / "n.md"; notes.write_text("Do the thing.")
    bars = tmp_path / "b.md"; bars.write_text("- bar one")
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "brief_pack.py"),
                        "--lane", "v2test", "--base", "abcdef12", "--spec", "§37 (6)",
                        "--rulings", "13aj", "--index", "road_terrain_conformance",
                        "--notes", str(notes), "--bars", str(bars)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.startswith("# Brief pack — lane `v2test`")
    assert "Do the thing." in out and "- bar one" in out
    assert "### §37 (6) " in out and "## 2026-09-13aj " in out
    assert "road_terrain_conformance.py" in out
    assert "Standing discipline" in out


# ── git conflict markers in the law docs ─────────────────────────────────
#
# RULINGS 2026-09-15af: docs/frames.jsonl carried three conflict-marker lines
# after a union; the design-spec §40 (5) hunk repaired at acbe3035 was left by
# a concurrent commit that completed a conflicted merge WITH its markers — and
# the suite passed.  These twins make that structurally impossible for the
# documents a lane reads as law: a marker line is a named FAILED line, file
# and line number quoted.
#
# Marker law: a line starting with `<<<<<<< ` or `>>>>>>> ` is a marker; a
# bare `=======` is a marker only while an open `<<<<<<< ` awaits its
# `>>>>>>> ` (so a setext H1 underline is never one).  Lines inside a fenced
# code block (``` / ~~~) are not markers — a doc may QUOTE the precedent.

DOCS_ROOT = os.path.join(ROOT, "docs")
LAW_DOCS = sorted(
    [
        os.path.join(ROOT, "Ortho4XP", "docs", "RULINGS.md"),
        os.path.join(ROOT, "Ortho4XP", "docs", "specs", "auto-patch-v2", "design-surface-spec.md"),
        os.path.join(ROOT, "Ortho4XP", "docs", "specs", "auto-patch-v2", "object-placement-spec.md"),
        os.path.join(DOCS_ROOT, "frames.jsonl"),
    ]
    + [
        os.path.join(DOCS_ROOT, "briefs", name)
        for name in os.listdir(os.path.join(DOCS_ROOT, "briefs"))
        if name.endswith(".md")
    ]
)
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def conflict_marker_lines(text: str, *, fenced: bool = True):
    """Return [(lineno, line)] for every git conflict-marker line in `text`.

    `fenced=True` honours Markdown code fences (a quoted marker is not a
    marker); pass `fenced=False` for line formats with no fences (JSONL).
    """
    hits, in_fence, open_head = [], False, None
    for n, line in enumerate(text.split("\n"), 1):
        if fenced and _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("<<<<<<< "):
            hits.append((n, line)); open_head = n
        elif line.startswith(">>>>>>> "):
            hits.append((n, line)); open_head = None
        elif line == "=======" and open_head is not None:
            hits.append((n, line))
    return hits


def _fmt(path, hits):
    rel = os.path.relpath(path, ROOT)
    return "git conflict markers in %s:\n%s" % (
        rel, "\n".join("  %s:%d: %s" % (rel, n, ln.rstrip()) for n, ln in hits))


@pytest.mark.parametrize("path", LAW_DOCS, ids=lambda p: os.path.relpath(p, ROOT))
def test_law_doc_carries_no_git_conflict_markers(path):
    assert os.path.isfile(path), "law doc missing: %s" % os.path.relpath(path, ROOT)
    text = open(path, encoding="utf-8").read()
    hits = conflict_marker_lines(text, fenced=path.endswith(".md"))
    assert not hits, _fmt(path, hits)


def test_frames_registry_every_line_is_json():
    path = os.path.join(DOCS_ROOT, "frames.jsonl")
    bad = []
    for n, line in enumerate(open(path, encoding="utf-8").read().split("\n"), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except ValueError as e:
            bad.append("  docs/frames.jsonl:%d: %s  (%s)" % (n, line[:80], e))
    assert not bad, "non-JSON lines in docs/frames.jsonl:\n" + "\n".join(bad)


def test_conflict_marker_detector_twin():
    # the detector itself: markers named, fenced quotes and setext ignored
    doc = "\n".join([
        "Title",
        "=======",                       # setext underline — not a marker
        "```",
        "<<<<<<< HEAD",                  # quoted inside a fence — not a marker
        "=======",
        ">>>>>>> theirs",
        "```",
        "<<<<<<< HEAD",                  # line 8 — the real thing
        "ours",
        "=======",                       # line 10
        "theirs",
        ">>>>>>> claude/peer",           # line 12
        "=======",                       # after the close — not a marker
    ])
    assert [n for n, _ in conflict_marker_lines(doc)] == [8, 10, 12]
    # an unterminated head is still a marker
    assert [n for n, _ in conflict_marker_lines("a\n<<<<<<< HEAD\nb")] == [2]
    # JSONL: fences are not honoured
    assert [n for n, _ in conflict_marker_lines("```\n<<<<<<< x\n", fenced=False)] == [2]
