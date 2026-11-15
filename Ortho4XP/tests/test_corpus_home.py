"""#2093 twins: the harness corpus is ONE setting, outside every app data
root, and the app knows nothing of it (owner 2026-11-15T02:42Z: "the app
shouldn't know anything about tests or development")."""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]          # Ortho4XP/
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(HARNESS))
import corpus_home as CH  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_one_setting_env_else_the_development_default():
    assert CH.data_repo({}) == CH.DEV_CORPUS_DEFAULT
    assert CH.data_repo({"O4_DATA_REPO": "/x/y"}) == Path("/x/y")
    assert CH.DEV_CORPUS_DEFAULT != CH.LEGACY_CORPUS


def test_every_reader_resolves_the_one_setting():
    """The guard, the snapshot leak root, the ritual's shell default and the
    suite's helper all name corpus_home's value — never a second literal."""
    guard = _load("_srg2093", HARNESS / "shared_repo_guard.py")
    assert guard.DATA_REPO == CH.data_repo()
    import corpus_snapshot as CS
    assert CS.SHARED_DATA_REPO_DEFAULT == CH.DEV_CORPUS_DEFAULT
    assert set(CH.app_data_roots()) <= set(CS.LEAK_ROOTS)
    src = (HARNESS / "lane_worktree.sh").read_text(encoding="utf-8")
    m = re.search(r'^DATA_REPO="\$\{O4_DATA_REPO:-([^}]*)\}"', src, re.M)
    assert m and Path(m.group(1)) == CH.DEV_CORPUS_DEFAULT
    from conftest import data_repo
    assert data_repo() == CH.data_repo()


def test_no_literal_corpus_path_outside_corpus_home():
    """A tool or test that spells the corpus path itself is a second
    setting; the old root may be named only by corpus_home (as the legacy
    and app root it is)."""
    pat = re.compile(r'"/Users/noah/XPTerrainBuilder(Dev)?Data')
    hits = []
    for base in (ROOT / "tools", ROOT / "tests", ROOT / "src"):
        for p in base.rglob("*.py"):
            if p.name in ("corpus_home.py", "test_corpus_home.py"):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="replace")):
                hits.append(str(p.relative_to(ROOT)))
    assert not hits, hits


def test_the_app_default_root_is_an_app_root_and_the_corpus_is_not():
    import O4_File_Names as FNAMES
    assert Path(FNAMES.default_data_root()) == CH.app_data_roots()[0]
    assert CH.app_root_overlap(CH.DEV_CORPUS_DEFAULT) is None
    assert CH.app_root_overlap(FNAMES.default_data_root()) is not None
    assert CH.app_root_overlap(
        os.path.join(FNAMES.default_data_root(), "Elevation_data")) is not None
    with pytest.raises(SystemExit, match="REFUSING"):
        CH.require_not_app_root(FNAMES.default_data_root())


def test_the_app_carries_no_knowledge_of_the_harness():
    """No app or engine cleanup code may special-case the harness corpus:
    the fix for #2093 is the corpus moving, never the app skipping it."""
    repo = ROOT.parent
    needles = ("O4_DATA_REPO", ".harness", "XPTerrainBuilderDevData",
               "refresh_ledger", "frames.jsonl")
    files = list((repo / "Sources").rglob("*.swift"))
    files += list((ROOT / "src" / "o4_engine").glob("storage*.py"))
    files += [ROOT / "src" / n for n in ("O4_Disk_Usage.py", "O4_DDS_Cache.py",
                                         "O4_Storage_Text.py",
                                         "O4_Qt_Settings_Storage.py")]
    hits = [(str(f.relative_to(repo)), n) for f in files if f.exists()
            for n in needles if n in f.read_text(encoding="utf-8", errors="replace")]
    assert not hits, hits


def test_frames_rehome_rewrites_rows_and_clones_products(tmp_path, monkeypatch):
    frames = _load("_frames2093", ROOT.parent / "tools" / "harness" / "frames.py")
    old = tmp_path / "old" / ".harness" / "frames"
    new = tmp_path / "new" / ".harness" / "frames"
    (old / "lane").mkdir(parents=True)
    (old / "lane" / "A.pkl").write_bytes(b"x")
    reg = tmp_path / "frames.jsonl"
    rows = [{"icao": "KXYZ", "kind": "capture", "path": str(old / "lane" / "A.pkl"),
             "copied_from": str(old / "lane" / "A.pkl")},
            {"icao": "KXYZ", "kind": "inset", "path": str(old / "gone.tif"),
             "sidecar": str(old / "gone.json")},
            {"icao": "KXYZ", "kind": "patch", "path": "/elsewhere/P.osm"}]
    reg.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(frames, "REGISTRY", str(reg))
    monkeypatch.setattr(frames, "DURABLE_ROOT", str(new))
    dry = frames.rehome(str(old))
    assert dry == {"rewritten": 3, "cloned": 1, "missing": 2, "applied": False}
    assert json.loads(reg.read_text().splitlines()[0])["path"].startswith(str(old))
    frames.rehome(str(old), apply=True)
    out = [json.loads(ln) for ln in reg.read_text().splitlines()]
    assert out[0]["path"] == str(new / "lane" / "A.pkl")
    assert out[0]["copied_from"] == str(old / "lane" / "A.pkl")   # history kept
    assert (new / "lane" / "A.pkl").read_bytes() == b"x"
    assert out[1]["sidecar"] == str(new / "gone.json")
    assert out[2]["path"] == "/elsewhere/P.osm"
    assert frames.rehome(str(old))["rewritten"] == 0                 # idempotent
