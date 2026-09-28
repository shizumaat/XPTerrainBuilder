"""Twins for the cloud test corpus (RULINGS 2026-09-28a (7)):
``tools/harness/corpus_snapshot.py`` and the snapshot mode it gives
``build_airport.py`` (``--corpus snapshot:DIR`` / ``O4_CORPUS_SNAPSHOT``).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"


def _load(name, path):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def CS():
    return _load("harness_twin_corpus_snapshot", HARNESS / "corpus_snapshot.py")


@pytest.fixture(scope="module")
def AL():
    return _load("harness_twin_al_snapshot", HARNESS / "artifact_ledger.py")


def _fake_snapshot(CS, tmp_path, icao="ZZZZ"):
    snap = tmp_path / "snap"
    files = {}
    for rel, body in {
            "data/Ortho4XP.cfg.in":
                f"custom_scenery_dir={CS.XPLANE_TOKEN}/Custom Scenery\n"
                f"cifp_data_path={CS.XPLANE_TOKEN}/Custom Data/CIFP\n",
            "data/Elevation_data/+10+010/N10E010.hgt": "dem",
            "xplane/Custom Data/CIFP/ZZZZ.dat": "cifp"}.items():
        p = snap / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        files[rel] = {"sha256": CS._sha256(p), "size": p.stat().st_size}
    man = {"schema": 1, "files": files, "hash": CS.manifest_hash(files),
           "source_corpus": {"install_root": "/nonexistent/X-Plane 12"},
           "airports": {icao: {"files": sorted(files)}}}
    (snap / "snapshot.json").write_text(json.dumps(man))
    return snap, man


def test_request_reads_flag_then_env(CS, tmp_path):
    assert CS.snapshot_request([], {}) is None
    assert CS.snapshot_request(["X", "--corpus", "shared"], {}) is None
    got = CS.snapshot_request(["X", "--corpus", f"snapshot:{tmp_path}"], {})
    assert got == tmp_path.resolve()
    got = CS.snapshot_request(["X"], {CS.SNAPSHOT_ENV: str(tmp_path)})
    assert got == tmp_path.resolve()
    # the flag wins over the env
    other = tmp_path / "o"
    assert CS.snapshot_request(["--corpus=snapshot:" + str(other)],
                               {CS.SNAPSHOT_ENV: str(tmp_path)}) == other.resolve()
    with pytest.raises(SystemExit):
        CS.snapshot_request(["--corpus", "private:/x"], {})
    env = {CS.SNAPSHOT_ENV: str(tmp_path)}
    CS.arm_snapshot_env([], env)
    assert env["O4_DATA_REPO"] == str(tmp_path.resolve() / "data")


def test_licence_gate(CS):
    allow = {"packs": {"Free Pack": "freeware"},
             "install_prefixes": ["Custom Data/CIFP/"],
             "excluded_substrings": ["OTHH"]}
    ok = CS.licence_verdict
    assert ok("xplane/Custom Scenery/Free Pack/Earth nav data/apt.dat", allow) is None
    assert ok("data/Airport_mod_cache/Free Pack/+30+031.dsf.x.text", allow) is None
    assert ok("xplane/Custom Scenery/Payware/x.obj", allow)
    assert ok("data/Airport_mod_cache/Payware/x.cache", allow)
    assert ok("xplane/Custom Scenery/scenery_packs.ini", allow) is None
    assert ok("xplane/Custom Data/CIFP/HECA.dat", allow) is None
    assert ok("xplane/Resources/default scenery/x.obj", allow)
    assert ok("data/Airport_mod_cache/Aeroscape OTHH Hamad Intl/a", {
        **allow, "packs": {"Aeroscape OTHH Hamad Intl": "x"}})
    assert ok("data/Elevation_data/+30+030/N30E031.hgt", allow) is None


def test_classify_maps_overlays_back_to_the_corpus(CS, tmp_path):
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "P").mkdir(parents=True)
    (repo / "Airport_mod_cache" / "P" / "a.text").write_text("x")
    ov = tmp_path / "ov"
    overlays = {"O4_AIRPORT_MOD_CACHE_DIR": str(ov)}
    hit = CS.classify(str(ov / "P" / "a.text"), repo, None, overlays)
    assert hit == ("data/Airport_mod_cache/P/a.text",
                   str(repo / "Airport_mod_cache" / "P" / "a.text"))
    # derived lane-local only: not corpus
    assert CS.classify(str(ov / "P" / "new.cache"), repo, None, overlays) is None
    assert CS.classify(str(repo.resolve() / "Patches" / "x.osm"), repo, None, {}) is None
    xp = tmp_path / "XP"
    assert CS.classify(str(xp.resolve() / "Custom Data" / "CIFP" / "A.dat"),
                       repo, str(xp), {}) == (
        "xplane/Custom Data/CIFP/A.dat",
        str(xp.resolve() / "Custom Data" / "CIFP" / "A.dat"))


def test_verify_refuses_a_mutated_snapshot(CS, tmp_path):
    snap, man = _fake_snapshot(CS, tmp_path)
    assert CS.verify(snap, quiet=True)["complete"] == ["ZZZZ"]
    (snap / "data/Elevation_data/+10+010/N10E010.hgt").write_text("DEM")
    with pytest.raises(SystemExit, match="do not match"):
        CS.verify(snap, quiet=True)


def test_verify_refuses_an_edited_manifest(CS, tmp_path):
    snap, man = _fake_snapshot(CS, tmp_path)
    man["files"]["data/Ortho4XP.cfg.in"]["sha256"] = "0" * 64
    (snap / "snapshot.json").write_text(json.dumps(man))
    with pytest.raises(SystemExit, match="re-derive"):
        CS.verify(snap, quiet=True)


def test_mount_and_unmount(CS, tmp_path, monkeypatch):
    monkeypatch.setenv("XPLANE_ROOT", "/real/X")
    snap, man = _fake_snapshot(CS, tmp_path)
    root = tmp_path / "lane"
    root.mkdir()
    shared = tmp_path / "shared" / "OSM_data"
    shared.mkdir(parents=True)
    (root / "OSM_data").symlink_to(shared)
    (root / "Ortho4XP.cfg").write_text("custom_scenery_dir=/real/X/Custom Scenery\n")
    rec = CS.mount(root, snap, icao="ZZZZ")
    assert rec["corpus"] == f"snapshot@{man['hash'][:12]}"
    for name in CS.DATA_DIRS:
        assert (root / name).resolve() == (snap / "data" / name).resolve()
    cfg = (root / "Ortho4XP.cfg").read_text()
    assert f"custom_scenery_dir={snap}/xplane/Custom Scenery" in cfg
    assert CS.XPLANE_TOKEN not in cfg
    assert os.environ["XPLANE_ROOT"] == str(snap / "xplane")
    with pytest.raises(SystemExit, match="complete read set"):
        CS.mount(root, snap, icao="QQQQ")
    CS.unmount(root, rec)
    assert (root / "OSM_data").resolve() == shared.resolve()
    assert "/real/X" in (root / "Ortho4XP.cfg").read_text()


def test_mount_refuses_a_real_directory(CS, tmp_path):
    snap, _ = _fake_snapshot(CS, tmp_path)
    root = tmp_path / "lane"
    (root / "Masks").mkdir(parents=True)
    with pytest.raises(SystemExit, match="real directory"):
        CS.mount(root, snap)


def test_corpus_stamp_keys_the_snapshot_and_only_the_snapshot(AL):
    frame = {"data_repo": "/r", "data_mounts": {}, "dem_cache_before": {},
             "dem_frame_effective": {}}
    shared = AL.corpus_stamp(frame, "/nonexistent")
    assert "snapshot" not in shared["parts"]          # shared keys unchanged
    snap_a = AL.corpus_stamp(dict(frame, corpus_snapshot={"hash": "a" * 64}),
                             "/nonexistent")
    snap_b = AL.corpus_stamp(dict(frame, corpus_snapshot={"hash": "b" * 64}),
                             "/nonexistent")
    assert len({shared["sha256"], snap_a["sha256"], snap_b["sha256"]}) == 3
    # one snapshot, two machines (different paths/mounts): ONE stamp
    moved = dict(frame, data_repo="/elsewhere", corpus_snapshot={"hash": "a" * 64},
                 data_mounts={"OSM_data": {"realpath": "/x"}})
    assert AL.corpus_stamp(moved, "/nonexistent") == snap_a
    assert "O4_CORPUS_SNAPSHOT" not in AL.key_env(
        {"O4_CORPUS_SNAPSHOT": "/a", "O4_DATA_REPO": "/a/data", "O4_X": "1"})


def test_lookup_refuses_across_snapshot_hashes(AL, tmp_path):
    store = tmp_path / "store"
    (store / "entries").mkdir(parents=True)
    theirs = {"icao": "ZZZZ", "tree": "t", "env": {}, "variant": {},
              "corpus": {"sha256": "x", "parts": {"snapshot": "a" * 64}}}
    (store / "entries" / "k.json").write_text(json.dumps(
        {"key": "k", "key_parts": theirs, "stored_at": 1}))
    ours = dict(theirs, corpus={"sha256": "y", "parts": {"snapshot": "b" * 64}})
    rec, why = AL.lookup("other", ours, store=store)
    assert rec is None and why.startswith("REFUSED") and "snapshot@bbbb" in why
    shared = dict(theirs, corpus={"sha256": "z", "parts": {}})
    rec, why = AL.lookup("other", shared, store=store)
    assert rec is None and "shared" in why


def test_read_trace_records_reads_not_writes(CS, tmp_path):
    r = tmp_path / "r.txt"
    r.write_text("x")
    tr = CS.ReadTrace().start()
    try:
        r.read_text()
        (tmp_path / "w.txt").write_text("y")
        os.listdir(tmp_path)
    finally:
        tr.stop()
    rec = tr.record()
    assert str(r.resolve()) in rec["reads"]
    assert str((tmp_path / "w.txt").resolve()) not in rec["reads"]
    assert str(tmp_path.resolve()) in rec["listed"]


def test_build_airport_publishes_the_flags():
    src = (HARNESS / "build_airport.py").read_text()
    for needle in ('"--corpus"', '"--trace-reads"', "CS.mount(",
                   'frame["corpus"]', "SNAPSHOT LEAK", "arm_snapshot_env"):
        assert needle in src, needle
