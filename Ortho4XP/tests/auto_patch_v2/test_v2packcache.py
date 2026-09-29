"""#27 / spec ``pack-read-once-fast-spec.md`` §B.4 + §B.5 (slices S2, S4):
the partition cache that HITS, the pack walk taken once per tile, and the
pool that releases a finished worker.

T1 two airports, one pack, one tile -> two paths, and each airport's
payload survives the other's write (the TNCM/TFFG overwrite).  T2 a
fingerprint handed the parent's walk never walks.  T3 §12a: an mtime-only
touch still HITS (the content hash decides); one changed byte of the same
size MISSES; a size change moves the key.  T4 a torn ``.tmp`` beside the
cache is ignored and a truncated cache is a miss.  T5 the stage profiler
calls the BUILD'S own ``pack_stage`` (import-not-copy) and its summary is
the median.  S4: the release rule, and a ``max_tasks_per_child=1`` pool
gives each task a fresh worker.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch_v2.airport import partition_cache as PC          # noqa: E402
from auto_patch_v2.law import Law                                # noqa: E402

LAW = Law.for_airport("")


class _Frame:
    crs = "EPSG:32620"
    lat0 = 18.04
    lon0 = -63.1


def _pack(tmp: Path) -> Path:
    root = tmp / "c_NLD TNCM_1_Apt"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n1100\n", encoding="utf-8", newline="")
    (root / "Objects").mkdir()
    (root / "Objects" / "HillBush.obj").write_text("A\n800\nOBJ\n# bushes\n", encoding="utf-8", newline="")
    (root / "Objects" / "Terminal.obj").write_text("A\n800\nOBJ\n# terminal\n", encoding="utf-8", newline="")
    return root


def _airport(root: Path, icao: str):
    class _Pk:
        name = root.name
        apt_dat_path = str(root / "Earth nav data" / "apt.dat")
        borrowed_apt_dat_path = ""
        borrowed_block_sha256 = ""

    class _Air:
        pack = _Pk()
        frame = _Frame()

    a = _Air()
    a.icao = icao
    return a


@pytest.fixture()
def world(tmp_path):
    root = _pack(tmp_path)
    dump = tmp_path / "+18-064.dsf.84ffe846.text"
    dump.write_text("OBJECT_DEF Objects/HillBush.obj\n", encoding="utf-8", newline="")
    return root, str(dump), str(tmp_path / "mod")


def test_t1_two_airports_one_tile_two_files_both_hit(world):
    root, dump, mod = world
    paths, fps = {}, {}
    for icao in ("TNCM", "TFFG"):
        a = _airport(root, icao)
        fps[icao] = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
        paths[icao] = PC.cache_path(a, mod, dump)
        assert PC.write(paths[icao], fps[icao], {"airport": icao})
    assert paths["TNCM"] != paths["TFFG"]
    assert paths["TNCM"].endswith("o4_v2_partition_+18-064_TNCM.cache")
    # the second build of the tile: BOTH hit (the tile-named file made
    # the second airport's write destroy the first's)
    for icao in ("TNCM", "TFFG"):
        assert PC.read(paths[icao], fps[icao]) == {"airport": icao}
    assert fps["TNCM"] != fps["TFFG"]


def test_t2_a_seeded_walk_is_never_walked_again(world, monkeypatch):
    root, dump, _mod = world
    stamps = PC.pristine_stamps(str(root))
    calls = []
    real = PC.pristine_stamps
    monkeypatch.setattr(PC, "pristine_stamps", lambda r: calls.append(r) or real(r))
    a = _airport(root, "TNCM")
    fp_seeded = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05,
                               pristine={str(root): stamps})
    assert calls == []
    fp_walked = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    assert calls == [str(root)]
    assert fp_seeded == fp_walked


def test_t2b_the_parent_walks_each_pack_root_once(world, monkeypatch):
    from auto_patch import driver as D
    root, _dump, _mod = world

    class _Sel:
        pass

    sel = _Sel()
    sel.root = str(root)
    import auto_patch_v2.airport.pack as P
    monkeypatch.setattr(P, "select_pack", lambda xp, icao, law=None: sel)
    calls = []
    real = PC.pristine_stamps
    monkeypatch.setattr(PC, "pristine_stamps", lambda r: calls.append(r) or real(r))
    tasks = [{"icao": "TNCM", "xp_root": "/x"}, {"icao": "TFFG", "xp_root": "/x"}]
    walks = D._seed_pack_walks(tasks)
    assert calls == [str(root)]
    assert set(walks) == {str(root)}
    assert tasks[0]["pack_pristine"] == tasks[1]["pack_pristine"] == {str(root): walks[str(root)]}


def test_t3_mtime_only_hits_same_size_edit_misses(world):
    root, dump, mod = world
    a = _airport(root, "TNCM")
    fp = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    assert PC.write(path, fp, "payload")
    obj = root / "Objects" / "HillBush.obj"
    # a pack restored from a backup: same bytes, new mtime -> still HIT
    st = obj.stat()
    os.utime(obj, (st.st_atime, st.st_mtime + 100.0))
    fp2 = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    assert fp2 == fp
    assert PC.read(path, fp2) == "payload"
    # one changed byte, same size -> MISS
    txt = obj.read_text(encoding="utf-8")
    obj.write_text(txt.replace("bushes", "bushex"), encoding="utf-8", newline="")
    fp3 = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    assert fp3 == fp                     # the size is the key...
    assert PC.read(path, fp3) is None    # ...and the content hash refuses
    # a size change moves the key itself
    obj.write_text(txt + "# more\n", encoding="utf-8", newline="")
    assert PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05) != fp


def test_t4_a_torn_tmp_is_ignored_and_a_truncated_cache_misses(world):
    root, dump, mod = world
    a = _airport(root, "TNCM")
    fp = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    assert PC.write(path, fp, "payload")
    Path(path + ".tmp999").write_bytes(b"torn")
    assert PC.read(path, fp) == "payload"
    raw = Path(path).read_bytes()
    Path(path).write_bytes(raw[: len(raw) // 2])
    assert PC.read(path, fp) is None


def test_t5_the_profiler_calls_the_builds_own_pack_stage():
    import inspect
    import pack_stage_profile as T
    import importlib
    B = importlib.import_module("auto_patch_v2.pipeline.build")
    src = inspect.getsource(T.run_once)
    assert "from auto_patch_v2.pipeline.build import pack_stage" in src
    assert callable(B.pack_stage)
    runs = [{"wall": {k: v for k in T.WALL_KEYS}, "counts": {"parts": 1},
             "groups": {"groups": 2}, "max_rss_gb": v} for v in (3.0, 1.0, 2.0)]
    s = T.summarise(runs)
    assert s["median_wall"]["stage"] == 2.0 and s["counts_agree"]
    assert s["max_rss_gb_max"] == 3.0


def test_s4_the_release_rule():
    from auto_patch import driver as D
    big = {"r": [("a.obj", D.POOL_RELEASE_PACK_BYTES + 1, 0.0, "a")]}
    small = {"r": [("a.obj", 10, 0.0, "a")]}
    assert D._pool_releases_workers(2, 2, small) is False     # few small airports keep reuse
    assert D._pool_releases_workers(3, 2, small) is True      # more airports than workers
    assert D._pool_releases_workers(2, 2, big) is True        # a large pack


def _pid(_x):
    return os.getpid()


def test_s4_a_released_pool_gives_each_task_a_fresh_worker():
    import concurrent.futures as cf
    import multiprocessing as mp
    ex = cf.ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"),
                                max_tasks_per_child=1)
    try:
        pids = list(ex.map(_pid, range(2)))
    finally:
        ex.shutdown(wait=True)
    assert pids[0] != pids[1]


def test_t5_site_report_names_the_cluster_at_the_site():
    """Issue #69: ``--site`` reads the cluster whose outline holds the
    site, its outline area and the counts."""
    import types
    import pack_stage_profile as T
    lat, lon = 25.0, 51.0
    d = 0.001                                        # ~100 m
    sq = lambda la, lo, s: ((la, lo), (la, lo + s), (la + s, lo + s), (la + s, lo))
    a = types.SimpleNamespace(id="a", unit="u1", members=("x", "y"), area_m2=5e4,
                              bodies=2, walled=1, rings=(sq(lat - d, lon - d, 2 * d),))
    b = types.SimpleNamespace(id="b", unit="u2", members=("z",), area_m2=10.0,
                              bodies=1, walled=0, rings=(sq(lat + 5 * d, lon, d),))
    r = T.site_report((b, a), lat, lon, min_m2=100.0)
    assert r["site_cluster"] == "a" and r["site_dist_m"] == 0.0
    assert r["site_members"] == 2 and r["clusters"] == 2 and r["clusters_over_min"] == 1
    assert 4.3e4 < r["site_outline_m2"] < 4.7e4


def test_t5_site_report_reads_the_largest_pad_at_the_site():
    """Issue #69: with the pads handed in, the LARGEST pad within 1 m of
    the site is named (the junction capture's 484,538 m² terminal sat
    0.1 m from the site beside a 2,642 m² piece containing it)."""
    import types
    from shapely.geometry import box
    import pack_stage_profile as T
    c = types.SimpleNamespace(id="c", unit="u", members=("m",) * 3, area_m2=1.0,
                              bodies=7, walled=7, rings=())
    pads = [("small", c, box(-0.5, -0.5, 0.5, 0.5)), ("big", c, box(0.6, -50, 100.6, 50)),
            ("far", c, box(500, 500, 900, 900))]
    r = T.site_report((c,), 25.0, 51.0, 0.0, pads, (0.0, 0.0))
    assert r["pads"] == 3 and r["pad_at_site"] == "big" and r["pad_at_site_m2"] == 10000.0
    assert r["pad_members"] == 3 and r["pad_bodies"] == 7


# ── issue #88: the resolved-placement set is in the key ─────────────────

def test_t88_unresolved_partition_never_served_to_a_resolved_run(world, tmp_path):
    """Same pack, same dump: the library index UNRESOLVED (one pack
    object resolves, the ``lib/`` placement does not) then RESOLVED (both
    do) -> two keys; the resolved run does not read the unresolved
    run's file, and ``peek`` names the digest it was written under."""
    from types import SimpleNamespace as NS
    root, dump, mod = world
    lib_obj = tmp_path / "Library" / "lib_tree.obj"
    lib_obj.parent.mkdir()
    lib_obj.write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    pack_obj = str(root / "Objects" / "Terminal.obj")
    a = _airport(root, "TNCM")
    a.dsf_objects = (NS(path="Objects/Terminal.obj", resolved_path=pack_obj),
                     NS(path="lib/tree.obj", resolved_path=None))
    rd_u = PC.resolved_digest(a)
    fp_u = PC.fingerprint(a, LAW, dump_path=dump, radius_deg=0.05)
    path = PC.cache_path(a, mod, dump)
    assert PC.write(path, fp_u, "unresolved partition")
    assert PC.read(path, fp_u) == "unresolved partition"
    assert rd_u[0] == 1 and PC.peek(path) == rd_u
    # the index resolves the lib/ placement
    b = _airport(root, "TNCM")
    b.dsf_objects = (NS(path="Objects/Terminal.obj", resolved_path=pack_obj),
                     NS(path="lib/tree.obj", resolved_path=str(lib_obj)))
    rd_r = PC.resolved_digest(b)
    fp_r = PC.fingerprint(b, LAW, dump_path=dump, radius_deg=0.05)
    assert rd_r[0] == 2 and rd_r != rd_u
    assert fp_r != fp_u
    assert PC.read(path, fp_r) is None           # never served
    assert PC.peek(path) == rd_u                 # the stale digest, logged
    # the engine's own y-bake (read through .anchor_bak) keeps the key
    c = _airport(root, "TNCM")
    c.dsf_objects = (NS(path="Objects/Terminal.obj",
                        resolved_path=pack_obj + ".anchor_bak"),
                     NS(path="lib/tree.obj", resolved_path=str(lib_obj)))
    assert PC.resolved_digest(c) == rd_r
    # order of placements does not move it
    d = _airport(root, "TNCM")
    d.dsf_objects = tuple(reversed(b.dsf_objects))
    assert PC.resolved_digest(d) == rd_r
