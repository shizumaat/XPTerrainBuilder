"""Twins for THE BASE-ARM ARTIFACT LEDGER (spec BS2).

No build, no network, no shared repo: a synthetic store under ``tmp_path``
and synthetic frames.  What is under test is the KEY LAW (what makes a hit
a hit) and the REFUSALS — the two places where a wrong answer is
indistinguishable from a right one until a census disagrees weeks later.

The store's own directory is redirected per test through
``O4_ARTIFACT_LEDGER_DIR`` AND by passing ``store=`` explicitly, because a
test that silently wrote the developer's real ``~/.ortho4xp`` would be the
same defect the shared-repo guard exists to stop, one directory over.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def AL():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    return _load("harness_twin_artifact_ledger", HARNESS / "artifact_ledger.py")


@pytest.fixture(scope="module")
def build_mod():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    return _load("harness_twin_build_al", HARNESS / "build_airport.py")


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_ARTIFACT_LEDGER_DIR", str(tmp_path / "store"))
    return tmp_path / "store"


def _frame(root, *, base=("Elevation_data/SRTM/N60W135.hgt",),
           insets=("Elevation_data/SRTM/N60W135_airport_insets",),
           mount="/corpus", cfg=None):
    return {"data_repo": mount,
            "data_mounts": {"Elevation_data": {"realpath": mount + "/Elevation_data",
                                               "shared": True, "present": True}},
            "dem_cache_before": {"tile_stem": "N60W135",
                                 "base_raster_files": list(base),
                                 "airports_layer_files": [],
                                 "airport_inset_dirs": list(insets)},
            "dem_frame_effective": cfg or {"apt_smoothing_pix": "8"}}


def _corpus_tree(root: Path, raster=b"RASTER-A", inset=b"INSET-A"):
    d = root / "Elevation_data" / "SRTM"
    d.mkdir(parents=True, exist_ok=True)
    (d / "N60W135.hgt").write_bytes(raster)
    ins = d / "N60W135_airport_insets"
    ins.mkdir(exist_ok=True)
    (ins / "KXXX_USGS3DEP.tif").write_bytes(inset)
    return root


def _artifacts(tmp_path, body=b"<osm>base</osm>"):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    (out / "a.osm").write_bytes(b"head\nprov\n" + body)
    (out / "a.osm.axes.json").write_text('{"axes": []}')
    (out / "a.frame.json").write_text('{"frame": 1}')
    (out / "a.env.json").write_text('{"env": 1}')
    (out / "a.result.json").write_text('{"result": 1}')
    return {"patch": str(out / "a.osm"), "sidecar": str(out / "a.osm.axes.json"),
            "frame": str(out / "a.frame.json"), "env": str(out / "a.env.json"),
            "result": str(out / "a.result.json")}


def _parts(AL, tmp_path, **over):
    corpus = AL.corpus_stamp(_frame(tmp_path), tmp_path)
    parts = {"tree": "tree-1", "icao": "CYXY", "env": {}, "corpus": corpus,
             "variant": AL.build_variant()}
    parts.update(over)
    return parts


def _key(AL, parts):
    return AL.artifact_key(parts["tree"], parts["icao"], parts["env"],
                           parts["corpus"], parts["variant"])


# ══════════════════════════════════════════════════════════════════════
# §1 STORE AND SERVE
# ══════════════════════════════════════════════════════════════════════

def test_a_stored_arm_is_served_back_byte_identical(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    key = _key(AL, parts)
    AL.store_build(key, parts, arts, {"tag": "CYXY_base", "lane": "/lane",
                                      "build_seconds": 34.7,
                                      "body_sha256": "abc"}, store=store)
    record, why = AL.lookup(key, parts, store=store)
    assert record is not None and why == "hit"
    written = AL.serve(record, tmp_path / "out2", "CYXY_arm", store=store)
    for role, src in arts.items():
        assert Path(written[role]).read_bytes() == Path(src).read_bytes()
    assert Path(written["patch"]).name == "CYXY_arm.osm"
    assert Path(written["sidecar"]).name == "CYXY_arm.osm.axes.json"


def test_the_provenance_line_names_the_original_build(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    key = _key(AL, parts)
    AL.store_build(key, parts, arts,
                   {"tag": "CYXY_20260812T0900", "lane": "/lane/sweeptools",
                    "build_seconds": 34.7, "body_sha256": "deadbeef" * 8},
                   store=store)
    record, _ = AL.lookup(key, parts, store=store)
    written = AL.serve(record, tmp_path / "o", "CYXY_arm", store=store)
    line = AL.provenance_line(record, written, store=store)
    assert "SERVED FROM THE ARTIFACT LEDGER — NO BUILD RAN" in line
    assert "CYXY_20260812T0900" in line and "34.7" in line
    assert key[:12] in line and "/lane/sweeptools" in line


def test_serving_records_the_use_for_the_lru(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    key = _key(AL, parts)
    AL.store_build(key, parts, arts, {"tag": "t"}, store=store)
    record, _ = AL.lookup(key, parts, store=store)
    AL.serve(record, tmp_path / "o", "arm", store=store)
    again, _ = AL.lookup(key, parts, store=store)
    assert again["uses"] == 1 and again["served"][0]["tag"] == "arm"


def test_identical_bytes_under_two_keys_cost_one_blob(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    arts = _artifacts(tmp_path)
    for tree in ("tree-1", "tree-2"):
        parts = _parts(AL, tmp_path, tree=tree)
        AL.store_build(_key(AL, parts), parts, arts, {"tag": tree}, store=store)
    assert len(list((store / "entries").glob("*.json"))) == 2
    assert len(list((store / "blobs").glob("*"))) == 5   # one per role, shared


def test_an_incomplete_build_is_never_stored(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    Path(arts["sidecar"]).unlink()
    with pytest.raises(ValueError, match="incomplete"):
        AL.store_build(_key(AL, parts), parts, arts, {"tag": "t"}, store=store)
    assert not list((store / "entries").glob("*.json")) if \
        (store / "entries").is_dir() else True


def test_a_corrupt_blob_refuses_instead_of_serving_it(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    key = _key(AL, parts)
    AL.store_build(key, parts, arts, {"tag": "t"}, store=store)
    record, _ = AL.lookup(key, parts, store=store)
    blob = store / "blobs" / record["files"]["patch"]["sha256"]
    blob.write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="does not hash to its own name"):
        AL.serve(record, tmp_path / "o", "arm", store=store)


def test_an_evicted_blob_refuses_instead_of_serving_a_hole(AL, tmp_path,
                                                            store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    key = _key(AL, parts)
    AL.store_build(key, parts, arts, {"tag": "t"}, store=store)
    record, _ = AL.lookup(key, parts, store=store)
    (store / "blobs" / record["files"]["patch"]["sha256"]).unlink()
    with pytest.raises(SystemExit, match="GONE"):
        AL.serve(record, tmp_path / "o", "arm", store=store)


# ══════════════════════════════════════════════════════════════════════
# §2 WHAT MAKES A MISS (the whole point of the key)
# ══════════════════════════════════════════════════════════════════════

def test_a_different_code_tree_is_a_miss(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    AL.store_build(_key(AL, parts), parts, arts, {"tag": "t"}, store=store)
    other = _parts(AL, tmp_path, tree="tree-CHANGED")
    record, why = AL.lookup(_key(AL, other), other, store=store)
    assert record is None and "tree" in why and why.startswith("MISS")


def test_a_different_o4_env_is_a_miss(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    AL.store_build(_key(AL, parts), parts, arts, {"tag": "t"}, store=store)
    other = _parts(AL, tmp_path, env={"O4_SEAT_BAND_CONSISTENT": "0"})
    record, why = AL.lookup(_key(AL, other), other, store=store)
    assert record is None and "env" in why


def test_a_synthetic_dem_world_is_a_miss_against_the_real_one(AL, tmp_path,
                                                              store):
    """A −500 m oracle patch is not a real-DEM patch; the two must never
    serve for each other however identical the tree and the corpus are."""
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    AL.store_build(_key(AL, parts), parts, arts, {"tag": "t"}, store=store)
    other = _parts(AL, tmp_path, variant=AL.build_variant(const_dem=-500.0))
    record, why = AL.lookup(_key(AL, other), other, store=store)
    assert record is None and "variant" in why


def test_a_changed_corpus_is_a_miss_and_says_so(AL, tmp_path, store):
    """THE KCLT ROAD-FEED PRECEDENT: same path, new bytes.  The stamp must
    move even though nothing in the frame's file LIST changed."""
    _corpus_tree(tmp_path)
    parts, arts = _parts(AL, tmp_path), _artifacts(tmp_path)
    AL.store_build(_key(AL, parts), parts, arts, {"tag": "t"}, store=store)
    # ONLY the raster, SAME LENGTH, different bytes — nothing else in the
    # corpus is touched, so a stamp that hashed only paths, sizes and the
    # inset listing would call this corpus unchanged.  That is precisely
    # the road-feed failure mode.
    raster = tmp_path / "Elevation_data" / "SRTM" / "N60W135.hgt"
    assert len(raster.read_bytes()) == len(b"RASTER-B")
    raster.write_bytes(b"RASTER-B")
    other = _parts(AL, tmp_path)
    assert other["corpus"]["sha256"] != parts["corpus"]["sha256"]
    record, why = AL.lookup(_key(AL, other), other, store=store)
    assert record is None
    assert "corpus[dem_files]" in why and "DIFFERENT MEASUREMENT" in why


def test_a_regenerated_inset_cache_moves_the_corpus_stamp(AL, tmp_path):
    _corpus_tree(tmp_path)
    before = AL.corpus_stamp(_frame(tmp_path), tmp_path)
    _corpus_tree(tmp_path, inset=b"INSET-REGENERATED-LONGER")
    assert AL.corpus_stamp(_frame(tmp_path), tmp_path)["sha256"] != \
        before["sha256"]


def test_a_different_mount_is_a_different_corpus(AL, tmp_path):
    _corpus_tree(tmp_path)
    a = AL.corpus_stamp(_frame(tmp_path), tmp_path)
    b = AL.corpus_stamp(_frame(tmp_path, mount="/private-corpus"), tmp_path)
    assert a["sha256"] != b["sha256"]


def test_a_diverged_dem_frame_cfg_is_a_different_corpus(AL, tmp_path):
    _corpus_tree(tmp_path)
    a = AL.corpus_stamp(_frame(tmp_path), tmp_path)
    b = AL.corpus_stamp(_frame(tmp_path, cfg={"apt_smoothing_pix": "0"}),
                        tmp_path)
    assert a["sha256"] != b["sha256"]


def test_an_empty_ledger_misses_by_name(AL, tmp_path, store):
    _corpus_tree(tmp_path)
    parts = _parts(AL, tmp_path)
    record, why = AL.lookup(_key(AL, parts), parts, store=store)
    assert record is None and "nothing stored for CYXY" in why


def test_the_per_run_env_variables_never_key_an_artifact(AL, monkeypatch):
    """``O4_DSF_CACHE_DIR`` and friends name the RUN's own tag directory; if
    they keyed the artifact every key would be unique and the ledger would
    never hit."""
    env = {"O4_SEAT_BAND_CONSISTENT": "1", "O4_HARNESS_IN_LEDGER": "1",
           "O4_DSF_CACHE_DIR": "/tmp/x/CYXY_20260812T0900.engine_caches",
           "O4_AIRPORT_MOD_CACHE_DIR": "/tmp/x/mod"}
    assert AL.key_env(env) == {"O4_SEAT_BAND_CONSISTENT": "1"}


# ══════════════════════════════════════════════════════════════════════
# §3 EVICTION
# ══════════════════════════════════════════════════════════════════════

def test_eviction_is_lru_and_stamped(AL, tmp_path, store, monkeypatch):
    _corpus_tree(tmp_path)
    keys = []
    for i in range(3):
        arts = _artifacts(tmp_path, body=b"x" * (5000 + i))
        parts = _parts(AL, tmp_path, tree=f"tree-{i}")
        key = _key(AL, parts)
        keys.append(key)
        AL.store_build(key, parts, arts, {"tag": f"t{i}"}, store=store)
    # Touch the OLDEST so the LRU order is not the insertion order.
    record, _ = AL.lookup(keys[0], _parts(AL, tmp_path, tree="tree-0"),
                          store=store)
    AL.serve(record, tmp_path / "o", "arm", store=store)
    monkeypatch.setenv("O4_ARTIFACT_LEDGER_MAX_MB", "0")
    dropped = AL.evict(store=store)
    assert dropped and all(d["reason"] == "size-capped LRU" for d in dropped)
    assert dropped[0]["key"] == keys[1], "the least recently USED goes first"
    lines = [json.loads(x) for x in
             (store / "evictions.jsonl").read_text().splitlines()]
    assert [d["key"] for d in lines] == [d["key"] for d in dropped]


# ══════════════════════════════════════════════════════════════════════
# §4 THE CLI REFUSALS (build_airport.py)
# ══════════════════════════════════════════════════════════════════════

def test_a_timing_run_may_never_be_served(build_mod):
    """--no-ledger marks a run whose OUTPUT IS A TIME; a stored artifact has
    no wall time to give it, and replaying one would report another day's
    build as this run's measurement."""
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["CYXY", "--base-arm", "--no-ledger"])
    assert "OUTPUT IS A TIME" in str(exc.value)


def test_a_tile_build_may_not_be_served_from_the_patch_store(build_mod):
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["CYXY", "--from-ledger", "--tile", "60", "-135"])
    assert "stores PATCH builds" in str(exc.value)


def test_a_refresh_run_may_not_be_served(build_mod):
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["CYXY", "--base-arm", "--refresh-data", "dem"])
    assert "CHANGES the corpus" in str(exc.value)


def test_asking_for_a_base_arm_with_the_ledger_off_is_refused(build_mod):
    """The pair is contradictory, and the silent reading of it (rebuild
    anyway) is indistinguishable from a ledger miss in the log."""
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["CYXY", "--base-arm", "--no-artifact-ledger"])
    assert "silently does nothing" in str(exc.value)
