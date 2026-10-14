"""ISSUE #156 TWIN, round 2: an ``Elevation_data`` overlay TAKES EFFECT.

``tools/harness/data_overlay.py`` composes the lane-local VIEW the capture
points both the core's ``Elevation_dir`` and ``Inputs.elevation_root`` at
(overlay files win, every other entry is a link to the shared corpus);
``tools/v2_solve_replay.arm_data_overlay`` arms it and records the overlay's
file manifest; a replay off a STALE overlay refuses by file name; and
``tools/harness/frames.py register`` carries the capture's
``<pkl>.overlay.json`` into the registry row.

Offline and synthetic: tmp fixture trees only, no corpus, no network, no
engine import (the production branch's two engine names are stubbed).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def D():
    return _load("_data_overlay_twin", ROOT / "tools" / "harness" / "data_overlay.py")


@pytest.fixture(scope="module")
def R():
    return _load("_v2_solve_replay_dov", ROOT / "tools" / "v2_solve_replay.py")


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def _corpus(tmp_path: Path) -> tuple[Path, Path]:
    """A shared ``Elevation_data`` with a base tile and an inset dir, and an
    overlay that replaces the inset index, adds one inset and one tile."""
    shared = tmp_path / "shared" / "Elevation_data"
    _write(shared / "+30-090" / "N36W087.hgt", "base\n")
    _write(shared / "+30-090" / "N36W087_airport_insets" / "index.json", "shared index\n")
    _write(shared / "+30-090" / "N36W087_airport_insets" / "KBNA_OLD.tif", "old inset\n")
    _write(shared / "+40-080" / "N40W077.hgt", "other block\n")
    over = tmp_path / "lane" / "ovl" / "Elevation_data"
    _write(over / "+30-090" / "N36W087_airport_insets" / "index.json", "lane index\n")
    _write(over / "+30-090" / "N36W087_airport_insets" / "KBNA_NEW.tif", "new inset\n")
    _write(over / "+30-090" / "N35W087.hgt", "lane tile\n")
    return shared, over


# ------------------------------------------------------------- the view

def test_the_view_reads_overlay_files_first_and_the_shared_corpus_otherwise(D, tmp_path):
    shared, over = _corpus(tmp_path)
    view = D.compose_view(shared, over, tmp_path / "views")
    ins = view / "+30-090" / "N36W087_airport_insets"
    assert (ins / "index.json").read_text(encoding="utf-8") == "lane index\n"          # overlay wins
    assert (ins / "KBNA_NEW.tif").read_text(encoding="utf-8") == "new inset\n"         # overlay adds
    assert (ins / "KBNA_OLD.tif").read_text(encoding="utf-8") == "old inset\n"         # shared stays
    assert (view / "+30-090" / "N36W087.hgt").read_text(encoding="utf-8") == "base\n"
    assert (view / "+30-090" / "N35W087.hgt").read_text(encoding="utf-8") == "lane tile\n"
    # a block the overlay does not touch is ONE link to the shared block
    assert (view / "+40-080").is_symlink()
    assert os.path.realpath(view / "+40-080") == str((shared / "+40-080").resolve())
    # a directory both carry is a real merged directory, never a link
    assert not (view / "+30-090").is_symlink() and not ins.is_symlink()
    assert view.name == "Elevation_data"


def test_the_view_holds_only_links_and_directories(D, tmp_path):
    shared, over = _corpus(tmp_path)
    view = D.compose_view(shared, over, tmp_path / "views")
    for dirpath, dirs, files in os.walk(view):
        for name in files:
            assert (Path(dirpath) / name).is_symlink(), name


def test_composing_writes_nothing_outside_the_view_parent(D, tmp_path):
    shared, over = _corpus(tmp_path)

    def _snap(root):
        return {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    before = (_snap(shared), _snap(over))
    D.compose_view(shared, over, tmp_path / "views")
    D.compose_view(shared, over, tmp_path / "views")                 # rebuilt
    assert (_snap(shared), _snap(over)) == before


def test_a_rebuild_shows_what_the_shared_corpus_gained(D, tmp_path):
    shared, over = _corpus(tmp_path)
    D.compose_view(shared, over, tmp_path / "views")
    _write(shared / "+30-090" / "N37W087.hgt", "new base\n")
    view = D.compose_view(shared, over, tmp_path / "views")
    assert (view / "+30-090" / "N37W087.hgt").read_text(encoding="utf-8") == "new base\n"


def test_a_lock_the_engine_dropped_into_the_view_is_cleared_on_rebuild(D, tmp_path):
    shared, over = _corpus(tmp_path)
    view = D.compose_view(shared, over, tmp_path / "views")
    _write(view / "+30-090" / "N36W087.lock", "")
    view = D.compose_view(shared, over, tmp_path / "views")
    assert not (view / "+30-090" / "N36W087.lock").exists()
    assert (shared / "+30-090" / "N36W087.hgt").exists()


def test_a_directory_that_is_not_a_view_is_never_cleared(D, tmp_path):
    shared, over = _corpus(tmp_path)
    parent = tmp_path / "views"
    token = __import__("hashlib").sha256(str(over.resolve()).encode()).hexdigest()[:16]
    victim = _write(parent / token / "precious.txt", "keep\n")
    with pytest.raises(SystemExit, match="is not an overlay view"):
        D.compose_view(shared, over, parent)
    assert victim.read_text(encoding="utf-8") == "keep\n"


@pytest.mark.parametrize("overlay_file", [True, False])
def test_a_file_directory_clash_refuses_by_name(D, tmp_path, overlay_file):
    shared = tmp_path / "shared" / "Elevation_data"
    over = tmp_path / "ovl" / "Elevation_data"
    if overlay_file:
        (shared / "+30-090").mkdir(parents=True)
        _write(over / "+30-090", "file\n")
    else:
        _write(shared / "+30-090", "file\n")
        _write(over / "+30-090" / "x.hgt", "dir\n")
    why = D.view_conflicts(shared, over)
    assert "+30-090" in why
    with pytest.raises(SystemExit, match="REFUSING the data overlay"):
        D.compose_view(shared, over, tmp_path / "views")


# ------------------------------------------------------- the manifest

def test_staleness_names_the_first_changed_missing_or_added_file(D, tmp_path):
    _, over = _corpus(tmp_path)
    root = over.parent
    files = D.overlay_manifest(root, ["Elevation_data"])
    assert "Elevation_data/+30-090/N35W087.hgt" in files
    assert D.stale_reason(root, files, ["Elevation_data"]) is None
    _write(over / "+30-090" / "N35W087.hgt", "edited\n")
    assert "N35W087.hgt changed" in D.stale_reason(root, files, ["Elevation_data"])
    (over / "+30-090" / "N35W087.hgt").unlink()
    assert "N35W087.hgt is missing" in D.stale_reason(root, files, ["Elevation_data"])
    files = D.overlay_manifest(root, ["Elevation_data"])
    _write(over / "+30-090" / "late.tif", "late\n")
    assert "late.tif was added" in D.stale_reason(root, files, ["Elevation_data"])


def test_a_vanished_overlay_is_stale(D, tmp_path):
    assert "no longer exists" in D.stale_reason(tmp_path / "gone", {}, [])


def test_the_sidecar_round_trips_and_absence_is_unknown(D, tmp_path):
    cap = tmp_path / "KXYZ.pkl"
    assert D.read_sidecar(cap) is None
    D.write_sidecar(cap, None)
    assert D.read_sidecar(cap) == {"data_overlay": None}
    D.write_sidecar(cap, {"dir": "/x", "provides": {}})
    assert D.read_sidecar(cap)["data_overlay"]["dir"] == "/x"
    assert Path(str(cap) + D.SIDECAR_SUFFIX).is_file()


# ----------------------------------------------- the capture's arming

@dataclasses.dataclass(frozen=True)
class _Inputs:
    osm_root: str
    elevation_root: str
    dem_frame: str = "authored"


def test_arming_points_elevation_root_at_the_view_and_records_the_files(R, tmp_path,
                                                                        monkeypatch):
    shared, over = _corpus(tmp_path)
    osm = tmp_path / "shared" / "OSM_data"
    osm.mkdir()
    monkeypatch.setattr(R, "OVERLAY_VIEW_DIR", tmp_path / "views")
    frame = R.resolve_data_overlay(str(over.parent), data_repo=tmp_path / "repo")
    inputs, rec = R.arm_data_overlay(_Inputs(str(osm), str(shared)), frame)
    assert inputs.elevation_root == rec["elevation_view"]
    assert Path(inputs.elevation_root).parent.parent == tmp_path / "views"
    assert inputs.osm_root == str(osm)                     # not provided: shared
    assert rec["manifested"] == ["Elevation_data"]
    assert set(rec["files"]) == {
        "Elevation_data/+30-090/N36W087_airport_insets/index.json",
        "Elevation_data/+30-090/N36W087_airport_insets/KBNA_NEW.tif",
        "Elevation_data/+30-090/N35W087.hgt"}
    assert R.overlay_stale(rec) is None
    _write(over / "+30-090" / "N35W087.hgt", "edited\n")
    assert "N35W087.hgt changed" in R.overlay_stale(rec)


def test_the_production_frame_points_the_core_at_the_same_view(R, tmp_path, monkeypatch):
    """The engine's one-corpus check compares the core's ``Elevation_dir``
    with ``elevation_root``; arming sets BOTH to the view (the two engine
    names are stubbed so the twin stays offline)."""
    shared, over = _corpus(tmp_path)
    monkeypatch.setattr(R, "OVERLAY_VIEW_DIR", tmp_path / "views")
    calls = []
    dem_prod = types.ModuleType("auto_patch_v2.airport.dem_production")
    dem_prod.ProductionDem = type("ProductionDem", (), {
        "_ensure_core_path": staticmethod(lambda: calls.append("core"))})
    fnames = types.ModuleType("O4_File_Names")
    fnames.Elevation_dir = str(shared)
    monkeypatch.setitem(sys.modules, "auto_patch_v2.airport.dem_production", dem_prod)
    monkeypatch.setitem(sys.modules, "O4_File_Names", fnames)
    frame = R.resolve_data_overlay(str(over.parent), data_repo=tmp_path / "repo")
    inputs, rec = R.arm_data_overlay(
        _Inputs(str(tmp_path), str(shared), dem_frame="production"), frame)
    assert calls == ["core"]
    assert fnames.Elevation_dir == inputs.elevation_root == rec["elevation_view"]


def test_the_shared_corpus_under_another_name_is_neither_hashed_nor_viewed(R, tmp_path,
                                                                          monkeypatch):
    shared, _ = _corpus(tmp_path)
    ovl = tmp_path / "alias"
    ovl.mkdir()
    (ovl / "Elevation_data").symlink_to(shared, target_is_directory=True)
    monkeypatch.setattr(R, "OVERLAY_VIEW_DIR", tmp_path / "views")
    frame = R.resolve_data_overlay(str(ovl), data_repo=tmp_path / "repo")
    inputs, rec = R.arm_data_overlay(_Inputs(str(tmp_path), str(shared)), frame)
    assert rec["manifested"] == [] and rec["files"] == {}
    assert "elevation_view" not in rec and not (tmp_path / "views").exists()


def test_no_overlay_arms_nothing(R):
    inp = _Inputs("/o", "/e")
    assert R.arm_data_overlay(inp, None) == (inp, None)
    assert R.overlay_stale(None) is None
    assert R.overlay_stale({"dir": "/x", "provides": {}}) is None   # pre-manifest


def test_the_capture_and_the_replay_wire_the_record():
    """Source pins: the capture ARMS (never just re-roots) and writes the
    sidecar; the replay refuses a stale overlay."""
    import inspect
    R = _load("_v2_solve_replay_pin", ROOT / "tools" / "v2_solve_replay.py")
    cap = inspect.getsource(R.capture)
    assert "inputs, _overlay = arm_data_overlay(inputs, _overlay)" in cap
    assert "_data_overlay().write_sidecar(out, _overlay)" in cap
    rep = inspect.getsource(R.replay_problem)
    assert "overlay_stale(_overlay)" in rep and "STALE" in rep


# ------------------------------------------------------- the registry

def test_frames_register_carries_the_capture_overlay(D, tmp_path, monkeypatch):
    frames = _load("_frames_dov", ROOT.parent / "tools" / "harness" / "frames.py")
    assert frames.CAPTURE_SIDECAR_SUFFIX == D.SIDECAR_SUFFIX
    monkeypatch.setattr(frames, "REGISTRY", str(tmp_path / "frames.jsonl"))
    durable = tmp_path / "data" / ".harness" / "frames"
    monkeypatch.setattr(frames, "DURABLE_ROOT", str(durable))
    lane_dir = tmp_path / "scratch"
    lane_dir.mkdir()
    cap = lane_dir / "KXYZ.pkl"
    cap.write_bytes(b"pickle")
    D.write_sidecar(cap, {"dir": "/lane/ovl", "provides": {"Elevation_data": "/lane/ovl/E"}})
    rec = frames.register("kxyz", "capture", str(cap), "abc123", "overlay156", copy=True)
    assert rec["data_overlay"]["dir"] == "/lane/ovl"
    assert Path(rec["path"] + D.SIDECAR_SUFFIX).is_file()           # --copy brought it
    assert "[DATA OVERLAY /lane/ovl]" in frames._fmt(rec)
    plain = lane_dir / "KABC.pkl"
    plain.write_bytes(b"p2")
    D.write_sidecar(plain, None)
    rec2 = frames.register("kabc", "capture", str(plain), "abc123", "overlay156", copy=True)
    assert rec2["data_overlay"] is None and "DATA OVERLAY" not in frames._fmt(rec2)
    old = lane_dir / "KOLD.pkl"
    old.write_bytes(b"p3")
    rec3 = frames.register("kold", "capture", str(old), "abc123", "overlay156", copy=True)
    assert "data_overlay" not in rec3
    rows = [json.loads(ln) for ln in (tmp_path / "frames.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["icao"] for r in rows] == ["KXYZ", "KABC", "KOLD"]
