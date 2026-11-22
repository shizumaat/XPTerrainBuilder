"""#2190: the condensed overlapping-packs answer — what "Prefer the
airports" / "Keep everything" give each row (``pack_overlap_default.
winners``), the default for all tiles (``mode`` / ``set_mode``), and a
build answering the rows it decides and asking only the rest
(``overlap_stage._by_default``).  Synthetic rows and folders; no X-Plane."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import pack_choice as PC
from auto_patch_v2.airport import pack_overlap_default as ODF

AIRPORTS = {"Field", "Other Field"}.__contains__


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))


def test_winners_decide_one_airport_pack_and_leave_two():
    assert ODF.winners({"packs": ["City", "Field"]}, AIRPORTS) == {
        "prefer": "Field", "keep": "both"}
    assert ODF.winners({"packs": ["Field", "Other Field"]}, AIRPORTS) == {
        "prefer": "", "keep": "both"}
    assert ODF.winners({"kind": "drapes", "packs": ["Field", "World"],
                        "default": "Field"}, AIRPORTS) == {"prefer": "Field", "keep": "both"}
    assert ODF.winners({"kind": "duplicate", "packs": ["Field", "Other Field"]},
                       AIRPORTS) == {"prefer": "", "keep": ""}


def test_the_default_is_stored_once_and_cleared(prefs):
    assert ODF.mode() == ""
    ODF.set_mode(ODF.PREFER)
    assert ODF.mode() == ODF.PREFER
    ODF.set_mode(ODF.KEEP_ALL)
    assert ODF.mode() == ODF.KEEP_ALL
    ODF.set_mode("")
    assert ODF.mode() == ""
    with pytest.raises(ValueError):
        ODF.set_mode("hide_everything")


ROWS = [{"key": "k1", "packs": ["City", "Field"], "winner": "", "prefer": "Field",
         "keep": "both", "summary": "s1"},
        {"key": "k2", "packs": ["Field", "Other Field"], "winner": "", "prefer": "",
         "keep": "both", "summary": "s2"},
        {"key": "k3", "kind": "duplicate", "packs": ["Field", "Other Field"],
         "winner": "", "prefer": "", "keep": "", "summary": "s3"}]


@pytest.fixture
def stage(prefs, monkeypatch):
    """``overlap_stage`` on fixed rows; returns ``(asked, answered)``."""
    from auto_patch import overlap_stage as OS
    asked, answered = [], []
    monkeypatch.setattr(OS, "_detect", lambda *a: [dict(r) for r in ROWS])
    monkeypatch.setattr(OS, "overlap_choice", lambda root, act, items, la, lo:
                        answered.append((act, list(items))))
    monkeypatch.setattr(OS, "_announce", lambda la, lo, state, items, *a, **k:
                        asked.append((state, [r["key"] for r in items])))
    monkeypatch.setattr(OS.UI, "vprint", lambda *a, **k: None)
    return OS, asked, answered


def test_without_a_default_every_row_is_asked(stage):
    OS, asked, answered = stage
    OS.overlap_stage(25, 55, "/XP")
    assert answered == [] and asked == [("found", ["k1", "k2", "k3"])]


def test_prefer_answers_the_rows_it_decides_and_asks_the_rest(stage):
    OS, asked, answered = stage
    ODF.set_mode(ODF.PREFER)
    OS.overlap_stage(25, 55, "/XP")
    assert answered == [("choose", [{"key": "k1", "winner": "Field"}])]
    assert asked == [("found", ["k2", "k3"])]


def test_keep_all_answers_every_structure_pair(stage):
    OS, asked, answered = stage
    ODF.set_mode(ODF.KEEP_ALL)
    OS.overlap_stage(25, 55, "/XP")
    assert answered == [("choose", [{"key": "k1", "winner": "both"},
                                    {"key": "k2", "winner": "both"}])]
    assert asked == [("found", ["k3"])]


def test_the_command_sets_the_default(prefs, monkeypatch):
    from auto_patch import overlap_stage as OS
    monkeypatch.setattr(OS, "_answer", lambda s, a, it: {
        "state": "chosen", "items": [], "files": []})
    seen = []
    monkeypatch.setattr(OS.UI, "pack_overlaps", lambda **f: seen.append(f))
    monkeypatch.setattr(OS.UI, "vprint", lambda *a, **k: None)
    OS.overlap_choice("/XP", "choose", [], 25, 55, default=ODF.KEEP_ALL)
    assert ODF.mode() == ODF.KEEP_ALL and seen[-1]["default"] == ODF.KEEP_ALL
    OS.overlap_choice("/XP", "choose", [], 25, 55)            # None leaves it
    assert ODF.mode() == ODF.KEEP_ALL
    OS.overlap_choice("/XP", "choose", [], 25, 55, default="")
    assert ODF.mode() == "" and seen[-1]["default"] == ""


def test_the_detection_carries_prefer_and_keep(prefs, tmp_path, monkeypatch):
    from auto_patch import overlap_stage as OS
    (tmp_path / "Field" / "Earth nav data").mkdir(parents=True)
    (tmp_path / "Field" / "Earth nav data" / "apt.dat").write_text(
        "I\n1100 Version\n\n1 10 0 0 XXXX Field\n100 45 1 0 0.25 0 2 1 "
        "09 25.25 55.36 0 0 2 0 0 0 27 25.25 55.37 0 0 2 0 0 0\n99\n",
        encoding="utf-8", newline="")
    (tmp_path / "City").mkdir()
    monkeypatch.setattr(OS, "_pairs", lambda *a: [
        {"key": "k", "packs": ["City", "Field"], "default": "Field"}])
    (row,) = OS._detect(str(tmp_path), 25, 55, "/XP")
    assert (row["prefer"], row["keep"]) == ("Field", "both")
