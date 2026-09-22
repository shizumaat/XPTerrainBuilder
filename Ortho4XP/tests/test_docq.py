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
    durable = tmp_path / "data" / ".harness" / "frames"
    monkeypatch.setattr(frames, "DURABLE_ROOT", str(durable))
    (durable / "v2test").mkdir(parents=True)
    p = durable / "v2test" / "KCLT.pkl"; p.write_bytes(b"x")
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


def _durable(tmp_path, monkeypatch):
    reg = tmp_path / "frames.jsonl"
    monkeypatch.setattr(frames, "REGISTRY", str(reg))
    durable = tmp_path / "data" / ".harness" / "frames"
    monkeypatch.setattr(frames, "DURABLE_ROOT", str(durable))
    return reg, durable


def test_frames_durable_root_is_the_guards_harness_state(monkeypatch):
    """ONE resolution of `.harness/` (issue #37): the durable root is the
    guard's own HARNESS_STATE — the directory the shared-repo write guard
    ALWAYS allows (the refresh ledger and the locks live there) — so a
    `--copy` under an armed build is never a refused corpus write, and
    `O4_DATA_REPO` re-points both together."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "srg", os.path.join(frames.ROOT, "Ortho4XP", "tools", "harness", "shared_repo_guard.py"))
    srg = importlib.util.module_from_spec(spec); spec.loader.exec_module(srg)
    assert frames.DURABLE_ROOT == os.path.join(str(srg.HARNESS_STATE), "frames")
    assert os.path.basename(os.path.dirname(frames.DURABLE_ROOT)) == ".harness"
    # ...and the guard's rule that makes it safe: `.harness` is never a violation
    assert 'if rel.startswith(".harness"):' in open(spec.origin, encoding="utf-8").read()


def test_frames_register_refuses_a_tmp_path_naming_the_durable_root(tmp_path, monkeypatch):
    """The #37 twin: a /tmp product registers NOWHERE without --copy — the
    refusal names the durable root and the flag, and the registry stays
    empty (a row pointing at a path the next reboot purges is the defect)."""
    reg, durable = _durable(tmp_path, monkeypatch)
    import tempfile
    with tempfile.TemporaryDirectory(dir="/tmp") as td:   # deliberately /tmp
        p = os.path.join(td, "KCLT.pkl")
        open(p, "wb").write(b"x")
        with pytest.raises(SystemExit) as exc:
            frames.register("KCLT", "capture", p, "864e7577", "v2test")
        msg = str(exc.value)
        assert "NON-DURABLE" in msg and str(durable) in msg and "--copy" in msg
        assert not reg.exists()
        # the CLI spells the same refusal
        with pytest.raises(SystemExit) as exc:
            frames.main(["register", "--icao", "KCLT", "--kind", "capture", "--path", p,
                         "--base", "864e7577", "--lane", "v2test"])
        assert "NON-DURABLE" in str(exc.value)
    # a scratchpad path is no more durable than /tmp
    p2 = tmp_path / "scratch" / "cap.pkl"; p2.parent.mkdir(); p2.write_bytes(b"y")
    assert not frames.is_durable(str(p2))
    with pytest.raises(SystemExit):
        frames.register("KCLT", "capture", str(p2), "x", "v2test")


def test_frames_register_copy_lands_under_the_lane_and_keeps_the_original(tmp_path, monkeypatch):
    reg, durable = _durable(tmp_path, monkeypatch)
    src = tmp_path / "scratch"; src.mkdir()
    # a file, and a patch WITH its sidecar (the census needs both)
    patch = src / "KCLT.patch.osm"; patch.write_bytes(b"<osm/>")
    (src / "KCLT.patch.osm.axes.json").write_text('{"ruleset": "FAA"}')
    rec = frames.register("kclt", "patch", str(patch), "864e7577", "v2test", copy=True)
    assert rec["path"] == str(durable / "v2test" / "KCLT.patch.osm")
    assert rec["copied_from"] == str(patch)
    assert frames.is_durable(rec["path"])
    assert (durable / "v2test" / "KCLT.patch.osm.axes.json").read_text() == '{"ruleset": "FAA"}'
    assert frames.latest("KCLT", "patch")["path"] == rec["path"]
    assert json.loads(reg.read_text().splitlines()[0])["copied_from"] == str(patch)
    # a directory product (a capture dir) copies whole
    cap = src / "cap"; cap.mkdir(); (cap / "stage.pkl").write_bytes(b"s")
    rec = frames.register("KCLT", "capture", str(cap), "864e7577", "v2test", copy=True)
    assert (durable / "v2test" / "cap" / "stage.pkl").read_bytes() == b"s"
    # a durable path registers as-is, --copy or not, and gets no copied_from
    rec2 = frames.register("KCLT", "capture", rec["path"], "864e7577", "v2test", copy=True)
    assert rec2["path"] == rec["path"] and "copied_from" not in rec2
    # never overwrite: a byte-identical file is reused, a differing one refuses
    frames.register("KCLT", "patch", str(patch), "x", "v2test", copy=True)
    patch.write_bytes(b"<osm>changed</osm>")
    with pytest.raises(SystemExit) as exc:
        frames.register("KCLT", "patch", str(patch), "x", "v2test", copy=True)
    assert "refusing to overwrite" in str(exc.value)
    with pytest.raises(SystemExit):                       # the dir already exists
        frames.register("KCLT", "capture", str(cap), "x", "v2test", copy=True)
    # the original is left where it was — --copy copies, never moves
    assert patch.exists() and cap.exists()
    # a lane name that is not a bare name cannot become a path component
    with pytest.raises(SystemExit):
        frames.register("KCLT", "patch", str(patch), "x", "claude/lane", copy=True)


def test_frames_list_marks_a_vanished_path_missing(tmp_path, monkeypatch, capsys):
    reg, durable = _durable(tmp_path, monkeypatch)
    (durable / "v2test").mkdir(parents=True)
    p = durable / "v2test" / "HECA.pkl"; p.write_bytes(b"x")
    frames.register("HECA", "capture", str(p), "abc", "v2test")
    p.unlink()
    frames.main(["list", "HECA"])
    out = capsys.readouterr().out
    assert "[MISSING]" in out and str(p) in out
    # ...and the rows written before this law are read, never rewritten
    assert reg.read_text().count("\n") == 1


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
