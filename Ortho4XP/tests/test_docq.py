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
                          capture_output=True, text=True,
                          encoding="utf-8")


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
    assert json.loads(reg.read_text(encoding="utf-8").splitlines()[0])["lane"] == "v2test"


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
    # deliberately /tmp; the OS temp dir where there is no /tmp (Windows, #92)
    with tempfile.TemporaryDirectory(
            dir="/tmp" if os.path.isdir("/tmp") else None) as td:
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
    (src / "KCLT.patch.osm.axes.json").write_text('{"ruleset": "FAA"}', encoding="utf-8", newline="")
    rec = frames.register("kclt", "patch", str(patch), "864e7577", "v2test", copy=True)
    assert rec["path"] == str(durable / "v2test" / "KCLT.patch.osm")
    assert rec["copied_from"] == str(patch)
    assert frames.is_durable(rec["path"])
    assert (durable / "v2test" / "KCLT.patch.osm.axes.json").read_text(encoding="utf-8") == '{"ruleset": "FAA"}'
    assert frames.latest("KCLT", "patch")["path"] == rec["path"]
    assert json.loads(reg.read_text(encoding="utf-8").splitlines()[0])["copied_from"] == str(patch)
    # a directory product (a capture dir) copies whole
    cap = src / "cap"; cap.mkdir(); (cap / "stage.pkl").write_bytes(b"s")
    rec = frames.register("KCLT", "capture", str(cap), "864e7577", "v2test", copy=True)
    assert (durable / "v2test" / "cap" / "stage.pkl").read_bytes() == b"s"
    # a durable path registers as-is, --copy or not, and gets no copied_from
    rec2 = frames.register("KCLT", "capture", rec["path"], "864e7577", "v2test", copy=True)
    assert rec2["path"] == rec["path"] and "copied_from" not in rec2
    # never overwrite: a byte-identical file is reused (the row names the
    # same bytes either way), a DIFFERING one lands beside it under the
    # base sha and the row names the NEW copy — issue #102 below
    frames.register("KCLT", "patch", str(patch), "x", "v2test", copy=True)
    patch.write_bytes(b"<osm>changed</osm>")
    rec3 = frames.register("KCLT", "patch", str(patch), "26f7fea6", "v2test",
                           copy=True)
    assert rec3["path"] != str(durable / "v2test" / "KCLT.patch.osm")
    assert (durable / "v2test" / "KCLT.patch.osm").read_bytes() == b"<osm/>"
    # the original is left where it was — --copy copies, never moves
    assert patch.exists() and cap.exists()
    # a lane name that is not a bare name cannot become a path component
    with pytest.raises(SystemExit):
        frames.register("KCLT", "patch", str(patch), "x", "claude/lane", copy=True)


def test_frames_register_copy_of_a_SECOND_frame_never_points_at_the_first(
        tmp_path, monkeypatch):
    """Issue #102 (found by lane train98): a second `HECA.rebake.json` on a
    new base copied into the same lane folder did not overwrite round 1
    (correct) but the registry ROW still pointed at ROUND 1's file — the
    registry silently attributed round 2's frame to round 1's bytes.

    THE INVARIANT: a row's path always names the bytes THIS invocation
    registered.  Taken as the issue's option (b) — the differing copy
    lands under a BASE-SUFFIXED name (`frames.BASE_SUFFIX_FMT`) and the
    row points at it — because `register` has the base sha right there,
    and (a) would make the second round of any lane unregisterable."""
    reg, durable = _durable(tmp_path, monkeypatch)
    src = tmp_path / "scratch"; src.mkdir()
    plan = src / "HECA.rebake.json"
    plan.write_text('{"round": 1}', encoding="utf-8", newline="\n")
    r1 = frames.register("HECA", "rebake", str(plan), "deadbeef", "train98",
                         copy=True)
    assert r1["path"] == str(durable / "train98" / "HECA.rebake.json")

    # round 2: same basename, DIFFERENT bytes, different base
    plan.write_text('{"round": 2}', encoding="utf-8", newline="\n")
    r2 = frames.register("HECA", "rebake", str(plan), "26f7fea6", "train98",
                         copy=True)
    assert r2["path"] != r1["path"]
    assert os.path.basename(r2["path"]) == frames.BASE_SUFFIX_FMT.format(
        stem="HECA.rebake", base="26f7fea6", ext=".json")
    # the row names the bytes just registered...
    assert json.loads(open(r2["path"], encoding="utf-8").read()) == {"round": 2}
    assert r2["copied_from"] == str(plan)
    # ...and round 1's row and file are untouched
    assert json.loads(open(r1["path"], encoding="utf-8").read()) == {"round": 1}
    rows = frames.list_frames("HECA", "rebake")
    assert [r["path"] for r in rows] == [r1["path"], r2["path"]]
    assert rows[0]["base"] == "deadbeef" and rows[1]["base"] == "26f7fea6"
    assert frames.latest("HECA", "rebake")["path"] == r2["path"]

    # re-registering the SAME bytes on the SAME base reuses that copy
    # (the row still names the bytes it registered)
    r2b = frames.register("HECA", "rebake", str(plan), "26f7fea6", "train98",
                          copy=True)
    assert r2b["path"] == r2["path"]

    # a THIRD set of bytes on the SAME base cannot be told apart: refused,
    # naming both paths, rather than a row pointing at bytes it did not write
    plan.write_text('{"round": 3}', encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit) as exc:
        frames.register("HECA", "rebake", str(plan), "26f7fea6", "train98",
                        copy=True)
    msg = str(exc.value)
    assert r1["path"] in msg and r2["path"] in msg
    assert len(frames.list_frames("HECA", "rebake")) == 3   # nothing appended

    # a directory product is the same law
    cap = src / "cap"; cap.mkdir(); (cap / "stage.pkl").write_bytes(b"1")
    d1 = frames.register("HECA", "capture", str(cap), "deadbeef", "train98",
                         copy=True)
    (cap / "stage.pkl").write_bytes(b"2")
    d2 = frames.register("HECA", "capture", str(cap), "26f7fea6", "train98",
                         copy=True)
    assert d2["path"] != d1["path"]
    assert open(os.path.join(d1["path"], "stage.pkl"), "rb").read() == b"1"
    assert open(os.path.join(d2["path"], "stage.pkl"), "rb").read() == b"2"

    # without a usable base sha there is no second name: the issue's
    # option (a), refusing with the existing path named
    plan2 = src / "SPJC.rebake.json"
    plan2.write_text("1", encoding="utf-8", newline="\n")
    frames.register("SPJC", "rebake", str(plan2), "", "train98", copy=True)
    plan2.write_text("2", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit) as exc:
        frames.register("SPJC", "rebake", str(plan2), "", "train98", copy=True)
    assert str(durable / "train98" / "SPJC.rebake.json") in str(exc.value)


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
    assert reg.read_text(encoding="utf-8").count("\n") == 1


def test_brief_pack_assembles_from_the_tools(tmp_path):
    notes = tmp_path / "n.md"; notes.write_text("Do the thing.", encoding="utf-8", newline="")
    bars = tmp_path / "b.md"; bars.write_text("- bar one", encoding="utf-8", newline="")
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "brief_pack.py"),
                        "--lane", "v2test", "--base", "abcdef12", "--spec", "§37 (6)",
                        "--rulings", "13aj", "--index", "road_terrain_conformance",
                        "--notes", str(notes), "--bars", str(bars)],
                       capture_output=True, text=True,
                          encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.startswith("# Brief pack — lane `v2test`")
    assert "Do the thing." in out and "- bar one" in out
    assert "### §37 (6) " in out and "## 2026-09-13aj " in out
    assert "road_terrain_conformance.py" in out
    assert "Standing discipline" in out


def test_brief_pack_attaches_the_generated_map(tmp_path):
    """RULINGS 2026-10-04a (4): the brief carries the map of each package
    it touches, generated by `blast.py --map`, never retyped."""
    env = dict(os.environ, BLAST_INDEX_DIR=str(tmp_path / "idx"))
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "brief_pack.py"),
                        "--lane", "v2test", "--base", "abcdef12",
                        "--map", "auto_patch_v2/geom", "--map", "o4_engine"],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "## Map: auto_patch_v2/geom" in out and "## Map: o4_engine" in out
    assert "\nsrc/auto_patch_v2/geom — " in out and "\nsrc/o4_engine — " in out
    assert out.index("## Map: o4_engine") < out.index("Standing discipline")


def test_frames_inset_kind_brings_its_provenance_sidecar(tmp_path, monkeypatch):
    """#154: lane-local witness insets register as kind ``inset``; the
    raster without its provenance sidecar is refused, ``--copy`` brings the
    sidecar along and the row names it."""
    reg, durable = _durable(tmp_path, monkeypatch)
    src = tmp_path / "scratch"; src.mkdir()
    tif = src / "KRDU_ncphase3.tif"; tif.write_bytes(b"II*\x00")
    with pytest.raises(SystemExit) as exc:
        frames.register("KRDU", "inset", str(tif), "33122938", "ladder154", copy=True)
    assert "sidecar" in str(exc.value)
    (src / "KRDU_ncphase3.json").write_text('{"provider": "NCPHASE3"}', encoding="utf-8", newline="\n")
    rec = frames.register("krdu", "inset", str(tif), "33122938", "ladder154", copy=True)
    assert rec["kind"] == "inset"
    assert rec["path"] == str(durable / "ladder154" / "KRDU_ncphase3.tif")
    assert rec["sidecar"] == str(durable / "ladder154" / "KRDU_ncphase3.json")
    assert json.loads((durable / "ladder154" / "KRDU_ncphase3.json").read_text(
        encoding="utf-8")) == {"provider": "NCPHASE3"}
    assert frames.latest("KRDU", "inset")["sidecar"] == rec["sidecar"]
    # a differing sidecar under an identical raster is refused, never overwritten
    (src / "KRDU_ncphase3.json").write_text('{"provider": "OTHER"}', encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit) as exc:
        frames.register("KRDU", "inset", str(tif), "33122938", "ladder154", copy=True)
    assert "refusing to overwrite" in str(exc.value)
